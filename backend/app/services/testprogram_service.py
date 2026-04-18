"""
Module 3 service.
Build test-program skeleton artifacts from module 1 and module 2 outputs.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.models.testprogram import (
    GeneratedFile,
    InputArtifacts,
    TestProgramGenerateRequest,
    TestProgramGenerateResult,
)
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


class TestProgramService:
    """Service for module 3 generation flow."""

    def generate(self, req: TestProgramGenerateRequest) -> TestProgramGenerateResult:
        """Generate test-program skeleton files from extracted artifacts."""
        inputs = self._resolve_inputs(file_id=req.file_id, resource_prefix=req.resource_prefix)
        testplan_data = self._load_json(Path(inputs.testplan_json))

        chip_name = self._safe_chip_name(testplan_data.get("chip_name") or "UnknownChip")
        chip_type = str(testplan_data.get("chip_type") or "UNKNOWN")
        functions = self._extract_functions(testplan_data.get("parameters", []))

        generation_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = settings.PROCESSED_DIR / "generated_programs" / f"{req.file_id}_{timestamp}_{chip_name}"
        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        dll_cpp = source_dir / f"{chip_name}.cpp"
        test_cpp = source_dir / "test.cpp"
        manifest_json = output_dir / "manifest.json"
        plan_json = output_dir / "codegen_plan.json"
        readme_txt = output_dir / "README.txt"

        dll_cpp.write_text(self._build_dll_cpp(chip_name), encoding="utf-8")
        test_cpp.write_text(self._build_test_cpp(functions), encoding="utf-8")
        manifest_json.write_text(
            json.dumps(
                {
                    "generation_id": generation_id,
                    "created_at": timestamp,
                    "chip_name": chip_name,
                    "chip_type": chip_type,
                    "inputs": inputs.model_dump(),
                    "outputs": [
                        str(dll_cpp),
                        str(test_cpp),
                        str(plan_json),
                        str(manifest_json),
                        str(readme_txt),
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        plan_json.write_text(
            json.dumps(
                {
                    "chip_name": chip_name,
                    "chip_type": chip_type,
                    "function_count": len(functions),
                    "functions": functions,
                    "generator_mode": req.generator_mode,
                    "notes": [
                        "This is a skeleton output.",
                        "Refine hardware settings, limits, and vector flow before production use.",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        readme_txt.write_text(self._build_readme(chip_name, chip_type, functions), encoding="utf-8")

        files = [
            GeneratedFile(file_type="dll_entry_cpp", path=str(dll_cpp)),
            GeneratedFile(file_type="test_cpp", path=str(test_cpp)),
            GeneratedFile(file_type="manifest_json", path=str(manifest_json)),
            GeneratedFile(file_type="plan_json", path=str(plan_json)),
            GeneratedFile(file_type="readme_txt", path=str(readme_txt)),
        ]

        logger.success(f"TestProgram skeleton generated: {output_dir}")

        return TestProgramGenerateResult(
            generation_id=generation_id,
            chip_name=chip_name,
            chip_type=chip_type,
            generator_mode=req.generator_mode,
            output_dir=str(output_dir),
            inputs=inputs,
            generated_files=files,
            function_count=len(functions),
            notes=[
                "PGS and VECDIO auto-generation is planned in next iteration.",
                "Current output provides a compile-oriented editable skeleton.",
            ],
        )

    def _resolve_inputs(self, file_id: str, resource_prefix: Optional[str]) -> InputArtifacts:
        """Resolve module 1/2 artifacts from processed directory."""
        processed = settings.PROCESSED_DIR

        testplan_candidates = sorted(processed.glob(f"*{file_id}*TestPlan.json"))
        if not testplan_candidates:
            raise FileNotFoundError(f"Cannot find TestPlan JSON for file_id={file_id}.")
        testplan_json = testplan_candidates[-1]

        resource_map_excel = None
        bom_excel = None
        schematic_svg = None

        if resource_prefix:
            rm = processed / f"{resource_prefix}_ResourceMap.xlsx"
            bom = processed / f"{resource_prefix}_BOM.xlsx"
            svg = processed / f"{resource_prefix}_Schematic.svg"
            resource_map_excel = str(rm) if rm.exists() else None
            bom_excel = str(bom) if bom.exists() else None
            schematic_svg = str(svg) if svg.exists() else None
        else:
            latest_rm = sorted(processed.glob("*_ResourceMap.xlsx"))
            latest_bom = sorted(processed.glob("*_BOM.xlsx"))
            latest_svg = sorted(processed.glob("*_Schematic.svg"))
            resource_map_excel = str(latest_rm[-1]) if latest_rm else None
            bom_excel = str(latest_bom[-1]) if latest_bom else None
            schematic_svg = str(latest_svg[-1]) if latest_svg else None

        return InputArtifacts(
            testplan_json=str(testplan_json),
            resource_map_excel=resource_map_excel,
            bom_excel=bom_excel,
            schematic_svg=schematic_svg,
        )

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _safe_chip_name(name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_\-]", "_", name.strip())
        return cleaned or "UnknownChip"

    @staticmethod
    def _extract_functions(parameters: List[Dict[str, Any]]) -> List[str]:
        funcs: List[str] = []
        for p in parameters:
            raw = str(p.get("param_name", "")).strip()
            if not raw:
                continue
            # Keep function names simple and C identifier friendly.
            fn = re.sub(r"[^0-9A-Za-z_]", "_", raw).upper()
            if fn and fn not in funcs:
                funcs.append(fn)
        return funcs[:120]

    @staticmethod
    def _build_dll_cpp(chip_name: str) -> str:
        return f"""// {chip_name}.cpp : DLL entry and fixed hooks.
