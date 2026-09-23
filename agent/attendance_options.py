"""Create and migrate capacity-safe options for attendance questions."""
from __future__ import annotations

import hashlib
import json
import random
import re


MINIMUM_GAP = 1_000
ATTENDANCE_QUESTION = re.compile(
    r"\b(highest|lowest) home league attendance in (\d{4}-\d{2})\b", re.I
)


def attendance_options(correct: int, capacity_ceiling: int, seed: str) -> list[str]:
    """Return four options whose distractors are safe and at least 1,000 away.

    ``capacity_ceiling`` is the season's highest recorded home attendance.  It
    is deliberately more conservative than a stadium-capacity lookup: a real
    attendance cannot exceed the capacity of the ground used for that season.
    """
    correct = int(correct)
    capacity_ceiling = int(capacity_ceiling)
    if correct < 0 or capacity_ceiling < correct:
        raise ValueError("attendance ceiling must be at least the correct answer")

    candidates = []
    for distance in range(MINIMUM_GAP, max(correct, capacity_ceiling) + MINIMUM_GAP, MINIMUM_GAP):
        for value in (correct - distance, correct + distance):
            if 0 <= value <= capacity_ceiling and value != correct:
                candidates.append(value)
        if len(set(candidates)) >= 3:
            break
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) < 3:
        raise ValueError("not enough capacity-safe attendance distractors")

    chooser = random.Random(hashlib.sha256(seed.encode("utf-8")).digest())
    chooser.shuffle(candidates)
    options = [correct, *candidates[:3]]
    chooser = random.Random(hashlib.sha256((seed + "|shuffle").encode("utf-8")).digest())
    chooser.shuffle(options)
    return [str(value) for value in options]


def _number(value) -> int | None:
    text = str(value).replace(",", "").strip()
    return int(text) if text.isdigit() else None


def migrate_attendance_options(con) -> int:
    """Update every stored numeric highest/lowest attendance question.

    Rows are grouped by club and season.  The largest correct attendance in a
    group is used as the safe ceiling, so generated choices cannot exceed the
    capacity of the ground.  This updates bank and already-published questions
    in place because daily rounds reference the same question rows.
    """
    rows = con.execute(
        "SELECT id,club_id,question_text,options_json,correct_index "
        "FROM questions WHERE lower(question_text) LIKE '%home league attendance%'"
    ).fetchall()
    parsed = []
    ceilings = {}
    for row in rows:
        match = ATTENDANCE_QUESTION.search(row["question_text"])
        if not match:
            continue
        options = json.loads(row["options_json"])
        correct = _number(options[int(row["correct_index"])])
        if correct is None:
            continue  # Opponent-answer attendance questions are unchanged.
        key = (int(row["club_id"]), match.group(2))
        ceilings[key] = max(ceilings.get(key, 0), correct)
        parsed.append((row, key, correct))

    changed = 0
    for row, key, correct in parsed:
        options = attendance_options(correct, ceilings[key], f"stored|{row['id']}")
        payload = json.dumps(options, ensure_ascii=False)
        answer = options.index(str(correct))
        if payload != row["options_json"] or answer != int(row["correct_index"]):
            con.execute(
                "UPDATE questions SET options_json=?,correct_index=? WHERE id=?",
                (payload, answer, row["id"]),
            )
            changed += 1
    return changed
