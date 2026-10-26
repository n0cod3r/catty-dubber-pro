from __future__ import annotations

import json
from pathlib import Path

from .models import Project, utc_now

PROJECT_FILE_NAME = "project.json"

class ProjectStore:
    def create(
            self,
            directory: Path,
            name: str
    ) -> Project:
        directory.mkdir(parents=True, exist_ok=True)

        project = Project(name=name)

        self.save(directory, project)

        return project

    def load(
            self,
            directory: Path,
    ) -> Project:
        project_file = directory / PROJECT_FILE_NAME

        if not project_file.exists():
            raise FileNotFoundError(
                f"Project file does not exist: {project_file}"
            )

        data = json.loads(
            project_file.read_text(encoding="utf-8")
        )

        return Project.model_validate(data)

    def save(
        self,
        directory: Path,
        project: Project,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)

        project.updated_at = utc_now()

        project_file = directory / PROJECT_FILE_NAME
        temp_file = directory / f"{PROJECT_FILE_NAME}.tmp"

        payload = project.model_dump_json(
            indent=2,
        )

        temp_file.write_text(
            payload,
            encoding="utf-8",
        )

        temp_file.replace(project_file)