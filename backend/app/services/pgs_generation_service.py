"""
PGS generation service.
Attach editable PGS starter artifacts to module 3 engineering packages.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.config import BASE_DIR
from app.utils.logger import setup_logger

logger = setup_logger()

FALLBACK_PGS_BY_SCENARIO = {
    "digital": "HD74LS00P.pgs",
    "analog": "Template.pgs",
}


class PGSGenerationService:
    """Generate editable PGS starter artifacts."""

    def __init__(self) -> None:
        self.template_root = BASE_DIR / "浼佷笟娴嬭瘯浠ｇ爜"

    def build_for_package(
        self,
        *,
        output_dir: Path,
        chip_name: str,
        chip_type: str,
        test_items: list[str],
        resource_map_excel: Optional[str],
    ) -> list[dict[str, str]]:
        template_source = self._find_template(chip_name, chip_type)
        pgs_name = f"{chip_name}.pgs"
        plan_path = output_dir / "pgs_plan.json"
        readme_path = output_dir / "PGS_README.txt"
        autoload_path = output_dir / "autoload_testui_args.txt"

        generated_files: list[dict[str, str]] = []
        if template_source:
            pgs_path = output_dir / pgs_name
            shutil.copyfile(template_source, pgs_path)
            generated_files.append(self._file_descriptor(output_dir, pgs_path, "pgs_template"))
            logger.info(f"PGS template copied from {template_source}")

        pgs_config_rows, pgs_detail_rows = self._load_resource_map_sheets(resource_map_excel)
        function_summary = self._build_function_summary(test_items, pgs_config_rows, pgs_detail_rows)
        hook_suggestions = self._build_hook_suggestions(test_items, function_summary)

        plan_payload = {
            "chip_name": chip_name,
            "chip_type": chip_type,
            "pgs_file": pgs_name,
            "template_source": str(template_source) if template_source else None,
            "resource_map_excel": resource_map_excel,
            "test_items": [item.upper() for item in test_items],
            "function_summary": function_summary,
            "hook_suggestions": hook_suggestions,
            "pgs_configs": pgs_config_rows,
            "pgs_detail_conditions": pgs_detail_rows,
            "autoload": {
                "command": r"C:\STS8200S\testui.exe",
                "arguments": f"-AutoLoad <PROJECT_DIR>\\{pgs_name}",
                "notes": [
                    "Replace <PROJECT_DIR> with the final engineering package folder.",
                    "Ensure the .pgs file and generated DLL are in the same package before AutoLoad.",
                ],
            },
            "notes": [
                "This is an editable PGS starter package.",
                "Confirm VECTOR_FILE, groups, labels, PMU ranges, and function names before loading.",
            ],
        }
        plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        generated_files.append(self._file_descriptor(output_dir, plan_path, "pgs_plan_json"))

        readme_path.write_text(
            self._build_readme(chip_name, pgs_name, template_source, resource_map_excel, function_summary),
            encoding="utf-8",
        )
        generated_files.append(self._file_descriptor(output_dir, readme_path, "pgs_readme_txt"))

        autoload_path.write_text(self._build_autoload_hint(chip_name, pgs_name), encoding="utf-8")
        generated_files.append(self._file_descriptor(output_dir, autoload_path, "testui_autoload_hint"))
        return generated_files

    def _find_template(self, chip_name: str, chip_type: str) -> Optional[Path]:
        if not self.template_root.exists():
            return None

        exact_matches = list(self.template_root.rglob(f"{chip_name}.pgs")) + list(self.template_root.rglob(f"{chip_name}.PGS"))
        if exact_matches:
            return exact_matches[0]

        scenario = self._resolve_scenario(chip_type)
        fallback_name = FALLBACK_PGS_BY_SCENARIO.get(scenario)
        if not fallback_name:
            return None
        fallback_matches = list(self.template_root.rglob(fallback_name)) + list(self.template_root.rglob(fallback_name.upper()))
        return fallback_matches[0] if fallback_matches else None

    @staticmethod
    def _resolve_scenario(chip_type: str) -> str:
        normalized = str(chip_type).upper()
        if "DIGITAL" in normalized or normalized in {"MEMORY", "DIGITAL_74"}:
            return "digital"
        if normalized in {"LDO", "ANALOG_GENERAL"} or "ANALOG" in normalized:
            return "analog"
        return "custom"

    def _load_resource_map_sheets(self, resource_map_excel: Optional[str]) -> tuple[list[dict], list[dict]]:
        if not resource_map_excel:
            return [], []
        excel_path = Path(resource_map_excel)
        if not excel_path.exists():
            return [], []

        try:
            workbook = pd.ExcelFile(excel_path)
            config_sheet = self._find_sheet_name(workbook.sheet_names, include_keywords=["pgs"], exclude_keywords=["detail", "condition"])
            detail_sheet = self._find_sheet_name(workbook.sheet_names, include_keywords=["pgs"], exclude_keywords=[])
            if detail_sheet == config_sheet:
                detail_sheet = self._find_sheet_name(
                    workbook.sheet_names,
                    include_keywords=["detail", "condition", "条件", "详", "細"],
                    exclude_keywords=[],
                )

            configs = pd.read_excel(excel_path, sheet_name=config_sheet).fillna("") if config_sheet else pd.DataFrame()
            details = pd.read_excel(excel_path, sheet_name=detail_sheet).fillna("") if detail_sheet else pd.DataFrame()
            return configs.to_dict(orient="records"), details.to_dict(orient="records")
        except Exception as exc:
            logger.warning(f"Failed to parse PGS sheets from resource map excel: {exc}")
            return [], []

    @staticmethod
    def _find_sheet_name(sheet_names: list[str], include_keywords: list[str], exclude_keywords: list[str]) -> Optional[str]:
        normalized_names = [(name, name.lower()) for name in sheet_names]
        for original, lowered in normalized_names:
            if include_keywords and not any(keyword.lower() in lowered for keyword in include_keywords):
                continue
            if any(keyword.lower() in lowered for keyword in exclude_keywords):
                continue
            return original
        return None

    @staticmethod
    def _build_function_summary(test_items: list[str], pgs_configs: list[dict], pgs_details: list[dict]) -> list[dict]:
        details_by_test: dict[str, list[dict]] = {}
        for detail in pgs_details:
            test_name = str(detail.get("test_name", "")).strip()
            if not test_name:
                continue
            details_by_test.setdefault(test_name, []).append(detail)

        if pgs_configs:
            summary = []
            for config in pgs_configs:
                test_name = str(config.get("test_name", "")).strip() or "UNNAMED"
                summary.append(
                    {
                        "test_name": test_name,
                        "function_type": config.get("function_type", ""),
                        "vector_file": config.get("vector_file", ""),
                        "start_label": config.get("start_label", ""),
                        "stop_label": config.get("stop_label", ""),
                        "groups": {
                            "all": config.get("all_group", ""),
                            "input": config.get("in_group", ""),
                            "output": config.get("out_group", ""),
                            "select": config.get("select_group", ""),
                        },
                        "limits": {
                            "min": config.get("limit_min", ""),
                            "max": config.get("limit_max", ""),
                            "unit": config.get("limit_unit", ""),
                        },
                        "detail_count": len(details_by_test.get(test_name, [])),
                    }
                )
            return summary

        return [
            {
                "test_name": item.upper(),
                "function_type": "FUNCTION" if item.upper() in {"CON", "FUN", "TPLH", "TPHL", "TR", "TF"} else "FIMV_PMU",
                "vector_file": "",
                "start_label": "",
                "stop_label": "",
                "groups": {"all": "", "input": "", "output": "", "select": ""},
                "limits": {"min": "", "max": "", "unit": ""},
                "detail_count": 0,
            }
            for item in test_items
        ]

    @staticmethod
    def _build_hook_suggestions(test_items: list[str], function_summary: list[dict]) -> list[dict]:
        hooks = [
            {"hook": "UserLoad", "purpose": "Initialize global variables and vector resources."},
            {"hook": "UserInitAfterLoad", "purpose": "Bind generated PGS functions after package load."},
            {"hook": "OnSot", "purpose": "Prepare site state before start-of-test."},
        ]
        if any(item.upper() in {"FUN", "TPLH", "TPHL", "TR", "TF"} for item in test_items):
            hooks.append({"hook": "InitBeforeTestFlow", "purpose": "Load vector labels and AC timing sets before functional flow."})
        if any(item.get("function_type") == "FIMV_PMU" for item in function_summary):
            hooks.append({"hook": "HardWareCfg", "purpose": "Review PMU ranges and disconnect/open states before measurement tests."})
        return hooks

    @staticmethod
    def _build_readme(
        chip_name: str,
        pgs_name: str,
        template_source: Optional[Path],
        resource_map_excel: Optional[str],
        function_summary: list[dict],
    ) -> str:
        functions = ", ".join(item["test_name"] for item in function_summary[:12]) or "No extracted PGS functions"
        return (
            "PGS Starter Guidance\n"
            f"Chip: {chip_name}\n"
            f"PGS File: {pgs_name}\n"
            f"Template Source: {template_source if template_source else 'No exact template found'}\n"
            f"Resource Map Excel: {resource_map_excel or 'Not provided'}\n"
            f"Functions: {functions}\n\n"
            "Recommended Steps:\n"
            "1. Open the copied .pgs file in the STS editor.\n"
            "2. Cross-check VECTOR_FILE and label settings against vector_plan.json.\n"
            "3. Use pgs_plan.json to fill or revise PGS fields from the generated resource-map workbook.\n"
            "4. Before TestUI autoload, verify the generated source functions match the PGS function names.\n"
        )

    @staticmethod
    def _build_autoload_hint(chip_name: str, pgs_name: str) -> str:
        return (
            "Suggested TestUI Debugging Arguments\n"
            r"Command: C:\STS8200S\testui.exe"
            "\n"
            f"Command Arguments: -AutoLoad <PROJECT_DIR>\\{pgs_name}\n"
            f"Expected DLL Entry: <PROJECT_DIR>\\source\\{chip_name}.cpp generated hooks\n\n"
            f"Replace <PROJECT_DIR> with the final engineering package path for {chip_name}.\n"
        )

    @staticmethod
    def _file_descriptor(root: Path, path: Path, file_type: str) -> dict[str, str]:
        return {
            "file_type": file_type,
            "path": str(path),
            "relative_path": path.relative_to(root).as_posix(),
        }
