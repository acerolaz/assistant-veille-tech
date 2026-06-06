from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Scraper:
    user_agent: str = "nauda-palisse-veille/0.1"
    timeout: float = 10.0

    def run(self, urls: list[str]) -> list[dict[str, Any]]:
        list_of_dico: list[dict[str, Any]] = []
        for url in urls:
            list_of_dico.append({
                "title": "",
                "source": "",
                "url": url,
                "content": ""
            })
        return list_of_dico
