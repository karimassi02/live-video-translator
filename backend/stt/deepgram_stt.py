"""Moteur STT Deepgram (streaming temps réel via WebSocket).

API brute (pas de SDK) : une seule dépendance `websockets`, et le protocole
est simple — on envoie du PCM binaire, on reçoit du JSON.
"""
import asyncio
import json
import logging
from urllib.parse import urlencode

from websockets.asyncio.client import connect

from config import settings
from stt.base import STTEngine, TranscriptCallback

log = logging.getLogger(__name__)

DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"


class DeepgramSTT(STTEngine):
    def __init__(self) -> None:
        self._ws = None
        self._tasks: list[asyncio.Task] = []

    async def start(self, on_transcript: TranscriptCallback) -> None:
        params = {
            "model": settings.deepgram_model,
            "language": settings.source_lang,
            "encoding": "linear16",
            "sample_rate": str(settings.sample_rate),
            "channels": "1",
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
            "endpointing": "300",
        }
        url = f"{DEEPGRAM_WS}?{urlencode(params)}"
        self._ws = await connect(
            url,
            additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )
        log.info("Connecté à Deepgram (model=%s, lang=%s)", settings.deepgram_model, settings.source_lang)
        self._tasks = [
            asyncio.create_task(self._receive_loop(on_transcript)),
            asyncio.create_task(self._keepalive_loop()),
        ]

    async def _receive_loop(self, on_transcript: TranscriptCallback) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if msg.get("type") != "Results":
                    continue
                alt = msg.get("channel", {}).get("alternatives", [{}])[0]
                text = alt.get("transcript", "")
                if not text.strip():
                    continue
                await on_transcript(text, bool(msg.get("is_final")))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Boucle de réception Deepgram interrompue")

    async def _keepalive_loop(self) -> None:
        """Deepgram coupe après ~10 s sans données : on maintient la connexion."""
        while True:
            await asyncio.sleep(5)
            try:
                await self._ws.send(json.dumps({"type": "KeepAlive"}))
            except Exception:
                return

    async def send_audio(self, pcm: bytes) -> None:
        if self._ws is not None:
            await self._ws.send(pcm)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
