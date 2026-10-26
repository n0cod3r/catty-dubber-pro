from __future__ import annotations

from pathlib import Path
from uuid import UUID

from .models import Episode, Project
from .store import ProjectStore

class ProjectService:
    def __init__(
        self,
        store: ProjectStore | None = None,
    ) -> None:
        self._store = store or ProjectStore()

    def create_project(
            self,
            directory: Path,
            name: str
    ) -> Project :
        return self._store.create(
            directory=directory,
            name=name
        )

    def open_project(
            self,
            directory: Path,
    ) -> Project:
        return self._store.laod(
            directory=directory,
        )

    def save_project(
        self,
        directory: Path,
        project: Project,
    ) -> None:
        self._store.save(
            directory=directory,
            project=project,
        )

    def import_episodes(
        self,
        directory: Path,
        project: Project,
        source_paths: list[str],
    ) -> list[Episode]:
        imported: list[Episode] = []

        existing_paths = {
            Path(episode.media.source_path).resolve()
            for episode in project.episodes
        }

        for source_path in source_paths:
            path = Path(source_path).expanduser().resolve()

            if not path.is_file():
                raise FileNotFoundError(
                    f"Episode does not exist: {path}"
                )

            if not path.is_file():
                raise ValueError(
                    f"Episode source is not a file: {path}"
                )

            if path in existing_paths:
                continue

            episode = project.add_episode(
                source_path=str(path),
            )

            imported.append(episode)
            existing_paths.add(path)

        self._store.save(
            directory=directory,
            project=project,
        )

        return imported

    def remove_episode(
        self,
        directory: Path,
        project: Project,
        episode_id: UUID,
    ) -> bool:
        before = len(project.episodes)

        project.episodes = [
            episode
            for episode in project.episodes
            if episode.id != episode_id
        ]

        if len(project.episodes) == before:
            return False

        for index, episode in enumerate(project.episodes):
            episode.order = index

        self._store.save(
            directory=directory,
            project=project,
        )

        return True