"""Orchestration d'une session : audio → STT → traduction → sous-titres."""
import asyncio
import logging
from collections import deque
from typing import Any, Awaitable, Callable

from config import settings
from stt.deepgram_stt import DeepgramSTT
from translate.claude_translator import ClaudeTranslator
from translate.deepl_translator import DeepLTranslator

log = logging.getLogger(__name__)

SendJson = Callable[[dict[str, Any]], Awaitable[None]]

# Nombre de phrases finalisées gardées comme contexte de traduction.
CONTEXT_WINDOW = 5


class SubtitlePipeline:
    def __init__(self, send_json: SendJson) -> None:
        self._send = send_json
        self._stt = DeepgramSTT()
        # Hybride : DeepL pour l'affichage immédiat (et les partiels),
        # Claude pour la version finale (idiomes/argot rendus par le sens).
        self._partial_translator = DeepLTranslator()
        self._final_translator = (
            ClaudeTranslator() if settings.final_translator == "claude" else self._partial_translator
        )
        # Couples [src, dst] mutables : la version DeepL affichée immédiatement
        # est remplacée par la version Claude quand elle arrive.
        self._context: deque[list[str]] = deque(maxlen=CONTEXT_WINDOW)
        self._seq = 0            # numéro du dernier transcript reçu
        self._final_seq = 0      # numéro du dernier transcript FINAL reçu
        self._last_partial_tx = 0.0

    async def start(self) -> None:
        await self._stt.start(self._on_transcript)
        # Préchauffe les connexions TLS pour que le premier sous-titre soit rapide.
        asyncio.create_task(self._prewarm())

    async def _prewarm(self) -> None:
        translators = {id(t): t for t in (self._partial_translator, self._final_translator)}
        results = await asyncio.gather(
            *(t.prewarm() for t in translators.values()), return_exceptions=True
        )
        for err in results:
            if isinstance(err, Exception):
                log.warning("Préchauffage d'un traducteur échoué : %s", err)

    async def feed(self, pcm: bytes) -> None:
        await self._stt.send_audio(pcm)

    async def _on_transcript(self, text: str, is_final: bool) -> None:
        self._seq += 1
        seq = self._seq

        if is_final:
            self._final_seq = seq
            await self._emit_final(text, seq)
        else:
            # Mode « bloc » (défaut) : on n'affiche pas les partiels, la phrase
            # apparaîtra entière à la finalisation.
            if not settings.translate_partials:
                return
            # Les partiels arrivent vite : on ne traduit qu'à intervalle limité
            # pour épargner le quota DeepL et éviter le flicker.
            now = asyncio.get_running_loop().time()
            if now - self._last_partial_tx >= settings.partial_translate_interval:
                self._last_partial_tx = now
                asyncio.create_task(self._translate_partial(text, seq))

    def _context_snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple((src, dst) for src, dst in self._context)

    async def _emit_final(self, text: str, seq: int) -> None:
        """Affichage en deux temps : DeepL tout de suite, Claude en remplacement.

        La version DeepL (~200 ms) apparaît dès la fin de la réplique ; la
        version Claude (~1 s) remplace ensuite discrètement le texte de la ligne.
        """
        context = self._context_snapshot()
        draft: str | None = None
        try:
            draft = await self._partial_translator.translate(text, context)
        except Exception:
            log.exception("Traduction DeepL du segment final échouée")

        entry: list[str] | None = None
        if draft:
            entry = [text, draft]
            self._context.append(entry)
        await self._safe_send({"type": "final", "id": seq, "src": text, "dst": draft})

        if self._final_translator is not self._partial_translator:
            asyncio.create_task(self._refine_final(text, seq, entry, context))

    async def _refine_final(
        self, text: str, seq: int, entry: list[str] | None, context: tuple[tuple[str, str], ...]
    ) -> None:
        try:
            dst = await self._final_translator.translate(text, context)
        except Exception as e:
            log.warning(
                "Claude indisponible (%s: %s), la version DeepL reste affichée", type(e).__name__, e
            )
            return
        if not dst:
            return
        # Garde-fou : une réponse démesurée par rapport à la source est un
        # commentaire du modèle, pas une traduction — on garde la version DeepL.
        if len(dst) > max(60, 3 * len(text)):
            log.warning("Réponse Claude suspecte ignorée pour %r : %r", text, dst)
            return
        if entry is not None:
            if dst == entry[1]:
                return  # identique à la version DeepL : rien à remplacer
            entry[1] = dst
        else:
            # DeepL avait échoué : la version Claude devient la ligne affichée.
            self._context.append([text, dst])
        await self._safe_send({"type": "final_update", "id": seq, "dst": dst})

    async def _translate_partial(self, text: str, seq: int) -> None:
        try:
            dst = await self._partial_translator.translate(text, self._context_snapshot())
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
        await self._partial_translator.close()
        if self._final_translator is not self._partial_translator:
            await self._final_translator.close()
