"""
Engineering package validation service.
Checks whether generated STS8200S project artifacts form a coherent VS project
and optionally tries a local MSBuild/devenv validation when available.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional


class EngineeringValidationService:
    """Validate generated engineering packages."""

    def __init__(self) -> None:
        self.msbuild = shutil.which("msbuild")
        self.devenv = shutil.which("devenv")

    def validate_package(self, *, output_dir: Path, generated_files: Iterable, chip_name: str) -> dict:
        relative_paths = {getattr(item, "relative_path", "") for item in generated_files}
        source_dir = output_dir / "source"
        checks: list[dict] = []

        def record(name: str, condition: bool, detail: str) -> None:
            checks.append({"name": name, "passed": condition, "detail": detail})

        solution_name = f"source/{chip_name}.sln"
        project_name = f"source/{chip_name}.vcxproj"
        test_cpp = "source/test.cpp"
        dll_cpp = f"source/{chip_name}.cpp"
        stdafx_h = "source/StdAfx.h"

        record("test_cpp", test_cpp in relative_paths, "Generated test entry source is present.")
        record("dll_entry", dll_cpp in relative_paths, "DLL entry source is present.")
        record("solution", solution_name in relative_paths, "Visual Studio solution file is present.")
        record("vcxproj", project_name in relative_paths, "Visual Studio project file is present.")
        record("stdafx", stdafx_h in relative_paths, "Precompiled-header scaffold is present.")
        record("vector_plan", "vector_plan.json" in relative_paths, "Vector planning artifact is present.")
        record("pgs_plan", "pgs_plan.json" in relative_paths, "PGS planning artifact is present.")

        diagnostics: list[str] = []
        sln_path = source_dir / f"{chip_name}.sln"
        vcxproj_path = source_dir / f"{chip_name}.vcxproj"
        test_cpp_path = source_dir / "test.cpp"

        if sln_path.exists() and vcxproj_path.exists():
            sln_text = sln_path.read_text(encoding="utf-8", errors="ignore")
            vcxproj_text = vcxproj_path.read_text(encoding="utf-8", errors="ignore")
            record(
                "solution_links_project",
                f"{chip_name}.vcxproj" in sln_text,
                "Solution references the generated vcxproj.",
            )
            record(
                "project_compiles_test_cpp",
                "test.cpp" in vcxproj_text,
                "Project includes test.cpp in ClCompile items.",
            )
            record(
                "project_compiles_chip_cpp",
                f'{chip_name}.cpp' in vcxproj_text,
                "Project includes the chip DLL entry source.",
            )
        else:
            record("solution_links_project", False, "Solution/project pair is incomplete.")
            record("project_compiles_test_cpp", False, "Project file missing.")
            record("project_compiles_chip_cpp", False, "Project file missing.")

        build_validation = self._try_local_build(solution=sln_path, output_dir=output_dir)
        diagnostics.extend(build_validation["diagnostics"])
        passed = all(item["passed"] for item in checks) and (
            not build_validation["attempted"] or build_validation["passed"]
        )

        if not test_cpp_path.exists():
            diagnostics.append("source/test.cpp is missing; Build Solution cannot proceed.")
        if not build_validation["attempted"]:
            diagnostics.append("No local MSBuild/devenv detected; package validation stayed at structure level.")

        return {
            "attempted": True,
            "passed": passed,
            "checks": checks,
            "build_validation": build_validation,
            "diagnostics": diagnostics[:40],
        }

    def _try_local_build(self, *, solution: Path, output_dir: Path) -> dict:
        if not solution.exists():
            return {
                "attempted": False,
                "passed": False,
                "tool": None,
                "command": [],
                "diagnostics": ["Solution file is missing; local build validation skipped."],
            }

        command: Optional[list[str]] = None
        tool = None
        if self.msbuild:
            tool = self.msbuild
            command = [
                self.msbuild,
                str(solution),
                "/nologo",
                "/t:Build",
                "/p:Configuration=Debug;Platform=Win32",
            ]
        elif self.devenv:
            tool = self.devenv
            command = [self.devenv, str(solution), "/Build", "Debug|Win32"]

        if not command:
            return {
                "attempted": False,
                "passed": False,
                "tool": None,
                "command": [],
                "diagnostics": ["Neither msbuild nor devenv is available in PATH."],
            }

        result = subprocess.run(
            command,
            cwd=output_dir / "source",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        diagnostics = []
        if result.stdout.strip():
            diagnostics.extend(line for line in result.stdout.splitlines() if line.strip())
        if result.stderr.strip():
            diagnostics.extend(line for line in result.stderr.splitlines() if line.strip())
        return {
            "attempted": True,
            "passed": result.returncode == 0,
            "tool": tool,
            "command": command,
            "diagnostics": diagnostics[:40],
        }
