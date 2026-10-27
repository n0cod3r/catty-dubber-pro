from __future__ import annotations

from pathlib import Path
from uuid import UUID

from catty_engine.media.audio import AudioAssetKind
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.fingerprint import source_fingerprint
from catty_engine.media.probe import MediaProbeService
from catty_engine.media.video_proxy import VideoProxyService

from .models import Episode, Project
from .store import ProjectStore

class ProjectService:
    def __init__(self, store: ProjectStore | None = None, media_probe: MediaProbeService | None = None, audio_preparation: AudioPreparationService | None = None, video_proxy: VideoProxyService | None = None) -> None:
        self._store = store or ProjectStore()
        self._media_probe = media_probe or MediaProbeService()
        self._audio_preparation = audio_preparation or AudioPreparationService()
        self._video_proxy = video_proxy or VideoProxyService()

    def create_project(self, directory: Path, name: str) -> Project:
        return self._store.create(directory=directory, name=name)
    def open_project(self, directory: Path) -> Project:
        return self._store.load(directory=directory)
    def save_project(self, directory: Path, project: Project) -> None:
        self._store.save(directory=directory, project=project)
    def find_episode_by_source(self, project: Project, source_path: str | Path) -> Episode | None:
        source = Path(source_path).expanduser().resolve()
        fingerprint = source_fingerprint(source)
        for episode in project.episodes:
            if Path(episode.media.source_path).expanduser().resolve() == source:
                return episode
            existing_asset = episode.audio_asset(AudioAssetKind.SPEECH)
            if existing_asset and existing_asset.source_fingerprint == fingerprint:
                return episode
        return None

    def import_episode(self, directory: Path, project: Project, source_path: str, *, prepare_audio: bool = True) -> Episode:
        path = Path(source_path).expanduser().resolve()
        if not path.is_file(): raise FileNotFoundError(f"Episode does not exist: {path}")
        episode = self.find_episode_by_source(project, path)
        if episode is None:
            episode = project.add_episode(source_path=str(path))
            episode.media = self._media_probe.probe(str(path))
            self._store.save(directory=directory, project=project)
        if prepare_audio:
            episode = self.prepare_episode_audio(directory, project, episode.id)
            episode = self.prepare_episode_proxy(directory, project, episode.id)
        return episode

    def import_episodes(self, directory: Path, project: Project, source_paths: list[str]) -> list[Episode]:
        imported: list[Episode] = []
        known_ids = {episode.id for episode in project.episodes}
        for source_path in source_paths:
            episode = self.import_episode(directory, project, source_path, prepare_audio=False)
            if episode.id not in known_ids:
                imported.append(episode); known_ids.add(episode.id)
        return imported

    def remove_episode(self, directory: Path, project: Project, episode_id: UUID) -> bool:
        before = len(project.episodes)
        project.episodes = [episode for episode in project.episodes if episode.id != episode_id]
        if len(project.episodes) == before: return False
        for index, episode in enumerate(project.episodes): episode.order = index
        self._store.save(directory=directory, project=project); return True

    def probe_episode_media(self, directory: Path, project: Project, episode_id: UUID) -> Episode:
        episode = project.episode(episode_id)
        if episode is None: raise ValueError(f"Episode does not exist: {episode_id}")
        episode.media = self._media_probe.probe(episode.media.source_path)
        self._store.save(directory=directory, project=project); return episode

    def probe_all_episode_media(self, directory: Path, project: Project) -> list[Episode]:
        for episode in project.episodes: episode.media = self._media_probe.probe(episode.media.source_path)
        self._store.save(directory=directory, project=project); return project.episodes

    def prepare_episode_audio(self, directory: Path, project: Project, episode_id: UUID) -> Episode:
        episode = project.episode(episode_id)
        if episode is None: raise ValueError(f"Episode does not exist: {episode_id}")
        asset = self._audio_preparation.prepare_speech_audio(project_directory=directory, episode_id=episode.id, source=episode.media.source_path, existing_asset=episode.audio_asset(AudioAssetKind.SPEECH))
        episode.set_audio_asset(asset)
        self._store.save(directory=directory, project=project); return episode

    def prepare_episode_proxy(self, directory: Path, project: Project, episode_id: UUID) -> Episode:
        episode = project.episode(episode_id)
        if episode is None: raise ValueError(f"Episode does not exist: {episode_id}")
        episode.playback_proxy_path = self._video_proxy.prepare_playback_proxy(project_directory=directory, source=episode.media.source_path, existing_path=episode.playback_proxy_path)
        self._store.save(directory=directory, project=project); return episode
