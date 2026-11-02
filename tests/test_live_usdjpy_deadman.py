"""Dead-man switch pings (2026-11-01). No network: fake GET and fake Keychain. The URL never appears in the result."""
from datetime import datetime, timezone

from src.live_usdjpy import deadman as DM

NOW = datetime(2026, 11, 2, 15, 2, tzinfo=timezone.utc)
URLS = {"trading-research-deadman-url": "https://hc-ping.com/11111111-2222-3333-4444-555555555555",
        "trading-research-deadman-url-weekday": "https://hc-ping.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}


class R:
    def __init__(self, code=200, text="OK"):
        self.status_code, self.text = code, text


def test_success_ping_hits_both_checks_and_never_returns_the_url():
    calls = []
    out = DM.ping(NOW, True, lambda u, timeout=None: calls.append(u) or R(), URLS.get)
    assert out["always"] == "ok" and out["weekday"] == "ok" and sorted(calls) == sorted(URLS.values())
    assert not any("hc-ping" in str(v) for v in out.values())


def test_fail_variant_after_a_run_error():
    calls = []
    out = DM.ping(NOW, False, lambda u, timeout=None: calls.append(u) or R(), URLS.get)
    assert all(c.endswith("/fail") for c in calls) and out["always"] == "fail sent"


def test_not_configured_unknown_check_timeout_and_foreign_host_never_raise():
    assert DM.ping(NOW, True, lambda u, timeout=None: R(), lambda k: None)["always"] == "not configured"
    assert "not found" in DM.ping(NOW, True, lambda u, timeout=None: R(404, "not found"), URLS.get)["always"]

    def boom(u, timeout=None):
        raise TimeoutError()
    assert DM.ping(NOW, True, boom, URLS.get)["weekday"] == "failed: TimeoutError"
    calls = []
    out = DM.ping(NOW, True, lambda u, timeout=None: calls.append(u) or R(),
                  {"trading-research-deadman-url": "https://evil.example.com/x"}.get)
    assert out["always"].startswith("refused") and calls == []
