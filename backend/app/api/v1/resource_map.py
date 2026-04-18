"""
资源映射 API端点 - 模块二
联动模块一结果，提供资源映射HTTP接口
支持自动读取模块一提取的引脚定义
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional
import pandas as pd
import json
import uuid
from datetime import datetime
from pathlib import Path
from io import BytesIO

from app.services.resource_mapping_service import ResourceMappingService
from app.utils.svg_generator import SVGGenerator
from app.utils.bom_generator import generate_bom_excel
from app.utils.resource_map_exporter import export_resource_map_excel
from app.models.testplan import ExtractionResult
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()
router   = APIRouter()

service = ResourceMappingService()
svg_gen = SVGGenerator()


@router.post("/generate")
async def generate_resource_map(
    file_id:   str                    = Form(...),
    dual_site: bool                   = Form(False),
    pin_file:  Optional[UploadFile]   = File(None)  # ← 改为可选
):
    """
    生成资源映射（核心接口）

    - **file_id**   : 模块一生成的文件ID
    - **dual_site** : 是否使用双工位适配器（LDO场景）
    - **pin_file**  : PinMapping文件（可选）
                      若模块一已自动提取引脚则不需要上传
                      若需要手动指定则上传xlsx/csv文件
    """
    # ── 1. 读取模块一JSON结果 ────────────────────────────────
    json_files = list(
        settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.json")
    )
    if not json_files:
        raise HTTPException(
            404,
            f"未找到file_id={file_id}对应的TestPlan JSON，"
            f"请先完成模块一提取"
        )

    with open(json_files[-1], "r", encoding="utf-8") as f:
        json_data = json.load(f)

    chip_name = json_data.get("chip_name", "Unknown")
    chip_type = json_data.get("chip_type", "UNKNOWN")
    stats     = json_data.get("statistics", {})

    extraction_result = ExtractionResult(
        status       = "success",
        chip_name    = chip_name,
        chip_type    = chip_type,
        test_scenario= json_data.get("test_scenario", "GENERAL"),
        total_params = stats.get("total",   0),
        a_params     = stats.get("A_class", 0),
        b_params     = stats.get("B_class", 0),
        c_params     = stats.get("C_class", 0),
    )

    # ── 2. 读取引脚定义（优先JSON，其次上传文件）────────────
    pin_defs_raw = json_data.get("pin_definitions", [])
    pin_df       = None

    if pin_defs_raw:
        # ✅ 模块一已自动提取引脚，直接使用
        pin_df = pd.DataFrame(pin_defs_raw)
        logger.info(
            f"✅ 自动读取引脚定义: {len(pin_df)}个 (来自模块一JSON)"
        )

    elif pin_file:
        # 用户手动上传PinMapping文件
        if not pin_file.filename.lower().endswith(
            (".xlsx", ".xls", ".csv")
        ):
            raise HTTPException(
                400, "PinMapping文件格式错误，支持xlsx/xls/csv"
            )
        contents = await pin_file.read()
        try:
            if pin_file.filename.endswith(".csv"):
                pin_df = pd.read_csv(BytesIO(contents))
            else:
                pin_df = pd.read_excel(BytesIO(contents))
            logger.info(
                f"✅ 从上传文件读取引脚: {len(pin_df)}个"
            )
        except Exception as e:
            raise HTTPException(400, f"PinMapping文件解析失败: {e}")

    else:
        # 既没有自动提取，也没有上传文件
        raise HTTPException(
            400,
            f"未找到引脚定义，请选择以下方案之一：\n"
            f"方案1：重新运行模块一（会自动提取引脚）\n"
            f"方案2：上传 pin_file（PinMapping Excel文件）\n"
            f"方案3：先下载模板填写: GET /api/v1/resource-map/"
            f"pinmapping-template/{chip_type}"
        )

    if pin_df is None or pin_df.empty:
        raise HTTPException(400, "引脚数据为空，请检查文件内容")

    # ── 3. 执行资源映射 ──────────────────────────────────────
    logger.info(
        f" 开始资源映射 | 芯片: {chip_name} [{chip_type}]"
    )
    result = service.generate_resource_map(
        extraction_result, pin_df, dual_site
    )

    if result.status != "success":
        raise HTTPException(
            500,
            f"资源映射失败: {'; '.join(result.errors)}"
        )

    # ── 4. 生成输出文件 ──────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_prefix = f"{chip_name}_{timestamp}"

    # 资源映射Excel
    excel_path = str(
        settings.PROCESSED_DIR / f"{out_prefix}_ResourceMap.xlsx"
    )
    export_resource_map_excel(
        chip_name         = chip_name,
        chip_type         = result.chip_type,
        adapter_info      = result.adapter_info,
        resource_mappings = result.resource_mappings,
        pgs_configs       = result.pgs_configs,
        pgs_details       = result.pgs_detail_conditions,
        pin_groups        = result.pin_groups,
        output_path       = excel_path
    )

    # SVG原理图
    svg_path = str(
        settings.PROCESSED_DIR / f"{out_prefix}_Schematic.svg"
    )
    svg_gen.generate(
        chip_name   = chip_name,
        chip_type   = result.chip_type,
        mappings    = result.resource_mappings,
        output_path = svg_path
    )

    # BOM清单Excel
    bom_path = str(
        settings.PROCESSED_DIR / f"{out_prefix}_BOM.xlsx"
    )
    generate_bom_excel(
        bom_items     = result.adapter_info.bom_items,
        chip_name     = chip_name,
        adapter_model = result.adapter_model,
        output_path   = bom_path
    )

    logger.success(
        f"✅ 资源映射完成 | 适配器: {result.adapter_model}"
    )

    return {
        "status":  "success",
        "message": "资源映射生成完成",
        "data": {
            "chip_name":       chip_name,
            "chip_type":       result.chip_type,
            "adapter":         result.adapter_model,
            "pin_count":       len(result.resource_mappings),
            "pgs_items":       len(result.pgs_configs),
            "pin_auto_loaded": len(pin_defs_raw) > 0,  # 是否自动加载引脚
            "download": {
                "resource_map_excel":
                    f"/api/v1/resource-map/download/{out_prefix}/excel",
                "schematic_svg":
                    f"/api/v1/resource-map/download/{out_prefix}/svg",
                "bom_excel":
                    f"/api/v1/resource-map/download/{out_prefix}/bom",
            },
            "warnings": result.warnings,
        }
    }


@router.get("/download/{prefix}/{file_type}")
async def download_resource_file(prefix: str, file_type: str):
    """
    下载资源映射生成的文件

    - **prefix**    : 文件前缀（从generate接口返回的download URL中提取）
    - **file_type** : excel / svg / bom
    """
    ext_map = {
        "excel": (
            "_ResourceMap.xlsx",
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        "svg": (
            "_Schematic.svg",
            "image/svg+xml"
        ),
        "bom": (
            "_BOM.xlsx",
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
    }

    if file_type not in ext_map:
        raise HTTPException(400, "file_type 必须是 excel/svg/bom")

    suffix, media_type = ext_map[file_type]
    file_path = settings.PROCESSED_DIR / f"{prefix}{suffix}"

    if not file_path.exists():
        raise HTTPException(404, f"文件不存在: {file_path.name}")

    return FileResponse(
        path       = str(file_path),
        filename   = file_path.name,
        media_type = media_type
    )


@router.get("/adapter-info/{chip_type}")
async def get_adapter_info(
    chip_type: str,
    dual_site: bool = False
):
    """
    查询芯片类型对应的适配器信息

    - **chip_type** : DIGITAL_74 / LDO / EEPROM 等
    - **dual_site** : 是否双工位
    """
    from app.models.resource_map import (
        ADAPTER_MODELS, BOM_DIGITAL,
        BOM_ANALOG_LDO, BOM_DUAL_LDO
    )

    bom_map = {
        "DIGITAL_74":     BOM_DIGITAL,
        "DIGITAL_54":     BOM_DIGITAL,
        "DIGITAL_4000":   BOM_DIGITAL,
        "MEMORY":         BOM_DIGITAL,
        "LDO":            BOM_DUAL_LDO if dual_site else BOM_ANALOG_LDO,
        "EEPROM":         BOM_ANALOG_LDO,
        "ANALOG_GENERAL": BOM_ANALOG_LDO,
    }

    if chip_type not in bom_map:
        raise HTTPException(
            404,
            f"不支持的芯片类型: {chip_type}。"
            f"支持: {list(bom_map.keys())}"
        )

    bom = bom_map[chip_type]
    adapter_key = (
        "LDO_DUAL"
        if chip_type == "LDO" and dual_site
        else (
            "DIGITAL"
            if "DIGITAL" in chip_type or chip_type == "MEMORY"
            else "LDO"
        )
    )

    return {
        "status": "success",
        "data": {
            "chip_type":     chip_type,
            "adapter_model": ADAPTER_MODELS.get(adapter_key, "未知"),
            "bom_count":     len(bom),
            "bom_items":     bom,
        }
    }


@router.get("/pinmapping-template/{chip_type}")
async def download_pinmapping_template(chip_type: str):
    """
    下载PinMapping填写模板（当自动提取失败时使用）

    - **chip_type**: 芯片类型
    """
    # 根据芯片类型生成示例数据
    if chip_type in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
        sample_data = [
            {"pin_no": 1,  "pin_name": "1A",  "function": "输入1A",
             "direction": "IN",  "voltage_max": 5.5, "notes": ""},
            {"pin_no": 2,  "pin_name": "1B",  "function": "输入1B",
             "direction": "IN",  "voltage_max": 5.5, "notes": ""},
            {"pin_no": 3,  "pin_name": "1Y",  "function": "输出1Y",
             "direction": "OUT", "voltage_max": 5.5, "notes": ""},
            {"pin_no": 7,  "pin_name": "GND", "function": "地",
             "direction": "GND", "voltage_max": 0,   "notes": ""},
            {"pin_no": 14, "pin_name": "VCC", "function": "电源",
             "direction": "PWR", "voltage_max": 5.5, "notes": ""},
        ]
    elif chip_type == "LDO":
        sample_data = [
            {"pin_no": 1, "pin_name": "VIN",  "function": "输入电压",
             "direction": "IN",  "voltage_max": 35, "notes": ""},
            {"pin_no": 2, "pin_name": "GND",  "function": "地",
             "direction": "GND", "voltage_max": 0,  "notes": ""},
            {"pin_no": 3, "pin_name": "VOUT", "function": "输出电压",
             "direction": "OUT", "voltage_max": 35, "notes": ""},
        ]
    elif chip_type == "EEPROM":
        sample_data = [
            {"pin_no": 1, "pin_name": "A0",  "function": "地址位0",
             "direction": "IN",    "voltage_max": 5.5, "notes": ""},
            {"pin_no": 2, "pin_name": "A1",  "function": "地址位1",
             "direction": "IN",    "voltage_max": 5.5, "notes": ""},
            {"pin_no": 3, "pin_name": "A2",  "function": "地址位2",
             "direction": "IN",    "voltage_max": 5.5, "notes": ""},
            {"pin_no": 4, "pin_name": "GND", "function": "地",
             "direction": "GND",   "voltage_max": 0,   "notes": ""},
            {"pin_no": 5, "pin_name": "SDA", "function": "I2C数据",
             "direction": "BIDIR", "voltage_max": 5.5, "notes": "开漏"},
            {"pin_no": 6, "pin_name": "SCL", "function": "I2C时钟",
             "direction": "IN",    "voltage_max": 5.5, "notes": ""},
            {"pin_no": 7, "pin_name": "WP",  "function": "写保护",
             "direction": "IN",    "voltage_max": 5.5, "notes": "低有效"},
            {"pin_no": 8, "pin_name": "VCC", "function": "电源",
             "direction": "PWR",   "voltage_max": 5.5, "notes": ""},
        ]
    else:
        sample_data = [
            {"pin_no": 1, "pin_name": "PIN1", "function": "功能描述",
             "direction": "IN", "voltage_max": 5.5, "notes": "请填写"},
        ]

    # 生成模板Excel
    tmp_path = (
        settings.PROCESSED_DIR
        / f"PinMapping_Template_{chip_type}.xlsx"
    )

    with pd.ExcelWriter(str(tmp_path), engine="openpyxl") as writer:
        pd.DataFrame(sample_data).to_excel(
            writer, sheet_name="PinMapping", index=False
        )
        # 填写说明Sheet
        instructions = [
            ["列名",        "必填", "说明",                  "示例"],
            ["pin_no",      "是",   "引脚编号(整数)",         "1"],
            ["pin_name",    "是",   "引脚名称",               "VIN"],
            ["function",    "否",   "功能描述",               "输入电压"],
            ["direction",   "是",   "IN/OUT/PWR/GND/BIDIR/NC","IN"],
            ["voltage_max", "否",   "最大电压(V)",            "35"],
            ["current_max", "否",   "最大电流(A)",            "1.5"],
            ["notes",       "否",   "备注",                   "开漏输出"],
        ]
        pd.DataFrame(
            instructions[1:], columns=instructions[0]
        ).to_excel(writer, sheet_name="填写说明", index=False)

    return FileResponse(
        path       = str(tmp_path),
        filename   = f"PinMapping_Template_{chip_type}.xlsx",
        media_type = (
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        )
    )