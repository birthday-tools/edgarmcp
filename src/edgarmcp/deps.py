from dataclasses import dataclass

from .config import Settings
from .http_client import EdgarClient
from .quotes import TradernetClient
from .telemetry import Telemetry
from .tickers import TickerResolver


@dataclass
class Context:
    client: EdgarClient
    resolver: TickerResolver
    settings: Settings
    tradernet: TradernetClient
    telemetry: Telemetry


def build_context(settings: Settings, client: EdgarClient, tradernet: TradernetClient | None = None) -> Context:
    resolver = TickerResolver(client, settings.tickers_url)
    telemetry = Telemetry(settings.telemetry_enabled, settings.telemetry_url, settings.cache_dir)
    telemetry.start()
    return Context(
        client=client,
        resolver=resolver,
        settings=settings,
        tradernet=tradernet or TradernetClient(),
        telemetry=telemetry,
    )
