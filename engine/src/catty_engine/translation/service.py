"""Contextual episode translation orchestration and persistence."""

from __future__ import annotations

from catty_engine.logging import logged_process

import time
import logging
from pathlib import Path
from uuid import UUID

from catty_engine.project.models import ProcessingStatus, Project, Translation, TranslationStatus, utc_now
from catty_engine.project.service import ProjectService
from catty_engine.settings.credentials import CredentialStore
from catty_engine.settings.service import SettingsService

from .base import ProviderError, ProviderErrorKind
from .credentials import CredentialPool
from .models import GlossaryTerm, TranslationBatchRequest, TranslationContextLine, TranslationInput
from .registry import create_provider, credential_ids

DEFAULT_BATCH_SIZE = 12
CONTEXT_LINES = 2
DEFAULT_RATE_LIMIT_COOLDOWN = 60.0


class TranslationService:
    def __init__(self, project_service: ProjectService | None = None) -> None:
        self._projects = project_service or ProjectService()

    @logged_process
    def translate_episode(self, project_directory: Path, episode_id: UUID, *, overwrite_manual: bool = False, batch_size: int = DEFAULT_BATCH_SIZE):
        if batch_size < 1 or batch_size > 20:
            raise ValueError("Translation batch size must be between 1 and 20")
        project = self._projects.open_project(project_directory)
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError(f"Episode does not exist: {episode_id}")
        if not episode.dialogue_segments:
            raise ValueError("Transcribe the episode before translating")

        app_settings = SettingsService().get()
        translation_settings = app_settings.translation
        store = CredentialStore()
        pool = CredentialPool(
            translation_settings.provider,
            store,
            credential_ids(translation_settings.provider, app_settings, store),
        )
        candidates = [segment for segment in episode.dialogue_segments if overwrite_manual or segment.translation is None or not segment.translation.manually_edited]
        if not candidates:
            return episode

        episode.processing.translation = ProcessingStatus.PROCESSING
        self._projects.save_project(project_directory, project)
        try:
            for start in range(0, len(candidates), batch_size):
                logging.getLogger(__name__).info("Translating dialogue batch %d–%d of %d", start + 1, min(start + batch_size, len(candidates)), len(candidates))
                batch = candidates[start : start + batch_size]
                request = self._build_request(project, episode_id, batch, app_settings)
                result = self._translate_batch(translation_settings.provider, app_settings, pool, request)
                by_id = {item.id: item.text.strip() for item in result.segments}
                for segment in batch:
                    segment.translation = Translation(
                        language=translation_settings.target_language,
                        text=by_id[str(segment.id)],
                        status=TranslationStatus.TRANSLATED,
                        provider=result.provider,
                        model=result.model,
                        manually_edited=False,
                    )
                    segment.updated_at = utc_now()
                # Every successful batch is durable, so a later failure can resume.
                self._projects.save_project(project_directory, project)
        except ProviderError:
            episode.processing.translation = ProcessingStatus.FAILED
            self._projects.save_project(project_directory, project)
            raise

        episode.processing.translation = ProcessingStatus.COMPLETED
        self._projects.save_project(project_directory, project)
        return episode

    @staticmethod
    @logged_process
    def _translate_batch(provider_id, app_settings, pool: CredentialPool, request: TranslationBatchRequest):
        if provider_id == "local":
            return create_provider(provider_id, app_settings).translate_batch(request)

        attempted: set[str] = set()
        last_error: ProviderError | None = None
        while True:
            available = [item for item in pool.available() if item.id not in attempted]
            if not available:
                if last_error is not None:
                    raise ProviderError(
                        "All configured credentials are temporarily unavailable. Completed batches were saved; retry later to resume.",
                        kind=last_error.kind,
                        retry_after=last_error.retry_after,
                    ) from last_error
                raise ProviderError("Add a credential for the selected translation provider.", kind=ProviderErrorKind.AUTH)
            credential = available[0]
            attempted.add(credential.id)
            provider = create_provider(provider_id, app_settings, credential=credential.secret)
            try:
                return provider.translate_batch(request)
            except ProviderError as exc:
                logging.getLogger(__name__).warning("Provider %s attempt failed: %s; kind=%s", provider_id, exc, exc.kind)
                last_error = exc
                if exc.kind == ProviderErrorKind.RATE_LIMIT:
                    pool.cooldown(credential.id, exc.retry_after or DEFAULT_RATE_LIMIT_COOLDOWN)
                    continue
                if exc.kind == ProviderErrorKind.AUTH:
                    pool.mark_invalid(credential.id)
                    continue
                if exc.kind == ProviderErrorKind.TEMPORARY:
                    time.sleep(1.0)
                    try:
                        return provider.translate_batch(request)
                    except ProviderError as retry_error:
                        logging.getLogger(__name__).warning("Provider %s retry failed: %s", provider_id, retry_error)
                        last_error = retry_error
                        attempted.add(credential.id)
                        continue
                raise

    def _build_request(self, project: Project, episode_id: UUID, batch, app_settings) -> TranslationBatchRequest:
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError(f"Episode does not exist: {episode_id}")
        speaker_names = {str(speaker.id): speaker.name for speaker in episode.speakers}
        positions = {segment.id: index for index, segment in enumerate(episode.dialogue_segments)}

        def context_line(segment) -> TranslationContextLine:
            speaker = speaker_names.get(str(segment.speaker_id)) if segment.speaker_id else None
            return TranslationContextLine(id=str(segment.id), text=segment.source_text, speaker=speaker)

        inputs: list[TranslationInput] = []
        for segment in batch:
            index = positions[segment.id]
            previous = episode.dialogue_segments[max(0, index - CONTEXT_LINES) : index]
            following = episode.dialogue_segments[index + 1 : index + 1 + CONTEXT_LINES]
            speaker = speaker_names.get(str(segment.speaker_id)) if segment.speaker_id else None
            inputs.append(TranslationInput(
                id=str(segment.id), text=segment.source_text, speaker=speaker,
                previous=[context_line(item) for item in previous], next=[context_line(item) for item in following],
            ))

        profile = project.settings.translation
        settings = app_settings.translation
        return TranslationBatchRequest(
            source_language=profile.source_language, target_language=settings.target_language, style=settings.style,
            glossary=[GlossaryTerm(source=item.source, target=item.target, note=item.note) for item in profile.glossary],
            custom_instructions=profile.custom_instructions, use_context=settings.use_context,
            use_speaker_context=settings.use_speaker_context, segments=inputs,
        )
