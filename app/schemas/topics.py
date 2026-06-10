from __future__ import annotations

from pydantic import BaseModel


class Topic(BaseModel):
    slug: str
    label: str
