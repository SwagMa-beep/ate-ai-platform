"""
Module 3 engineering package service.
Build editable STS8200S project artifacts from module 1/2 outputs and generated code.
"""
from __future__ import annotations

import json
import re
import shutil
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
from app.services.engineering_validation_service import EngineeringValidationService
from app.services.pgs_generation_service import PGSGenerationService
from app.services.project_template_service import ProjectTemplateService
from app.services.vector_generation_service import VectorGenerationService
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


class TestProgramService:
    """Service for module 3 engineering package generation."""

    def __init__(self) -> None:
        self.vector_service = VectorGenerationService()
        self.pgs_service = PGSGenerationService()
        self.project_template_service = ProjectTemplateService()
        self.engineering_validation_service = EngineeringValidationService()

    def generate(self, req: TestProgramGenerateRequest) -> TestProgramGenerateResult:
        """Generate a baseline engineering package from extracted artifacts only."""
        inputs = self._resolve_inputs(file_id=req.file_id, resource_prefix=req.resource_prefix)
        testplan_data = self._load_json(Path(inputs.testplan_json))

        chip_name = self._safe_chip_name(testplan_data.get("chip_name") or "UnknownChip")
        chip_type = str(testplan_data.get("chip_type") or "UNKNOWN")
        functions = self._extract_functions(testplan_data.get("parameters", []))
        test_cpp = self._build_test_cpp(functions)
        package = self.export_package(
            file_id=req.file_id,
            chip_name=chip_name,
            chip_type=chip_type,
            test_items=functions,
            code=test_cpp,
            user_prompt="",
            inputs=inputs,
            generator_mode=req.generator_mode,
            source="testprogram",
            extra_notes=[
                "PGS and VECDIO auto-generation is planned in next iteration.",
                "Current output provides a compile-oriented editable skeleton.",
            ],
        )
        return package

    def export_package(
        self,
        *,
        file_id: str,
        chip_name: str,
        chip_type: str,
        test_items: List[str],
        code: str,
        user_prompt: str,
        inputs: Optional[InputArtifacts] = None,
        generator_mode: str = "engineering_package",
        source: str = "codegen",
        extra_notes: Optional[List[str]] = None,
    ) -> TestProgramGenerateResult:
        """Write a generated engineering package to processed storage."""
        resolved_inputs = inputs or self._resolve_inputs(file_id=file_id, resource_prefix=None)
        generation_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_chip_name = self._safe_chip_name(chip_name or "UnknownChip")
        output_dir = settings.PROCESSED_DIR / "generated_programs" / f"{file_id}_{timestamp}_{safe_chip_name}"
        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        testplan_data = self._load_json(Path(resolved_inputs.testplan_json))

        dll_cpp = source_dir / f"{safe_chip_name}.cpp"
        test_cpp = source_dir / "test.cpp"
        manifest_json = output_dir / "manifest.json"
        plan_json = output_dir / "codegen_plan.json"
        readme_txt = output_dir / "README.txt"

        dll_cpp.write_text(self._build_dll_cpp(safe_chip_name), encoding="utf-8")
        test_cpp.write_text(code, encoding="utf-8")

        generated_files = [
            self._build_generated_file(output_dir, dll_cpp, "dll_entry_cpp"),
            self._build_generated_file(output_dir, test_cpp, "test_cpp"),
        ]

        plan_payload = {
            "chip_name": chip_name,
            "chip_type": chip_type,
            "function_count": len(test_items),
            "functions": test_items,
            "generator_mode": generator_mode,
            "source": source,
            "notes": [
                "Editable engineering package generated from module 1/module 3 artifacts.",
                "Review hardware settings, limits, vector labels, and resource mapping before production use.",
            ],
        }
        plan_json.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        readme_txt.write_text(self._build_readme(chip_name, chip_type, test_items), encoding="utf-8")

        generated_files.extend([
            self._build_generated_file(output_dir, manifest_json, "manifest_json"),
            self._build_generated_file(output_dir, plan_json, "plan_json"),
            self._build_generated_file(output_dir, readme_txt, "readme_txt"),
        ])
        for file_info in self.project_template_service.build_for_package(
            output_dir=output_dir,
            source_dir=source_dir,
            chip_name=safe_chip_name,
            chip_type=chip_type,
        ):
            generated_files.append(GeneratedFile(**file_info))
        for file_info in self.vector_service.build_for_package(
            output_dir=output_dir,
            chip_name=safe_chip_name,
            chip_type=chip_type,
            test_items=test_items,
            testplan_data=testplan_data,
        ):
            generated_files.append(GeneratedFile(**file_info))
        for file_info in self.pgs_service.build_for_package(
            output_dir=output_dir,
            chip_name=safe_chip_name,
            chip_type=chip_type,
            test_items=test_items,
            resource_map_excel=resolved_inputs.resource_map_excel,
        ):
            generated_files.append(GeneratedFile(**file_info))

        manifest_payload = {
            "generation_id": generation_id,
            "created_at": timestamp,
            "source": source,
            "generator_mode": generator_mode,
            "chip_name": chip_name,
            "chip_type": chip_type,
            "test_items": test_items,
            "user_prompt": user_prompt,
            "inputs": resolved_inputs.model_dump(),
            "outputs": [item.relative_path for item in generated_files],
        }
        manifest_json.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        package_validation = self.engineering_validation_service.validate_package(
            output_dir=output_dir,
            generated_files=generated_files,
            chip_name=safe_chip_name,
        )
        package_zip = self._build_package_archive(output_dir)

        notes = [
            "Engineering package exported under data/processed/generated_programs.",
            "Current package includes editable source files and generation metadata.",
            "PGS/TestUI starter files are included when enterprise templates or resource-map outputs are available.",
            "Visual Studio/STS project scaffold is generated from enterprise project templates when available.",
        ]
        if extra_notes:
            notes.extend(extra_notes)

        logger.success(f"Engineering package generated: {output_dir}")
        return TestProgramGenerateResult(
            generation_id=generation_id,
            chip_name=chip_name,
            chip_type=chip_type,
            generator_mode=generator_mode,
            output_dir=str(output_dir),
            package_zip=str(package_zip),
            download_url=f"/api/v1/testprogram/package/{generation_id}/download",
            inputs=resolved_inputs,
            generated_files=generated_files,
            function_count=len(test_items),
            test_items=test_items,
            package_validation=package_validation,
            notes=notes,
        )

    @staticmethod
    def _build_package_archive(output_dir: Path) -> Path:
        archive_base = output_dir.parent / output_dir.name
        archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=output_dir.parent, base_dir=output_dir.name))
        return archive_path

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
    def _build_generated_file(root: Path, path: Path, file_type: str) -> GeneratedFile:
        return GeneratedFile(
            file_type=file_type,
            path=str(path),
            relative_path=path.relative_to(root).as_posix(),
        )

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _safe_chip_name(name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_\-]", "_", name.strip())
        return cleaned or "UnknownChip"

    @staticmethod
    def _extract_functions(parameters: List[Dict[str, Any]]) -> List[str]:
        funcs: List[str] = []
        for parameter in parameters:
            raw = str(parameter.get("param_name", "")).strip()
            if not raw:
                continue
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
            "Module 3 Engineering Package\n"
            f"Chip: {chip_name}\n"
            f"Chip Type: {chip_type}\n"
            f"Function Count: {len(functions)}\n"
            f"Function Preview: {fn_preview}\n\n"
            "Package Contents:\n"
            "1. source/test.cpp - editable generated test program\n"
            "2. source/<chip>.cpp - DLL entry and fixed STS hooks\n"
            "3. manifest.json - generation metadata\n"
            "4. codegen_plan.json - function plan and notes\n"
            "5. README.txt - package guidance\n\n"
            "Next Steps:\n"
            "1. Align function names with PGS entries.\n"
            "2. Add vector files and time sets.\n"
            "3. Refine hardware mapping, limits, and measurement flow.\n"
        )
