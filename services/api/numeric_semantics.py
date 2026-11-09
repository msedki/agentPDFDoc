"""Conservative operand-local qualifications for literal numeric evidence.

The recognizer does not solve inequalities or infer a maximum from a strict
bound. It prevents a written bound or non-equality becoming an exact operand.
Its finite English/French grammar is not a general entailment verifier.
"""

import re
import unicodedata

NONEXACT_SYMBOL_PREFIX = re.compile(r"(?:[<>]=?|[≤≥≠≈~]|!=|<>)\s*(?:\(|\[)?\s*$")
NONEXACT_PREFIX = re.compile(
    r"\b(?:less\s+than|greater\s+than|more\s+than|at\s+(?:most|least)|"
    r"no\s+(?:more|less)\s+than|up\s+to|below|above|under|over|"
    r"exceeds?|different\s+from|not\s+equal\s+to|"
    r"(?:inferieure?|superieure?)(?:\s+ou\s+egale?)?\s+a|"
    r"(?:plus|moins)\s+de|au\s+(?:plus|moins)(?:\s+de)?|"
    r"(?:differente?|distincte?)\s+de|depasse|excede|"
    r"n['’][a-z]+\s+(?:pas|plus|jamais)(?:\s+de)?)\s*(?:\(|\[)?\s*$"
)
NONEXACT_SUFFIX = re.compile(
    r"^\s*(?:\)|\])?\s*(?:or\s+(?:less|more|lower|higher|below|above)|"
    r"ou\s+(?:moins|plus)|au\s+(?:plus|moins)|max(?:imum)?|min(?:imum)?)\b"
)


def _fold(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(char))


def has_nonexact_numeric_modifier(prefix: str, suffix: str) -> bool:
    """Check the words/operators adjoining this operand, not other values.

    For example, ``3 V when TA < 85 °C`` qualifies the temperature condition,
    not the voltage. The complete source clause remains quoted by the caller.
    """
    # Unicode decomposition turns ≠ into '=' + an overlay. Check operators
    # before accent folding so the mathematical sign cannot be erased.
    return bool(NONEXACT_SYMBOL_PREFIX.search(prefix)
                or NONEXACT_PREFIX.search(_fold(prefix)) or NONEXACT_SUFFIX.search(_fold(suffix)))
