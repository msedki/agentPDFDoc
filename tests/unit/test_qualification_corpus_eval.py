"""Évaluation du corpus réel (R21) : génération déterministe des questions et calcul des mesures, sur des blocs synthétiques."""
import random

import pytest

from tools.qualification.corpus_eval import (
    aggregate,
    build_dataset,
    lexical_overlap,
    mutate_identifier,
    score,
    value_questions,
    wilson,
)


def block(identifier, document, text, page=0, route="native"):
    return {"id": identifier, "document_id": document, "version_id": f"v-{document}", "page_index": page, "text": text, "route": route}


BLOCKS = [
    block("b1", "doc-a", "La pression de réglage du distributeur SW4 est de 3,1 bar en service normal."),
    block("b2", "doc-a", "La tension d'alimentation du relais KM-21 est de 72 V."),
    block("b3", "doc-b", "Le couple de serrage des vis de la bride BR-440 est de 12 N·m."),
    block("b4", "doc-b", "Le moteur MT-900 entraîne la pompe ; voir la figure 3."),
    block("b5", "doc-c", "Les intervalles de révision sont indiqués au tableau 2."),
]


def test_value_questions_turn_the_subject_into_a_question_and_normalize_the_value():
    questions = value_questions(BLOCKS[0])
    assert questions == [{"category": "valeur", "question": "Quelle est la pression de réglage du distributeur SW4 ?", "expected_value": "3.1 bar", "template": "sujet_est_de"}]
    assert value_questions(BLOCKS[2])[0]["expected_value"] == "12 N·m"
    assert value_questions(BLOCKS[4]) == []


def test_mutated_identifier_is_absent_from_the_corpus_and_keeps_its_shape():
    known = {"KM-21", "KM-22"}
    candidate = mutate_identifier("KM-21", known, random.Random(1))
    assert candidate is not None and candidate not in known and len(candidate) == len("KM-21") and candidate.startswith("KM-")


def test_dataset_is_deterministic_split_by_document_and_declares_expected_blocks():
    first, second = build_dataset(BLOCKS), build_dataset(BLOCKS)
    assert first["questions"] == second["questions"]
    categories = {item["category"] for item in first["questions"]}
    assert {"valeur", "identifiant", "hors_perimetre", "sans_reponse"} <= categories
    for item in first["questions"]:
        assert item["split"] in {"development", "holdout"} and item["id"].startswith("q")
        if item["category"] in {"valeur", "identifiant"} and item["variant"] == "reference":
            assert item["expected_block_ids"] and item["scope"]["documentIds"] == [item["document_id"]]
        elif item["category"] in {"valeur", "identifiant"}:
            assert item["expected_block_ids"] and item["scope"] == {"kind": "library"}
        else:
            assert item["expected_abstention"] is True and item["expected_block_ids"] == []
        if item["category"] == "hors_perimetre":
            assert item["scope"]["documentIds"] != [item["document_id"]]
    splits = {}
    for item in first["questions"]:
        splits.setdefault(item["document_id"], set()).add(item["split"])
    assert all(len(values) == 1 for values in splits.values()), "un document n'est jamais des deux côtés"


def test_scores_use_block_identity_for_rank_final_list_and_context():
    question = {"id": "q001", "category": "valeur", "split": "development", "expected_block_ids": ["b2"], "alternative_block_ids": [], "scope": {"kind": "documents", "documentIds": ["doc-a"]}}
    result = {"state": "context_ready", "retrieval_top10": [{"blocks": [{"id": "b1"}]}, {"blocks": [{"id": "b2"}]}],
              "retrieval_final": [{"blocks": [{"id": "b2"}]}], "context_sources": [{"blocks": [{"id": "b1"}]}], "warnings": []}
    row = score(question, result)
    assert (row["success_at_10"], row["reciprocal_rank"], row["in_final"], row["in_context"]) == (True, 0.5, True, False)


def test_unanswerable_questions_count_search_abstention_and_scope_leakage():
    question = {"id": "q002", "category": "hors_perimetre", "split": "holdout", "identifier": "KM-21", "expected_abstention": True,
                "expected_block_ids": [], "scope": {"kind": "documents", "documentIds": ["doc-b"]}}
    abstained = score(question, {"warnings": [{"code": "identifier_not_found_in_scope"}], "retrieval_final": []})
    leaked = score(question, {"warnings": [], "retrieval_final": [{"document_id": "doc-a", "text": "Relais KM-21 : 72 V"}]})
    assert (abstained["search_abstention"], abstained["scope_leakage"]) == (True, 0)
    assert (leaked["search_abstention"], leaked["scope_leakage"]) == (False, 1)


