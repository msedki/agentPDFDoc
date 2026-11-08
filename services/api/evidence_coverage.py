"""Bounded, monotonic selection of independently verified quantitative evidence.

The same literal relation contract is used here and at publication. Ranking is
only a tie breaker: it cannot establish a fact. A swap must preserve every
already covered relation, requested identifier and comparison document. This
bounded greedy search does not claim a globally optimal set cover.
"""

import json
from typing import Any

from .structured_answer import StructuredAnswerBuilder

REVISION = "verified-property-coverage-v1"
MAX_CANDIDATES = 48


def _relation_key(fact):
    fields = ("document_id", "version_id", "subjects", "property", "quantity", "values", "unit",
              "condition", "role", "bound_role", "assertion_status")
    return json.dumps({key: fact.get(key) for key in fields}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _matches_obligation(fact, support, obligation):
    return (support <= set(obligation["reference_ids"])
            and (obligation.get("document_id") is None or obligation["document_id"] == fact["document_id"])
            and (obligation.get("subject") is None or obligation["subject"] in fact.get("subjects", []))
            and (obligation.get("property") is None or obligation["property"] == fact.get("property")))


def select_evidence_coverage(db, snapshot, question, mode, candidates, selected, maximum, references):
    """Return authorized sources, notices and a diagnostic; never source text.

    Candidates are already retrieved and scope-filtered. Their provenance is
    checked again by the real catalogue builder before any coverage is credited.
    Alternative occurrences of one identical relation may replace each other;
    different conditions, values or document versions remain separate obligations.
    """
    from .retrieval import evidence_identity

    diagnostic: dict[str, Any] = {"revision": REVISION, "maximum_fragments": maximum,
                                  "scope": "retrieved_candidates_only", "status": "not_applicable"}
    if not selected or snapshot.spans or snapshot.scope["kind"] in {"selection", "cell_range"}:
        return selected, [], diagnostic
    pool: list[dict[str, Any]] = []
    positions: dict[tuple, int] = {}
    for source in candidates:
        identity = evidence_identity(source)
        if identity not in positions:
            positions[identity] = len(pool)
            pool.append(source)
        if len(pool) >= MAX_CANDIDATES:
            break
    # A configured larger upstream pool must not silently evict an original
    # mandatory source which lies beyond this bounded verifier's window.
    if any(evidence_identity(source) not in positions for source in selected):
        diagnostic["status"] = "original_selection_outside_verification_window"
        return selected, [], diagnostic
    original = {positions[evidence_identity(source)] for source in selected}
    identified = [{**source, "source_id": f"C{index:03d}"} for index, source in enumerate(pool)]
    catalogue = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(identified, mode)
    documents = tuple(dict.fromkeys(snapshot.documents.values())) if mode == "comparison" else ()
    assessment = catalogue.assess(required_documents=documents)
    obligations = [item for item in assessment.get("obligations", []) if item.get("quantity")]
    if not obligations:
        return selected, [], diagnostic
    refs_by_source: dict[int, set[str]] = {index: set() for index in range(len(pool))}
    for reference in catalogue.references:
        for source_id in reference["source_ids"]:
            refs_by_source[int(source_id[1:])].add(reference["id"])
    atoms: dict[str, list[frozenset[str]]] = {}
    obligation_atoms: list[set[str]] = [set() for _ in obligations]
    for fact in assessment.get("matched_relations", []):
        if not fact.get("quantity") or not fact.get("values"):
            continue
        support = frozenset(fact.get("reference_ids", [fact["reference_id"]]))
        matching = [index for index, obligation in enumerate(obligations)
                    if _matches_obligation(fact, support, obligation)]
        if not matching:
            continue
        key = _relation_key(fact)
        alternatives = atoms.setdefault(key, [])
        if support not in alternatives:
            alternatives.append(support)
        for index in matching:
            obligation_atoms[index].add(key)

    def source_references(indices):
        return set().union(*(refs_by_source[index] for index in indices)) if indices else set()

    def covered_atoms(indices):
        visible = source_references(indices)
        return {key for key, alternatives in atoms.items() if any(support <= visible for support in alternatives)}

    identifier_features = {index: {code for code in references.priority if references.source_matches(source, code)}
                           for index, source in enumerate(pool)}

    def identifiers_at(indices):
        return set().union(*(identifier_features[index] for index in indices)) if indices else set()

    protected_identifiers = identifiers_at(original)
    protected_documents = {pool[index]["document_id"] for index in original} if mode == "comparison" else set()

    def protected(indices, required_atoms):
        return (required_atoms <= covered_atoms(indices)
                and protected_identifiers <= identifiers_at(indices)
                and protected_documents <= {pool[index]["document_id"] for index in indices})

    def support_group(support, retained, available=None) -> set[int] | None:
        # Greedy cover of exact reference dependencies, bounded by 48 sources.
        remaining = set(support) - source_references(retained)
        additions: set[int] = set()
        while remaining:
            choices = [(len(remaining & ids), -index, index) for index, ids in refs_by_source.items()
                       if index not in retained | additions and (available is None or index in available)]
            if not choices or max(choices)[0] == 0:
                return None
            index = max(choices)[2]
            additions.add(index)
            remaining -= refs_by_source[index]
        return additions

    retained = set(original)
    initial_atoms = covered_atoms(original)
    # Missing properties/documents first, then additional explicit conditions or
    # conflicting variants. Ties retain upstream rank, never model preference.
    ordered_atoms = list(atoms)
    atom_rank = {key: index for index, key in enumerate(ordered_atoms)}
    initially_missing = [keys for keys in obligation_atoms if not keys & initial_atoms]
    ordered_atoms.sort(key=lambda key: (not any(key in keys for keys in initially_missing), atom_rank[key]))
    for key in ordered_atoms:
        existing = covered_atoms(retained)
        if key in existing:
            continue
        groups: list[set[int]] = [group for support in atoms[key]
                                  if (group := support_group(support, retained)) is not None]
        for group in sorted(groups, key=lambda item: (len(item), sorted(item))):
            proposal = retained | group
            required_atoms = existing | {key}
            while len(proposal) > maximum:
                removable = next((index for index in sorted(proposal, reverse=True)
                                  if protected(proposal - {index}, required_atoms)), None)
                if removable is None:
                    break
                proposal.remove(removable)
            if len(proposal) <= maximum and protected(proposal, required_atoms):
                retained = proposal
                break
    final_atoms = covered_atoms(retained)
    lost = initial_atoms - final_atoms
    if lost or not protected(retained, initial_atoms):
        raise AssertionError("Evidence selection lost a previously retained obligation")
    missing_variants = set(atoms) - final_atoms
    final_visible = source_references(retained)
    final_assessment = catalogue.assess(selected_ids=sorted(final_visible), required_documents=documents)
    # A later token budget consumes a prefix. Put the first complete proof of
    # each retained relation before redundant occurrences, with dependencies
    # kept adjacent. Returning upstream rank here would discard a recovered
    # minority property for exactly the same reason as the original selection.
    prefix: list[int] = []
    for key in ordered_atoms:
        if key not in final_atoms or key in covered_atoms(set(prefix)):
            continue
        groups = [group for support in atoms[key]
                  if (group := support_group(support, set(prefix), retained)) is not None]
        if groups:
            first_group = min(groups, key=lambda item: (len(item), sorted(item)))
            prefix.extend(sorted(first_group))
    for index in sorted(retained - set(prefix)):
        if (identifier_features[index] - identifiers_at(prefix)
                or pool[index]["document_id"] in protected_documents
                - {pool[position]["document_id"] for position in prefix}):
            prefix.append(index)
    ordered = [*prefix, *sorted(retained - set(prefix))]
    notices = []
    if missing_variants:
        notices.append({"code": "evidence_coverage_incomplete", "message":
                        "Le budget de passages ne permet pas de conserver toutes les preuves complémentaires retrouvées. "
                        "Les conditions ou divergences disponibles ne sont pas toutes représentées dans ce contexte.",
                        "missing_relation_variants": len(missing_variants), "maximum_fragments": maximum})
    diagnostic.update(status="incomplete" if missing_variants else "retained_candidate_relations",
                      candidate_count=len(pool), candidate_relation_variants=len(atoms),
                      initial_relation_variants=len(initial_atoms), retained_relation_variants=len(final_atoms),
                      candidate_obligations=len(obligations),
                      retained_covered_obligations=sum(bool(item.get("covered")) for item in final_assessment.get("obligations", [])),
                      missing_relation_variants=len(missing_variants),
                      added_sources=len(retained - original), removed_sources=len(original - retained),
                      proof_prefix_fragments=len(prefix))
    return [{**pool[index], "evidence_coverage_rank": rank} for rank, index in enumerate(ordered)], notices, diagnostic


def quantitative_relation_keys(catalogue, mode):
    """Relations actually supported by the supplied, scope-checked catalogue."""
    documents = tuple(dict.fromkeys(reference["document_id"] for reference in catalogue.references)) if mode == "comparison" else ()
    assessment = catalogue.assess(required_documents=documents)
    obligations = [item for item in assessment.get("obligations", []) if item.get("quantity")]
    return {_relation_key(fact) for fact in assessment.get("matched_relations", [])
            if fact.get("quantity") and fact.get("values") and any(
                _matches_obligation(fact, frozenset(fact.get("reference_ids", [fact["reference_id"]])), obligation)
                for obligation in obligations)}
