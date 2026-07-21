"""Interface abstraite d'un moteur de reconnaissance vocale (STT) en streaming.

Permet de remplacer Deepgram par un autre moteur (ex: faster-whisper en local
sur GPU) sans toucher au reste du pipeline.
"""
from abc import ABC, abstractmethod
from typing import Awaitable, Callable

# Callback appelé pour chaque transcription : (texte, est_final)
TranscriptCallback = Callable[[str, bool], Awaitable[None]]


class STTEngine(ABC):
    @abstractmethod
    async def start(self, on_transcript: TranscriptCallback) -> None:
        """Ouvre la connexion / initialise le moteur."""

    @abstractmethod
    async def send_audio(self, pcm: bytes) -> None:
        """Pousse un chunk PCM 16 bits mono (sample_rate de la config)."""

    @abstractmethod
    async def stop(self) -> None:
        """Ferme proprement la session."""
