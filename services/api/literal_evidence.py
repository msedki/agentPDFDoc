"""Bounded literal intervals; no generated documentary text or inferred facts.

An interval may be shortened only at an observed sentence/clause boundary. An
explicit continuation, exception or restriction remains in its envelope. The
caller still establishes the requested relation and source quality separately.
"""

import re

from .point_conditions import condition_measures

CONTINUATION = re.compile(
    r"^(?:this|that|these|those|such|it|they|its|their|however|except|unless|otherwise|"
    r"provided\s+that|only\s+(?:when|if|at)|note\b|ce(?:tte|s)?|cela|ceci|il|elle|ils|elles|"
    r"ces\s+valeurs|cette\s+plage|toutefois|cependant|sauf|sinon|uniquement|seulement|"
    r"à\s+condition|see\s+(?:section|note|table|figure)|voir\s+(?:la\s+)?(?:section|note|tableau|figure))\b", re.IGNORECASE)

APPOSITIVE = re.compile(r",\s*(?:facilitating|enabling|allowing|facilitant|permettant)\b", re.IGNORECASE)
RESTRICTION = re.compile(
    r"\b(?:only|except|unless|provided|when|if|at|under|without|but|while|above|below|up\s+to|"
    r"subject\s+to|seulement|uniquement|sauf|si|lorsque|quand|sous|sans|mais|condition|conditions)\b|[<>=±]",
    re.IGNORECASE)

# A literal repeated nominal subject can carry a restriction without an
# anaphoric connector ("The output current ... The output current is not ...").
# This bounded grammar neither equates different names/properties nor resolves
# a pronoun or an omitted subject. Preserve the source text, not a paraphrase.
SUBJECT_PREDICATE = re.compile(
    r"^(?P<subject>[^\n:;.!?]{1,160}?)(?:\s+(?:is|are|was|were|has|have|had|"
    r"must|may|can|shall|will|est|sont|sera|seront|reste|restent|n['’]est)\b|\s*:)",
    re.IGNORECASE)
NEGATION = re.compile(r"\b(?:not|never|no|ne|pas|jamais|aucun|aucune)\b", re.IGNORECASE)
LOCAL_NEGATION = re.compile(
    r"\s*(?:(?:not|never)\s+(?:established|specified|guaranteed|defined|available|known|valid)|"
    r"(?:pas|jamais|non)\s+(?:[ée]tablie?|sp[ée]cifi[ée]e?|garantie?|d[ée]finie?|disponible|connue?|valide))\s*",
    re.IGNORECASE)
FINAL_NAMED_CONTEXT = re.compile(
    r"\b(?:for|pour)\s+(?P<name>[A-Za-z][A-Za-z0-9_+-]*\d[A-Za-z0-9_+-]*)\s*[.!]?\s*$",
    re.IGNORECASE)


def _disjoint_local_restriction(anchor, following, predicate_start):
    """Do not apply an explicitly point-local negation at a different point.

    Only one exact terminal point and a plain negative predicate establish this
    exception. Exclusive words, ranges, multiple points, extra qualifications or
    different variable names never prove disjointness. Unit equality uses the
    same Decimal grammar as the obligations; no value is rewritten for display.
    An explicit terminal named context is compared literally by the same rule.
    """
    first_points, second_points = condition_measures(anchor), condition_measures(following)
    if len(first_points) == len(second_points) == 1:
        first, second = first_points[0], second_points[0]
        if (not anchor[first["end"]:].strip(" .!?") and not following[second["end"]:].strip(" .!?")
                and LOCAL_NEGATION.fullmatch(following[predicate_start:second["start"]])
                and (first["quantity"], first["symbol"], first["aliases"])
                == (second["quantity"], second["symbol"], second["aliases"])
                and first["value"] != second["value"]):
            return True
    first_name, second_name = FINAL_NAMED_CONTEXT.search(anchor), FINAL_NAMED_CONTEXT.search(following)
    return bool(first_name and second_name and first_name["name"].casefold() != second_name["name"].casefold()
                and LOCAL_NEGATION.fullmatch(following[predicate_start:second_name.start()]))


