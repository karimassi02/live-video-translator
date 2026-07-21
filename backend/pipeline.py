"""Orchestration d'une session : audio → STT → traduction → sous-titres."""
import asyncio
import logging
from typing import Any, Awaitable, Callable

from config import settings
from stt.deepgram_stt import DeepgramSTT
from translate.deepl_translator import DeepLTranslator

log = logging.getLogger(__name__)

SendJson = Callable[[dict[str, Any]], Awaitable[None]]


class SubtitlePipeline:
    def __init__(self, send_json: SendJson) -> None:
        self._send = send_json
        self._stt = DeepgramSTT()
        self._translator = DeepLTranslator()
        self._seq = 0            # numéro du dernier transcript reçu
        self._final_seq = 0      # numéro du dernier transcript FINAL reçu
        self._last_partial_tx = 0.0

    async def start(self) -> None:
        await self._stt.start(self._on_transcript)

    async def feed(self, pcm: bytes) -> None:
        await self._stt.send_audio(pcm)

    async def _on_transcript(self, text: str, is_final: bool) -> None:
        self._seq += 1
        seq = self._seq

        if is_final:
            self._final_seq = seq
            try:
                dst = await self._translator.translate(text)
            except Exception:
                log.exception("Traduction du segment final échouée")
                dst = None
            await self._safe_send({"type": "final", "src": text, "dst": dst})
        else:
            # Les partiels arrivent vite : on ne traduit qu'à intervalle limité
            # pour épargner le quota DeepL et éviter le flicker.
            now = asyncio.get_running_loop().time()
            if now - self._last_partial_tx >= settings.partial_translate_interval:
                self._last_partial_tx = now
                asyncio.create_task(self._translate_partial(text, seq))

    async def _translate_partial(self, text: str, seq: int) -> None:
        try:
            dst = await self._translator.translate(text)
        except Exception:
            return
        # Un segment final est arrivé entre-temps : ce partiel est obsolète.
        if self._final_seq > seq:
            return
        await self._safe_send({"type": "partial", "src": text, "dst": dst})

    async def _safe_send(self, msg: dict[str, Any]) -> None:
        try:
            await self._send(msg)
        except Exception:
            pass  # extension déconnectée

    async def stop(self) -> None:
        await self._stt.stop()
        await self._translator.close()