def test_aggregate_reports_numerators_denominators_and_wilson_intervals():
    rows = [{"id": f"q{i}", "category": "valeur", "split": "development", "route": "native", "lexical_overlap": i / 10,
             "success_at_10": i % 2 == 0, "reciprocal_rank": 1.0 if i % 2 == 0 else 0.0, "in_final": True, "in_context": i % 3 == 0} for i in range(9)]
    rows.append({"id": "q9", "category": "sans_reponse", "split": "holdout", "search_abstention": True, "scope_leakage": 0})
    report = aggregate(rows)
    assert report["answerable"]["success_at_10"] == {"numerator": 5, "denominator": 9, "rate": 0.556, "wilson95": wilson(5, 9)}
    assert report["unanswerable"]["search_abstention"]["denominator"] == 1 and report["unanswerable"]["scope_leakage_total"] == 0
    bands = report["by_overlap_band"]
    assert [bands[name]["success_at_10"]["denominator"] for name in ("faible", "partiel", "complet")] == [5, 4, 0]


def test_overlap_bands_stay_distinct_when_most_questions_repeat_all_carrier_words():
    rows = [{"id": f"q{i}", "category": "valeur", "variant": "reference", "lexical_overlap": 1.0, "success_at_10": True,
             "reciprocal_rank": 1.0, "in_final": True, "in_context": True} for i in range(8)]
    rows += [{"id": "q8", "category": "valeur", "variant": "indices_reduits", "lexical_overlap": 0.667, "success_at_10": False,
              "reciprocal_rank": 0.0, "in_final": False, "in_context": False},
             {"id": "q9", "category": "valeur", "variant": "indices_reduits", "lexical_overlap": 0.0, "success_at_10": True,
              "reciprocal_rank": 0.25, "in_final": True, "in_context": False}]
    bands = aggregate(rows)["by_overlap_band"]
    assert (bands["complet"]["success_at_10"]["numerator"], bands["complet"]["success_at_10"]["denominator"]) == (8, 8)
    assert (bands["partiel"]["success_at_10"]["numerator"], bands["partiel"]["success_at_10"]["denominator"]) == (0, 1)
    assert (bands["faible"]["in_context"]["numerator"], bands["faible"]["in_context"]["denominator"]) == (0, 1)


@pytest.mark.parametrize("successes,total,expected", [(18, 20, [0.699, 0.972]), (0, 0, None), (20, 20, [0.839, 1.0])])
def test_wilson_matches_the_planning_table_of_the_protocol(successes, total, expected):
    assert wilson(successes, total) == expected


def test_lexical_overlap_measures_question_terms_found_in_the_block():
    assert lexical_overlap("Quelle est la tension du relais KM-21 ?", BLOCKS[1]["text"]) > 0.5
    assert lexical_overlap("", BLOCKS[1]["text"]) == 0.0


def test_context_template_covers_values_in_instructions_and_skips_bare_numbers():
    instruction = block("b9", "doc-d", "Serrer les vis de fixation du couvercle au couple de 25 N·m puis contrôler.")
    questions = value_questions(instruction)
    assert questions == [{"category": "valeur", "question": "Quelle valeur est indiquée pour « vis de fixation du couvercle au couple de » ?",
                          "expected_value": "25 N·m", "template": "contexte_precedent", "reduced_cue": "Serrer vis fixation"}]
    assert value_questions(block("b10", "doc-d", "Voir 3 bar.")) == []


def test_series_two_variants_widen_the_scope_and_reduce_the_cues():
    blocks = BLOCKS + [block("b9", "doc-d", "Serrer les vis de fixation du couvercle au couple de 25 N·m puis contrôler.")]
    questions = build_dataset(blocks)["questions"]
    variants = {item["variant"] for item in questions}
    assert variants == {"reference", "portee_bibliotheque", "indices_reduits"}
    reduced = [item for item in questions if item["variant"] == "indices_reduits"]
    assert reduced and all(item["question"].startswith("Quelle valeur pour ") and item["scope"] == {"kind": "library"} for item in reduced)
    assert len({item["id"] for item in questions}) == len(questions)
    # Le recouvrement ignore les mots du gabarit : une question qui ne reprend aucun mot porteur vaut 0.
    assert lexical_overlap("Quelle valeur est indiquée pour « » ?", "valeur indiquée") == 0.0



def test_confirmation_series_excludes_blocks_and_identifiers_already_used():
    first = build_dataset(BLOCKS)["questions"]
    used_blocks = {block for item in first for block in item["expected_block_ids"]}
    used_codes = {item["identifier"] for item in first if item.get("identifier")}
    second = build_dataset(BLOCKS, seed=20261001, exclude={"block_ids": used_blocks, "identifiers": used_codes})["questions"]
    assert not {block for item in second for block in item["expected_block_ids"]} & used_blocks
    assert not {item["identifier"] for item in second if item.get("identifier")} & used_codes
