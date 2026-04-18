"""
TestProgram API endpoints - module 3.
Generate test-program skeleton from module 1 and module 2 artifacts.
"""
from fastapi import APIRouter

from app.core.response import error, success
from app.models.testprogram import TestProgramGenerateRequest
from app.services.testprogram_service import TestProgramService
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger()
service = TestProgramService()


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
                "manifest.json",
                "codegen_plan.json",
                "README.txt",
            ],
        },
        message="Module 3 requirements loaded",
    )
