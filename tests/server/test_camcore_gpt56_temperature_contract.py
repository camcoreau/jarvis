"""Regression contract for CamCore GPT-5.6 provider temperature policy."""

from openjarvis.server.camcore_portal_routes import _generation_temperature


def test_camcore_provider_temperature_policy():
    assert _generation_temperature("local") == 0.2
    assert _generation_temperature("openai") == 1.0
