import re

import requests

TIPICO_BASE = "https://sports.tipico.de"
API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def tipico_correct_score_odds(url: str) -> dict[str, float]:
    """Return all full-time exact-score odds for a Tipico event URL."""
    match = re.search(r"/event/(\d+)", url)
    if not match:
        raise ValueError("The URL does not contain a Tipico event ID.")

    response = requests.get(
        f"{TIPICO_BASE}/v1/tpapi/programgateway/program/events/{match.group(1)}",
        headers=API_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    event_details = response.json()

    result_ids = []
    for group_id, group in event_details.get("oddGroups", {}).items():
        if group.get("type") == "point-bet":
            result_ids.extend(
                event_details.get("oddGroupResultsMap", {}).get(str(group_id), [])
            )

    odds = {}
    for result_id in result_ids:
        result = event_details.get("results", {}).get(str(result_id), {})
        score = result.get("caption", "")
        quote = result.get("quoteFloatValue")
        if re.fullmatch(r"\d+:\d+", score) and isinstance(quote, (int, float)):
            odds[score] = float(quote)

    return odds


if __name__ == "__main__":
    url = "https://sports.tipico.de/de/alle/fussball/deutschland/event/724236010?mode=ql&t=match&eventPanelMode=2"
    print(tipico_correct_score_odds(url))
