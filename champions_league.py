from tipico import send_telegram_message, upcoming_predictions

CHAMPIONS_LEAGUE_COMPETITION_ID = 2425910


def upcoming_champions_league_predictions() -> str:
    """Return predictions for the next Champions League matchweek."""
    return upcoming_predictions("Champions League", CHAMPIONS_LEAGUE_COMPETITION_ID)


if __name__ == "__main__":
    if predictions := upcoming_champions_league_predictions():
        send_telegram_message(predictions)
