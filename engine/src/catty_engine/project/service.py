from __future__ import annotations

import logging

from catty_engine.logging import logged_process

from pathlib import Path
from math import isclose
from uuid import UUID

from catty_engine.media.audio import AudioAssetKind
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.fingerprint import source_fingerprint
from catty_engine.media.probe import MediaProbeService
from catty_engine.media.video_proxy import VideoProxyService
from catty_engine.speech.models import TranscriptSegment

from .models import (
    DialogueSegment,
    EpisodeSpeaker,
    DubSegment,
    Episode,
    ProcessingStatus,
    Project,
    Translation,
    TranslationStatus,
    utc_now,
)
from .store import ProjectStore


def _is_spoken(character: str) -> bool:
    return character.isalnum()


class ProjectService:
    def __init__(
        self,
        store: ProjectStore | None = None,
        media_probe: MediaProbeService | None = None,
        audio_preparation: AudioPreparationService | None = None,
        video_proxy: VideoProxyService | None = None,
    ) -> None:
        self._store = store or ProjectStore()
        self._media_probe = media_probe or MediaProbeService()
        self._audio_preparation = audio_preparation or AudioPreparationService()
        self._video_proxy = video_proxy or VideoProxyService()

    @logged_process
    def create_project(self, directory: Path, name: str) -> Project:
        return self._store.create(directory=directory, name=name)

    def open_project(self, directory: Path) -> Project:
        return self._store.load(directory=directory)

    @logged_process
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

    @logged_process
    def import_episode(self, directory: Path, project: Project, source_path: str, *, prepare_audio: bool = True) -> Episode:
        path = Path(source_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Episode does not exist: {path}")
        episode = self.find_episode_by_source(project, path)
        added = episode is None
        if episode is None:
            episode = project.add_episode(source_path=str(path))
        try:
            # Re-probe even for a known path: users often replace a file in
            # place (same episode name/download), and stale duration/resolution
            # breaks the timeline and the playback proxy.
            episode.media = self._media_probe.probe(str(path))
            self._store.save(directory=directory, project=project)
            if prepare_audio:
                episode = self.prepare_episode_audio(directory, project, episode.id)
                episode = self.prepare_episode_proxy(directory, project, episode.id)
        except Exception:
            # A failed first import must not leave a half-imported episode that
            # the UI never showed but that reappears on the next project open.
            if added:
                try:
                    self.remove_episode(directory, project, episode.id)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Could not roll back failed episode import"
                    )
            raise
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

    @logged_process
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
        asset = self._audio_preparation.prepare_speech_audio(
            project_directory=directory,
            episode_id=episode.id,
            source=episode.media.source_path,
            existing_asset=episode.audio_asset(AudioAssetKind.SPEECH),
        )
        episode.set_audio_asset(asset)
        self._store.save(directory=directory, project=project)
        return episode

    def prepare_episode_proxy(self, directory: Path, project: Project, episode_id: UUID, *, force: bool = False) -> Episode:
        episode = self._episode(project, episode_id)
        episode.playback_proxy_path = self._video_proxy.prepare_playback_proxy(
            project_directory=directory,
            source=episode.media.source_path,
            existing_path=episode.playback_proxy_path,
            force=force,
        )
        self._store.save(directory=directory, project=project)
        return episode

    @logged_process
    def replace_dialogue_segments(self, directory: Path, project: Project, episode_id: UUID, segments: list[TranscriptSegment], *, source_language: str, speaker_error: str | None = None) -> Episode:
        episode = self._episode(project, episode_id)
        speakers = {
            label: EpisodeSpeaker(name=f"S{index + 1}")
            for index, label in enumerate(dict.fromkeys(segment.speaker for segment in segments if segment.speaker is not None))
        }
        episode.dialogue_segments = [
            DialogueSegment(
                start=segment.start,
                end=segment.end,
                speaker_id=speakers[segment.speaker].id if segment.speaker is not None else None,
                source_language=source_language,
                source_text=segment.text,
                confidence=segment.confidence,
            )
            for segment in segments
        ]
        episode.speakers = list(speakers.values())
        for speaker in episode.speakers:
            speaker.segment_ids = [segment.id for segment in episode.dialogue_segments if segment.speaker_id == speaker.id]
        episode.dub_segments = []
        episode.processing.transcription = ProcessingStatus.COMPLETED
        episode.processing.translation = ProcessingStatus.IDLE
        if speaker_error is None:
            episode.processing.speakers = ProcessingStatus.COMPLETED
            episode.processing.speaker_error = None
        else:
            episode.processing.speakers = ProcessingStatus.FAILED
            episode.processing.speaker_error = speaker_error
        self._touch_and_save(directory, project, episode)
        return episode

    @logged_process
    def assign_dialogue_speaker(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID, speaker_id: UUID | None, expected_speaker_id: UUID | None, *, create_new: bool = False) -> Episode:
        episode = self._episode(project, episode_id)
        segment = episode.dialogue_segments[self._segment_index(episode, segment_id)]
        if segment.speaker_id != expected_speaker_id:
            raise ValueError("Dialogue speaker changed since editing began. Reload the dialogue before saving.")
        if create_new:
            if speaker_id is not None:
                raise ValueError("Cannot select a speaker and create one simultaneously")
            names = {speaker.name for speaker in episode.speakers}
            index = 1
            while f"S{index}" in names:
                index += 1
            speaker = EpisodeSpeaker(name=f"S{index}")
            episode.speakers.append(speaker)
            speaker_id = speaker.id
        elif speaker_id is not None and not any(s.id == speaker_id for s in episode.speakers):
            raise ValueError("Speaker does not belong to this episode")
        segment.speaker_id = speaker_id
        segment.updated_at = utc_now()
        for speaker in episode.speakers:
            speaker.segment_ids = [item.id for item in episode.dialogue_segments if item.speaker_id == speaker.id]
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id != segment.id]
        self._touch_and_save(directory, project, episode)
        return episode

    @logged_process
    def update_dialogue_text(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID, text: str, expected_text: str) -> Episode:
        episode = self._episode(project, episode_id)
        segment = episode.dialogue_segments[self._segment_index(episode, segment_id)]
        if segment.source_text != expected_text:
            raise ValueError("Dialogue text changed since editing began. Reload the dialogue before saving.")
        text = text.strip()
        if not text:
            raise ValueError("Dialogue text cannot be empty")
        if text == segment.source_text:
            return episode
        segment.source_text = text
        segment.updated_at = utc_now()
        segment.translation = None
        episode.processing.translation = ProcessingStatus.IDLE
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id != segment.id]
        self._touch_and_save(directory, project, episode)
        return episode

    @logged_process
    def update_dialogue_translation(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID, text: str, expected_text: str | None) -> Episode:
        episode = self._episode(project, episode_id)
        segment = episode.dialogue_segments[self._segment_index(episode, segment_id)]
        current_text = segment.translation.text if segment.translation is not None else None
        if current_text != expected_text:
            raise ValueError("Khmer translation changed since editing began. Reload before saving.")
        text = text.strip()
        if not text:
            raise ValueError("Khmer translation cannot be empty")
        if segment.translation is not None and text == segment.translation.text and segment.translation.manually_edited:
            return episode
        previous = segment.translation
        segment.translation = Translation(
            language=previous.language if previous is not None else project.settings.translation.target_language,
            text=text,
            status=TranslationStatus.EDITED,
            provider=previous.provider if previous is not None else None,
            model=previous.model if previous is not None else None,
            manually_edited=True,
        )
        segment.updated_at = utc_now()
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id != segment.id]
        episode.processing.translation = ProcessingStatus.COMPLETED
        self._touch_and_save(directory, project, episode)
        return episode

    @logged_process
    def split_dialogue_segment(self, directory: Path, project: Project, episode_id: UUID, segment_id: UUID, split_at: float) -> Episode:
        episode = self._episode(project, episode_id)
        index = self._segment_index(episode, segment_id)
        segment = episode.dialogue_segments[index]
        margin = 0.05
        if split_at <= segment.start + margin or split_at >= segment.end - margin:
            raise ValueError("Split point must be inside the dialogue segment")
        ratio = (split_at - segment.start) / segment.duration
        text = segment.source_text.strip()
        spoken = [index for index, character in enumerate(text) if _is_spoken(character)]
        if len(spoken) < 2:
            raise ValueError(
                "Dialogue segment needs at least two spoken characters to split"
            )
        target = round(len(text) * ratio)
        cut = min(max(target, spoken[0] + 1), spoken[-1])
        left_text = text[:cut].strip()
        right_text = text[cut:].strip()
        left = DialogueSegment(start=segment.start, end=split_at, speaker_id=segment.speaker_id, source_language=segment.source_language, source_text=left_text, confidence=segment.confidence)
        right = DialogueSegment(start=split_at, end=segment.end, speaker_id=segment.speaker_id, source_language=segment.source_language, source_text=right_text, confidence=segment.confidence)
        episode.dialogue_segments[index : index + 1] = [left, right]
        self._replace_speaker_segment_ids(episode, {segment.id}, [left, right])
        episode.processing.translation = ProcessingStatus.IDLE
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id != segment.id]
        self._touch_and_save(directory, project, episode)
        return episode

    @logged_process
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
        merged = DialogueSegment(
            start=first.start,
            end=second.end,
            speaker_id=first.speaker_id if first.speaker_id == second.speaker_id else None,
            source_language=first.source_language,
            source_text=f"{first.source_text.rstrip()}{separator}{second.source_text.lstrip()}",
            confidence=self._average_confidence(first.confidence, second.confidence),
        )
        episode.dialogue_segments[index : index + 2] = [merged]
        replaced_ids = {first.id, second.id}
        self._replace_speaker_segment_ids(episode, replaced_ids, [merged])
        episode.processing.translation = ProcessingStatus.IDLE
        episode.dub_segments = [dub for dub in episode.dub_segments if dub.dialogue_segment_id not in replaced_ids]
        self._touch_and_save(directory, project, episode)
        return episode

    @staticmethod
    def _same_dialogue(current: list[DialogueSegment], expected: list[DialogueSegment]) -> bool:
        if len(current) != len(expected):
            return False
        for actual, previous in zip(current, expected):
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

    @logged_process
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
