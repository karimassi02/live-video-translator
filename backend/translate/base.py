"""Interface abstraite d'un traducteur.

Permet de remplacer DeepL par un LLM (meilleur sur l'argot) ou un modèle
local sans toucher au reste du pipeline.
"""
from abc import ABC, abstractmethod


class Translator(ABC):
    @abstractmethod
    async def translate(self, text: str) -> str:
        """Traduit `text` de la langue source vers la langue cible (config)."""

    async def close(self) -> None:  # noqa: B027
        pass
