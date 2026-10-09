"""Recommendation engine: skill matching, scoring and skill-gap analysis.

Match Score = (Matched Skills / Required Skills) * 100
"""
from collections import Counter


def normalize_skills(text):
    """Turn 'python, SQL ,  machine learning' into a clean, de-duplicated list."""
    seen, out = set(), []
    for part in (text or "").replace("\n", ",").replace(";", ",").split(","):
        name = " ".join(part.strip().split())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def match_score(student_skills, required_skills):
    """Return (score_percent, matched_list, missing_list)."""
    have = {s.lower() for s in student_skills}
    matched = [s for s in required_skills if s.lower() in have]
    missing = [s for s in required_skills if s.lower() not in have]
    score = round(len(matched) / len(required_skills) * 100) if required_skills else 0
    return score, matched, missing


def recommend(student_skills, internships, preferred_domain=None, location=None,
              duration=None, min_score=0):
    """Score every internship for a student and return them best-first.

    `internships` is a list of dicts with keys: id, title, company, domain,
    location, duration, stipend, description, skills (list[str]).
    Domain/location/duration preferences are used as tie-breakers so that the
    displayed score always follows the plain skill-match formula.
    """
    results = []
    for it in internships:
        score, matched, missing = match_score(student_skills, it["skills"])
        if score < min_score:
            continue
        domain_hit = bool(preferred_domain) and it["domain"].lower() == preferred_domain.lower()
        loc_hit = bool(location) and it["location"].lower() in (location.lower(), "remote")
        dur_hit = bool(duration) and str(it["duration"]) == str(duration)
        results.append({
            **it,
            "score": score,
            "matched": matched,
            "missing": missing,
            "pref_points": int(domain_hit) * 4 + int(loc_hit) * 2 + int(dur_hit),
            "domain_match": domain_hit,
        })
    results.sort(key=lambda r: (-r["score"], -r["pref_points"], r["title"]))
    return results


def skill_gap(student_skills, internships, target_domain=None, top_n=8):
    """Find which missing skills would unlock the most internships.

    Looks at internships in the target domain (or all if none given) and
    counts how often each missing skill appears.
    """
    pool = [i for i in internships
            if not target_domain or i["domain"].lower() == target_domain.lower()]
    counter = Counter()
    for it in pool:
        _, _, missing = match_score(student_skills, it["skills"])
        counter.update(missing)
    return counter.most_common(top_n), len(pool)
