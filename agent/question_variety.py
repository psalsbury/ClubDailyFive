"""Broad question families: variants, seasons and different facts still conflict."""
import re


def banned_question(row):
    text = row['question_text'].lower()
    return bool(re.search(r"which (?:team|side).*?(?:scored first|first to score|opening goal|first goal)", text))


def match_keys(row):
    """A club/date key joins matches across datasets and hashed bank variants.

    Conservative: two fixtures for the same club/date also conflict. Season
    aggregates and transfer dates are not individual match references.
    """
    row = dict(row)
    text = row['question_text'].lower()
    if row.get('semantic_key', '').startswith('seasonfact|'):
        return set()
    topics = question_topics(row)
    linked = bool(topics & {'high_scoring', 'match_score', 'first_goal', 'attendance', 'cups'})
    linked |= 'hat-trick' in text or 'sent off' in text
    linked |= 'cards' in text and 'match' in text
    linked |= 'ended' in text and 'run' in text
    if not linked:
        return set()
    date = row.get('fact_date')
    if not date:
        raise ValueError('Match question missing fact_date: ' + row['question_text'])
    return {str(date)}


def question_topics(row):
    text=row["question_text"].lower()
    topics=set()
    if "high-scoring" in text: topics.add("high_scoring")
    if "score" in text or "goals" in text:
        # Player scoring records are a separate family from match score questions.
        if any(x in text for x in ("goalscorer","goal scorer","hat-trick")):
            topics.add("player_scoring")
        elif any(x in text for x in ("how many goals","score in","score for","score when","final score")):
            topics.add("match_score")
    if "first goal" in text or "scored first" in text: topics.add("first_goal")
    if any(x in text for x in ("league wins","league draws","league losses")): topics.add("season_record")
    if "manager" in text: topics.add("managers")
    if "transfer" in text: topics.add("transfers")
    if "attendance" in text: topics.add("attendance")
    if any(x in text for x in ("yellow card","red card","yellow-card","red-card","sent off")):
        topics.add("discipline")
    if "run" in text and ("continuous" in text or "longest" in text): topics.add("runs")
    if any(x in text for x in ("how far","knocked","trophy","trophies")):
        topics.add("cups")
    if not topics:
        raise ValueError("Unclassified question type: "+row["question_text"])
    return topics

def select_varied(bank, fresh, count=4):
    if banned_question(fresh):
        raise ValueError('First-scoring team questions are prohibited')
    used = question_topics(fresh)
    matches = match_keys(fresh)
    candidates = []
    signatures = set()
    for row in bank:
        if banned_question(row):
            continue
        topics = frozenset(question_topics(row))
        keys = frozenset(match_keys(row))
        signature = (topics, keys)
        if topics & used or keys & matches or signature in signatures:
            continue
        signatures.add(signature)
        candidates.append((row, topics, keys))
    def search(start, chosen, seen, seen_matches):
        if len(chosen) == count:
            return chosen
        for i in range(start, len(candidates)):
            row, topics, keys = candidates[i]
            if not topics & seen and not keys & seen_matches:
                result = search(i + 1, chosen + [row], seen | topics, seen_matches | keys)
                if result is not None:
                    return result
        return None
    result = search(0, [], used, matches)
    if result is None:
        raise RuntimeError('No round satisfies question-family and match uniqueness')
    return result


def validate_round(rows):
    seen = set()
    matches = set()
    for row in rows:
        if banned_question(row):
            raise ValueError('First-scoring team questions are prohibited')
        topics = question_topics(row)
        keys = match_keys(row)
        if seen & topics:
            raise ValueError('Repeated question family: ' + ', '.join(sorted(seen & topics)))
        if matches & keys:
            raise ValueError('Repeated match: ' + ', '.join(sorted(matches & keys)))
        seen.update(topics)
        matches.update(keys)
