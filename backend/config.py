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
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Traduction des phrases finales : "claude" (LLM, rend l'argot par le sens)
    # ou "deepl" (comportement historique, gratuit).
    final_translator: str = field(default_factory=lambda: os.getenv("FINAL_TRANSLATOR", "claude"))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-haiku-4-5"))

    # Langues
    source_lang: str = field(default_factory=lambda: os.getenv("SOURCE_LANG", "fr"))
    target_lang: str = field(default_factory=lambda: os.getenv("TARGET_LANG", "EN-GB"))

    # STT
    deepgram_model: str = field(default_factory=lambda: os.getenv("DEEPGRAM_MODEL", "nova-2"))
    sample_rate: int = field(default_factory=lambda: int(os.getenv("SAMPLE_RATE", "16000")))
    # Silence (ms) avant de considérer la réplique terminée. Plus bas = sous-titres
    # plus réactifs, mais phrases plus souvent coupées en fragments.
    deepgram_endpointing: int = field(default_factory=lambda: int(os.getenv("DEEPGRAM_ENDPOINTING", "200")))

    # Traduire/afficher les partiels (ligne « live » qui s'écrit en continu).
    # Désactivé : chaque phrase s'affiche d'un bloc une fois la réplique terminée.
    translate_partials: bool = field(
        default_factory=lambda: os.getenv("TRANSLATE_PARTIALS", "false").lower() in ("1", "true", "yes")
    )

    # Fréquence max de traduction des résultats partiels (secondes)
    partial_translate_interval: float = field(
        default_factory=lambda: float(os.getenv("PARTIAL_TRANSLATE_INTERVAL", "0.7"))
    )

    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8710")))


settings = Settings()
