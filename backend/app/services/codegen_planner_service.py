"""
Structured planning for module 3 code generation.
Turns chip/test selections into a transparent intermediate plan before code assembly.
"""
from __future__ import annotations

from typing import Optional

from app.services.codegen_service import TEMPLATES
from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service


DIGITAL_ITEMS = {
    "CON", "FUN", "VIH", "VIL", "VOH", "VOL", "IOS", "ICC",
    "VIK", "IIH", "IIL", "IOH", "IOL", "TP1", "TP2", "TP3", "TP4",
    "TPLH", "TPHL", "TR", "TF",
}
LDO_ITEMS = {"LDO_DROPOUT", "LDO_ACCURACY", "LDO_IQ"}
OUTPUT_REQUIRED_ITEMS = {"VOH", "VOL", "IOS", "IOH", "IOL", "TP1", "TP2", "TP3", "TP4", "TPLH", "TPHL", "TR", "TF"}
INPUT_REQUIRED_ITEMS = {"VIH", "VIL", "VIK", "FUN", "IIH", "IIL", "TP1", "TP2", "TP3", "TP4", "TPLH", "TPHL", "TR", "TF"}
POWER_REQUIRED_ITEMS = DIGITAL_ITEMS | LDO_ITEMS
VECTOR_REQUIRED_ITEMS = {
    "CON", "FUN", "VIH", "VIL", "VOH", "VOL", "IOS", "ICC",
    "TP1", "TP2", "TP3", "TP4", "TPLH", "TPHL", "TR", "TF",
}


class CodegenPlannerService:
    """Build a structured generation plan with constraints and template sources."""

    def build_plan(
        self,
        *,
        chip_name: str,
        chip_type: str,
        test_items: list[str],
        pin_names: Optional[list[str]] = None,
        input_pins: Optional[list[str]] = None,
        output_pins: Optional[list[str]] = None,
        vcc: float = 5.0,
        vout: float = 3.3,
        ldo_out_pin: int = 2,
        load_ma: float = 100.0,
    ) -> dict:
        knowledge = get_enterprise_code_knowledge_service()
        scenario = knowledge.resolve_scenario(chip_type)
        recommended_items = knowledge.recommend_test_items(chip_type)
        selected_items = [str(item).upper() for item in (test_items or recommended_items) if str(item).strip()]

        pins = [str(item) for item in (pin_names or []) if str(item).strip()]
        inputs = [str(item) for item in (input_pins or []) if str(item).strip()]
        outputs = [str(item) for item in (output_pins or []) if str(item).strip()]
        power_pins = [pin for pin in pins if pin.upper() in {"VCC", "VDD", "VIN", "VOUT", "AVDD", "DVDD", "VSS", "GND"}]

        plan_items = []
        warnings: list[str] = []
        errors: list[str] = []
        requires_vector = False
        requires_pgs = bool(selected_items)

        for item in selected_items:
            entry = knowledge.get_item_knowledge(item) or {}
            template_source = "built_in" if item in TEMPLATES else "enterprise_sample" if entry.get("sample_code") else "generated_stub"
            apis = entry.get("apis", [])
            vector_required = item in VECTOR_REQUIRED_ITEMS
            output_required = item in OUTPUT_REQUIRED_ITEMS
            input_required = item in INPUT_REQUIRED_ITEMS
            power_required = item in POWER_REQUIRED_ITEMS
            item_errors: list[str] = []
            item_warnings: list[str] = []

            if vector_required:
                requires_vector = True
            if output_required and not outputs:
                item_errors.append(f"{item} 依赖输出引脚，但当前没有识别到 output_pins。")
            if input_required and not inputs:
                item_errors.append(f"{item} 依赖输入引脚，但当前没有识别到 input_pins。")
            if power_required and not power_pins and scenario != "custom":
                item_warnings.append(f"{item} 需要电源相关引脚，当前 pin 信息里没有明显的 power/gnd 标识。")

            if scenario == "analog" and item in DIGITAL_ITEMS:
                item_errors.append(f"{item} 属于数字测试项，不能直接用于当前 analog/LDO 场景。")
            if scenario == "digital" and item in LDO_ITEMS:
                item_errors.append(f"{item} 属于 LDO 测试项，不能直接用于当前 digital 场景。")

            plan_items.append(
                {
                    "item": item,
                    "description": entry.get("description", f"{item} test item"),
                    "apis": apis,
                    "template_source": template_source,
                    "vector_required": vector_required,
                    "pin_requirements": {
                        "needs_input_pins": input_required,
                        "needs_output_pins": output_required,
                    },
                    "blocking_errors": item_errors,
                    "warnings": item_warnings,
                }
            )
            errors.extend(item_errors)
            warnings.extend(item_warnings)

        if scenario == "analog":
            if ldo_out_pin <= 0:
                errors.append("模拟/LDO 场景要求 ldo_out_pin 大于 0。")
            if vout <= 0:
                errors.append("模拟/LDO 场景要求 vout 大于 0。")
            if load_ma <= 0:
                errors.append("模拟/LDO 场景要求 load_ma 大于 0。")
        if scenario == "digital":
            if vcc < 1.0 or vcc > 6.5:
                warnings.append(f"数字芯片当前 VCC={vcc}V 超出常见范围 1.0V~6.5V，请确认是否为特殊器件。")
        else:
            if vcc <= 0:
                errors.append("VCC 必须大于 0。")

        if not pins:
            warnings.append("当前未提供完整 pin_names，生成结果会退化为模板骨架。")
        if not selected_items:
            errors.append("当前没有有效测试项可供生成。")
        if requires_vector and not pins:
            warnings.append("当前测试项依赖 VECDIO，但缺少 pin 信息，后续需要手工补完 vector/label。")
        if scenario == "custom" and not pins:
            warnings.append("custom 模式下没有模块一结果时，推荐可信度和工程可落地性会明显下降。")

        resources = {
            "digital": ["FOVI", "UserDIO", "CBIT128", "QTMU_PLUS"],
            "analog": ["FOVI", "CBIT128", "QTMU_PLUS"],
            "multisite": ["FOVI", "CBIT128", "QTMU_PLUS"],
            "custom": ["FOVI", "UserPMU", "UserDIO"],
        }.get(scenario, ["FOVI", "UserPMU", "UserDIO"])

        return {
            "chip_name": chip_name,
            "chip_type": chip_type,
            "scenario": scenario,
            "selected_items": selected_items,
            "recommended_items": recommended_items,
            "resources": resources,
            "requires_vector": requires_vector,
            "requires_pgs": requires_pgs,
            "electrical": {
                "vcc": vcc,
                "vout": vout,
                "ldo_out_pin": ldo_out_pin,
                "load_ma": load_ma,
            },
            "pins": {
                "pin_count": len(pins),
                "input_count": len(inputs),
                "output_count": len(outputs),
                "power_like_count": len(power_pins),
            },
            "items": plan_items,
            "errors": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)),
        }
