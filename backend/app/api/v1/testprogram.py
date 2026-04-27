"""
TestProgram API endpoints - module 3.
Generate test-program skeleton from module 1 and module 2 artifacts.
"""
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.response import error, success
from app.models.testprogram import TestProgramGenerateRequest
from app.services.testprogram_service import TestProgramService
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger()
service = TestProgramService()
settings = get_settings()


def _find_package_archive(generation_id: str) -> tuple[Path | None, str | None]:
    root = settings.PROCESSED_DIR / "generated_programs"
    if not root.exists():
        return None, None
    for manifest_path in sorted(root.glob("*/manifest.json"), reverse=True):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("generation_id") != generation_id:
            continue
        output_dir = manifest_path.parent
        archive_path = output_dir.parent / f"{output_dir.name}.zip"
        if archive_path.exists():
            return archive_path, output_dir.name
        return None, output_dir.name
    return None, None


@router.post("/generate", summary="Generate module 3 test-program skeleton")
async def generate_testprogram(req: TestProgramGenerateRequest):
    try:
        result = service.generate(req)
        return success(
            data=result.model_dump(),
            message="TestProgram skeleton generated successfully",
        )
    except FileNotFoundError as e:
        logger.warning(str(e))
        return error(message=str(e), code=404)
    except Exception as e:
        logger.error(f"TestProgram generation failed: {e}")
        return error(message=f"Generation failed: {e}", code=500)


@router.get("/requirements", summary="Get module 3 baseline requirements")
async def get_requirements():
    return success(
        data={
            "versions": {
                "sts_software": "STS8200S VerP1.1 Build 20251201",
                "pgs_editor": "3.0",
            },
            "required_inputs": ["*{file_id}*TestPlan.json"],
            "optional_inputs": [
                "*_ResourceMap.xlsx",
                "*_BOM.xlsx",
                "*_Schematic.svg",
            ],
            "output_files": [
                "source/{chip}.cpp",
                "source/test.cpp",
                "source/{chip}.sln",
                "source/{chip}.vcxproj",
                "manifest.json",
                "codegen_plan.json",
                "README.txt",
                "{package}.zip",
            ],
        },
        message="Module 3 requirements loaded",
    )


@router.get("/package/{generation_id}/download", summary="Download generated engineering package zip")
async def download_package(generation_id: str):
    archive_path, package_name = _find_package_archive(generation_id)
    if not archive_path or not archive_path.exists():
        return error(message=f"Package archive not found for generation_id={generation_id}", code=404)
    return FileResponse(
        path=str(archive_path),
        filename=f"{package_name or generation_id}.zip",
        media_type="application/zip",
    )
