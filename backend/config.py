"""Configuration centralisée, chargée depuis backend/.env"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Clés API
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    deepl_api_key: str = field(default_factory=lambda: os.getenv("DEEPL_API_KEY", ""))

    # Langues
    source_lang: str = field(default_factory=lambda: os.getenv("SOURCE_LANG", "fr"))
    target_lang: str = field(default_factory=lambda: os.getenv("TARGET_LANG", "EN-GB"))

    # STT
    deepgram_model: str = field(default_factory=lambda: os.getenv("DEEPGRAM_MODEL", "nova-2"))
    sample_rate: int = field(default_factory=lambda: int(os.getenv("SAMPLE_RATE", "16000")))

    # Fréquence max de traduction des résultats partiels (secondes)
    partial_translate_interval: float = field(
        default_factory=lambda: float(os.getenv("PARTIAL_TRANSLATE_INTERVAL", "0.7"))
    )

    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8710")))


settings = Settings()
