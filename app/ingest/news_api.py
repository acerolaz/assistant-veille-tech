from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings


@dataclass
class NewsApiIngester:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    def run(self, topics: list[str]) -> list[dict[str, Any]]:
        list_of_dico: list[dict[str, Any]] = []
        for topic in topics:
            list_of_dico.append({
                "id": f"{topic}-1",
                "title": "",
                "source": "",
                "date": "",
                "url": "",
                "content": ""
            })
        return list_of_dico
