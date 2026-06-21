from edgarmcp.config import Settings


def test_defaults_when_env_absent(monkeypatch):
    for key in ("EDGAR_USER_AGENT", "EDGAR_RATE_LIMIT", "EDGAR_CACHE_DIR"):
        monkeypatch.delenv(key, raising=False)
    s = Settings.from_env()
    assert s.user_agent == "EdgarMCP/0.1 (contact: info+sec@birthday.tools)"
    assert s.rate_limit_per_sec == 10.0
    assert s.cache_dir == "edgar_cache"
    assert s.base_data == "https://data.sec.gov"
    assert s.base_www == "https://www.sec.gov"
    assert s.tickers_url == "https://www.sec.gov/files/company_tickers.json"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("EDGAR_USER_AGENT", "Custom/1.0 (a@b.com)")
    monkeypatch.setenv("EDGAR_RATE_LIMIT", "5")
    monkeypatch.setenv("EDGAR_CACHE_DIR", "/tmp/c")
    s = Settings.from_env()
    assert s.user_agent == "Custom/1.0 (a@b.com)"
    assert s.rate_limit_per_sec == 5.0
    assert s.cache_dir == "/tmp/c"


def test_fred_and_allowlist_defaults(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    s = Settings.from_env()
    assert s.base_fred == "https://api.stlouisfed.org"
    assert s.fred_api_key == ""
    assert "www.sec.gov" in s.allowed_hosts
    assert "data.sec.gov" in s.allowed_hosts
    assert "api.stlouisfed.org" in s.allowed_hosts


def test_fred_api_key_from_env(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "abc123")
    assert Settings.from_env().fred_api_key == "abc123"


def test_telemetry_defaults_off(monkeypatch):
    monkeypatch.delenv("EDGAR_TELEMETRY", raising=False)
    monkeypatch.delenv("EDGAR_TELEMETRY_URL", raising=False)
    s = Settings.from_env()
    assert s.telemetry_enabled is False
    assert s.telemetry_url == "https://t.birthday.tools/v1/events"


def test_telemetry_enabled_from_env(monkeypatch):
    monkeypatch.setenv("EDGAR_TELEMETRY", "YES")
    monkeypatch.setenv("EDGAR_TELEMETRY_URL", "https://example/collect")
    s = Settings.from_env()
    assert s.telemetry_enabled is True
    assert s.telemetry_url == "https://example/collect"
