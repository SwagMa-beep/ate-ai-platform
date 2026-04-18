"""
TestPlan服务 - 面向STS8200S测试平台
整合芯片类型识别 + 场景化提取 + 引脚定义自动提取
"""
import pandas as pd
from pathlib import Path
import json
from typing import Optional, List, Dict

from app.utils.pdf_parser import PDFParser
from app.services.llm_extractor import LLMExtractor
from app.services.data_validator import DataValidator
from app.utils.excel_exporter import export_excel
from app.models.testplan import ExtractionResult, PinDefinition
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

# 参数白名单常量
DIGITAL_DC_PARAMS_SET = {
    "CONNECT", "FUN", "VIH", "VIL", "VOH", "VOL", "VIK",
    "II", "IIH", "IIL", "IOZH", "IOZL",
    "IOH", "IOL", "IOS", "ICCH", "ICCL", "Ron", "DeltaRon"
}
DIGITAL_AC_PARAMS_SET = {
    "Tr", "tTLH", "Tf", "tTHL", "tPHL", "tPLH"
}


class TestPlanService:
    """TestPlan提取服务（完整流程）- STS8200S专用"""

    def __init__(self):
        self.llm_extractor = LLMExtractor()
        self.validator     = DataValidator()
        logger.info("TestPlan服务初始化完成 [STS8200S模式]")

    def extract_from_pdf(
            self,
            pdf_path: str,
            pages: Optional[str] = None,
            max_workers: int = 3,
            progress_callback = None
    ) -> ExtractionResult:
        """
        完整提取流程（含芯片类型识别 + 引脚定义自动提取）
        """
        max_workers  = max_workers or settings.MAX_WORKERS
        pdf_path_obj = Path(pdf_path)
        pdf_name     = pdf_path_obj.stem  # 完整文件名（不含扩展名）

        # ✅ 修复：正确提取芯片名
        # 文件名格式：{file_id}_{timestamp}_{原始文件名}
        # 例如：8ec851c8_20260412_193825_Renesas-HD74LS00P
        # 需要去掉前两段（file_id 和 timestamp）
        name_parts = pdf_name.split("_")
        if len(name_parts) >= 3:
            # 去掉 file_id(第1段) 和 timestamp(第2段)
            chip_name = "_".join(name_parts[2:])
        else:
            chip_name = pdf_name

        # 进一步清理后缀关键词
        chip_name = (
            chip_name
            .replace("_datasheet", "")
            .replace("_Datasheet", "")
            .replace("_DataSheet", "")
        )

        try:
            # ── Step 1: 解析PDF ────────────────────────────
            self._print_step(1, 5, "解析PDF")
            parser = PDFParser(pdf_path)
            chunks = parser.parse(pages=pages)

            if not chunks:
                return ExtractionResult(
                    status="error",
                    errors=["未解析到任何有效页面，请检查PDF文件或页码范围"]
                )

            # ── Step 2: 识别芯片类型 ───────────────────────
            self._print_step(2, 5, "识别芯片类型")
            chip_type = self.llm_extractor.detect_chip_type(chunks[:3])
            logger.info(f"芯片类型: {chip_type}")
            self._print_chip_type_info(chip_type)

            # ── Step 2.5: 页面过滤与合并 (提速核心) ─────────
            filtered_chunks = self._filter_and_batch_chunks(chunks)

            # ── Step 3: LLM并发提取（参数 + 引脚）────────
            self._print_step(
                3, 5,
                f"AI提取参数和引脚 [场景:{chip_type}] [并发:{max_workers}]"
            )

            # 如果传入了进度回调，我们可以将其进行二次封装，以匹配 chunks 数量
            def _llm_progress_update(current, total, *args, **kwargs):
                if progress_callback:
                    # 将 20% ~ 80% 的进度分配给 LLM 提取阶段
                    progress_callback(current, total)

            all_params, all_pins = self.llm_extractor.extract_parallel(
                filtered_chunks, chip_type, max_workers, progress_callback=_llm_progress_update
            )

            if not all_params:
                return ExtractionResult(
                    status="error",
                    chip_type=chip_type,
                    errors=[
                        "未提取到任何参数。可能原因：",
                        "1. 页面无参数表",
                        "2. PDF是扫描件（非文字版）",
                        "3. API额度不足",
                        "4. 页码范围设置不当"
                    ]
                )

            logger.info(
                f"提取统计: 参数{len(all_params)}个 | "
                f"引脚{len(all_pins)}个"
            )

            # ── Step 4: 数据清洗与STS8200S校验 ───────────
            self._print_step(4, 5, "数据清洗与STS8200S适配性校验")
            df = pd.DataFrame([p.model_dump() for p in all_params])
            df = self.validator.clean_and_validate(df, chip_type)

            sts_report = self.validator.get_sts_compatibility_report(
                df, chip_type
            )

            # ── 统计分类 ────────────────────────────────────
            df_a = df[
                (df["category"] == "A")
                & (~df["Status"].str.contains("已拦截", na=False))
            ]
            df_b = df[
                (df["category"] == "B")
                & (~df["Status"].str.contains("已拦截", na=False))
            ]
            df_c = df[
                (df["category"] == "C")
                & (~df["Status"].str.contains("已拦截", na=False))
            ]
            df_blocked = df[
                df["Status"].str.contains("已拦截", na=False)
            ]

            dc_items  = len(df[df["param_name"].isin(DIGITAL_DC_PARAMS_SET)])
            ac_items  = len(df[df["param_name"].isin(DIGITAL_AC_PARAMS_SET)])
            ldo_items = len(df[df["param_name"].isin({"VO","Sv","Si","Iq"})])

            # ── Step 5: 导出 ───────────────────────────────
            self._print_step(5, 5, "导出Excel和JSON")

            # 文件路径（使用完整pdf_name避免冲突）
            excel_path = (
                settings.PROCESSED_DIR / f"{pdf_name}_TestPlan.xlsx"
            )
            json_path = (
                settings.PROCESSED_DIR / f"{pdf_name}_TestPlan.json"
            )

            export_excel(
                df, chip_name, str(excel_path),
                chip_type       = chip_type,
                sts_report      = sts_report,
                pin_definitions = all_pins
            )

            json_data = {
                "chip_name":     chip_name,
                "chip_type":     chip_type,
                "test_scenario": self._get_scenario_name(chip_type),
                "sts_report":    sts_report,
                "pin_definitions": [
                    p.model_dump() for p in all_pins
                ],
                "pin_count": len(all_pins),
                "statistics": {
                    "total":          len(all_params),
                    "A_class":        len(df_a),
                    "B_class":        len(df_b),
                    "C_class":        len(df_c),
                    "blocked":        len(df_blocked),
                    "dc_test_items":  dc_items,
                    "ac_test_items":  ac_items,
                    "ldo_test_items": ldo_items,
                },
                "parameters": [p.model_dump() for p in all_params]
            }

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            logger.success(f"JSON已保存: {json_path}")

            self._print_report(
                df, chip_name, chip_type,
                df_a, df_b, df_c, df_blocked,
                dc_items, ac_items, ldo_items,
                sts_report, all_pins
            )

            validation = self.validator.get_validation_summary(df)

            return ExtractionResult(
                status          = "success",
                chip_name       = chip_name,
                chip_type       = chip_type,
                test_scenario   = self._get_scenario_name(chip_type),
                total_params    = len(df),
                a_params        = len(df_a),
                b_params        = len(df_b),
                c_params        = len(df_c),
                blocked_params  = len(df_blocked),
                dc_test_items   = dc_items,
                ac_test_items   = ac_items,
                ldo_test_items  = ldo_items,
                excel_path      = str(excel_path),
                json_path       = str(json_path),
                errors          = validation.errors[:10],
                warnings        = (
                    validation.warnings + validation.sts_warnings
                )[:10],
                sts_compatibility = sts_report,
                pin_definitions   = all_pins,
                range_recommendations = self._generate_range_recommendations(df, chip_type),
            )

        except Exception as e:
            logger.error(f"提取过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ExtractionResult(
                status="error",
                errors=[f"提取失败: {str(e)}"]
            )

    # ----------------------------------------------------------
    # 私有辅助方法
    # ----------------------------------------------------------

    @staticmethod
    def _get_scenario_name(chip_type: str) -> str:
        scenario_map = {
            "DIGITAL_74":     "DIGITAL",
            "DIGITAL_54":     "DIGITAL",
            "DIGITAL_4000":   "DIGITAL",
            "MEMORY":         "DIGITAL",
            "LDO":            "ANALOG_LDO",
            "EEPROM":         "ANALOG_EEPROM",
            "ANALOG_GENERAL": "GENERAL",
            "UNKNOWN":        "GENERAL"
        }
        return scenario_map.get(chip_type, "GENERAL")

    @staticmethod
    def _print_step(current: int, total: int, name: str) -> None:
        logger.info(f"--- Step {current}/{total}: {name} ---")

    @staticmethod
    def _print_chip_type_info(chip_type: str) -> None:
        info_map = {
            "DIGITAL_74":
                "  → 场景A: 74系列数字芯片\n"
                "  → 提取: VIH/VIL/VOH/VOL等参数 + 引脚定义",
            "DIGITAL_54":
                "  → 场景A: 54系列(军品)数字芯片\n"
                "  → 提取: VIH/VIL/VOH/VOL等参数 + 引脚定义",
            "DIGITAL_4000":
                "  → 场景A: 4000系列CMOS数字芯片\n"
                "  → 提取: VIH/VIL/VOH/VOL等参数 + 引脚定义",
            "MEMORY":
                "  → 场景A: 存储器\n"
                "  → 提取: 时序参数 + 引脚定义",
            "LDO":
                "  → 场景B1: 线性稳压器\n"
                "  → 提取: VO/Sv/Si/Iq + 引脚定义",
            "EEPROM":
                "  → 场景B2: EEPROM\n"
                "  → 提取: 电气参数 + 引脚定义",
            "ANALOG_GENERAL":
                "  → 场景C: 通用模拟芯片\n"
                "  → 提取: A/B/C三类参数 + 引脚定义",
            "UNKNOWN":
                "  → 场景C: 未识别类型，使用通用提取\n"
                "  → 提取: A/B/C三类参数 + 引脚定义",
        }
        logger.info(info_map.get(chip_type, f"芯片类型: {chip_type}"))

    @staticmethod
    def _filter_and_batch_chunks(chunks: List[Dict]) -> List[Dict]:
        """
        核心优化：过滤无关页面并合并文本块以减少 LLM 并发数量
        """
        # 关键词库（中英文兼容）
        keywords = [
            "electrical", "characteristics", "absolute maximum", "pin configuration",
            "symbol", "parameter", "min", "typ", "max", "unit", "test condition",
            "vcc", "gnd", "pinout", "specifications", "rating", "limits", "features",
            "电气特性", "引脚", "绝对最大", "参数", "符号", "测试条件"
        ]
        
        filtered = []
        for i, chunk in enumerate(chunks):
            content_lower = chunk["content"].lower()
            # 前两页通常是关键摘要和引脚图，无条件保留
            if i < 2:
                filtered.append(chunk)
                continue
                
            # 计算关键词命中率
            hit_count = sum(1 for kw in keywords if kw in content_lower)
            if hit_count >= 2:  # 至少命中2个关键词才保留
                filtered.append(chunk)
            else:
                # 进一步排除常见的纯包装尺寸页
                if "package outline" in content_lower or "dimensions" in content_lower or "ordering information" in content_lower:
                    pass # 丢弃
                else:
                    # 如果文本中包含大量数字，可能也是表格，尝试保留
                    digit_count = sum(c.isdigit() for c in chunk["content"])
                    if digit_count > 50:
                        filtered.append(chunk)

        # 动态合并：每 2-3 页合并为一个 Chunk
        BATCH_SIZE = 3
        batched_chunks = []
        for i in range(0, len(filtered), BATCH_SIZE):
            batch = filtered[i:i + BATCH_SIZE]
            combined_content = "\n\n=== NEXT PAGE ===\n\n".join(
                f"[Page {c['page']}]\n{c['content']}" for c in batch
            )
            # 以第一页的页码作为代表
            page_label = f"{batch[0]['page']}-{batch[-1]['page']}" if len(batch) > 1 else str(batch[0]['page'])
            batched_chunks.append({
                "page": page_label,
                "content": combined_content
            })
            
        logger.info(f"提速漏斗: 原始 {len(chunks)} 页 -> 过滤后 {len(filtered)} 页 -> 合并为 {len(batched_chunks)} 个请求")
        return batched_chunks

    def _generate_range_recommendations(self, df: pd.DataFrame, chip_type: str) -> List[Dict]:
        """
        基于 STS8200S 硬件规范的 8 套量程判定规则
        """
        recs = []
        
        # 规则1: 高压检测 (>10V)
        if "max_val" in df.columns:
            hv_mask = (df["unit"] == "V") & (df["max_val"] > 10.0)
            if hv_mask.any():
                recs.append({
                    "param": "VI源量程",
                    "value": "20V/60V 扩展量程",
                    "reason": "检测到部分参数电压 > 10V，需开启高压板卡支持",
                    "priority": "high"
                })

        # 规则2: 大电流检测 (>200mA)
        if "max_val" in df.columns:
            cur_mask = ((df["unit"] == "A") & (df["max_val"] > 0.2)) | \
                       ((df["unit"] == "mA") & (df["max_val"] > 200.0))
            if cur_mask.any():
                recs.append({
                    "param": "电流驱动",
                    "value": "EXT-Current 模式",
                    "reason": "存在大电流需求，建议配置外部扩流模块",
                    "priority": "normal"
                })

        # 规则3: 数字电平匹配 (LDO/Analog 场景)
        if chip_type == "LDO":
            recs.append({
                "param": "DIO电平",
                "value": "3.3V CMOS",
                "reason": "LDO控制逻辑通常工作在 3.3V 电平范围",
                "priority": "normal"
            })

        # 规则4: 静态电流小量程 (uA)
        iq_mask = df["param_name"].str.contains("Iq|ICC|ISB", case=False, na=False)
        if iq_mask.any():
            recs.append({
                "param": "QTMU量程",
                "value": "2uA / 20uA 精密档",
                "reason": "包含静态电流测试，建议使用 QTMU 小量程以保证精度",
                "priority": "normal"
            })

        # 规则5: 数字芯片 VCC 推荐
        if "DIGITAL" in chip_type:
            recs.append({
                "param": "FVI供电",
                "value": "5V / 200mA",
                "reason": "标准 74 系列推荐供电配置",
                "priority": "normal"
            })

        # 规则6: 阈值余量
        recs.append({
            "param": "采样率",
            "value": "100kHz / 16-bit",
            "reason": "平衡直流精度与瞬态捕捉能力的最佳配置",
            "priority": "normal"
        })

        return recs

    def _print_report(
        self,
        df: pd.DataFrame,
        chip_name: str,
        chip_type: str,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        df_c: pd.DataFrame,
        df_blocked: pd.DataFrame,
        dc_items: int,
        ac_items: int,
        ldo_items: int,
        sts_report: dict,
        all_pins: List[PinDefinition]
    ) -> None:
        logger.info(f"提取统计报告 - {chip_name} [{chip_type}]")

        if all_pins:
            in_count  = sum(1 for p in all_pins if p.direction == "IN")
            out_count = sum(1 for p in all_pins if p.direction == "OUT")
            pwr_count = sum(1 for p in all_pins if p.direction == "PWR")
            gnd_count = sum(1 for p in all_pins if p.direction == "GND")
            logger.info(f"引脚定义: {len(all_pins)} 个")
            logger.info(
                f"输入:{in_count} 输出:{out_count} "
                f"电源:{pwr_count} 地:{gnd_count}"
            )
        else:
            logger.info("引脚定义: 未提取到（PDF可能无引脚表）")

        if chip_type in {
            "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"
        }:
            logger.info(f"DC测试项(VIH/VIL/VOH/VOL等): {dc_items} 条")
            logger.info(f"AC测试项(Tr/Tf/tPHL/tPLH):   {ac_items} 条")
        elif chip_type == "LDO":
            logger.info(f"LDO测试项(VO/Sv/Si/Iq):      {ldo_items} 条")
        elif chip_type == "EEPROM":
            logger.info(f"功能测试项(读写55/AA/DIFF):   3 条(固定)")
            logger.info(f"电气参数项:                   {len(df_a)} 条")

        logger.info(f"B类(绝对最大值-保护限):       {len(df_b)} 条")
        logger.info(f"C类(工作条件-全局设置):       {len(df_c)} 条")
        logger.info(f"已拦截(无效参数):             {len(df_blocked)} 条")
        logger.info(f"总计:                         {len(df)} 条")

        compatible = sts_report.get("is_compatible", True)
        logger.info(
            f"STS8200S适配性: "
            f"{'兼容' if compatible else '存在问题'}"
        )
        for issue in sts_report.get("issues", []):
            logger.info(f"Issue: {issue}")
        logger.info(f"接线建议:")
        for rec in sts_report.get("recommendations", [])[:3]:
            logger.info(f" -> {rec}")

        if len(df_a) > 0:
            logger.info(f"测试参数预览（前5条）:")
            for _, row in df_a.head(5).iterrows():
                min_v    = row.get('min_val', '')
                typ_v    = row.get('typ_val', '')
                max_v    = row.get('max_val', '')
                unit     = row.get('unit', '')
                sts_func = row.get('sts_test_function', '')
                sts_str  = f" [{sts_func}]" if sts_func else ""
                logger.info(
                    f"    {str(row['param_name']):30s} "
                    f"[{min_v}/{typ_v}/{max_v}] {unit}{sts_str}"
                )
