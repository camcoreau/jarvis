"""Deployment guardrails for CamCore live capability scope."""

from pathlib import Path


CONFIG = Path("deploy/camcore/config.toml")


def test_portainer_scope_is_docker_only():
    text = CONFIG.read_text(encoding="utf-8")

    assert "Portainer capability boundary:" in text
    assert "Docker-only live access" in text
    assert "Portainer does not provide Synology DSM host storage telemetry" in text
    assert "SMART data" in text
    assert "RAID/SHR state" in text
    assert "filesystem capacity/free space" in text


def test_drive_counts_must_not_imply_raid_layout():
    text = CONFIG.read_text(encoding="utf-8")

    assert "Never infer RAID/SHR configuration from drive counts" in text
    assert "report only the documented disk information" in text
