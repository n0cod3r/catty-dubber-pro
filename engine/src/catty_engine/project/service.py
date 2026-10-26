from __future__ import annotations

from pathlib import Path
from uuid import UUID

from .models import Episode, Project
from .store import ProjectStore
from catty_engine.media.probe import MediaProbeService
from catty_engine.media.audio import AudioAssetKind
from catty_engine.media.audio_preparation import (
    AudioPreparationService,
)

class ProjectService:
    def __init__(
        self,
        store: ProjectStore | None = None,
        media_probe: MediaProbeService | None = None,
        audio_preparation: AudioPreparationService | None = None,
    ) -> None:
        self._store = store or ProjectStore()
        self._media_probe = media_probe or MediaProbeService()
        self._audio_preparation = (
            audio_preparation
            or AudioPreparationService()
        )

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

    def probe_episode_media(
        self,
        directory: Path,
        project: Project,
        episode_id: UUID,
    ) -> Episode:
        episode = project.episode(episode_id)

        if episode is None:
            raise ValueError(
                f"Episode does not exist: {episode_id}"
            )

        episode.media = self._media_probe.probe(
            episode.media.source_path
        )

        self._store.save(
            directory=directory,
            project=project,
        )

        return episode


    def probe_all_episode_media(
        self,
        directory: Path,
        project: Project,
    ) -> list[Episode]:
        probed: list[Episode] = []

        for episode in project.episodes:
            episode.media = self._media_probe.probe(
                episode.media.source_path
            )
            probed.append(episode)

        self._store.save(
            directory=directory,
            project=project,
        )

        return probed

    def prepare_episode_audio(
        self,
        directory: Path,
        project: Project,
        episode_id: UUID,
    ) -> Episode:
        episode = project.episode(episode_id)

        if episode is None:
            raise ValueError(
                f"Episode does not exist: {episode_id}"
            )

        existing = episode.audio_asset(
            AudioAssetKind.SPEECH
        )

        asset = self._audio_preparation.prepare_speech_audio(
            project_directory=directory,
            episode_id=episode.id,
            source=episode.media.source_path,
            existing_asset=existing,
        )

        episode.set_audio_asset(asset)

        self._store.save(
            directory=directory,
            project=project,
        )

        return episode