def _repeated_subject_restriction(anchor, following):
    first, second = SUBJECT_PREDICATE.match(anchor), SUBJECT_PREDICATE.match(following)
    if first is None or second is None:
        return False
    first_subject = " ".join(first["subject"].casefold().split())
    second_subject = " ".join(second["subject"].casefold().split())
    predicate = following[second.end():]
    return bool(first_subject and first_subject == second_subject
                and not _disjoint_local_restriction(anchor, following, second.end())
                and (NEGATION.search(predicate) or RESTRICTION.search(predicate)))


def nonrestrictive_tail_start(line, after):
    """Locate an explicit consequence incise, never a condition or exception.

    The caller must also rule out a following dependent sentence. This finite
    grammar neither summarizes the tail nor asserts that arbitrary prose is
    independent; unknown connectors and conditional language remain intact.
    """
    match = APPOSITIVE.search(line, after)
    if match is not None and RESTRICTION.search(line[match.end():]) is None:
        return match.start()
    return len(line)


def sentence_spans(text):
    """Keep original offsets and punctuation; decimal points are never splits."""
    start = 0
    for match in re.finditer(r"\n+|(?<=[.!?])\s+(?=[A-ZÀ-Þ])", text):
        end = match.start()
        if text[start:end].strip():
            low = start + len(text[start:end]) - len(text[start:end].lstrip())
            high = end - len(text[start:end]) + len(text[start:end].rstrip())
            yield low, high, text[low:high]
        start = match.end()
    if text[start:].strip():
        low = start + len(text[start:]) - len(text[start:].lstrip())
        high = len(text.rstrip())
        yield low, high, text[low:high]


def proof_envelope(text, start, end, subjects=()):
    """Preserve explicitly dependent following sentences and a short identity.

    This grammar does not assert general paragraph independence. Unknown
    qualitative questions retain their original passages in the audit catalogue
    with an unassessed status. Recognized relations supply their exact span.
    """
    sentences = list(sentence_spans(text))
    position = next((index for index, (low, high, _) in enumerate(sentences)
                     if low <= start <= end <= high), None)
    if position is None:
        return start, end
    if position:
        low, high, previous = sentences[position - 1]
        if (any(re.fullmatch(r"(?:Composant|Component)?\s*" + re.escape(subject) + r"\s*[.!]?",
                            previous, re.IGNORECASE) for subject in subjects)
                or re.fullmatch(r"(?:Composant|Component)\s+[A-Za-z][A-Za-z0-9_+\-]*\d[A-Za-z0-9_+\-]*\s*[.!]?",
                                previous, re.IGNORECASE)):
            start = low
    anchor = sentences[position][2]
    for low, high, following in sentences[position + 1:]:
        repeated_limit = (not re.search(r"\n\s*\n", text[end:low])
                          and _repeated_subject_restriction(anchor, following))
        if not CONTINUATION.match(following) and not repeated_limit:
            break
        end = high
    return start, end


def exact_intervals(text, literal):
    if not literal:
        return []
    return [(match.start(), match.end()) for match in re.finditer(re.escape(literal), text)]


def merged_spans(spans, text):
    result: list[tuple[int, int]] = []
    for low, high in sorted(set(spans)):
        if type(low) is not int or type(high) is not int or not 0 <= low < high <= len(text):
            raise ValueError("invalid literal publication interval")
        if result and (low <= result[-1][1] or not text[result[-1][1]:low].strip()):
            result[-1] = (result[-1][0], max(high, result[-1][1]))
        else:
            result.append((low, high))
    return [{"start_offset": low, "end_offset": high} for low, high in result]


def projected_text(reference, spans):
    text = reference["text"]
    checked = merged_spans([(item["start_offset"], item["end_offset"]) for item in spans], text)
    if checked != spans:
        raise ValueError("noncanonical literal publication intervals")
    return " […] ".join(text[item["start_offset"]:item["end_offset"]] for item in spans)
