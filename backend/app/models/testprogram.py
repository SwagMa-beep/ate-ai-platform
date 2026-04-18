"""
Module 3 data models.
Generate STS8200S test program skeleton from module 1/2 artifacts.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class TestProgramGenerateRequest(BaseModel):
    """Request model for test-program generation."""

    file_id: str = Field(..., description="File id produced by module 1 upload/extract flow.")
    resource_prefix: Optional[str] = Field(
        default=None,
        description="Optional prefix for module 2 output files."
    )
    generator_mode: Literal["skeleton"] = Field(
        default="skeleton",
        description="Current generation mode."
    )


class InputArtifacts(BaseModel):
    """Resolved input artifact paths."""

    testplan_json: str = ""
    resource_map_excel: Optional[str] = None
    bom_excel: Optional[str] = None
    schematic_svg: Optional[str] = None


class GeneratedFile(BaseModel):
    """Generated output file descriptor."""

    file_type: str
    path: str


class TestProgramGenerateResult(BaseModel):
    """Result model for test-program generation."""

    generation_id: str
    chip_name: str
    chip_type: str
    generator_mode: str
    output_dir: str
    inputs: InputArtifacts
    generated_files: List[GeneratedFile] = Field(default_factory=list)
    function_count: int = 0
    notes: List[str] = Field(default_factory=list)
