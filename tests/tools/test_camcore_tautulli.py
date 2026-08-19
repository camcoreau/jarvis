"""Tests for privacy-preserving CamCore Tautulli activity."""

from __future__ import annotations

import json

import httpx

from openjarvis.tools.camcore_tautulli import CamCoreTautulliActivityTool


def test_tautulli_returns_aggregate_activity_without_viewer_or_media_identity(
    monkeypatch,
):
    monkeypatch.setenv("CAMCORE_TAUTULLI_URL", "http://tautulli:8181")
    monkeypatch.setenv("CAMCORE_TAUTULLI_API_KEY", "tautulli-secret")

    def get(url, **kwargs):
        assert url == "http://tautulli:8181/api/v2"
        assert kwargs["params"]["cmd"] == "get_activity"
        assert kwargs["params"]["apikey"] == "tautulli-secret"
        return httpx.Response(
            200,
            json={
                "response": {
                    "result": "success",
                    "data": {
                        "stream_count": "2",
                        "stream_count_transcode": "1",
                        "stream_count_direct_play": "1",
                        "stream_count_direct_stream": "0",
                        "stream_count_lan": "1",
                        "stream_count_wan": "1",
                        "total_bandwidth": "12000",
                        "lan_bandwidth": "4000",
                        "wan_bandwidth": "8000",
                        "sessions": [
                            {
                                "username": "private-user",
                                "friendly_name": "Private User",
                                "email": "private@example.com",
                                "ip_address": "192.168.5.55",
                                "full_title": "Private Movie Title",
                                "file": "/private/media/movie.mkv",
                                "media_type": "movie",
                                "transcode_decision": "direct play",
                                "state": "playing",
                            },
                            {
                                "username": "another-user",
                                "ip_address": "203.0.113.10",
                                "full_title": "Private Episode",
                                "file": "/private/media/show.mkv",
                                "media_type": "episode",
                                "transcode_decision": "transcode",
                                "state": "paused",
                            },
                        ],
                    },
                }
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", get)
    result = CamCoreTautulliActivityTool().execute()

    assert result.success is True
    payload = json.loads(result.content)
    assert payload["stream_count"] == 2
    assert payload["transcode_count"] == 1
    assert payload["direct_play_count"] == 1
    assert payload["media_types"] == {"episode": 1, "movie": 1}
    assert payload["transcode_decisions"] == {"direct play": 1, "transcode": 1}
    assert payload["session_states"] == {"paused": 1, "playing": 1}
    assert payload["privacy"] == "aggregate-only"

    forbidden = [
        "private-user",
        "another-user",
        "private@example.com",
        "192.168.5.55",
        "203.0.113.10",
        "Private Movie Title",
        "Private Episode",
        "/private/media",
        "tautulli-secret",
    ]
    for value in forbidden:
        assert value not in result.content


def test_tautulli_missing_api_key_fails_without_network_call(monkeypatch):
    monkeypatch.setenv("CAMCORE_TAUTULLI_URL", "http://tautulli:8181")
    monkeypatch.delenv("CAMCORE_TAUTULLI_API_KEY", raising=False)

    called = False

    def get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network should not be called")

    monkeypatch.setattr(httpx, "get", get)
    result = CamCoreTautulliActivityTool().execute()

    assert result.success is False
    assert "CAMCORE_TAUTULLI_API_KEY" in result.content
    assert called is False
