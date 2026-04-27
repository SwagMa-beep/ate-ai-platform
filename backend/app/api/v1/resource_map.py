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
from app.models.resource_map import AdapterInfo, PinGroupConfig, PGSConfig, PGSDetailCondition, ResourceMapping
from app.services.run_store import get_run_store
from app.flows.module2_resource_map_flow import (
    build_module2_resource_map_controller,
    finalize_module2_run,
)
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()
router   = APIRouter()

service = ResourceMappingService()
svg_gen = SVGGenerator()
run_store = get_run_store()
controller = build_module2_resource_map_controller(service=service)


@router.post("/generate")
async def generate_resource_map(
    file_id: str = Form(...),
    dual_site: bool = Form(False),
    pin_file: Optional[UploadFile] = File(None),
):
    """????????????"""
    json_files = list(settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.json"))
    if not json_files:
        raise HTTPException(404, f"??? file_id={file_id} ??? TestPlan JSON??????????")

    with open(json_files[-1], "r", encoding="utf-8") as f:
        json_data = json.load(f)

    chip_name = json_data.get("chip_name", "Unknown")
    chip_type = json_data.get("chip_type", "UNKNOWN")
    stats = json_data.get("statistics", {})

    extraction_result = ExtractionResult(
        status="success",
        chip_name=chip_name,
        chip_type=chip_type,
        test_scenario=json_data.get("test_scenario", "GENERAL"),
        total_params=stats.get("total", 0),
        a_params=stats.get("A_class", 0),
        b_params=stats.get("B_class", 0),
        c_params=stats.get("C_class", 0),
    )

    pin_defs_raw = json_data.get("pin_definitions", [])
    pin_df = None

    if pin_defs_raw:
        pin_df = pd.DataFrame(pin_defs_raw)
        logger.info(f"Auto-loaded pin definitions: {len(pin_df)} from module 1 JSON")
    elif pin_file:
        if not pin_file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, "PinMapping ????????? xlsx/xls/csv")
        contents = await pin_file.read()
        try:
            if pin_file.filename.endswith(".csv"):
                pin_df = pd.read_csv(BytesIO(contents))
            else:
                pin_df = pd.read_excel(BytesIO(contents))
            logger.info(f"Loaded pin definitions from uploaded file: {len(pin_df)}")
        except Exception as exc:
            raise HTTPException(400, f"PinMapping ??????: {exc}")
    else:
        raise HTTPException(
            400,
            "????????????????????????? pin_file?PinMapping Excel/CSV?",
        )

    if pin_df is None or pin_df.empty:
        raise HTTPException(400, "??????????????")

    logger.info(f"Start resource mapping: {chip_name} [{chip_type}]")
    run = controller.run_flow(
        flow_name="module2_resource_map",
        payload={
            "file_id": file_id,
            "chip_type": chip_type,
            "dual_site": dual_site,
            "extraction_result": extraction_result,
            "pin_mapping_df": pin_df,
        },
    )
    run_store.save_run(run.to_dict())

    if run.status != "completed":
        message = run.errors[-1] if run.errors else "??????"
        raise HTTPException(500, message)

    result = run.shared.get("resource_map_result") or {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_prefix = f"{chip_name}_{timestamp}"

    excel_path = str(settings.PROCESSED_DIR / f"{out_prefix}_ResourceMap.xlsx")
    adapter_info = AdapterInfo.model_validate(result.get("adapter_info") or {})
    resource_mappings = [ResourceMapping.model_validate(item) for item in result.get("resource_mappings", [])]
    pgs_configs = [PGSConfig.model_validate(item) for item in result.get("pgs_configs", [])]
    pgs_details = [PGSDetailCondition.model_validate(item) for item in result.get("pgs_detail_conditions", [])]
    pin_groups = PinGroupConfig.model_validate(result.get("pin_groups") or {})

    export_resource_map_excel(
        chip_name=chip_name,
        chip_type=result.get("chip_type", chip_type),
        adapter_info=adapter_info,
        resource_mappings=resource_mappings,
        pgs_configs=pgs_configs,
        pgs_details=pgs_details,
        pin_groups=pin_groups,
        output_path=excel_path,
    )

    svg_path = str(settings.PROCESSED_DIR / f"{out_prefix}_Schematic.svg")
    svg_gen.generate(
        chip_name=chip_name,
        chip_type=result.get("chip_type", chip_type),
        mappings=resource_mappings,
        output_path=svg_path,
    )

    bom_path = str(settings.PROCESSED_DIR / f"{out_prefix}_BOM.xlsx")
    generate_bom_excel(
        bom_items=adapter_info.bom_items,
        chip_name=chip_name,
        adapter_model=result.get("adapter_model", ""),
        output_path=bom_path,
    )

    mappings = result.get("resource_mappings", [])
    summary = {
        "resource_type_counts": {
            resource_type: sum(1 for mapping in mappings if mapping.get("resource_type") == resource_type)
            for resource_type in sorted({mapping.get("resource_type", "UNKNOWN") for mapping in mappings})
        },
        "power_pin_count": sum(1 for mapping in mappings if mapping.get("resource_type") == "VI" and str(mapping.get("signal_type", "")).upper() == "POWER"),
        "bidir_pin_count": sum(1 for mapping in mappings if str(mapping.get("signal_type", "")).upper() == "BIDIR"),
        "unassigned_count": sum(1 for mapping in mappings if mapping.get("resource_type") == "NC"),
        "dio_site1_count": sum(1 for mapping in mappings if mapping.get("resource_type") == "DIO" and int(mapping.get("channel_no", 0)) < 12),
        "dio_site2_count": sum(1 for mapping in mappings if mapping.get("resource_type") == "DIO" and int(mapping.get("channel_no", 0)) >= 12),
        "site_count": 2 if dual_site else 1,
    }

    finalized = finalize_module2_run(
        run,
        chip_name=chip_name,
        out_prefix=out_prefix,
        pin_auto_loaded=len(pin_defs_raw) > 0,
        summary=summary,
    )
    logger.success(f"Resource mapping finished | adapter={finalized.get('adapter', "")}")
    return {
        "status": "success",
        "message": "????????",
        "data": finalized,
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