//

#include "stdafx.h"

BOOL APIENTRY DllMain(HANDLE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{{
    switch (ul_reason_for_call)
    {{
    case DLL_PROCESS_ATTACH:
    case DLL_THREAD_ATTACH:
        break;
    case DLL_THREAD_DETACH:
    case DLL_PROCESS_DETACH:
        break;
    }}
    return TRUE;
}}

// Keep these signatures stable for PGS loading.
DUT_API void UserLoad() {{}}
DUT_API void UserInitAfterLoad() {{}}
DUT_API void UserExit() {{}}
DUT_API void OnSot() {{}}
DUT_API void BinOutDut() {{}}
DUT_API void OnNewLot(const char *Lotid) {{}}
DUT_API void OnWaferEnd(const char *Lotid) {{}}
"""

    @staticmethod
    def _build_test_cpp(functions: List[str]) -> str:
        header = """#include "stdafx.h"
#include "UserClass.h"

// Module 3 generated skeleton.
// Refine hardware mapping, limits, vector labels, and measurement flow.

DUT_API void HardWareCfg()
{
    STSSetHardwareCheck(FALSE);
}

DUT_API void InitBeforeTestFlow()
{
}

DUT_API void InitAfterTestFlow()
{
}

DUT_API void SetupFailSite(const unsigned char*byFailSite)
{
}

"""
        body_parts: List[str] = []
        if not functions:
            body_parts.append(
                """DUT_API int PLACEHOLDER(short funcindex, LPCTSTR funclabel)
{
    CParam *param = StsGetParam(funcindex, "PLACEHOLDER");
    param->SetTestResult(0, 0, 0);
    return 0;
}
"""
            )
        else:
            for fn in functions:
                body_parts.append(
                    f"""DUT_API int {fn}(short funcindex, LPCTSTR funclabel)
{{
    CParam *param = StsGetParam(funcindex, "{fn}");
    // TODO: Replace this with generated instrument flow.
    param->SetTestResult(0, 0, 0);
    return 0;
}}
"""
                )
        return header + "\n".join(body_parts)

    @staticmethod
    def _build_readme(chip_name: str, chip_type: str, functions: List[str]) -> str:
        fn_preview = ", ".join(functions[:20]) if functions else "PLACEHOLDER"
        return (
            f"Module 3 Generated Skeleton\n"
            f"Chip: {chip_name}\n"
            f"Chip Type: {chip_type}\n"
            f"Function Count: {len(functions)}\n"
            f"Function Preview: {fn_preview}\n\n"
            f"Next Steps:\n"
            f"1. Map module 2 resources into instrument setup calls.\n"
            f"2. Fill per-function measurement and limit logic.\n"
            f"3. Align function names with PGS entries.\n"
        )
