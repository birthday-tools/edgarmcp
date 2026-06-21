import re
from urllib.parse import urlencode

from .http_client import EdgarClient, EdgarHTTPError


def _redact(msg: str) -> str:
    return re.sub(r"(api_key=)[^&\s]+", r"\1REDACTED", msg)


class MissingApiKey(Exception):
    pass


class FredError(Exception):
    pass


def _fred_get(client: EdgarClient, base_fred: str, api_key: str, path: str, params: dict) -> dict:
    if not api_key:
        raise MissingApiKey(
            "FRED_API_KEY is required (free key: https://fred.stlouisfed.org/docs/api/api_key.html)"
        )
    query = dict(params)
    query["api_key"] = api_key
    query["file_type"] = "json"
    url = f"{base_fred}/fred/{path}?{urlencode(query)}"
    # Macro data is mutable (revised/extended) — do not cache, unlike filings.
    try:
        data = client.get_json(url, use_cache=False)
    except EdgarHTTPError as e:
        raise FredError(_redact(str(e))) from None
    if not isinstance(data, dict):
        raise FredError("unexpected FRED response (not a JSON object)")
    if isinstance(data, dict) and data.get("error_message"):
        raise FredError(data["error_message"])
    return data


def _parse_value(raw) -> float | None:
    if raw is None or raw in (".", ""):
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def get_latest_observation(client: EdgarClient, base_fred: str, api_key: str, series_id: str) -> dict | None:
    data = _fred_get(
        client, base_fred, api_key, "series/observations",
        {"series_id": series_id, "sort_order": "desc", "limit": 1},
    )
    obs = data.get("observations", [])
    if not obs:
        return None
    o = obs[0]
    return {"date": o.get("date", ""), "value": _parse_value(o.get("value"))}


def get_macro_series(
    client: EdgarClient,
    base_fred: str,
    api_key: str,
    series_id: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    meta = _fred_get(client, base_fred, api_key, "series", {"series_id": series_id})
    series_list = meta.get("seriess") or [{}]
    s = series_list[0]

    obs_params: dict = {"series_id": series_id}
    if start:
        obs_params["observation_start"] = start
    if end:
        obs_params["observation_end"] = end
    obs_data = _fred_get(client, base_fred, api_key, "series/observations", obs_params)

    observations = [
        {"date": o.get("date", ""), "value": _parse_value(o.get("value"))}
        for o in obs_data.get("observations", [])
    ]
    return {
        "series_id": series_id,
        "title": s.get("title"),
        "units": s.get("units"),
        "frequency": s.get("frequency"),
        "observations": observations,
        "count": len(observations),
    }
