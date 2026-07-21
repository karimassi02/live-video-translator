"""Traducteur par LLM (Claude) — rend les idiomes et l'argot par le sens.

Utilisé pour les phrases finales : « il ne me calcule pas » doit donner
« he's ignoring me », pas « he doesn't calculate me ».
"""
import logging

from anthropic import AsyncAnthropic

from config import settings
from translate.base import TranslationContext, Translator

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a live subtitle translator. Translate each segment from "{src}" into \
natural, colloquial "{dst}", exactly as a professional subtitler would.

Rules:
- Render idioms and slang by MEANING, never word for word (e.g. French \
"il ne me calcule pas" -> "he's ignoring me").
- Match the speaker's register: casual stays casual, formal stays formal.
- Keep it concise — it must read comfortably as a subtitle.
- Use the previous dialogue lines only for coherence (pronouns, tone, topic).
- Segments come from live speech-to-text: they may be sentence fragments, \
fillers, or garbled words. Translate whatever is there as best you can \
("euh ouais enfin bref" -> "uh yeah anyway"), without ever commenting on it.
- Your reply is displayed VERBATIM as a subtitle on screen. Reply with the \
translation ONLY — never apologize, never ask for clarification, never \
explain, never add quotes or notes. Anything that is not the translation \
is a bug.
- Only if the segment contains nothing translatable at all, reply with \
exactly: ∅
"""


class ClaudeTranslator(Translator):
    def __init__(self) -> None:
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=10.0,
            max_retries=1,
        )
        self._system = SYSTEM_PROMPT.format(src=settings.source_lang, dst=settings.target_lang)

    async def translate(self, text: str, context: TranslationContext = ()) -> str:
        parts = []
        if context:
            lines = "\n".join(f"{src} -> {dst}" for src, dst in context)
            parts.append(f"Previous dialogue:\n{lines}\n")
        parts.append(f"Translate this segment:\n{text}")

        response = await self._client.messages.create(
            model=settings.claude_model,
            max_tokens=200,
            system=self._system,
            messages=[{"role": "user", "content": "\n".join(parts)}],
        )
        out = "".join(b.text for b in response.content if b.type == "text").strip()
        if out == "∅":
            return ""  # segment intraduisible : l'appelant garde la version DeepL
        # Le modèle encadre parfois sa réponse de guillemets absents de la source.
        if len(out) >= 2 and out[0] in "\"'«“" and out[-1] in "\"'»”" and text.strip()[0] not in "\"'«“":
            out = out[1:-1].strip()
        return out

    async def prewarm(self) -> None:
        # count_tokens est gratuit et suffit à établir la connexion TLS.
        await self._client.messages.count_tokens(
            model=settings.claude_model,
            messages=[{"role": "user", "content": "ok"}],
        )

    async def close(self) -> None:
        await self._client.close()
