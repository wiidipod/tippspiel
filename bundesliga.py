from tipico import send_telegram_message, upcoming_predictions

BUNDESLIGA_COMPETITION_ID = 42301


def upcoming_bundesliga_predictions() -> str:
    """Return predictions for the next Bundesliga matchweek."""
    return upcoming_predictions("Bundesliga", BUNDESLIGA_COMPETITION_ID)


if __name__ == "__main__":
    if predictions := upcoming_bundesliga_predictions():
        send_telegram_message(predictions)
