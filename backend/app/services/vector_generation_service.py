"""
Vector generation service.
Build richer editable VECDIO starter artifacts for module 3 engineering packages.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

from app.core.config import BASE_DIR
from app.utils.logger import setup_logger

logger = setup_logger()

VECTOR_REQUIRED_ITEMS = {
    "CON",
    "FUN",
    "VIH",
    "VIL",
    "VOH",
    "VOL",
    "IOS",
    "ICC",
    "IIH",
    "IIL",
    "IOH",
    "IOL",
    "VIK",
    "TP1",
    "TP2",
    "TP3",
    "TP4",
    "TPLH",
    "TPHL",
    "TR",
    "TF",
}

FALLBACK_TEMPLATE_BY_SCENARIO = {
    "digital": "HD74LS00P.vecdio",
}

AC_ITEMS = {"FUN", "TP1", "TP2", "TP3", "TP4", "TPLH", "TPHL", "TR", "TF"}
DC_WINDOW_ITEMS = {"CON", "VIH", "VIL", "VOH", "VOL", "IIH", "IIL", "IOH", "IOL", "VIK", "IOS", "ICC"}


class VectorGenerationService:
    """Generate editable vector starter artifacts."""

    def __init__(self) -> None:
        self.template_root = BASE_DIR / "浼佷笟娴嬭瘯浠ｇ爜"

    def build_for_package(
        self,
        *,
        output_dir: Path,
        chip_name: str,
        chip_type: str,
        test_items: list[str],
        testplan_data: dict[str, Any],
    ) -> list[dict[str, str]]:
        if not self._needs_vector(chip_type, test_items):
            return []

        pin_defs = testplan_data.get("pin_definitions", []) or []
        normalized_items = [str(item).upper() for item in test_items if str(item).strip()]
        vector_name = f"{chip_name}.vecdio"
        plan_path = output_dir / "vector_plan.json"
        readme_path = output_dir / "VECTOR_README.txt"

        template_source = self._find_template(chip_name, chip_type)
        generated_files: list[dict[str, str]] = []

        if template_source:
            vecdio_path = output_dir / vector_name
            shutil.copyfile(template_source, vecdio_path)
            generated_files.append(self._file_descriptor(output_dir, vecdio_path, "vecdio_template"))
            logger.info(f"Vector template copied from {template_source}")

        pin_groups = self._build_pin_groups(pin_defs)
        channel_map = self._build_channel_map(pin_defs)
        site_plan = self._build_site_plan(chip_type, channel_map)
        time_sets = self._build_time_sets(chip_type, normalized_items)
        labels = self._build_labels(normalized_items)
        pattern_sets = self._build_pattern_sets(chip_name, normalized_items, labels)

        plan_payload = {
            "chip_name": chip_name,
            "chip_type": chip_type,
            "vector_file": vector_name,
            "template_source": str(template_source) if template_source else None,
            "test_items": normalized_items,
            "scenario": self._resolve_scenario(chip_type),
            "pins": [
                {
                    "pin_no": pin.get("pin_no"),
                    "pin_name": pin.get("pin_name"),
                    "direction": pin.get("direction"),
                    "function": pin.get("function", ""),
                }
                for pin in pin_defs
            ],
            "pin_groups": pin_groups,
            "channel_map": channel_map,
            "site_plan": site_plan,
            "time_sets": time_sets,
            "labels": labels,
            "pattern_sets": pattern_sets,
            "vector_edit_checklist": [
                "Confirm pin groups and channel assignments before loading in ACVector Editor.",
                "Align label windows with the generated PGS test names and source functions.",
                "Review compare edges and drive edges for AC items such as FUN, tPLH, and tPHL.",
                "For multi-site packages, duplicate or split pattern labels by site before TestUI autoload.",
            ],
            "notes": [
                "This is an editable vector starter plan for ACVector Editor.",
                "Confirm pins, time sets, labels, and channel-site mapping before loading into PGS/TestUI.",
            ],
        }
        plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        generated_files.append(self._file_descriptor(output_dir, plan_path, "vector_plan_json"))

        readme_path.write_text(
            self._build_readme(chip_name, vector_name, template_source, normalized_items, time_sets, site_plan),
            encoding="utf-8",
        )
        generated_files.append(self._file_descriptor(output_dir, readme_path, "vector_readme_txt"))
        return generated_files

    def _needs_vector(self, chip_type: str, test_items: list[str]) -> bool:
        normalized = str(chip_type).upper()
        if "DIGITAL" in normalized or normalized in {"MEMORY", "DIGITAL", "DIGITAL_74"}:
            return True
        return any(item.upper() in VECTOR_REQUIRED_ITEMS for item in test_items)

    def _find_template(self, chip_name: str, chip_type: str) -> Optional[Path]:
        if not self.template_root.exists():
            return None

        exact_matches = list(self.template_root.rglob(f"{chip_name}.vecdio"))
        if exact_matches:
            return exact_matches[0]

        scenario = self._resolve_scenario(chip_type)
        fallback_name = FALLBACK_TEMPLATE_BY_SCENARIO.get(scenario)
        if not fallback_name:
            return None

        fallback_matches = list(self.template_root.rglob(fallback_name))
        return fallback_matches[0] if fallback_matches else None

    @staticmethod
    def _resolve_scenario(chip_type: str) -> str:
        normalized = str(chip_type).upper()
        if "DIGITAL" in normalized or normalized in {"MEMORY", "DIGITAL_74"}:
            return "digital"
        if normalized == "LDO" or "ANALOG" in normalized:
            return "analog"
        return "custom"

    @staticmethod
    def _build_pin_groups(pin_defs: list[dict[str, Any]]) -> dict[str, list[str]]:
        all_pins = [str(pin.get("pin_name")) for pin in pin_defs if str(pin.get("pin_name", "")).strip()]
        groups = {
            "all": all_pins,
            "input": [],
            "output": [],
            "bidir": [],
            "power": [],
            "ground": [],
            "control": [],
        }
        for pin in pin_defs:
            pin_name = str(pin.get("pin_name", "")).strip()
            direction = str(pin.get("direction", "")).upper()
            function = str(pin.get("function", "")).upper()
            if not pin_name:
                continue
            if direction in {"IN", "I"}:
                groups["input"].append(pin_name)
            elif direction in {"OUT", "O"}:
                groups["output"].append(pin_name)
            elif direction in {"BIDIR", "IO"}:
                groups["bidir"].append(pin_name)
            elif direction == "PWR":
                groups["power"].append(pin_name)
            elif direction == "GND":
                groups["ground"].append(pin_name)
            if any(keyword in function for keyword in {"EN", "CTRL", "RESET", "CLK", "SCL", "SDA"}):
                groups["control"].append(pin_name)
        return groups

    @staticmethod
    def _build_channel_map(pin_defs: list[dict[str, Any]]) -> list[dict[str, str]]:
        signal_index = 0
        channel_map: list[dict[str, str]] = []
        for pin in pin_defs:
            pin_name = str(pin.get("pin_name", "")).strip()
            direction = str(pin.get("direction", "")).upper()
            if not pin_name:
                continue
            if direction in {"PWR", "GND", "NC"}:
                continue
            channel = "UNASSIGNED" if signal_index >= 24 else f"D{signal_index}"
            site = "SITE1" if signal_index < 12 else "SITE2"
            if signal_index < 24:
                signal_index += 1
            channel_map.append(
                {
                    "pin_name": pin_name,
                    "pin_no": str(pin.get("pin_no", "")),
                    "direction": direction or "IN",
                    "dio_channel": channel,
                    "site": site,
                    "compare_role": "sense" if direction in {"OUT", "BIDIR"} else "drive",
                }
            )
        return channel_map

    @staticmethod
    def _build_site_plan(chip_type: str, channel_map: list[dict[str, str]]) -> list[dict[str, Any]]:
        normalized = str(chip_type).upper()
        sites: list[dict[str, Any]] = []
        if normalized == "LDO":
            sites.append(
                {
                    "site": "SITE1",
                    "mode": "single_site_default",
                    "channels": [item["dio_channel"] for item in channel_map[:12]],
                    "notes": "Default single-site analog package. Duplicate site definition only when final fixture supports dual-site execution.",
                }
            )
            return sites

        site_names = sorted({item["site"] for item in channel_map}) or ["SITE1"]
        for site in site_names:
            site_channels = [item["dio_channel"] for item in channel_map if item["site"] == site]
            sites.append(
                {
                    "site": site,
                    "mode": "digital_parallel" if normalized.startswith("DIGITAL") or normalized == "MEMORY" else "generic",
                    "channels": site_channels,
                    "notes": "Keep labels and compare windows aligned across sites before enabling parallel run.",
                }
            )
        return sites

    @staticmethod
    def _build_time_sets(chip_type: str, test_items: list[str]) -> list[dict[str, str]]:
        normalized = str(chip_type).upper()
        time_sets = [
            {
                "name": "TS0",
                "purpose": "Default DC/digital setup",
                "period": "100ns",
                "suggested_drive": "10ns",
                "suggested_compare": "40ns",
            }
        ]

        if any(item in AC_ITEMS for item in test_items) or normalized.startswith("DIGITAL") or normalized == "MEMORY":
            time_sets.append(
                {
                    "name": "TS_AC",
                    "purpose": "AC timing / functional pattern window",
                    "period": "40ns",
                    "suggested_drive": "5ns",
                    "suggested_compare": "20ns",
                }
            )
        if any(item in DC_WINDOW_ITEMS for item in test_items):
            time_sets.append(
                {
                    "name": "TS_DC",
                    "purpose": "Static threshold and leakage window",
                    "period": "200ns",
                    "suggested_drive": "20ns",
                    "suggested_compare": "120ns",
                }
            )
        return time_sets

    @staticmethod
    def _build_labels(test_items: list[str]) -> list[dict[str, str]]:
        labels: list[dict[str, str]] = []
        cursor = 0
        for item in test_items:
            span = 4 if item in AC_ITEMS else 2
            labels.append(
                {
                    "test_item": item,
                    "start_label": f"L{cursor:03d}_{item}",
                    "stop_label": f"L{cursor + span:03d}_{item}_END",
                    "window_type": "pattern" if item in AC_ITEMS else "static",
                }
            )
            cursor += span + 1
        return labels

    @staticmethod
    def _build_pattern_sets(chip_name: str, test_items: list[str], labels: list[dict[str, str]]) -> list[dict[str, Any]]:
        label_by_item = {item["test_item"]: item for item in labels}
        pattern_sets: list[dict[str, Any]] = []
        for item in test_items:
            if item not in AC_ITEMS and item != "CON":
                continue
            label_info = label_by_item[item]
            pattern_sets.append(
                {
                    "name": f"{chip_name}_{item}",
                    "test_item": item,
                    "recommended_vector_rows": 16 if item in {"FUN", "TP1", "TP2", "TP3", "TP4"} else 8,
                    "start_label": label_info["start_label"],
                    "stop_label": label_info["stop_label"],
                }
            )
        return pattern_sets

    @staticmethod
    def _build_readme(
        chip_name: str,
        vector_name: str,
        template_source: Optional[Path],
        test_items: list[str],
        time_sets: list[dict[str, str]],
        site_plan: list[dict[str, Any]],
    ) -> str:
        template_line = str(template_source) if template_source else "No exact enterprise template found"
        time_set_names = ", ".join(item["name"] for item in time_sets)
        site_names = ", ".join(site["site"] for site in site_plan)
        return (
            "VECDIO Starter Guidance\n"
            f"Chip: {chip_name}\n"
            f"Vector File: {vector_name}\n"
            f"Template Source: {template_line}\n"
            f"Suggested Tests: {', '.join(test_items)}\n"
            f"Suggested Time Sets: {time_set_names}\n"
            f"Site Plan: {site_names}\n\n"
            "Recommended Steps:\n"
            "1. Open the copied .vecdio file with ACVector Editor.\n"
            "2. Update pin names, pin groups, and channel-site mapping based on vector_plan.json.\n"
            "3. Review suggested labels and time sets before linking the vector file to PGS.\n"
            "4. Keep the final .vecdio file in the same project directory as the generated source files.\n"
        )

    @staticmethod
    def _file_descriptor(root: Path, path: Path, file_type: str) -> dict[str, str]:
        return {
            "file_type": file_type,
            "path": str(path),
            "relative_path": path.relative_to(root).as_posix(),
        }
