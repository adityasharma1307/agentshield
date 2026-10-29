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


def _services() -> dict[str, dict[str, object]]:
    document = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services: dict[str, dict[str, object]] = document["services"]
    return services


def test_database_and_redis_publish_no_ports() -> None:
    services = _services()
    assert "ports" not in services["postgres"]
    assert "ports" not in services["redis"]


def test_every_published_port_binds_loopback_only() -> None:
    for name, service in _services().items():
        ports = service.get("ports", [])
        assert isinstance(ports, list)
        for port in ports:
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port}"


def test_passwords_come_from_the_environment_with_no_default() -> None:
    text = _COMPOSE.read_text(encoding="utf-8")
    services = _services()
    postgres_env = services["postgres"]["environment"]
    assert isinstance(postgres_env, dict)
    assert postgres_env["POSTGRES_PASSWORD"] == "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}"
    assert "${REDIS_PASSWORD:?set REDIS_PASSWORD}" in services["redis"]["command"]  # type: ignore[operator]
    assert "agentshield:agentshield@" not in text
    assert "POSTGRES_PASSWORD:-" not in text
    assert "REDIS_PASSWORD:-" not in text
