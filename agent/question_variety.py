"""Broad question families: variants, seasons and different facts still conflict."""
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
    used=question_topics(fresh)
    candidates=[]; signatures=set()
    for row in bank:
        topics=frozenset(question_topics(row))
        if topics & used or topics in signatures: continue
        signatures.add(topics); candidates.append((row,topics))
    def search(start, chosen, seen):
        if len(chosen)==count:return chosen
        for i in range(start,len(candidates)):
            row,topics=candidates[i]
            if not topics & seen:
                result=search(i+1,chosen+[row],seen | topics)
                if result is not None:return result
        return None
    result=search(0,[],used)
    if result is None:
        raise RuntimeError("Not enough distinct question families; refusing a repetitive round")
    return result

def validate_round(rows):
    seen=set()
    for row in rows:
        topics=question_topics(row)
        if seen & topics:raise ValueError("Repeated question family: "+", ".join(sorted(seen & topics)))
        seen.update(topics)
