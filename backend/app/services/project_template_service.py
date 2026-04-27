"""
Project template scaffolding service.
Copies and adapts enterprise Visual Studio/ST S8200S project files into the generated package.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import BASE_DIR


class ProjectTemplateService:
    """Build a VS project scaffold from enterprise sample projects."""

    def __init__(self) -> None:
        root = BASE_DIR / "企业测试代码"
        self.template_roots: Dict[str, Path] = {
            "digital": root / "数字芯片例程" / "HD74LS00P" / "HD74LS00P" / "source",
            "ldo": root / "模拟芯片例程" / "ADP7118A" / "ADP7118A" / "source",
            "analog": root / "模拟芯片例程" / "ADP7118A" / "ADP7118A" / "source",
            "custom": root / "TestProject Rev3.00" / "TestProject Rev3.00" / "source",
        }

    def build_for_package(self, *, output_dir: Path, source_dir: Path, chip_name: str, chip_type: str) -> List[dict]:
        template_dir = self._resolve_template_dir(chip_type)
        if not template_dir or not template_dir.exists():
            return []

        template_name = self._detect_project_name(template_dir)
        project_guid = "{" + str(uuid.uuid4()).upper() + "}"
        generated: List[dict] = []

        support_files = [
            "StdAfx.cpp",
            "StdAfx.h",
            "UserClass.cpp",
            "UserClass.h",
            "ReadMe.txt",
        ]
        for filename in support_files:
            source_path = template_dir / filename
            if not source_path.exists():
                continue
            target_path = source_dir / filename
            target_path.write_text(source_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            generated.append(self._file_info(output_dir, target_path, self._support_file_type(filename)))

        templated_files = [
            (f"{template_name}.sln", f"{chip_name}.sln"),
            (f"{template_name}.vcxproj", f"{chip_name}.vcxproj"),
            (f"{template_name}.vcxproj.filters", f"{chip_name}.vcxproj.filters"),
            (f"{template_name}.vcxproj.user", f"{chip_name}.vcxproj.user"),
        ]
        for source_name, target_name in templated_files:
            source_path = template_dir / source_name
            if not source_path.exists():
                continue
            content = source_path.read_text(encoding="utf-8", errors="ignore")
            content = self._rewrite_content(
                content=content,
                template_name=template_name,
                chip_name=chip_name,
                project_guid=project_guid,
            )
            target_path = source_dir / target_name
            target_path.write_text(content, encoding="utf-8")
            generated.append(self._file_info(output_dir, target_path, self._project_file_type(target_name)))

        plan_path = output_dir / "project_template_plan.json"
        plan_path.write_text(
            (
                "{\n"
                f'  "chip_name": "{chip_name}",\n'
                f'  "chip_type": "{chip_type}",\n'
                f'  "template_source": "{template_dir.as_posix()}",\n'
                f'  "project_name": "{chip_name}",\n'
                f'  "project_guid": "{project_guid}"\n'
                "}\n"
            ),
            encoding="utf-8",
        )
        generated.append(self._file_info(output_dir, plan_path, "project_template_plan_json"))
        return generated

    def _resolve_template_dir(self, chip_type: str) -> Optional[Path]:
        normalized = str(chip_type or "").upper()
        if "DIGITAL" in normalized or normalized == "MEMORY":
            return self.template_roots["digital"]
        if "LDO" in normalized or "ANALOG" in normalized:
            return self.template_roots["ldo"]
        return self.template_roots["custom"]

    @staticmethod
    def _detect_project_name(template_dir: Path) -> str:
        vcxproj = next(template_dir.glob("*.vcxproj"), None)
        if vcxproj:
            return vcxproj.stem
        sln = next(template_dir.glob("*.sln"), None)
        if sln:
            return sln.stem
        return "TestProject"

    @staticmethod
    def _rewrite_content(*, content: str, template_name: str, chip_name: str, project_guid: str) -> str:
        updated = content.replace(template_name, chip_name)
        updated = re.sub(r"\{[0-9A-Fa-f\-]{36}\}", project_guid, updated)
        return updated

    @staticmethod
    def _support_file_type(filename: str) -> str:
        mapping = {
            "StdAfx.cpp": "stdafx_cpp",
            "StdAfx.h": "stdafx_h",
            "UserClass.cpp": "userclass_cpp",
            "UserClass.h": "userclass_h",
            "ReadMe.txt": "vs_readme_txt",
        }
        return mapping.get(filename, "support_file")

    @staticmethod
    def _project_file_type(filename: str) -> str:
        if filename.endswith(".sln"):
            return "vs_solution"
        if filename.endswith(".vcxproj"):
            return "vs_project"
        if filename.endswith(".vcxproj.filters"):
            return "vs_project_filters"
        if filename.endswith(".vcxproj.user"):
            return "vs_project_user"
        return "vs_project_asset"

    @staticmethod
    def _file_info(root: Path, path: Path, file_type: str) -> dict:
        return {
            "file_type": file_type,
            "path": str(path),
            "relative_path": path.relative_to(root).as_posix(),
        }
