import re
from datetime import datetime
from enum import Enum
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TIPICO_BASE = "https://sports.tipico.de"
BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")
TELEGRAM_CHAT_ID = 66421324
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class Outcome(Enum):
    HOME = "home"
    DRAW = "draw"
    AWAY = "away"


def upcoming_competition_urls(search_value: str, competition_id: int | None = None) -> list[str]:
    """Return URLs for the next calendar week's fixtures of a competition."""
    response = requests.get(
        f"{TIPICO_BASE}/v1/tpapi/sense/search",
        params={
            "language": "de",
            "searchValue": search_value,
            "flcChannel": "LICENSE_ONLINE",
            "flcLicenseId": "DE",
            "searchVersion": 0,
        },
        headers=API_HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    now = datetime.now(BERLIN_TIMEZONE)
    events = sorted(
        (
            event
            for event in response.json().get("events", {}).values()
            if competition_id is None or int(event.get("groupId") or 0) == competition_id
            and datetime.fromtimestamp(event["eventStartTime"] / 1000, BERLIN_TIMEZONE) >= now
        ),
        key=lambda event: event["eventStartTime"],
    )
    if not events:
        return []

    week = datetime.fromtimestamp(events[0]["eventStartTime"] / 1000, BERLIN_TIMEZONE).isocalendar()[:2]
    return [
        f"{TIPICO_BASE}/de/alle/fussball/event/{event['id']}"
        for event in events
        if datetime.fromtimestamp(event["eventStartTime"] / 1000, BERLIN_TIMEZONE).isocalendar()[:2] == week
    ]


def event_details(url: str) -> dict:
    """Return Tipico event details for an event URL."""
    match = re.search(r"/event/(\d+)", url)
    if not match:
        raise ValueError("The URL does not contain a Tipico event ID.")

    response = requests.get(
        f"{TIPICO_BASE}/v1/tpapi/programgateway/program/events/{match.group(1)}",
        headers=API_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def correct_score_odds(event: dict) -> dict[tuple[int, int], float]:
    """Return all full-time exact-score odds from Tipico event details."""
    result_ids = []
    for group_id, group in event.get("oddGroups", {}).items():
        if group.get("type") == "point-bet":
            result_ids.extend(event.get("oddGroupResultsMap", {}).get(str(group_id), []))

    odds = {}
    for result_id in result_ids:
        result = event.get("results", {}).get(str(result_id), {})
        score = result.get("caption", "")
        quote = result.get("quoteFloatValue")
        if re.fullmatch(r"\d+:\d+", score) and isinstance(quote, (int, float)):
            odds[tuple(map(int, score.split(":")))] = float(quote)
    return odds


def most_likely_outcome(odds: dict[tuple[int, int], float]) -> Outcome:
    """Return the most likely outcome from exact-score odds."""
    probabilities = {outcome: 0.0 for outcome in Outcome}
    for (home_goals, away_goals), odd in odds.items():
        if odd <= 0:
            raise ValueError("Exact-score odds must be positive.")
        outcome = Outcome.HOME if home_goals > away_goals else Outcome.AWAY if home_goals < away_goals else Outcome.DRAW
        probabilities[outcome] += 1 / odd

    if not any(probabilities.values()):
        raise ValueError("At least one positive exact-score odd is required.")
    return max(probabilities, key=lambda outcome: probabilities[outcome])


def most_likely_goal_difference(odds: dict[tuple[int, int], float], outcome: Outcome) -> int:
    """Return the most likely winning margin for an outcome."""
    if outcome is Outcome.DRAW:
        return 0

    probabilities: dict[int, float] = {}
    for (home_goals, away_goals), odd in odds.items():
        if odd <= 0:
            raise ValueError("Exact-score odds must be positive.")
        difference = home_goals - away_goals
        if (outcome is Outcome.HOME and difference > 0) or (outcome is Outcome.AWAY and difference < 0):
            margin = abs(difference)
            probabilities[margin] = probabilities.get(margin, 0.0) + 1 / odd

    if not probabilities:
        raise ValueError(f"No score odds available for {outcome.value} wins.")
    return max(probabilities, key=lambda margin: probabilities[margin])


def most_likely_exact_score(
    odds: dict[tuple[int, int], float], outcome: Outcome, difference: int
) -> tuple[int, int]:
    """Return the most likely score for an outcome and winning margin."""
    if difference < 0 or (outcome is Outcome.DRAW) != (difference == 0):
        raise ValueError("Draws require a zero margin; wins require a positive margin.")

    matching_odds = {
        score: odd
        for score, odd in odds.items()
        if odd > 0
        and abs(score[0] - score[1]) == difference
        and (
            outcome is Outcome.DRAW
            or (outcome is Outcome.HOME and score[0] > score[1])
            or (outcome is Outcome.AWAY and score[0] < score[1])
        )
    }
    if not matching_odds:
        raise ValueError("No score odds available for the requested outcome and margin.")
    return min(matching_odds, key=lambda score: matching_odds[score])


def format_team_name(name: str) -> str:
    """Format a team name for display."""
    parts = name.split()
    longest = max(map(len, parts), default=0)
    keep_longest = True
    formatted = []
    for part in reversed(parts):
        if not any(char.islower() for char in part):
            formatted.append(part)
        elif keep_longest and len(part) == longest:
            formatted.append(part)
            keep_longest = False
        else:
            formatted.append(part[0])
    return " ".join(part[:8] for part in reversed(formatted))[:12]


def upcoming_predictions(search_value: str, competition_id: int | None = None) -> str:
    """Return formatted exact-score predictions for a competition's next fixtures."""
    days: dict[str, dict[str, list[str]]] = {}
    for url in upcoming_competition_urls(search_value, competition_id):
        details = event_details(url)
        odds = correct_score_odds(details)
        if not odds:
            continue
        outcome = most_likely_outcome(odds)
        difference = most_likely_goal_difference(odds, outcome)
        home_goals, away_goals = most_likely_exact_score(odds, outcome, difference)
        event = details["event"]
        kickoff = datetime.fromtimestamp(event["eventStartTime"] / 1000, BERLIN_TIMEZONE)
        day = f"{WEEKDAYS[kickoff.weekday()]}, {kickoff:%d.%m.}"
        time = f"{kickoff:%H:%M} Uhr"
        home_team = format_team_name(event["team1"])
        away_team = format_team_name(event["team2"])
        days.setdefault(day, {}).setdefault(time, []).append(
            f"<code>{escape(home_team.rjust(12))}</code> {home_goals}\ufe0f\u20e3:{away_goals}\ufe0f\u20e3 <code>{escape(away_team.ljust(12))}</code>"
        )
    return "\n\n".join(
        "\n".join([f"<code>    {day}</code>", *(f"<code>        {time}</code>\n" + "\n".join(games) for time, games in times.items())])
        for day, times in days.items()
    )


def send_telegram_message(message: str) -> None:
    """Send a message to the configured Telegram chat."""
    token = Path(__file__).with_name("token").read_text().strip()
    if not token:
        raise ValueError("Telegram bot token is empty.")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=30,
    )
    response.raise_for_status()
