from __future__ import annotations

from pathlib import Path
from math import isclose
from uuid import UUID

from catty_engine.media.audio import AudioAssetKind
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.fingerprint import source_fingerprint
from catty_engine.media.probe import MediaProbeService
from catty_engine.media.video_proxy import VideoProxyService
from catty_engine.speech.models import TranscriptSegment

from .models import DialogueSegment, EpisodeSpeaker, DubSegment, Episode, ProcessingStatus, Project, utc_now
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
        if not path.is_file():
            raise FileNotFoundError(f"Episode does not exist: {path}")
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
                imported.append(episode)
                known_ids.add(episode.id)
        return imported

    def remove_episode(self, directory: Path, project: Project, episode_id: UUID) -> bool:
        before = len(project.episodes)
        project.episodes = [episode for episode in project.episodes if episode.id != episode_id]
        if len(project.episodes) == before:
            return False
        for index, episode in enumerate(project.episodes):
            episode.order = index
        self._store.save(directory=directory, project=project)
        return True

    def probe_episode_media(self, directory: Path, project: Project, episode_id: UUID) -> Episode:
        episode = self._episode(project, episode_id)
        episode.media = self._media_probe.probe(episode.media.source_path)
        self._store.save(directory=directory, project=project)
        return episode

    def probe_all_episode_media(self, directory: Path, project: Project) -> list[Episode]:
        for episode in project.episodes:
            episode.media = self._media_probe.probe(episode.media.source_path)
        self._store.save(directory=directory, project=project)
        return project.episodes

    def prepare_episode_audio(self, directory: Path, project: Project, episode_id: UUID) -> Episode:
        episode = self._episode(project, episode_id)
        asset = self._audio_preparation.prepare_speech_audio(project_directory=directory, episode_id=episode.id, source=episode.media.source_path, existing_asset=episode.audio_asset(AudioAssetKind.SPEECH))
        episode.set_audio_asset(asset)
        self._store.save(directory=directory, project=project)
        return episode

    def prepare_episode_proxy(self, directory: Path, project: Project, episode_id: UUID, *, force: bool = False) -> Episode:
        episode = self._episode(project, episode_id)
        episode.playback_proxy_path = self._video_proxy.prepare_playback_proxy(project_directory=directory, source=episode.media.source_path, existing_path=episode.playback_proxy_path, force=force)
        self._store.save(directory=directory, project=project)
        return episode

    def replace_dialogue_segments(self, directory: Path, project: Project, episode_id: UUID, segments: list[TranscriptSegment], *, source_language: str) -> Episode:
        episode = self._episode(project, episode_id)
        episode.dialogue_segments = [DialogueSegment(start=segment.start, end=segment.end, source_language=source_language, source_text=segment.text, confidence=segment.confidence) for segment in segments]
        episode.processing.transcription = ProcessingStatus.COMPLETED
        self._touch_and_save(directory, project, episode)
        return episode

    def split_dialogue_segment(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID, split_at: float) -> Episode:
        episode = self._episode(project, episode_id)
        index = self._segment_index(episode, segment_id)
        segment = episode.dialogue_segments[index]
        margin = 0.05
        if split_at <= segment.start + margin or split_at >= segment.end - margin:
            raise ValueError("Split point must be inside the dialogue segment")
        ratio = (split_at - segment.start) / segment.duration
        text = segment.source_text.strip()
        cut = max(1, min(len(text) - 1, round(len(text) * ratio))) if len(text) > 1 else 0
        left_text = text[:cut].strip() if cut else text
        right_text = text[cut:].strip() if cut else text
        left = DialogueSegment(start=segment.start, end=split_at, speaker_id=segment.speaker_id, source_language=segment.source_language, source_text=left_text, confidence=segment.confidence)
        right = DialogueSegment(start=split_at, end=segment.end, speaker_id=segment.speaker_id, source_language=segment.source_language, source_text=right_text, confidence=segment.confidence)
        episode.dialogue_segments[index:index + 1] = [left, right]
        self._replace_speaker_segment_ids(episode, {segment.id}, [left, right])
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id != segment.id]
        self._touch_and_save(directory, project, episode)
        return episode

    def merge_dialogue_segment_with_next(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID) -> Episode:
        episode = self._episode(project, episode_id)
        index = self._segment_index(episode, segment_id)
        if index + 1 >= len(episode.dialogue_segments):
            raise ValueError("There is no next dialogue segment to merge")
        first = episode.dialogue_segments[index]
        second = episode.dialogue_segments[index + 1]
        if first.source_language != second.source_language:
            raise ValueError("Dialogue segments must use the same source language")
        separator = "" if first.source_language.startswith("zh") else " "
        merged = DialogueSegment(start=first.start, end=second.end, speaker_id=first.speaker_id if first.speaker_id == second.speaker_id else None, source_language=first.source_language, source_text=f"{first.source_text.rstrip()}{separator}{second.source_text.lstrip()}", confidence=self._average_confidence(first.confidence, second.confidence))
        episode.dialogue_segments[index:index + 2] = [merged]
        replaced_ids = {first.id, second.id}
        self._replace_speaker_segment_ids(episode, replaced_ids, [merged])
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id not in replaced_ids]
        self._touch_and_save(directory, project, episode)
        return episode

    @staticmethod
    def _same_dialogue(current: list[DialogueSegment], expected: list[DialogueSegment]) -> bool:
        if len(current) != len(expected):
            return False
        for actual, previous in zip(current, expected):
            # JS/Rust JSON transport can round the final float digit. Timestamps
            # are metadata; IDs and all non-numeric dialogue content must match.
            excluded = {"created_at", "updated_at", "start", "end", "confidence"}
            if actual.model_dump(exclude=excluded) != previous.model_dump(exclude=excluded):
                return False
            for field in ("start", "end", "confidence"):
                left, right = getattr(actual, field), getattr(previous, field)
                if left is None or right is None:
                    if left != right:
                        return False
                elif not isclose(left, right, rel_tol=0, abs_tol=1e-9):
                    return False
        return True

    def restore_dialogue(self, directory: Path, project: Project, episode_id: UUID, expected_segments: list[DialogueSegment], segments: list[DialogueSegment], speakers: list[EpisodeSpeaker], dubs: list[DubSegment]) -> Episode:
        episode = self._episode(project, episode_id)
        if not self._same_dialogue(episode.dialogue_segments, expected_segments):
            raise ValueError("Dialogue changed since this edit. Reopen the project before undoing.")
        episode.dialogue_segments = [segment.model_copy(deep=True) for segment in segments]
        episode.speakers = [speaker.model_copy(deep=True) for speaker in speakers]
        episode.dub_segments = [dub.model_copy(deep=True) for dub in dubs]
        self._touch_and_save(directory, project, episode)
        return episode

    @staticmethod
    def _replace_speaker_segment_ids(episode: Episode, removed: set[UUID], replacements: list[DialogueSegment]) -> None:
        for speaker in episode.speakers:
            # Segment ownership is authoritative. A mixed-speaker merge becomes
            # unassigned, so neither speaker retains the merged segment.
            ids = [segment_id for segment_id in speaker.segment_ids if segment_id not in removed]
            ids.extend(segment.id for segment in replacements if segment.speaker_id == speaker.id)
            speaker.segment_ids = list(dict.fromkeys(ids))

    @staticmethod
    def _episode(project: Project, episode_id: UUID) -> Episode:
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError(f"Episode does not exist: {episode_id}")
        return episode

    @staticmethod
    def _segment_index(episode: Episode, segment_id: UUID) -> int:
        for index, segment in enumerate(episode.dialogue_segments):
            if segment.id == segment_id:
                return index
        raise ValueError(f"Dialogue segment does not exist: {segment_id}")

    @staticmethod
    def _average_confidence(first: float | None, second: float | None) -> float | None:
        values = [value for value in (first, second) if value is not None]
        return sum(values) / len(values) if values else None

    def _touch_and_save(self, directory: Path, project: Project, episode: Episode) -> None:
        episode.updated_at = utc_now()
        project.updated_at = utc_now()
        self._store.save(directory=directory, project=project)
