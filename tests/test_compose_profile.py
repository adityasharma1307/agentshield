"""The Jaeger service stays behind the debug profile. Tests do not start Docker."""

from pathlib import Path

import yaml

_COMPOSE = Path(__file__).resolve().parents[1] / "docker" / "compose.yaml"


def test_jaeger_is_not_started_without_the_debug_profile() -> None:
    document = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services = document["services"]
    jaeger = services["jaeger"]
    assert jaeger["profiles"] == ["debug"]
    assert jaeger["image"].startswith("jaegertracing/all-in-one:")
