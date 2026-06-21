import os
from dataclasses import dataclass

DEFAULT_USER_AGENT = "EdgarMCP/0.1 (contact: info+sec@birthday.tools)"


@dataclass(frozen=True)
class Settings:
    user_agent: str
    rate_limit_per_sec: float
    cache_dir: str
    base_data: str
    base_www: str
    tickers_url: str
    base_fred: str
    fred_api_key: str
    base_figi: str
    openfigi_api_key: str
    telemetry_enabled: bool
    telemetry_url: str
    allowed_hosts: frozenset[str]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            user_agent=os.environ.get("EDGAR_USER_AGENT", DEFAULT_USER_AGENT),
            rate_limit_per_sec=float(os.environ.get("EDGAR_RATE_LIMIT", "10")),
            cache_dir=os.environ.get("EDGAR_CACHE_DIR", "edgar_cache"),
            base_data="https://data.sec.gov",
            base_www="https://www.sec.gov",
            tickers_url="https://www.sec.gov/files/company_tickers.json",
            base_fred="https://api.stlouisfed.org",
            fred_api_key=os.environ.get("FRED_API_KEY", ""),
            base_figi="https://api.openfigi.com",
            openfigi_api_key=os.environ.get("OPENFIGI_API_KEY", ""),
            telemetry_enabled=os.environ.get("EDGAR_TELEMETRY", "").strip().lower() in {"1", "true", "yes", "on"},
            telemetry_url=os.environ.get("EDGAR_TELEMETRY_URL", "https://t.birthday.tools/v1/events"),
            allowed_hosts=frozenset({"www.sec.gov", "data.sec.gov", "api.stlouisfed.org", "api.openfigi.com"}),
        )
