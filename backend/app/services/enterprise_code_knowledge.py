from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import BASE_DIR, get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


ITEM_DESCRIPTIONS: Dict[str, str] = {
    "CON": "Continuity test for contact/open-short screening.",
    "FUN": "Functional vector test with VECDIO pattern execution.",
    "VIH": "Input high threshold scan.",
    "VIL": "Input low threshold search.",
    "VIK": "Input clamp voltage test.",
    "VOH": "Output high level under load.",
    "VOL": "Output low level under load.",
    "IOS": "Output short-circuit current.",
    "II": "Input extreme voltage leakage.",
    "IIN": "Input leakage split into IIH/IIL.",
    "ICC": "Supply current measurement.",
    "TP1": "Timing test variant for TPHL path A.",
    "TP2": "Timing test variant for TPHL path B.",
    "TP3": "Timing test variant for TPLH path A.",
    "TP4": "Timing test variant for TPLH path B.",
    "VO": "Output voltage test.",
    "LNR": "Line regulation test.",
    "LDR": "Load regulation test.",
    "VDO1": "Dropout voltage test under light load.",
    "VDO2": "Dropout voltage test under heavy load.",
    "ICL": "Current limit threshold test.",
    "TP": "Startup timing test.",
    "UVLO": "Under-voltage lockout threshold and hysteresis.",
    "ENT": "Enable threshold sweep.",
    "IGND": "Ground/quiescent current test.",
    "IQ": "Quiescent current test.",
    "VO1": "Output voltage test for site configuration 1.",
    "VO2": "Output voltage test for site configuration 2.",
    "LNR1": "Line regulation test for site configuration 1.",
    "LNR2": "Line regulation test for site configuration 2.",
    "LDR1": "Load regulation test for site configuration 1.",
    "LDR2": "Load regulation test for site configuration 2.",
    "LDR3": "Load regulation test for site configuration 3.",
    "LDR4": "Load regulation test for site configuration 4.",
}

DIGITAL_ITEM_ORDER = [
    "CON", "FUN", "VIH", "VIL", "VIK", "VOH", "VOL", "IOS",
    "II", "IIN", "ICC", "TP1", "TP2", "TP3", "TP4",
]
ANALOG_ITEM_ORDER = [
    "VO", "LNR", "LDR", "VDO1", "VDO2", "ICL", "TP", "UVLO", "ENT", "IGND",
]
MULTISITE_ITEM_ORDER = [
    "VO1", "VO2", "LNR1", "LNR2", "LDR1", "LDR2", "LDR3", "LDR4", "IQ", "IOS",
]


