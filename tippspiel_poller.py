from pathlib import Path

import requests

from bundesliga import upcoming_bundesliga_predictions
from champions_league import upcoming_champions_league_predictions
from tipico import TELEGRAM_CHAT_ID

TOKEN = Path(__file__).with_name("token").read_text().strip()
COMMANDS = {
    "/bl": upcoming_bundesliga_predictions,
    "/cl": upcoming_champions_league_predictions,
}


def run() -> None:
    """Reply to prediction commands received by the configured Telegram chat."""
    if not TOKEN:
        raise ValueError("Telegram bot token is empty.")

    offset = None
    while True:
        response = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 30},
            timeout=35,
        )
        response.raise_for_status()
        for update in response.json()["result"]:
            offset = update["update_id"] + 1
            message = update.get("message", {})
            if message.get("chat", {}).get("id") != TELEGRAM_CHAT_ID:
                continue
            predictions = COMMANDS.get(message.get("text", ""), lambda: "")()
            if predictions:
                response = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": predictions, "parse_mode": "HTML"},
                    timeout=30,
                )
                response.raise_for_status()


if __name__ == "__main__":
    run()
