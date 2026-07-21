"""Traducteur DeepL (API REST v2)."""
import logging

import httpx

from config import settings
from translate.base import Translator

log = logging.getLogger(__name__)


class DeepLTranslator(Translator):
    def __init__(self) -> None:
        # Les clés du plan gratuit se terminent par ":fx" et utilisent un autre domaine.
        base = "https://api-free.deepl.com" if settings.deepl_api_key.endswith(":fx") else "https://api.deepl.com"
        self._client = httpx.AsyncClient(
            base_url=base,
            headers={"Authorization": f"DeepL-Auth-Key {settings.deepl_api_key}"},
            timeout=10.0,
        )
        # Cache simple : les partiels successifs répètent souvent le même début de phrase.
        self._cache: dict[str, str] = {}

    async def translate(self, text: str) -> str:
        key = text.strip()
        if key in self._cache:
            return self._cache[key]

        resp = await self._client.post(
            "/v2/translate",
            json={
                "text": [text],
                "source_lang": settings.source_lang.upper(),
                "target_lang": settings.target_lang,
            },
        )
        resp.raise_for_status()
        result = resp.json()["translations"][0]["text"]

        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[key] = result
        return result

    async def close(self) -> None:
        await self._client.aclose()
