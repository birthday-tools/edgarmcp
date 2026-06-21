from dataclasses import dataclass

from .config import Settings
from .http_client import EdgarClient
from .quotes import TradernetClient
from .tickers import TickerResolver


@dataclass
class Context:
    client: EdgarClient
    resolver: TickerResolver
    settings: Settings
    tradernet: TradernetClient


def build_context(settings: Settings, client: EdgarClient, tradernet: TradernetClient | None = None) -> Context:
    resolver = TickerResolver(client, settings.tickers_url)
    return Context(client=client, resolver=resolver, settings=settings, tradernet=tradernet or TradernetClient())
