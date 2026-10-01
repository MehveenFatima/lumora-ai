"""
SM-2 spaced-repetition scheduling (Wozniak, 1990) for flashcard reviews.

Ratings map to SM-2 quality scores: again = 0, hard = 3, good = 4, easy = 5.
- "again" resets the card: it is due again today and its ease drops by 0.2.
- Successful reviews schedule 1 day, then 6 days, then interval x ease
  (x 1.2 instead of the ease for "hard", and an extra x 1.3 bonus for "easy").
- Ease is updated with the standard SM-2 formula and never falls below 1.3.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

RATING_QUALITY = {"again": 0, "hard": 3, "good": 4, "easy": 5}
MIN_EASE = 1.3


@dataclass
class ReviewSchedule:
    repetitions: int
    interval_days: int
    ease_factor: float
    due_date: date


def schedule_review(
    rating: str,
    repetitions: int = 0,
    interval_days: int = 0,
    ease_factor: float = 2.5,
    today: Optional[date] = None,
) -> ReviewSchedule:
    if rating not in RATING_QUALITY:
        raise ValueError(f"rating must be one of {sorted(RATING_QUALITY)}")
    today = today or date.today()
    q = RATING_QUALITY[rating]
    ease = max(MIN_EASE, ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))

    if q < 3:
        return ReviewSchedule(repetitions=0, interval_days=0, ease_factor=max(MIN_EASE, ease_factor - 0.2), due_date=today)

    if repetitions == 0:
        interval = 1
    elif repetitions == 1:
        interval = 6
    else:
        multiplier = 1.2 if rating == "hard" else ease
        interval = max(interval_days + 1, round(max(interval_days, 1) * multiplier))
    if rating == "easy":
        interval = max(interval + 1, round(interval * 1.3))

    return ReviewSchedule(
        repetitions=repetitions + 1,
        interval_days=interval,
        ease_factor=round(ease, 4),
        due_date=today + timedelta(days=interval),
    )
