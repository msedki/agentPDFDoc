"""Jeu de référence W014 : rattachement des extraits aux blocs et mesures par page et par bloc, sur des blocs synthétiques."""
from tools.qualification.annotated_eval import (
    generation_sample,
    grade_answer,
    locate,
    resolve_dataset,
    resolve_unit,
    score_annotated,
    summarize,
)


def block(identifier, page, text, document="doc-a"):
    return {"id": identifier, "document_id": document, "page_index": page, "text": text}


BLOCKS = [
    block("b1", 0, "Réglage du distributeur SW4"),
    block("b2", 0, "La pression de service est de 3,1 bar en marche normale."),
    block("b3", 1, "Contrôler l’étanchéité du circuit avant la remise en service."),
    block("b4", 1, "Tableau 2 : couple de serrage 12 N·m pour les vis M8"),
]


def test_excerpts_are_located_exactly_across_two_blocks_or_approximately():
    assert locate("pression de service est de 3,1 BAR", BLOCKS) == (["b2"], "EXACT", 1.0)
    assert locate("distributeur SW4 La pression", BLOCKS) == (["b1", "b2"], "EXACT_SPAN", 1.0)
    ids, status, coverage = locate("Contrôler étanchéité du circuit avant remise en service", BLOCKS)
    assert (ids, status) == (["b3"], "FUZZY") and coverage >= 0.7
    assert locate("Vidanger le réservoir principal chaque semaine", BLOCKS)[1] == "NOT_RESOLVED"


def test_a_wrong_page_number_is_corrected_from_the_whole_document():
    unit = resolve_unit({"page_number": 1, "required_texts": ["couple de serrage 12 N·m pour les vis M8"]}, BLOCKS)
    assert unit["resolved"] and unit["block_ids"] == ["b4"] and unit["page_indices"] == [0, 1]
    assert unit["excerpts"][0]["status"] == "PAGE_CORRECTED_EXACT"
    # Correspondance seulement approchée sur une autre page : refusée (textes répétés d'une page à l'autre).
    approximate = resolve_unit({"page_number": 1, "required_texts": ["couple de serrage 12 N·m vis M8 tableau"]}, BLOCKS)
    assert not approximate["resolved"] and approximate["page_indices"] == [0] and approximate["excerpts"][0]["status"] == "NOT_RESOLVED"


def test_dataset_has_document_and_library_variants_and_keeps_unanswerable_questions():
    annotated = [{"document": {"document_id": "doc-a"}, "questions": [
        {"id": "X-01", "category": "factual_fr_en", "question": "Quelle pression ?", "answerable": True,
         "expected_units": [{"page_index": 0, "required_texts": ["pression de service est de 3,1 bar"], "role": "answer"}]},
        {"id": "X-02", "category": "unanswerable_in_scope", "question": "Quel est le poids ?", "answerable": False, "expected_units": []}]}]
    dataset = resolve_dataset(annotated, BLOCKS)
    assert [(item["source_id"], item["variant"]) for item in dataset["questions"]] == [
        ("X-01", "reference"), ("X-01", "portee_bibliotheque"), ("X-02", "reference"), ("X-02", "portee_bibliotheque")]
    first = dataset["questions"][0]
    assert first["expected_block_ids"] == ["b2"] and first["expected_pages"] == [0] and first["block_resolved"]
    assert first["scope"] == {"kind": "documents", "documentIds": ["doc-a"]} and dataset["questions"][1]["scope"] == {"kind": "library"}
    assert dataset["resolution_summary"] == {"excerpts": {"EXACT": 1}, "answerable_questions": 1, "block_resolved": 1}


def test_scores_count_page_and_block_evidence_in_top10_final_list_and_context():
    question = {"id": "a001", "source_id": "X-01", "category": "factual_fr_en", "variant": "reference", "split": "annotated", "document_id": "doc-a",
                "expected_block_ids": ["b2"], "expected_pages": [0], "block_resolved": True, "scope": {"kind": "documents", "documentIds": ["doc-a"]}}
    result = {"state": "context_ready",
              "retrieval_top10": [{"document_id": "doc-a", "page_indices": [1], "blocks": [{"id": "b3", "page_index": 1}]},
                                  {"document_id": "doc-a", "page_indices": [0], "blocks": [{"id": "b1", "page_index": 0}]}],
              "retrieval_final": [{"document_id": "doc-a", "page_indices": [0], "blocks": [{"id": "b1", "page_index": 0}]}],
              "context_sources": [{"document_id": "doc-b", "page_indices": [0], "blocks": [{"id": "z", "page_index": 0}]}]}
    row = score_annotated(question, result)
    # Bonne page trouvée au rang 2 mais pas le bloc attendu ; la page 0 d'un autre document ne compte pas.
    assert (row["page_at_10"], row["page_reciprocal_rank"], row["page_in_final"], row["page_in_context"]) == (True, 0.5, True, False)
    assert (row["success_at_10"], row["in_context"]) == (False, False)
    unresolved = score_annotated({**question, "block_resolved": False}, result)
    assert "success_at_10" not in unresolved
    report = summarize([row, unresolved])
    assert report["reference"]["page"]["page_at_10"]["denominator"] == 2 and report["reference"]["block"]["success_at_10"]["denominator"] == 1


def test_generation_sample_takes_documents_in_turn_and_skips_followups():
    questions = []
    for document in ("doc-a", "doc-b"):
        for index in range(4):
            questions.append({"id": f"{document}-{index}", "source_id": f"{document}-{index}", "variant": "reference", "document_id": document,
                              "category": "conversation_followup" if index == 3 else "factual_fr_en", "answerable": index < 3})
    questions.append({"id": "lib", "source_id": "lib", "variant": "portee_bibliotheque", "document_id": "doc-a", "category": "factual_fr_en", "answerable": True})
    chosen = generation_sample({"questions": questions}, answerable=4, unanswerable=0)
    assert [item["id"] for item in chosen] == ["doc-a-1", "doc-b-1", "doc-a-2", "doc-b-2"]
    assert generation_sample({"questions": questions}, answerable=4, unanswerable=0) == chosen


def test_answer_grading_checks_values_citations_page_and_abstention():
    record = {"id": "a1", "source_id": "X-01", "answerable": True, "status": "done", "answer_text": "La pression de service est de 3,1 bar [S002].",
              "cited": ["S002"], "sources": [{"source_id": "S001", "document_id": "doc-a", "page_index": 4}, {"source_id": "S002", "document_id": "doc-a", "page_index": 0}],
              "metrics": {"ttft_ms": 1.0}}
    row = grade_answer(record, {"document_id": "doc-a", "expected_pages": [0]}, {"important_values": [{"key": "p", "value": "3.1", "unit": "bar"}]})
    assert (row["answered"], row["citations_valid"], row["cites_expected_page"], row["values_found"], row["abstention_phrase"]) == (True, True, True, 1, False)
    refusal = {**record, "answer_text": "Les preuves ne précisent pas le poids de l'appareil.", "cited": ["S009"]}
    row = grade_answer(refusal, {"document_id": "doc-a", "expected_pages": [0]}, {"important_values": []})
    assert (row["citations_valid"], row["abstention_phrase"], row["values_expected"]) == (False, True, 0)
