"""Language registry, loaded from languages/<id>/config.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

LANGUAGES_DIR = Path(__file__).resolve().parent.parent / "languages"


@dataclass(frozen=True)
class Language:
    id: str
    display_name: str
    image: str
    source_file: str
    run: list[str]
    compile: list[str] | None = None
    prepare: list[str] | None = None
    time_multiplier: float = 1
    extra_memory_mb: int = 0
    template: str = ""


@lru_cache
def load_languages(directory: Path = LANGUAGES_DIR) -> dict[str, Language]:
    languages = {}
    for config in sorted(directory.glob("*/config.yaml")):
        data = yaml.safe_load(config.read_text())
        languages[config.parent.name] = Language(id=config.parent.name, **data)
    return languages


def get_language(language_id: str) -> Language:
    languages = load_languages()
    if language_id not in languages:
        raise KeyError(f"unsupported language: {language_id}")
    return languages[language_id]
