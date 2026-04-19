import json

from refund_demo.config import AppConfig
from refund_demo.providers import HeuristicProvider, build_provider


def test_config_defaults_to_heuristic_provider():
    config = AppConfig.from_env({})

    assert config.model_provider == "heuristic"
    assert config.consistency_on_violation == "raise"


def test_provider_factory_builds_default_provider():
    provider = build_provider(AppConfig.from_env({}))

    assert isinstance(provider, HeuristicProvider)


def test_heuristic_provider_returns_json_for_intake():
    provider = HeuristicProvider()

    raw = provider.complete(
        system="Extract refund JSON",
        user="Customer says damaged item",
        json_mode=True,
    )

    payload = json.loads(raw)
    assert payload["intent"] == "refund_request"
    assert payload["reason"] == "damaged item"