class EnterpriseCodeKnowledgeService:
    """Parse enterprise sample code and expose reusable knowledge for codegen."""

    def __init__(self) -> None:
        self.root = BASE_DIR / "企业测试代码"
        self.catalog = self._build_catalog()

    def _build_catalog(self) -> Dict:
        catalog = {
            "available_items": {},
            "samples": [],
            "scenario_items": {
                "digital": [],
                "analog": [],
                "multisite": [],
                "custom": [],
            },
        }
        if not self.root.exists():
            logger.warning(f"Enterprise code folder not found: {self.root}")
            return catalog

        for cpp_path in sorted(self.root.rglob("*.cpp")):
            lower = str(cpp_path).lower()
            if any(part in lower for part in ["\\backup\\", "\\debug\\", "\\ipch\\"]):
                continue
            if cpp_path.name.lower() in {"stdafx.cpp", "userclass.cpp"}:
                continue

            try:
                text = cpp_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.warning(f"Skip enterprise code file {cpp_path}: {exc}")
                continue

            scenario = self._infer_scenario(cpp_path)
            sample_name = self._infer_sample_name(cpp_path)
            functions = self._extract_functions(text)
            if not functions:
                continue

            catalog["samples"].append({
                "name": sample_name,
                "scenario": scenario,
                "path": str(cpp_path),
                "function_count": len(functions),
            })

            for item, block in functions.items():
                apis = self._extract_api_tokens(block)
                entry = catalog["available_items"].setdefault(item, {
                    "item": item,
                    "description": ITEM_DESCRIPTIONS.get(item, f"Enterprise sample for {item}."),
                    "scenarios": [],
                    "samples": [],
                    "apis": [],
                    "sample_code": block.strip(),
                })
                if scenario not in entry["scenarios"]:
                    entry["scenarios"].append(scenario)
                entry["apis"] = sorted(set(entry["apis"]) | set(apis))
                entry["samples"].append({
                    "sample_name": sample_name,
                    "scenario": scenario,
                    "path": str(cpp_path),
                })
                if item not in catalog["scenario_items"][scenario]:
                    catalog["scenario_items"][scenario].append(item)

        for scenario_name, items in catalog["scenario_items"].items():
            ordered = self._order_items(items, scenario_name)
            catalog["scenario_items"][scenario_name] = ordered

        return catalog

    @staticmethod
    def _infer_scenario(path: Path) -> str:
        text = str(path)
        if "数字芯片例程" in text or "TestProject Rev3.00" in text:
            return "digital"
        if "模拟芯片例程" in text:
            return "analog"
        if "多工位测试例程" in text:
            return "multisite"
        return "custom"

    @staticmethod
    def _infer_sample_name(path: Path) -> str:
        for parent in path.parents:
            if parent.name in {"source", "Backup"}:
                continue
            if any(ch.isalnum() for ch in parent.name):
                return parent.name
        return path.stem

    @staticmethod
    def _extract_functions(text: str) -> Dict[str, str]:
        functions: Dict[str, str] = {}
        pattern = re.compile(r"DUT_API\s+int\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{", re.MULTILINE)
        for match in pattern.finditer(text):
            name = match.group(1)
            block = EnterpriseCodeKnowledgeService._extract_brace_block(text, match.start())
            if block:
                functions[name] = block
        return functions

    @staticmethod
    def _extract_brace_block(text: str, start: int) -> str:
        brace_index = text.find("{", start)
        if brace_index == -1:
            return ""
        depth = 0
        for idx in range(brace_index, len(text)):
            ch = text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]
        return text[start:]

    @staticmethod
    def _extract_api_tokens(code: str) -> List[str]:
        tokens = []
        for token in [
            "StsGetParam", "SetTestResult", "SetResultRemark", "Set", "MeasureVI",
            "GetMeasResult", "AwgLoader", "AwgSelect", "AwgClear", "SetPinLevel",
            "Run", "Connect", "Disconnect", "SetCBITOn", "SetCBITOff",
            "STSEnableAWG", "STSEnableMeas", "STSAWGRun", "STSAWGRunTriggerStop",
            "SetStartTrigger", "SetStopTrigger", "SinglePlsMeas",
            "StsSetModuleToSite", "STSSetHardwareCheck",
        ]:
            if token in code:
                tokens.append(token)
        return tokens

    @staticmethod
    def _order_items(items: List[str], scenario: str) -> List[str]:
        preferred = {
            "digital": DIGITAL_ITEM_ORDER,
            "analog": ANALOG_ITEM_ORDER,
            "multisite": MULTISITE_ITEM_ORDER,
        }.get(scenario, [])
        rest = sorted(item for item in items if item not in preferred)
        return [item for item in preferred if item in items] + rest

    def get_catalog(self) -> Dict:
        return self.catalog

    def list_items(self, chip_type: Optional[str] = None) -> List[Dict]:
        items = []
        allowed = set(self.recommend_test_items(chip_type)) if chip_type else None
        for item_name, entry in sorted(self.catalog["available_items"].items()):
            if allowed is not None and item_name not in allowed:
                continue
            items.append({
                "id": item_name,
                "name": item_name,
                "desc": entry["description"],
                "apis": entry["apis"],
                "scenarios": entry["scenarios"],
            })
        return items

    def resolve_scenario(self, chip_type: Optional[str]) -> str:
        value = str(chip_type or "").upper()
        if value in {"DIGITAL", "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            return "digital"
        if value in {"LDO", "ANALOG_GENERAL", "ANALOG", "LDO_ANALOG"}:
            return "analog"
        if value in {"MULTISITE"}:
            return "multisite"
        if value in {"LDO", "ANALOG_GENERAL"}:
            return "analog"
        raw = str(chip_type or "").lower()
        if raw == "digital":
            return "digital"
        if raw == "ldo":
            return "analog"
        return "custom"

    def recommend_test_items(self, chip_type: Optional[str], param_names: Optional[List[str]] = None) -> List[str]:
        scenario = self.resolve_scenario(chip_type)
        if param_names:
            names = {str(name or "").upper() for name in param_names}
            recommended: List[str] = []
            if scenario == "digital":
                mapping = {
                    "CONNECT": "CON",
                    "FUN": "FUN",
                    "VIH": "VIH",
                    "VIL": "VIL",
                    "VIK": "VIK",
                    "VOH": "VOH",
                    "VOL": "VOL",
                    "IOS": "IOS",
                    "II": "II",
                    "IIH": "IIN",
                    "IIL": "IIN",
                    "ICCH": "ICC",
                    "ICCL": "ICC",
                    "ICC": "ICC",
                }
                for param, item in mapping.items():
                    if param in names and item not in recommended:
                        recommended.append(item)
                if names & {"TPHL", "TPLH", "TR", "TF", "TTLH", "TTHL"}:
                    for item in ["TP1", "TP2", "TP3", "TP4"]:
                        if item not in recommended:
                            recommended.append(item)
                return recommended or self.catalog["scenario_items"]["digital"]
            if scenario == "analog":
                mapping = {
                    "VO": "VO",
                    "SV": "LNR",
                    "SI": "LDR",
                    "IQ": "IGND",
                }
                for param, item in mapping.items():
                    if param in names and item not in recommended:
                        recommended.append(item)
                for item in ["VDO1", "VDO2", "ICL", "TP", "UVLO", "ENT"]:
                    if item not in recommended:
                        recommended.append(item)
                return recommended or self.catalog["scenario_items"]["analog"]
        if scenario in {"digital", "analog", "multisite"}:
            return list(self.catalog["scenario_items"][scenario])
        merged = set(self.catalog["scenario_items"]["digital"]) | set(self.catalog["scenario_items"]["analog"])
        return self._order_items(list(merged), "custom")

    def get_item_knowledge(self, item: str) -> Optional[Dict]:
        return self.catalog["available_items"].get(item)

    def get_sample_code(self, item: str) -> Optional[str]:
        entry = self.get_item_knowledge(item)
        return entry.get("sample_code") if entry else None

    def get_reference_sections(self, test_items: List[str], chip_type: Optional[str]) -> List[Dict[str, str]]:
        sections: List[Dict[str, str]] = []
        for item in test_items:
            entry = self.get_item_knowledge(item)
            if not entry:
                continue
            sections.append({
                "title": f"Enterprise Sample - {item}",
                "content": (
                    f"Description: {entry['description']}\n"
                    f"Scenarios: {', '.join(entry['scenarios'])}\n"
                    f"APIs: {', '.join(entry['apis'])}\n"
                    f"Code:\n{entry['sample_code']}"
                ),
            })
        return sections

    def summary(self) -> Dict:
        return {
            "root": str(self.root),
            "sample_count": len(self.catalog["samples"]),
            "item_count": len(self.catalog["available_items"]),
            "digital_items": self.catalog["scenario_items"]["digital"],
            "analog_items": self.catalog["scenario_items"]["analog"],
            "multisite_items": self.catalog["scenario_items"]["multisite"],
        }


@lru_cache()
def get_enterprise_code_knowledge_service() -> EnterpriseCodeKnowledgeService:
    return EnterpriseCodeKnowledgeService()
