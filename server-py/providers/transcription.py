"""Transcription provider seam — audio bytes → text.

Three implementations:
- `MockTranscriber` — returns a fixed string. Default for dev where the
  detective is testing the upload + extraction flow without paying for
  Whisper credits.
- `OpenAIWhisperTranscriber` — production fallback. Cheap (~$0.006/min)
  but sends officer-recorded audio to OpenAI.
- `LocalWhisperTranscriber` — placeholder for an on-device model
  (faster-whisper / whisper.cpp / Azure Speech in private network). Slots
  in behind the same interface when the agency picks one.

Selected via TRANSCRIPTION_PROVIDER env var. Officer-recorded audio is
officer working memory under §13663 — once an agency goes live, the
private-network local option should be preferred.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Protocol


logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    model: str
    duration_seconds: float | None = None


class Transcriber(Protocol):
    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str) -> TranscriptionResult:
        ...


class MockTranscriber:
    """Always returns the same placeholder transcript. Default for dev."""

    name = "mock-transcriber-v1"

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str) -> TranscriptionResult:
        kb = max(1, len(audio_bytes) // 1024)
        text = (
            "[Mock transcript — set TRANSCRIPTION_PROVIDER=openai_whisper or "
            "local_whisper for real transcription.]\n\n"
            f"Detective brain-dump from {filename} ({kb} KB, {mime_type}). "
            "I think the witness statement and the patrol report contradict "
            "each other on the time the body was found. We should re-interview "
            "the dog walker. Also worth checking whether the suspect's car was "
            "in the area that morning — there might be tag-reader data we missed."
        )
        return TranscriptionResult(text=text, model=self.name, duration_seconds=None)


class OpenAIWhisperTranscriber:
    """OpenAI Whisper API. Cheap (~$0.006/min). Sends audio to OpenAI —
    not appropriate for agencies that require on-prem processing."""

    name = "openai-whisper-1"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = model or os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
        if self._model:
            self.name = self._model

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str) -> TranscriptionResult:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY missing — cannot transcribe with OpenAI Whisper")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openai package missing — install via requirements.txt"
            ) from exc
        client = OpenAI(api_key=self._api_key)
        # openai-python wants a file-like with .name
        buf = io.BytesIO(audio_bytes)
        buf.name = filename or "audio.webm"
        resp = client.audio.transcriptions.create(model=self._model, file=buf)
        return TranscriptionResult(text=resp.text, model=self._model)


class LocalWhisperTranscriber:
    """Stub — agency picks a local provider (faster-whisper, whisper.cpp,
    Azure Speech in private VNet) and we fill this in. For now it raises so
    misconfiguration is loud."""

    name = "local-whisper-stub"

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str) -> TranscriptionResult:
        raise NotImplementedError(
            "LocalWhisperTranscriber not yet wired — set TRANSCRIPTION_PROVIDER=mock "
            "or openai_whisper, or implement this against the agency's chosen model"
        )


def get_transcriber() -> Transcriber:
    name = os.getenv("TRANSCRIPTION_PROVIDER", "mock").strip().lower()
    if name in {"openai_whisper", "openai", "whisper"}:
        return OpenAIWhisperTranscriber()
    if name in {"local_whisper", "local"}:
        return LocalWhisperTranscriber()
    return MockTranscriber()
