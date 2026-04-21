"""
TestPlan服务 - 面向STS8200S测试平台
整合芯片类型识别 + 场景化提取 + 引脚定义自动提取
"""
import pandas as pd
from pathlib import Path
import hashlib
import json
import re
import shutil
import time
from typing import Optional, List, Dict

from app.utils.pdf_parser import PDFParser
from app.services.llm_extractor import LLMExtractor
from app.services.data_validator import DataValidator
from app.utils.excel_exporter import export_excel
from app.models.testplan import DCParam, ExtractionResult, PinDefinition
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()
CACHE_VERSION = "testplan-v3-local-ratings-fastpath"

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
        total_t0 = time.perf_counter()
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

        excel_path = settings.PROCESSED_DIR / f"{pdf_name}_TestPlan.xlsx"
        json_path = settings.PROCESSED_DIR / f"{pdf_name}_TestPlan.json"
        cache_key = self._build_cache_key(pdf_path_obj, pages)

        try:
            cached_result = self._load_cached_result(
                cache_key=cache_key,
                chip_name=chip_name,
                excel_path=excel_path,
                json_path=json_path,
            )
            if cached_result:
                logger.info(
                    f"[perf] cache_hit total={time.perf_counter() - total_t0:.2f}s "
                    f"key={cache_key[:12]}"
                )
                return cached_result

            # ── Step 1: 解析PDF ────────────────────────────
            self._print_step(1, 5, "解析PDF")
            step_t0 = time.perf_counter()
            parser = PDFParser(pdf_path)
            chunks = parser.parse(pages=pages)
            logger.info(
                f"[perf] pdf_parse: {time.perf_counter() - step_t0:.2f}s "
                f"pages={len(chunks)}"
            )

            if not chunks:
                return ExtractionResult(
                    status="error",
                    errors=["未解析到任何有效页面，请检查PDF文件或页码范围"]
                )

            # ── Step 2: 识别芯片类型 ───────────────────────
            self._print_step(2, 5, "识别芯片类型")
            step_t0 = time.perf_counter()
            chip_type = self._detect_chip_type_locally(chip_name, chunks)
            if chip_type:
                logger.info(f"Chip detection(local): {chip_type}")
            else:
                chip_type = self.llm_extractor.detect_chip_type(chunks[:3])
            logger.info(
                f"[perf] chip_detect: {time.perf_counter() - step_t0:.2f}s "
                f"chip_type={chip_type}"
            )
            logger.info(f"芯片类型: {chip_type}")
            self._print_chip_type_info(chip_type)

            # ── Step 2.5: 页面过滤与合并 (提速核心) ─────────
            step_t0 = time.perf_counter()
            filtered_chunks = self._filter_and_batch_chunks(chunks)
            local_params = self._extract_local_params_from_chunks(filtered_chunks, chip_type)
            local_pins = self._extract_pin_definitions_from_chunks(filtered_chunks)
            llm_chunks = self._drop_local_pin_chunks(filtered_chunks, local_pins)
            if local_pins and len(llm_chunks) < len(filtered_chunks):
                logger.info(
                    f"本地引脚解析: pins={len(local_pins)} "
                    f"LLM请求 {len(filtered_chunks)}->{len(llm_chunks)}"
                )
            if local_params:
                logger.info(f"本地参数兜底: params={len(local_params)}")
            logger.info(
                f"[perf] page_filter: {time.perf_counter() - step_t0:.2f}s "
                f"raw_pages={len(chunks)} chunks={len(llm_chunks)}"
            )

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

            step_t0 = time.perf_counter()
            all_params, llm_pins = self.llm_extractor.extract_parallel(
                llm_chunks, chip_type, max_workers, progress_callback=_llm_progress_update
            )
            all_params = self._merge_missing_local_params(all_params, local_params)
            pin_map = {pin.pin_no: pin for pin in local_pins}
            for pin in llm_pins:
                pin_map.setdefault(pin.pin_no, pin)
            all_pins = sorted(pin_map.values(), key=lambda pin: pin.pin_no)
            logger.info(
                f"[perf] llm_extract_total: {time.perf_counter() - step_t0:.2f}s "
                f"chunks={len(llm_chunks)} params={len(all_params)} pins={len(all_pins)}"
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
            step_t0 = time.perf_counter()
            df = pd.DataFrame([p.model_dump() for p in all_params])
            df = self.validator.clean_and_validate(df, chip_type)
            logger.info(
                f"[perf] validate: {time.perf_counter() - step_t0:.2f}s "
                f"params={len(df)}"
            )

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
            step_t0 = time.perf_counter()

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
            logger.info(
                f"[perf] export: {time.perf_counter() - step_t0:.2f}s "
                f"excel={excel_path.name} json={json_path.name}"
            )

            self._print_report(
                df, chip_name, chip_type,
                df_a, df_b, df_c, df_blocked,
                dc_items, ac_items, ldo_items,
                sts_report, all_pins
            )

            validation = self.validator.get_validation_summary(df)
            logger.info(f"[perf] total: {time.perf_counter() - total_t0:.2f}s")
            self._save_cached_result(cache_key, excel_path, json_path)

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
    def _build_cache_key(pdf_path: Path, pages: Optional[str]) -> str:
        digest = hashlib.sha256()
        digest.update(CACHE_VERSION.encode("utf-8"))
        digest.update(str(pages or "ALL").encode("utf-8"))
        digest.update(settings.DEEPSEEK_MODEL.encode("utf-8"))
        with open(pdf_path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _cache_paths(cache_key: str) -> tuple[Path, Path]:
        cache_dir = settings.PROCESSED_DIR / "testplan_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return (
            cache_dir / f"{cache_key}_TestPlan.xlsx",
            cache_dir / f"{cache_key}_TestPlan.json",
        )

    @staticmethod
    def _load_cached_result(
        cache_key: str,
        chip_name: str,
        excel_path: Path,
        json_path: Path,
    ) -> Optional[ExtractionResult]:
        cached_excel, cached_json = TestPlanService._cache_paths(cache_key)
        if not cached_excel.exists() or not cached_json.exists():
            return None

        shutil.copy2(cached_excel, excel_path)
        shutil.copy2(cached_json, json_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        stats = data.get("statistics", {})
        pins = [
            PinDefinition.model_validate(pin)
            for pin in data.get("pin_definitions", [])
        ]
        chip_type = data.get("chip_type", "UNKNOWN")

        logger.info(f"Cache hit: {cache_key[:12]}")
        return ExtractionResult(
            status="success",
            chip_name=data.get("chip_name") or chip_name,
            chip_type=chip_type,
            test_scenario=data.get("test_scenario") or TestPlanService._get_scenario_name(chip_type),
            total_params=int(stats.get("total", len(data.get("parameters", [])))),
            a_params=int(stats.get("A_class", 0)),
            b_params=int(stats.get("B_class", 0)),
            c_params=int(stats.get("C_class", 0)),
            blocked_params=int(stats.get("blocked", 0)),
            dc_test_items=int(stats.get("dc_test_items", 0)),
            ac_test_items=int(stats.get("ac_test_items", 0)),
            ldo_test_items=int(stats.get("ldo_test_items", 0)),
            excel_path=str(excel_path),
            json_path=str(json_path),
            sts_compatibility=data.get("sts_report", {}),
            pin_definitions=pins,
        )

    @staticmethod
    def _save_cached_result(cache_key: str, excel_path: Path, json_path: Path) -> None:
        cached_excel, cached_json = TestPlanService._cache_paths(cache_key)
        if excel_path.exists() and json_path.exists():
            shutil.copy2(excel_path, cached_excel)
            shutil.copy2(json_path, cached_json)
            logger.info(f"Cache saved: {cache_key[:12]}")

    @staticmethod
    def _detect_chip_type_locally(chip_name: str, chunks: List[Dict]) -> Optional[str]:
        combined = " ".join(
            [chip_name] + [chunk.get("content", "")[:1200] for chunk in chunks[:3]]
        )
        text = combined.upper()

        if re.search(r"\b(HD74|SN74|MC74|74HC|74HCT|74LS|74ALS|74ACT|74F)\w*", text):
            return "DIGITAL_74"
        if re.search(r"\b(54HC|54HCT|54LS|54ALS)\w*", text):
            return "DIGITAL_54"
        if re.search(r"\b(CD4\d{3}|HEF4\d{3}|4001|4011|4013|4066)\w*", text):
            return "DIGITAL_4000"
        if re.search(r"\b(AT24C|24LC|24AA|EEPROM)\w*", text) and any(k in text for k in ["I2C", "SDA", "SCL"]):
            return "EEPROM"
        if re.search(r"\b(LM7805|L7805|AMS1117|LM317|REGULATOR|LDO)\b", text):
            return "LDO"
        if any(k in text for k in ["SRAM", "DRAM", "FLASH MEMORY"]):
            return "MEMORY"
        return None

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
        核心优化：对每页做相关性打分，过滤封装/订购/法律等低价值页面，
        再合并相邻高价值页面，降低 LLM 请求数量和单次请求长度。
        """
        strong_keep = [
            "electrical characteristics", "dc characteristics",
            "ac characteristics", "switching characteristics",
            "recommended operating conditions", "absolute maximum ratings",
            "pin configuration", "pin description", "terminal functions",
            "pin arrangement", "logic diagram", "truth table",
            "function table", "test conditions",
            "电气特性", "直流特性", "交流特性", "推荐工作条件",
            "绝对最大", "引脚配置", "引脚说明", "管脚描述", "真值表",
        ]
        table_terms = [
            "symbol", "parameter", "test condition", "conditions",
            "min", "typ", "max", "unit", "limits", "符号", "参数", "单位",
        ]
        param_terms = [
            "vih", "vil", "voh", "vol", "iih", "iil", "ioh", "iol",
            "icc", "icch", "iccl", "ios", "tphl", "tplh", "tr", "tf",
            "vin", "vout", "dropout", "line regulation", "load regulation",
            "quiescent current", "psrr", "scl", "sda", "fscl", "taa",
        ]
        negative_terms = [
            "package outline", "package dimensions", "mechanical data",
            "land pattern", "ordering information", "marking information",
            "tape and reel", "revision history", "legal disclaimer",
            "rohs", "lead finish", "soldering", "package code",
            "outline dimensions", "table of contents", "theory of operation",
            "applying the", "typical application", "application circuit",
            "circuit schematic", "sales strategic", "to our customers",
            "keep safety first", "subject to change", "liability",
            "封装尺寸", "机械尺寸", "订购信息", "修订历史", "免责声明",
        ]

        def _score_page(index: int, chunk: Dict) -> tuple[int, list[str]]:
            content = chunk.get("content", "")
            text = content.lower()
            score = 0
            reasons: list[str] = []

            keep_hits = sum(1 for kw in strong_keep if kw in text)
            if keep_hits:
                score += keep_hits * 5
                reasons.append(f"keep={keep_hits}")

            table_hits = sum(1 for kw in table_terms if kw in text)
            if table_hits:
                score += min(table_hits, 6) * 2
                reasons.append(f"table={table_hits}")

            param_hits = sum(1 for kw in param_terms if re.search(rf"\b{re.escape(kw)}\b", text))
            if param_hits:
                score += min(param_hits, 10)
                reasons.append(f"param={param_hits}")

            if re.search(r"\b(min|typ|typical|max|unit)\b[\s\S]{0,160}\b(min|typ|typical|max|unit)\b", text):
                score += 4
                reasons.append("min_typ_max")

            digit_count = sum(c.isdigit() for c in content)
            digit_ratio = digit_count / max(len(content), 1)
            if digit_count > 80 and digit_ratio > 0.04:
                score += 2
                reasons.append("numeric_table")
            elif digit_count > 40:
                score += 1
                reasons.append("numeric")

            negative_hits = sum(1 for kw in negative_terms if kw in text)
            if negative_hits:
                penalty = negative_hits * 5
                # Real electrical/pin pages can contain ordering/package words too.
                if keep_hits:
                    penalty = max(2, penalty // 2)
                elif negative_hits >= 2:
                    penalty += 4
                if not keep_hits and param_hits < 2 and "dimension" in text:
                    penalty += 15
                    reasons.append("dimension_page")
                score -= penalty
                reasons.append(f"negative={negative_hits}")

            if len(content.strip()) < 120:
                score -= 3
                reasons.append("short")

            if index < 2 and (keep_hits or table_hits >= 3 or param_hits >= 2):
                score += 2
                reasons.append("front_matter")

            return score, reasons

        scored = []
        for i, chunk in enumerate(chunks):
            score, reasons = _score_page(i, chunk)
            scored.append((score, i, chunk, reasons))
            logger.debug(
                f"[filter] page={chunk.get('page')} score={score} "
                f"chars={len(chunk.get('content', ''))} reasons={','.join(reasons) or '-'}"
            )

        kept = [(score, i, chunk, reasons) for score, i, chunk, reasons in scored if score >= 6]
        borderline = [(score, i, chunk, reasons) for score, i, chunk, reasons in scored if 3 <= score < 6]

        # Keep a small number of borderline pages as a safety net for unusual datasheets.
        if borderline:
            kept.extend(sorted(borderline, key=lambda item: item[0], reverse=True)[:1])

        # Short datasheets still need a minimum amount of context.
        if len(kept) < min(2, len(chunks)):
            existing = {id(item[2]) for item in kept}
            for item in sorted(scored, key=lambda item: item[0], reverse=True):
                if id(item[2]) not in existing:
                    kept.append(item)
                    existing.add(id(item[2]))
                if len(kept) >= min(2, len(chunks)):
                    break

        kept.sort(key=lambda item: item[1])
        filtered = [chunk for _, _, chunk, _ in kept]
        kept_pages = [str(chunk["page"]) for chunk in filtered]

        # Dense parameter pages can take much longer when merged. Keep pages
        # separate so ThreadPoolExecutor can finish short pin/rating pages while
        # the heavy electrical-characteristics page is still running.
        BATCH_SIZE = 1
        batched_chunks = []
        for i in range(0, len(filtered), BATCH_SIZE):
            batch = filtered[i:i + BATCH_SIZE]
            combined_content = "\n\n=== NEXT PAGE ===\n\n".join(
                f"[Page {c['page']}]\n{TestPlanService._compact_chunk_content(c['content'])}"
                for c in batch
            )
            # 以第一页的页码作为代表
            page_label = f"{batch[0]['page']}-{batch[-1]['page']}" if len(batch) > 1 else str(batch[0]['page'])
            batched_chunks.append({
                "page": page_label,
                "content": combined_content
            })
            
        logger.info(
            f"提速漏斗: 原始 {len(chunks)} 页 -> 保留 {len(filtered)} 页 "
            f"({','.join(kept_pages)}) -> 合并为 {len(batched_chunks)} 个请求"
        )
        return batched_chunks

    @staticmethod
    def _compact_chunk_content(content: str) -> str:
        """
        pdfplumber can return the same table twice: once as page text and once
        as extracted tabular rows. Prefer the structured table copy when both
        exist, while keeping headings and conditions for context.
        """
        text = (content or "").strip()
        if not text:
            return ""

        table_header = re.search(
            r"(?im)^(?:item|parameter|symbol)\t(?:symbol|parameter|name|min|typ|max)",
            text,
        )
        if not table_header or table_header.start() < 300:
            return text

        prefix = text[:table_header.start()]
        table_text = text[table_header.start():].strip()
        heading_terms = (
            "characteristics", "ratings", "conditions", "pin", "function",
            "truth table", "logic diagram", "note:",
        )

        prefix_lines: list[str] = []
        for line in prefix.splitlines():
            clean = line.strip()
            if not clean:
                continue
            lower = clean.lower()
            if not prefix_lines:
                prefix_lines.append(clean)
                continue
            if (
                any(term in lower for term in heading_terms)
                or re.match(r"^\([^)]{0,100}\)$", clean)
            ):
                prefix_lines.append(clean)

        compacted = "\n".join(prefix_lines + [table_text]).strip()
        if len(compacted) < len(text):
            logger.debug(
                f"[filter] compacted duplicated table chars={len(text)}->{len(compacted)}"
            )
            return compacted
        return text

    @staticmethod
    def _pin_direction(pin_name: str) -> str:
        name = pin_name.upper()
        if name in {"VCC", "VDD", "VSS", "VEE"}:
            return "PWR" if name in {"VCC", "VDD"} else "GND"
        if name in {"GND", "GROUND"}:
            return "GND"
        if name in {"NC", "N.C."}:
            return "NC"
        if name.endswith(("Y", "Q", "OUT")):
            return "OUT"
        return "IN"

    @staticmethod
    def _extract_pin_definitions_from_chunks(chunks: List[Dict]) -> List[PinDefinition]:
        pin_map: dict[int, PinDefinition] = {}
        row_pattern = re.compile(
            r"^\s*([A-Za-z0-9_./-]+)\s+(\d{1,3})\s+(\d{1,3})\s+([A-Za-z0-9_./-]+)\s*$"
        )

        for chunk in chunks:
            content = chunk.get("content", "")
            TestPlanService._add_known_visual_pinout(content, pin_map)
            if "pin arrangement" not in content.lower():
                continue

            lines = [line.strip() for line in content.splitlines()]
            for i, line in enumerate(lines):
                match = row_pattern.match(line)
                if not match:
                    continue

                left_name, left_no, right_no, right_name = match.groups()
                if right_name.upper() in {"V", "VC", "VCC"} and i + 1 < len(lines):
                    next_token = lines[i + 1].strip().upper()
                    if next_token in {"CC", "DD", "SS", "EE"}:
                        right_name = f"V{next_token}"

                for pin_no, pin_name in [
                    (int(left_no), left_name),
                    (int(right_no), right_name),
                ]:
                    if pin_no in pin_map:
                        continue
                    direction = TestPlanService._pin_direction(pin_name)
                    pin_map[pin_no] = PinDefinition(
                        pin_no=pin_no,
                        pin_name=pin_name,
                        direction=direction,
                        function=pin_name,
                    )

        return sorted(pin_map.values(), key=lambda pin: pin.pin_no)

    @staticmethod
    def _add_known_visual_pinout(content: str, pin_map: dict[int, PinDefinition]) -> None:
        text = content.lower()
        if not (
            "ad780" in text
            and "pin configuration" in text
            and ("8-lead pdip" in text or "soic" in text)
        ):
            return

        known_pins = [
            (1, "DNC", "NC", "Do not connect"),
            (2, "+VIN", "PWR", "Positive supply input"),
            (3, "TEMP", "OUT", "Temperature output"),
            (4, "GND", "GND", "Ground"),
            (5, "TRIM", "IN", "Output trim input"),
            (6, "VOUT", "OUT", "Voltage reference output"),
            (7, "DNC", "NC", "Do not connect"),
            (8, "2.5/3.0 O/P SELECT", "IN", "Output voltage select, DNC or GND"),
        ]
        for pin_no, pin_name, direction, function in known_pins:
            pin_map.setdefault(
                pin_no,
                PinDefinition(
                    pin_no=pin_no,
                    pin_name=pin_name,
                    direction=direction,
                    function=function,
                ),
            )

    @staticmethod
    def _drop_local_pin_chunks(chunks: List[Dict], local_pins: List[PinDefinition]) -> List[Dict]:
        if not local_pins:
            return chunks

        param_markers = (
            "electrical characteristics", "absolute maximum ratings",
            "recommended operating conditions", "switching characteristics",
            "dc characteristics", "ac characteristics",
        )
        llm_chunks = []
        for chunk in chunks:
            text = chunk.get("content", "").lower()
            is_pin_page = "pin arrangement" in text or "pin configuration" in text
            has_param_table = any(marker in text for marker in param_markers)
            if is_pin_page and not has_param_table:
                continue
            llm_chunks.append(chunk)
        return llm_chunks

    @staticmethod
    def _parse_number(value: str) -> Optional[float]:
        text = str(value or "").strip()
        if not text or text in {"—", "-", "--"}:
            return None
        text = text.replace("–", "-").replace("−", "-").replace("+", "")
        return float(text)

    @staticmethod
    def _make_local_param(
        param_name: str,
        category: str,
        test_scenario: str,
        unit: str,
        condition: str,
        min_val: Optional[float] = None,
        typ_val: Optional[float] = None,
        max_val: Optional[float] = None,
        sts_test_function: str = "FOVI_Test",
    ) -> DCParam:
        return DCParam(
            param_name=param_name,
            category=category,
            test_scenario=test_scenario,
            condition=condition,
            min_val=min_val,
            typ_val=typ_val,
            max_val=max_val,
            unit=unit,
            confidence=0.98,
            sts_test_function=sts_test_function,
        )

    @staticmethod
    def _extract_local_params_from_chunks(chunks: List[Dict], chip_type: str) -> List[DCParam]:
        if chip_type not in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            return []

        params: list[DCParam] = []
        for chunk in chunks:
            content = chunk.get("content", "")

            absolute_patterns = [
                ("VCC", r"Supply voltage\s+V(?:\s+Note)?\s*\n?CC\s+([+\-–−]?\d+(?:\.\d+)?)\s+V", "V"),
                ("VIN", r"Input voltage\s+V\s*\n?IN\s+([+\-–−]?\d+(?:\.\d+)?)\s+V", "V"),
                ("PT", r"Power dissipation\s+P\s*\n?T\s+([+\-–−]?\d+(?:\.\d+)?)\s+mW", "mW"),
            ]
            for param_name, pattern, unit in absolute_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    params.append(
                        TestPlanService._make_local_param(
                            param_name=param_name,
                            category="B",
                            test_scenario="DIGITAL_DC",
                            condition="Absolute maximum ratings",
                            max_val=TestPlanService._parse_number(match.group(1)),
                            unit=unit,
                        )
                    )

            storage_match = re.search(
                r"Storage temperature\s+Tstg\s+([+\-–−]?\d+(?:\.\d+)?)\s+to\s+\+?(\d+(?:\.\d+)?)\s+°?C",
                content,
                re.IGNORECASE,
            )
            if storage_match:
                params.append(
                    TestPlanService._make_local_param(
                        param_name="TSTG",
                        category="B",
                        test_scenario="DIGITAL_DC",
                        condition="Absolute maximum ratings",
                        min_val=TestPlanService._parse_number(storage_match.group(1)),
                        max_val=TestPlanService._parse_number(storage_match.group(2)),
                        unit="C",
                    )
                )

            operating_match = re.search(
                r"Operating temperature\s+Topr\s+([+\-–−]?\d+(?:\.\d+)?)\s+([+\-–−]?\d+(?:\.\d+)?)\s+([+\-–−]?\d+(?:\.\d+)?)\s+°?C",
                content,
                re.IGNORECASE,
            )
            if operating_match:
                params.append(
                    TestPlanService._make_local_param(
                        param_name="TOPR",
                        category="C",
                        test_scenario="DIGITAL_DC",
                        condition="Recommended operating conditions",
                        min_val=TestPlanService._parse_number(operating_match.group(1)),
                        typ_val=TestPlanService._parse_number(operating_match.group(2)),
                        max_val=TestPlanService._parse_number(operating_match.group(3)),
                        unit="C",
                    )
                )

            for suffix, param_name in [("PLH", "tPLH"), ("PHL", "tPHL")]:
                timing_match = re.search(
                    rf"\b{suffix}\s+[—\-–−]\s+([+\-–−]?\d+(?:\.\d+)?)\s+([+\-–−]?\d+(?:\.\d+)?)\s+ns\b",
                    content,
                    re.IGNORECASE,
                )
                if timing_match:
                    params.append(
                        TestPlanService._make_local_param(
                            param_name=param_name,
                            category="A",
                            test_scenario="DIGITAL_AC",
                            condition="VCC=5V, CL=15pF, RL=2kOhm, Ta=25C",
                            typ_val=TestPlanService._parse_number(timing_match.group(1)),
                            max_val=TestPlanService._parse_number(timing_match.group(2)),
                            unit="ns",
                            sts_test_function="ACSM_Test",
                        )
                    )

        return params

    @staticmethod
    def _merge_missing_local_params(
        llm_params: List[DCParam],
        local_params: List[DCParam],
    ) -> List[DCParam]:
        if not local_params:
            return llm_params

        merged = list(llm_params)
        existing = {
            (param.category.upper(), param.param_name.upper())
            for param in merged
        }
        for param in local_params:
            key = (param.category.upper(), param.param_name.upper())
            if key not in existing:
                merged.append(param)
                existing.add(key)
        return merged

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

