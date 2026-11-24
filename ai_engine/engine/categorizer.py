"""
Transparent, rule-based expense auto-categoriser.

Each category carries a comma-separated keyword list (editable in the admin).
The description is lower-cased and tokenised; the category with the most
keyword hits wins. Ties and zero hits return None so the student chooses.

A rule-based approach is used deliberately: with a handful of records per
student there is not enough labelled data to train a reliable text
classifier, and rules are easy to explain during a project defence.
"""
import re

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenise(text):
    return TOKEN_RE.findall((text or "").lower())


def score_categories(description, categories):
    """Return a list of (category, hits) sorted by hits descending."""
    text = " " + " ".join(tokenise(description)) + " "
    scored = []
    for category in categories:
        keywords = [k.strip().lower() for k in (category.keywords or "").split(",") if k.strip()]
        hits = 0
        for keyword in keywords:
            # match whole words or multi-word phrases
            if f" {' '.join(tokenise(keyword))} " in text:
                hits += 1
        if hits:
            scored.append((category, hits))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def suggest_category(description, categories):
    scored = score_categories(description, categories)
    if not scored:
        return None
    if len(scored) > 1 and scored[0][1] == scored[1][1]:
        return None  # ambiguous: let the student decide
    return scored[0][0]
