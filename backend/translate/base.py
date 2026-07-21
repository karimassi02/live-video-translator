"""Interface abstraite d'un traducteur.

Permet de remplacer DeepL par un LLM (meilleur sur l'argot) ou un modèle
local sans toucher au reste du pipeline.
"""
from abc import ABC, abstractmethod
from typing import Sequence

# Derniers couples (source, traduction) finalisés, du plus ancien au plus récent.
TranslationContext = Sequence[tuple[str, str]]


class Translator(ABC):
    @abstractmethod
    async def translate(self, text: str, context: TranslationContext = ()) -> str:
        """Traduit `text` de la langue source vers la langue cible (config).

        `context` sert à la cohérence (pronoms, registre, idiomes).
        """

    async def prewarm(self) -> None:  # noqa: B027
        """Établit la connexion (TLS) pour que le premier appel réel soit rapide."""

    async def close(self) -> None:  # noqa: B027
        pass
