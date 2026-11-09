"""Literal predicate conditions on numeric requests, without paraphrase.

Named numeric points retain their existing Decimal grammar. A written verbal
condition must occur with positive polarity in the source; an exact exclusion
vetoes it. No synonym, entity inference or model decision is used here.
"""

import re
import unicodedata
from typing import Any

from .point_conditions import condition_measures

CONNECTOR = re.compile(
    r"\b(?P<marker>except\s+(?:when|if)|sauf\s+(?:lorsque|quand|si)|unless|"
    r"when|if|lorsque|quand|si|[àa]\s+condition\s+que)\s+", re.IGNORECASE)


def predicate_conditions(text):
    """Return exact non-point condition clauses and their explicit polarity."""
    markers = list(CONNECTOR.finditer(text))
    result: list[dict[str, Any]] = []
    excluded_scope = False
    for index, marker in enumerate(markers):
        negative = marker["marker"].casefold().startswith(("unless", "except", "sauf"))
        # Even an empty or point-only clause retains the governing exclusion.
        # It must not turn a following nested marker into positive evidence.
        if index and excluded_scope and not re.search(r";|[!?]|(?<!\d)\.(?!\d)", text[markers[index - 1].end():marker.start()]):
            negative = True
        excluded_scope = negative
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        clause = re.split(r"(?<!\d)[;,](?!\d)|\n", text[marker.end():end], maxsplit=1)[0].strip(" ,;.?!")
        if not clause:
            continue
        remaining = list(clause)
        for point in [*condition_measures(clause), *condition_measures(clause, excluded=True)]:
            remaining[point["start"]:point["end"]] = " " * (point["end"] - point["start"])
        if not re.sub(r"\b(?:and|or|et|ou|at|a|à)\b", " ", "".join(remaining), flags=re.IGNORECASE).strip(" ,;()[]"):
            continue
        key = " ".join(unicodedata.normalize("NFKC", clause).casefold().replace("’", "'").split())
        result.append({"text": clause, "key": key, "excluded": negative})
    return result


def predicates_established(condition, requested):
    if not requested:
        return True
    available = predicate_conditions(condition)
    positive = {item["key"] for item in available if not item["excluded"]}
    excluded = {item["key"] for item in available if item["excluded"]}
    # Different verbal states are not proved mutually exclusive by different
    # spelling. An additional verbal exception keeps applicability unresolved.
    return not excluded and all(not item["excluded"] and item["key"] in positive for item in requested)
