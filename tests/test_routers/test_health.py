from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_topics_returns_popular_list(client: TestClient) -> None:
    r = client.get("/topics")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    labels = {t["label"] for t in data}
    assert {"Python", "JavaScript", "AI/ML", "DevOps", "CSharp"} <= labels
