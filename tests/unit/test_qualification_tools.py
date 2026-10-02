"""Outils de qualification : sorties protégées, gel du final, fusion de bindings, runners API et grille D05.

Les runners API sont exercés avec httpx.MockTransport : ce sont des doubles explicites du contrat HTTP/SSE local,
pas une intégration réelle. Aucun modèle, service ou téléchargement n'est lancé.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import answers  # noqa: E402
import capture_bindings  # noqa: E402
import check_reproducibility  # noqa: E402
import evidence_io  # noqa: E402
import extra_fixtures  # noqa: E402
import generate  # noqa: E402
import grade  # noqa: E402
import merge_bindings  # noqa: E402
import perf  # noqa: E402
import resolve  # noqa: E402
from corpus_data import frozen_digest  # noqa: E402

BASE = "http://127.0.0.1:8785"
IDENTITY = {"profile_sha256": "p" * 64, "selector_sha256": "s" * 64, "dense_identity": {"model": "unit"}, "llm_tokenizer_identity": {"model": "unit"}, "qdrant_collection": "unit"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- 1. resolve.py : sortie exclusive, jamais un jeu gelé ---------------------------------------------------------

def test_resolve_refuses_frozen_names_foreign_folders_and_existing_evidence(tmp_path, monkeypatch):
    evals = tmp_path / "evals"
    (evals / "runtime").mkdir(parents=True)
    dataset, bindings = evals / "development.json", evals / "bindings.json"
    dataset.write_text(json.dumps({"questions": []}), encoding="utf-8")
    bindings.write_text(json.dumps({"documents": {}}), encoding="utf-8")
    sentinel = evals / "final.json"
    sentinel.write_bytes(b"SENTINEL-FINAL")
    monkeypatch.setattr(resolve, "EVALS", evals)
    # tmp_path peut être sous la vraie QA : isoler les deux racines pour garder une cible réellement étrangère.
    monkeypatch.setattr(resolve, "LOCAL_QA", tmp_path / "local-qa")
    argv = ["--dataset", str(dataset), "--bindings", str(bindings), "--output"]
    # Défaut reproduit sur l'ancien code : --output evals/qualification-v2.1/final.json écrasait le jeu gelé.
    for target in (sentinel, evals / "runtime" / "final.json", evals / "resolved" / "FINAL.FREEZE.JSON", evals / "runtime" / "manifest.json",
                   evals / "runtime" / "questions.json", evals / "runtime" / "development.json", evals / "other.json", bindings):
        with pytest.raises(SystemExit):
            resolve.main([*argv, str(target)])
    assert sentinel.read_bytes() == b"SENTINEL-FINAL"
    output = evals / "resolved" / "2026-09-30-development-resolved.json"
    assert resolve.main([*argv, str(output)])["resolved_questions"] == 0
    first = output.read_bytes()
    with pytest.raises(SystemExit):
        resolve.main([*argv, str(output)])
    assert output.read_bytes() == first and b"\r\n" not in first


def test_protected_names_are_refused_even_in_the_real_evals_folder_without_writing():
    for name in evidence_io.PROTECTED_NAMES:
        with pytest.raises(ValueError, match="protégé"):
            evidence_io.checked_output(evidence_io.EVALS / "runtime" / name, [evidence_io.EVALS / "runtime"])
    with pytest.raises(ValueError, match="hors des dossiers"):
        evidence_io.checked_output(evidence_io.EVALS / "unit-report.json", [evidence_io.EVALS / "runtime", evidence_io.EVALS / "resolved"])


# --- 2. generate.py / check_reproducibility.py : gel du final, contrôle en dossier temporaire ----------------------

def fake_generator(final: dict, pdf: bytes = b"%PDF-unit"):
    def write(root: Path) -> dict:
        (root / "fixtures/qualification-v2.1/licenses").mkdir(parents=True, exist_ok=True)
        (root / "fixtures/qualification-v2.1/a.pdf").write_bytes(pdf)
        (root / "fixtures/qualification-v2.1/licenses/bitstream-vera-license.txt").write_bytes(b"license")
        folder = root / "evals/qualification-v2.1"
        folder.mkdir(parents=True, exist_ok=True)
        digest = frozen_digest(final)
        documents = {"questions.json": {"questions": final["questions"]}, "development.json": {"questions": []}, "final.json": final,
                     "manifest.json": {"entries": [{"path": "qualification-v2.1/a.pdf"}]}, "final.freeze.json": {"canonical_sha256": digest, "questions": len(final["questions"])}}
        for name, value in documents.items():
            (folder / name).write_text(json.dumps(value), encoding="utf-8")
        return {"final_canonical_sha256": digest, "manifest": str(folder / "manifest.json")}
    return write


def snapshot_tree(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_generate_never_writes_directly_into_the_repository(monkeypatch):
    def forbidden():
        raise AssertionError("la garde n'a pas arrêté l'écriture dans le dépôt")

    # Si la garde régresse, le test échoue avant la première écriture au lieu de régénérer le dépôt.
    monkeypatch.setattr(generate, "register_fonts", forbidden)
    with pytest.raises(ValueError, match="publish"):
        generate.generate(generate.ROOT)


def test_publish_refuses_to_replace_a_final_that_differs_from_its_freeze(tmp_path, monkeypatch):
    frozen = {"questions": [{"id": "FIN-1", "question": "Q ?"}]}
    monkeypatch.setattr(generate, "generate", fake_generator(frozen))
    first = generate.publish(tmp_path)
    assert first["final_canonical_sha256"] == frozen_digest(frozen) and not first["final_regenerated_explicitly"]
    delivered = snapshot_tree(tmp_path)
    # Rejouer le même générateur réécrit des octets identiques ; un final différent est refusé sans rien toucher.
    generate.publish(tmp_path)
    assert snapshot_tree(tmp_path) == delivered
    changed = {"questions": [{"id": "FIN-1", "question": "Q modifiée ?"}]}
    monkeypatch.setattr(generate, "generate", fake_generator(changed, b"%PDF-other"))
    with pytest.raises(ValueError, match="diffère du gel"):
        generate.publish(tmp_path)
    assert snapshot_tree(tmp_path) == delivered
    final = tmp_path / "evals/qualification-v2.1/final.json"
    final.write_text(json.dumps(changed), encoding="utf-8")
    tampered = snapshot_tree(tmp_path)
    with pytest.raises(ValueError, match="diffère de son gel"):
        generate.publish(tmp_path)
    assert snapshot_tree(tmp_path) == tampered
    (tmp_path / "evals/qualification-v2.1/final.freeze.json").unlink()
    with pytest.raises(ValueError, match="ensemble"):
        generate.frozen_final_state(tmp_path / "evals/qualification-v2.1")
    explicit = generate.publish(tmp_path, regenerate_final=True)
    assert explicit["final_regenerated_explicitly"] and explicit["final_canonical_sha256"] == frozen_digest(changed)
    freeze = json.loads((tmp_path / "evals/qualification-v2.1/final.freeze.json").read_text(encoding="utf-8"))
    assert freeze["canonical_sha256"] == frozen_digest(json.loads(final.read_text(encoding="utf-8")))


def test_reproducibility_compares_in_a_temporary_directory_without_touching_delivered_files(tmp_path, monkeypatch):
    final = {"questions": [{"id": "FIN-1"}]}
    monkeypatch.setattr(generate, "generate", fake_generator(final))
    generate.publish(tmp_path)
    delivered = snapshot_tree(tmp_path)
    monkeypatch.setattr(check_reproducibility, "generate", fake_generator(final))
    result = check_reproducibility.compare(tmp_path)
    assert result["status"] == "PASS" and result["changed_paths"] == [] and result["files_compared"] == 6
    assert result["final_json_identical_bytes"] and result["regenerated_final_matches_freeze"]
    monkeypatch.setattr(check_reproducibility, "generate", fake_generator(final, b"%PDF-drift"))
    result = check_reproducibility.compare(tmp_path)
    assert result["status"] == "FAIL" and result["changed_paths"] == ["fixtures/qualification-v2.1/a.pdf"]
    assert snapshot_tree(tmp_path) == delivered


def test_reproducibility_report_is_exclusive_under_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(check_reproducibility, "EVALS", tmp_path)
    monkeypatch.setattr(check_reproducibility, "LOCAL_QA", tmp_path / "local-qa")
    monkeypatch.setattr(check_reproducibility, "compare", lambda: {"status": "PASS", "files_compared": 1, "changed_paths": [], "final_json_identical_bytes": True,
                                                                    "regenerated_final_matches_freeze": True})
    for target in (tmp_path / "reproducibility.json", tmp_path / "reports" / "final.freeze.json"):
        with pytest.raises(SystemExit):
            check_reproducibility.main(["--output", str(target)])
    output = tmp_path / "reports" / "reproducibility-unit.json"
    check_reproducibility.main(["--output", str(output)])
    with pytest.raises(SystemExit):
        check_reproducibility.main(["--output", str(output)])


def test_generated_datasets_have_the_delivered_bytes_whatever_the_platform(tmp_path):
    # Jeux livrés générés sous Windows, en CRLF, conservés tels quels par « * -text » : sous Linux, write_text sans
    # newline= écrivait LF et check_reproducibility échouait sur les seules fins de ligne (J8, L0, 02/10/2026).
    generate.generate(tmp_path)
    for name in generate.EVAL_FILES:
        regenerated, delivered = (tmp_path / "evals/qualification-v2.1" / name).read_bytes(), (evidence_io.EVALS / name).read_bytes()
        assert b"\n" not in regenerated.replace(b"\r\n", b""), f"{name} : fin de ligne LF seule"
        if name == "manifest.json":
            # Le manifeste consigne les versions de Python, ReportLab et pypdfium2 du poste qui génère.
            assert {**json.loads(regenerated), "versions": None} == {**json.loads(delivered), "versions": None}
        else:
            assert regenerated == delivered, name


def test_reproducibility_report_may_stay_out_of_git_under_runtime_qa(tmp_path, monkeypatch):
    qa = tmp_path / "qa"
    monkeypatch.setattr(check_reproducibility, "EVALS", tmp_path / "evals")
    monkeypatch.setattr(check_reproducibility, "LOCAL_QA", qa, raising=False)
    monkeypatch.setattr(check_reproducibility, "compare", lambda: {"status": "PASS", "files_compared": 1, "changed_paths": [], "final_json_identical_bytes": True,
                                                                    "regenerated_final_matches_freeze": True})
    output = qa / "j8-linux" / "reproducibility.json"
    check_reproducibility.main(["--output", str(output)])
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "PASS"
    for target in (output, qa, qa / "final.freeze.json", tmp_path / "reproducibility.json"):
        with pytest.raises(SystemExit):
            check_reproducibility.main(["--output", str(target)])
    # Défaut inchangé : un rapport versionné sous evals/qualification-v2.1/reports/ reste accepté.
    check_reproducibility.main(["--output", str(tmp_path / "evals" / "reports" / "reproducibility-unit.json")])


# --- 3. merge_bindings.py ----------------------------------------------------------------------------------------

def binding_snapshot(key, file_sha, *, document="d1", version="v1", revision="r1", generation="g1", text="La pression est de 3.5 bar."):
    block = {"id": f"b-{document}", "raw_text": text, "source_text_hash": sha(text.encode()), "extraction_revision_id": revision, "version_id": version}
    return {"captured_at_utc": "2026-09-30T00:00:00+00:00", "method": "unit-test double", "documents": {key: {
        "document_id": document, "version_id": version, "extraction_revision_id": revision, "generation_id": generation, "file_sha256": file_sha,
        "pages": [{"version_id": version, "page": {"page_index": 0}, "blocks": [block]}]}}}


def write_snapshot(folder: Path, name: str, value: dict) -> tuple[Path, str]:
    path = folder / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, sha(path.read_bytes())


def test_merge_bindings_checks_file_hashes_duplicates_conflicts_and_manifest(tmp_path):
    manifest = {"entries": [{"key": "k1", "sha256": "a" * 64}, {"key": "k2", "sha256": "b" * 64}]}
    first = write_snapshot(tmp_path, "one-published.json", binding_snapshot("k1", "a" * 64))
    second = write_snapshot(tmp_path, "two-published.json", binding_snapshot("k2", "b" * 64, document="d2", version="v2", generation="g2"))
    merged = merge_bindings.merge([first, second], manifest, tmp_path)
    assert sorted(merged["documents"]) == ["k1", "k2"] and [source["sha256"] for source in merged["sources"]] == [first[1], second[1]]
    assert merged["sources"][0]["path"] == "one-published.json"
    with pytest.raises(ValueError, match="différent de la valeur attendue"):
        merge_bindings.merge([(first[0], "0" * 64)], manifest, tmp_path)
    with pytest.raises(ValueError, match="deux fois"):
        merge_bindings.merge([first, first], manifest, tmp_path)
    duplicate = write_snapshot(tmp_path, "dup-published.json", binding_snapshot("k1", "a" * 64, document="d9", version="v9", generation="g9"))
    with pytest.raises(ValueError, match="plusieurs snapshots"):
        merge_bindings.merge([first, duplicate], manifest, tmp_path)
    conflict = write_snapshot(tmp_path, "conflict-published.json", binding_snapshot("k2", "b" * 64, document="d1", version="v2", generation="g2"))
    with pytest.raises(ValueError, match="document_id d1"):
        merge_bindings.merge([first, conflict], manifest, tmp_path)
    wrong_original = write_snapshot(tmp_path, "sha-published.json", binding_snapshot("k2", "c" * 64, document="d2", version="v2", generation="g2"))
    with pytest.raises(ValueError, match="SHA de l'original"):
        merge_bindings.merge([wrong_original], manifest, tmp_path)
    altered = binding_snapshot("k2", "b" * 64, document="d2", version="v2", generation="g2")
    altered["documents"]["k2"]["pages"][0]["blocks"][0]["raw_text"] += " modifié"
    with pytest.raises(ValueError, match="altéré"):
        merge_bindings.merge([write_snapshot(tmp_path, "text-published.json", altered)], manifest, tmp_path)
    unknown = write_snapshot(tmp_path, "unknown-published.json", binding_snapshot("k3", "a" * 64, document="d3", version="v3", generation="g3"))
    with pytest.raises(ValueError, match="manifeste"):
        merge_bindings.merge([unknown], manifest, tmp_path)


def test_merge_bindings_real_published_snapshot_resolves_the_same_development_questions():
    path = evidence_io.EVALS / "runtime" / "2026-09-30-DA-P01-published.json"
    manifest = json.loads((evidence_io.EVALS / "manifest.json").read_text(encoding="utf-8"))
    merged = merge_bindings.merge([(path, sha(path.read_bytes()))], manifest)
    assert list(merged["documents"]) == ["development-DA-P01"] and merged["sources"][0]["path"] == "evals/qualification-v2.1/runtime/2026-09-30-DA-P01-published.json"
    development = json.loads((evidence_io.EVALS / "development.json").read_text(encoding="utf-8"))
    assert resolve.resolve_dataset(development, merged)["resolution_summary"]["resolved_questions"] == 15


def test_merge_bindings_cli_requires_runtime_inputs_and_exclusive_output(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (tmp_path / "manifest.json").write_text(json.dumps({"entries": [{"key": "k1", "sha256": "a" * 64}]}), encoding="utf-8")
    monkeypatch.setattr(merge_bindings, "EVALS", tmp_path)
    monkeypatch.setattr(merge_bindings, "LOCAL_QA", tmp_path / "local-qa")
    path, digest = write_snapshot(runtime, "k1-published.json", binding_snapshot("k1", "a" * 64))
    outside, outside_digest = write_snapshot(tmp_path, "outside-published.json", binding_snapshot("k1", "a" * 64))
    with pytest.raises(SystemExit):
        merge_bindings.main(["--input", str(outside), outside_digest, "--output", str(runtime / "merged.json")])
    with pytest.raises(SystemExit):
        merge_bindings.main(["--input", str(path), digest, "--output", str(runtime / "manifest.json")])
    output = runtime / "2026-09-30-merged-bindings.json"
    assert merge_bindings.main(["--input", str(path), digest, "--output", str(output)])["documents"] == ["k1"]
    with pytest.raises(SystemExit):
        merge_bindings.main(["--input", str(path), digest, "--output", str(output)])


# --- 4. answers.py : runner headless (doubles HTTP/SSE explicites) --------------------------------------------------

def question(identifier, *, split="development", answerable=True, followup=None, resolved=True, language="fr", values=None, mode=None):
    item = {"id": identifier, "split": split, "family": "unit", "category": "conversation_followup" if followup else "factual_fr_en" if answerable else "unanswerable_in_scope",
            "language": language, "question": f"Question {identifier} ?", "answerable": answerable, "scope_template": {"kind": "documents", "document_keys": ["k1"]},
            "scope_resolved": None, "expected_answer": "La pression de DA-P01 est de 3.1 bar." if answerable else None,
            "important_values": values if values is not None else ([{"key": "pressure", "value": "3.1", "unit": "bar"}] if answerable else []),
            "expected_units": [{"document_key": "k1", "file_sha256": "a" * 64, "page_index": 0, "required_texts": ["3.1 bar"], "version_id": None, "resolved_spans": None,
                                "resolution_status": "NOT_RESOLVED"}] if answerable else [],
            "annotation_state": "SOURCE_TEMPLATE_NOT_RESOLVED", "required_identifiers": ["DA-P01"] if answerable else None, "forbidden_identifiers": ["DA-P010"] if answerable else None}
    if mode:
        item["mode"] = mode
    if followup:
        item.update(followup_of_question_id=followup, prior_user_question=f"Question {followup} ?")
    item["_resolved"] = resolved
    return item


def datasets(tmp_path, questions, split="development"):
    source = {"questions": [{key: value for key, value in item.items() if key != "_resolved"} for item in questions]}
    resolved = copy.deepcopy(source)
    for item, original in zip(resolved["questions"], questions, strict=True):
        if original["_resolved"]:
            item.update(scope_resolved={"kind": "documents", "documentIds": ["d1"]}, annotation_state="RESOLVED",
                        versions_snapshot=[{"document_id": "d1", "version_id": "v1", "generation_id": "g1", "extraction_revision_id": "r1"}])
            for unit in item["expected_units"]:
                unit.update(version_id="v1", resolved_spans=[{"text": "3.1 bar"}], resolution_status="RESOLVED")
        else:
            item["annotation_state"] = "UNRESOLVED"
    paths = tmp_path / f"{split}-source.json", tmp_path / f"{split}-resolved.json"
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    paths[1].write_text(json.dumps(resolved), encoding="utf-8")
    return paths


def sse(events, *, chunk=7):
    text = ": heartbeat\n\n" + "".join(f"id: {index}\nevent: {kind}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
                                        for index, (kind, data) in enumerate(events, 1))
    data = text.encode("utf-8")
    # Petits morceaux : coupe volontairement des caractères UTF-8 multioctets et des lignes.
    return [data[index:index + chunk] for index in range(0, len(data), chunk)]


def answered(text, *, model_called=True, eval_count=42, load_ns=20_000_000, sources=("S1",)):
    registered = [{"source_id": source, "chunk_id": f"c-{source}", "document_id": "d1", "version_id": "v1", "generation_id": "g1", "extraction_revision_id": "r1",
                   "page_index": 0, "page_number": 1, "block_ids": ["b1"], "precision": "block", "text": "long source text"} for source in sources]
    metrics = {"model_called": model_called, "elapsed_ms": 1500.0, "ttft_ms": 900.0, "retrieval_ms": 40.0, "queue_wait_ms": 1.0, "prompt_eval_count": 3000,
               "prompt_eval_cached_count": 0, "eval_count": eval_count, "load_duration": load_ns, "prompt_eval_duration": 600_000_000, "eval_duration": 700_000_000,
               "local_prompt_tokens": 2990}
    cited = [item for item in registered if f"[{item['source_id']}]" in text]
    return [("status", {"state": "queued"}), ("status", {"state": "searching"}), ("sources", {"sources": registered}),
            *[("delta", {"text": part}) for part in re.findall(r"\S+\s*", text)],
            ("done", {"message": text, "text": text, "status": "done", "citations": cited, "finish_reason": "stop", "metrics": metrics, "warnings": []})]


def refused():
    return [("status", {"state": "queued"}), ("error", {"code": "resource_admission_denied", "message": "Réserve hôte menacée.", "metrics": {"model_called": False}})]


class FakeApi:
    """Double explicite de l'API locale : contrôle Host/Origin et rejoue des flux SSE scriptés."""

    def __init__(self, scripts, *, identity=None):
        self.scripts, self.posts, self.searches, self.streams, self.created = scripts, [], [], [], {}
        self.identity = identity or [IDENTITY]
        self.diagnostics_calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == "127.0.0.1:8785" and request.headers["origin"] == BASE
        path = request.url.path
        if path == "/api/v1/diagnostics":
            identity = self.identity[min(self.diagnostics_calls, len(self.identity) - 1)]
            self.diagnostics_calls += 1
            return httpx.Response(200, json={**identity, "resources": {"available_mib": 5000}})
        if path == "/api/v1/search":
            body = json.loads(request.content)
            self.searches.append(body)
            return httpx.Response(200, json={"results": [{}] * 3, "elapsed_ms": 10.0 + 20.0 * (len(self.searches) - 1), "warnings": []})
        if path == "/api/v1/queries" and request.method == "POST":
            body = json.loads(request.content)
            self.posts.append(body)
            query_id = f"q{len(self.posts)}"
            self.created[query_id] = body
            return httpx.Response(202, json={"query_id": query_id, "conversation_id": body.get("conversation_id") or f"c{len(self.posts)}",
                                             "events_url": f"/api/v1/queries/{query_id}/events"})
        if path.endswith("/events"):
            query_id = path.split("/")[4]
            self.streams.append(query_id)
            script = self.scripts[self.created[query_id]["question"]]
            events = script.pop(0) if isinstance(script[0], list) else script
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=iter(sse(events)))
        return httpx.Response(404, json={"code": "not_found"})


def journal(path):
    return evidence_io.read_jsonl(path)


def test_answers_runs_one_generation_per_question_and_keeps_raw_sse(tmp_path):
    items = [question("DEV-001"), question("DEV-002", followup="DEV-001"), question("DEV-003", answerable=False), question("DEV-004", resolved=False)]
    source, resolved = datasets(tmp_path, items)
    api = FakeApi({"Question DEV-001 ?": answered("La pression de DA-P01 est de 3,1 bar [S1]."), "Question DEV-002 ?": answered("Sa tolérance est de ± 2.0 % [S1]."),
                   "Question DEV-003 ?": answered(grade.API_ABSTENTION, model_called=False, sources=())})
    runtime = tmp_path / "runtime"
    output = runtime / "2026-09-30-development-answers.jsonl"
    result = answers.run(resolved, source, output, BASE, "development", transport=httpx.MockTransport(api), runtime_root=runtime)
    assert result["complete"] and result["results"] == {"ANSWERED": 3, "NOT_RUN_UNRESOLVED_SCOPE": 1} and result["submissions_this_run"] == 3
    assert [body["question"] for body in api.posts] == ["Question DEV-001 ?", "Question DEV-002 ?", "Question DEV-003 ?"]
    assert api.posts[0] == {"question": "Question DEV-001 ?", "scope": {"kind": "documents", "documentIds": ["d1"]}, "mode": "question"}
    assert api.posts[1]["conversation_id"] == "c1" and api.posts[1]["followup_of"] == "q1"
    records = journal(output)
    assert records[0]["record"] == "header" and records[0]["api_identity"] == IDENTITY and records[0]["split"] == "development"
    results = {record["question_id"]: record for record in records if record["record"] == "result"}
    first = results["DEV-001"]
    assert first["answer_text"] == first["streamed_text"] == "La pression de DA-P01 est de 3,1 bar [S1]."
    assert first["cited_source_ids"] == ["S1"] and first["sources"][0]["source_id"] == "S1" and "text" not in first["sources"][0]
    assert first["model_called"] is True and first["tokens"]["eval_count"] == 42 and first["durations_ms"]["api_ttft"] == 900.0
    assert first["durations_ms"]["client_first_delta"] is not None and first["timings_replayed"] is False
    assert first["sse"]["raw"].startswith(": heartbeat") and first["sse"]["sha256"] == sha(first["sse"]["raw"].encode("utf-8"))
    assert first["sse"]["event_counts"]["done"] == 1 and "± 2.0 %" in results["DEV-002"]["answer_text"]
    assert results["DEV-003"]["model_called"] is False and results["DEV-004"]["status"] == "NOT_RUN_UNRESOLVED_SCOPE"
    with pytest.raises(ValueError, match="aucun écrasement"):
        answers.run(resolved, source, output, BASE, "development", transport=httpx.MockTransport(api), runtime_root=runtime)
    for target in (tmp_path / "answers.jsonl", runtime / "final.json"):
        with pytest.raises(ValueError):
            answers.run(resolved, source, target, BASE, "development", transport=httpx.MockTransport(api), runtime_root=runtime)
    assert len(api.posts) == 3


def test_answers_resume_rereads_created_query_without_second_post(tmp_path):
    items = [question("DEV-001"), question("DEV-002", followup="DEV-001"), question("DEV-003")]
    source, resolved = datasets(tmp_path, items)
    truncated = answered("Sa tolérance est de 2.0 % [S1].")[:-1]
    api = FakeApi({"Question DEV-001 ?": answered("3.1 bar [S1]."), "Question DEV-002 ?": [truncated, answered("Sa tolérance est de 2.0 % [S1].")],
                   "Question DEV-003 ?": answered("3.1 bar [S1].")})
    runtime, output = tmp_path / "runtime", tmp_path / "runtime" / "answers.jsonl"
    first = answers.run(resolved, source, output, BASE, "development", limit=2, transport=httpx.MockTransport(api), runtime_root=runtime)
    assert first["pending_questions"] == ["DEV-002", "DEV-003"] and len(api.posts) == 2
    assert [record["status"] for record in journal(output) if record["record"] == "incident"] == ["STREAM_INCOMPLETE"]
    with pytest.raises(ValueError, match="Reprise impossible"):
        answers.run(resolved, source, runtime / "missing.jsonl", BASE, "development", resume=True, transport=httpx.MockTransport(api), runtime_root=runtime)
    second = answers.run(resolved, source, output, BASE, "development", resume=True, transport=httpx.MockTransport(api), runtime_root=runtime)
    assert second["complete"] and second["submissions_this_run"] == 1 and len(api.posts) == 3 and api.streams == ["q1", "q2", "q2", "q3"]
    records = journal(output)
    replayed = next(record for record in records if record["record"] == "result" and record["question_id"] == "DEV-002")
    assert replayed["query_id"] == "q2" and replayed["timings_replayed"] and replayed["durations_ms"]["client_first_delta"] is None
    assert [record["record"] for record in records].count("resumed") == 1
    third = answers.run(resolved, source, output, BASE, "development", resume=True, transport=httpx.MockTransport(api), runtime_root=runtime)
    assert third["submissions_this_run"] == 0 and len(api.posts) == 3
    drifted = FakeApi({}, identity=[{**IDENTITY, "selector_sha256": "x" * 64}])
    with pytest.raises(ValueError, match="reprise refusée"):
        answers.run(resolved, source, output, BASE, "development", resume=True, transport=httpx.MockTransport(drifted), runtime_root=runtime)


def test_answers_final_split_requires_valid_freeze_and_complete_resolution(tmp_path):
    items = [question("FIN-001", split="final"), question("FIN-002", split="final", answerable=False)]
    source, resolved = datasets(tmp_path, items, "final")
    freeze = tmp_path / "final.freeze.json"
    runtime = tmp_path / "runtime"
    api = FakeApi({"Question FIN-001 ?": answered("3.1 bar [S1]."), "Question FIN-002 ?": answered(grade.API_ABSTENTION, model_called=False, sources=())})
    run = lambda name, **extra: answers.run(resolved, source, runtime / name, BASE, "final", transport=httpx.MockTransport(api), runtime_root=runtime, **extra)  # noqa: E731
    with pytest.raises(ValueError, match="final-freeze"):
        run("a.jsonl")
    freeze.write_text(json.dumps({"canonical_sha256": "0" * 64, "questions": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="gel fourni"):
        run("a.jsonl", freeze_path=freeze)
    digest = answers.canonical_sha(json.loads(source.read_text(encoding="utf-8")))
    assert digest == frozen_digest(json.loads(source.read_text(encoding="utf-8")))
    freeze.write_text(json.dumps({"canonical_sha256": digest, "questions": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="ne se limite pas"):
        run("a.jsonl", freeze_path=freeze, limit=1)
    development_source, development = datasets(tmp_path, [question("DEV-001")])
    with pytest.raises(ValueError, match="splits"):
        answers.run(development, development_source, runtime / "a.jsonl", BASE, "final", freeze_path=freeze, transport=httpx.MockTransport(api), runtime_root=runtime)
    assert api.posts == []
    result = run("final-answers.jsonl", freeze_path=freeze)
    assert result["complete"] and journal(runtime / "final-answers.jsonl")[0]["final_freeze_sha256"] == digest
    unresolved_source, unresolved = datasets(tmp_path, [question("FIN-001", split="final", resolved=False)], "final")
    freeze.write_text(json.dumps({"canonical_sha256": answers.canonical_sha(json.loads(unresolved_source.read_text(encoding="utf-8"))), "questions": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="résolues"):
        answers.run(unresolved, unresolved_source, runtime / "b.jsonl", BASE, "final", freeze_path=freeze, transport=httpx.MockTransport(api), runtime_root=runtime)


def test_answers_refuses_non_loopback_or_implicit_port_origins():
    for url in ("http://192.168.1.2:8785", "https://127.0.0.1:8785", "http://127.0.0.1", "http://user:pw@127.0.0.1:8785", "http://127.0.0.1:8785/api"):
        with pytest.raises(ValueError, match="loopback"):
            answers.api_client(url)


# --- 5. grade.py ---------------------------------------------------------------------------------------------------

def test_grade_value_unit_precheck_is_numeric_and_unit_exact():
    assert grade.value_check("La pression est de 3,1 bar [S1].", "3.1", "bar")["status"] == "VALUE_AND_UNIT"
    assert grade.value_check("La pression est de 3.10 bar.", "3.1", "bar")["status"] == "VALUE_AND_UNIT"
    assert grade.value_check("Couple : 12 N·m.", "12", "N·m")["status"] == "VALUE_AND_UNIT"
    assert grade.value_check("Tolérance ± 2,0 %.", "2.0", "%")["status"] == "VALUE_AND_UNIT"
    assert grade.value_check("Environ 3.1 bars.", "3.1", "bar")["status"] == "VALUE_WITHOUT_EXPECTED_UNIT"
    error = grade.value_check("DA-P01 : 31 bar ou 3 bar.", "3.1", "bar")
    assert error["status"] == "VALUE_ABSENT" and error["other_values_with_unit"] == ["31", "3"]
    check = grade.precheck(question("DEV-001"), "DA-P01-IN et DA-P010 : 3.1 bar")
    assert check["required_identifiers_missing"] == ["DA-P01"] and check["forbidden_identifiers_without_value_in_sentence"] == []
    assert check["forbidden_identifiers_with_value"] == [{"identifier": "DA-P010", "sentence": "DA-P01-IN et DA-P010 : 3.1 bar"}]
    assert check["annotation_values_in_expected_answer"] is True and check["all_values_with_unit"] is True
    assert grade.precheck(question("DEV-003", answerable=False), grade.API_ABSTENTION)["api_fixed_abstention"] is True
    assert grade.value_check("Tension : 230V.", "230", "V")["status"] == "VALUE_AND_UNIT"
    assert grade.value_check("Pression 3.1bar", "3.1", "bar")["status"] == "VALUE_AND_UNIT"
    thousands = grade.value_check("Révision à 1 020 h ou 1 740 h.", "1020", "h")
    assert thousands["status"] == "VALUE_AND_UNIT" and thousands["other_values_with_unit"] == ["1740"]


# Réponses réelles du jeu DEV (J8, L8, Linux, 02/10/2026) : l'identifiant voisin n'y est cité que pour l'écarter.
DEV_036 = ("La pression nominale exacte pour la référence **DA-P01** est de **3.1 bar**.\n\nCette information provient directement du document S001, qui "
           "stipule : « La pression nominale de DA-P01 est de 3.1 bar. » [S001]\n\nIl est important de noter que le même document précise explicitement "
           "que la référence proche **DA-P010** appartient à un autre équipement et que ses valeurs ne sont pas celles de DA-P01, confirmant ainsi "
           "l'exactitude de cette donnée pour la référence spécifique demandée. [S001]")
DEV_050 = ("Sur la base des preuves fournies, il est impossible de déterminer l'intervalle de contrôle (valeur nominale et tolérance) pour la référence "
           "**DA-P01**.\n\nVoici les éléments documentaires disponibles et leurs implications :\n\n*   **Identification du document :** La preuve [S002] "
           "confirme que le document concerne bien DA-P01 et non DA-P010, en précisant explicitement que \"La référence proche DA-P010 appartient à un autre "
           "équipement ; ses valeurs ne sont pas celles de DA-P01\" [S002].\n*   **Données disponibles pour DA-P01 :** La preuve [S002] fournit des paramètres "
           "techniques spécifiques (pression nominale : 3.1 bar, tolérance : ± 2.0 %, couple de serrage : 12 N·m, alimentation d'essai : 22 V) mais ne "
           "mentionne pas un \"intervalle de contrôle\" au sens d'un tableau de mesure ou de limites de tolérance pour une grandeur physique spécifique "
           "(comme la pression).\n*   **Données manquantes :** La preuve [S003] liste des valeurs mesurées (DA-P01-IN : 13 mm, DA-P01-OUT : 9 mm, "
           "DA-P01-LEAK : 0.1 L/min) mais ne fournit pas les intervalles de contrôle associés à ces mesures ni l'unité d'un éventuel \"intervalle\" global. "
           "La preuve [S004] mentionne un \"Tableau de contrôle\", mais le contenu de ce tableau n'est pas extrait dans les données fournies.\n\n"
           "**Conclusion :**\nIl n'existe aucune donnée dans les preuves [S001] à [S005] permettant de définir l'intervalle de contrôle avec son unité pour "
           "DA-P01. Les seules valeurs numériques disponibles sont des paramètres d'opération (pression nominale, couple, tension) ou des mesures "
           "ponctuelles, sans indication des limites de tolérance ou des intervalles de contrôle demandés.")


def test_grade_precheck_flags_a_forbidden_identifier_only_in_a_sentence_carrying_a_value():
    asked = question("DEV-036")  # 3.1 bar attendu, DA-P01 exigé, DA-P010 interdit
    # Défaut J8 (L8) : 14 réponses sur 15 signalées alors qu'elles citent DA-P0x0 pour l'écarter ; la phrase reste listée, sans alerte.
    for text in (DEV_036, DEV_050):
        check = grade.precheck(asked, text)
        assert check["forbidden_identifiers_with_value"] == []
        [mention] = check["forbidden_identifiers_without_value_in_sentence"]
        assert mention["identifier"] == "DA-P010" and "appartient à un autre équipement" in mention["sentence"]
    # Confusion d'identifiant : la valeur attendue, ou une autre valeur suivie de l'unité annotée, dans la même phrase.
    confused = grade.precheck(asked, "Selon S001, la pression nominale de DA-P010 est de 3,1 bar. Celle de DA-P01 n'est pas indiquée.")
    assert confused["forbidden_identifiers_with_value"] == [{"identifier": "DA-P010", "sentence": "Selon S001, la pression nominale de DA-P010 est de 3,1 bar."}]
    other = grade.precheck(asked, "DA-P01 : 3,1 bar ; DA-P010 : 4,1 bar.")
    assert other["forbidden_identifiers_with_value"] == [{"identifier": "DA-P010", "sentence": "DA-P010 : 4,1 bar."}]
    table = grade.precheck(asked, "| Référence | Pression |\n|---|---|\n| DA-P010 | 3,1 bar |")
    assert table["forbidden_identifiers_with_value"] == [{"identifier": "DA-P010", "sentence": "| DA-P010 | 3,1 bar |"}]
    # Chaque phrase qui nomme l'identifiant figure dans l'une des deux listes : aucune mention n'est perdue.
    both = grade.precheck(asked, "La référence DA-P010 est un autre équipement.\nDA-P010 vaut 3.1 bar.")
    assert both["forbidden_identifiers_with_value"] == [{"identifier": "DA-P010", "sentence": "DA-P010 vaut 3.1 bar."}]
    assert both["forbidden_identifiers_without_value_in_sentence"] == [{"identifier": "DA-P010", "sentence": "La référence DA-P010 est un autre équipement."}]
    absent = grade.precheck(asked, "La pression nominale de DA-P01 est de 3,1 bar [S001].")
    assert absent["forbidden_identifiers_with_value"] == [] and absent["forbidden_identifiers_without_value_in_sentence"] == []
    # Limite du découpage par phrase (revue J8) : ces confusions ne lèvent pas d'alerte, la phrase qui nomme l'identifiant
    # reste listée sans valeur ; INSTRUCTIONS et le README demandent de la relire dans la réponse complète.
    missed = {
        "Pour **DA-P010**, la documentation indique :\n\n- Pression nominale : 3,1 bar": "Pour **DA-P010**, la documentation indique :",
        "La référence demandée correspond à DA-P010. Sa pression nominale est de 3,1 bar [S001].": "La référence demandée correspond à DA-P010.",
        "DA-P010 (p. 2) : 3,1 bar.": "DA-P010 (p.",
        "La pression de DA-P010 est d'env. 3,1 bar.": "La pression de DA-P010 est d'env.",
        "| DA-P010 |\n|---|\n| 3,1 bar |": "| DA-P010 |",
    }
    for text, sentence in missed.items():
        check = grade.precheck(asked, text)
        assert check["forbidden_identifiers_with_value"] == []
        assert check["forbidden_identifiers_without_value_in_sentence"] == [{"identifier": "DA-P010", "sentence": sentence}]
    notice = " ".join(grade.INSTRUCTIONS)
    assert "forbidden_identifiers_without_value_in_sentence" in notice and "deux phrases" in notice and "« env. »" in notice


def graded_run(tmp_path, split="development"):
    # Question 4 : scope non résolu en développement ; refus d'admission réel (événement error) sur le final.
    prefix = split[:3].upper()
    items = [question(f"{prefix}-001", split=split), question(f"{prefix}-002", split=split, language="en"),
             question(f"{prefix}-003", split=split, answerable=False), question(f"{prefix}-004", split=split, resolved=split == "final")]
    source, resolved = datasets(tmp_path, items, split)
    api = FakeApi({f"Question {prefix}-001 ?": answered("DA-P01 : 3,1 bar [S1]."), f"Question {prefix}-002 ?": answered("DA-P01 : 31 bar [S1] [S2].", sources=("S1", "S2")),
                   f"Question {prefix}-003 ?": answered(grade.API_ABSTENTION, model_called=False, sources=()), f"Question {prefix}-004 ?": refused()})
    runtime = tmp_path / "runtime"
    freeze = None
    if split == "final":
        freeze = tmp_path / "final.freeze.json"
        freeze.write_text(json.dumps({"canonical_sha256": answers.canonical_sha(json.loads(source.read_text(encoding="utf-8"))), "questions": 4}), encoding="utf-8")
    output = runtime / f"{split}-answers.jsonl"
    answers.run(resolved, source, output, BASE, split, freeze_path=freeze, transport=httpx.MockTransport(api), runtime_root=runtime)
    return json.loads(resolved.read_text(encoding="utf-8")), output


def fill(grid, verdicts):
    for row in grid["rows"]:
        choice = verdicts.get(row["question_id"])
        if choice is None:
            continue
        verdict, assertions = choice
        row["manual"].update(verdict=verdict, assertions=assertions, reviewer="Relecteur qualification", reviewed_at_utc="2026-09-30T12:00:00+00:00")
        for citation in row["citations"]:
            citation["manual"]["page_ok"] = True
    return grid


TARGETS = {"answer_correctness_on_answerable_min": .85, "supported_claim_ratio_min": .95, "no_answer_correct_ratio_min": .9, "citation_integrity_ratio": 1.0}


def test_grade_grid_and_metrics_keep_denominators_and_refuse_tampering(tmp_path):
    dataset, answers_path = graded_run(tmp_path)
    grid = grade.build_grid(dataset, answers_path)
    rows = {row["question_id"]: row for row in grid["rows"]}
    assert rows["DEV-001"]["precheck"]["all_values_with_unit"] is True and rows["DEV-002"]["precheck"]["values"][0]["other_values_with_unit"] == ["31"]
    assert rows["DEV-004"]["manual"]["verdict"] == "not_generated" and rows["DEV-004"]["precheck"] is None
    assert [citation["source_id"] for citation in rows["DEV-002"]["citations"]] == ["S1", "S2"] and rows["DEV-001"]["citations"][0]["version_in_frozen_snapshot"] is True
    grid = json.loads(json.dumps(grid))
    incomplete = grade.metrics(copy.deepcopy(grid), dataset, answers_path, TARGETS)
    assert incomplete["status"] == "INCOMPLETE" and incomplete["metrics"]["ungraded_questions"] == ["DEV-001", "DEV-002", "DEV-003"]
    supported = {"text": "La pression nominale est de 3,1 bar.", "citations": ["S1"], "support": "supported"}
    wrong = {"text": "La pression est de 31 bar.", "citations": ["S2"], "support": "unsupported"}
    filled = fill(grid, {"DEV-001": ("correct", [supported]), "DEV-002": ("value_unit_error", [wrong]), "DEV-003": ("justified_abstention", [])})
    report = grade.metrics(copy.deepcopy(filled), dataset, answers_path, TARGETS)
    metrics = report["metrics"]
    assert report["status"] == "DEVELOPMENT_DIAGNOSTIC" and report["targets_met"]["correct_abstention"] is True
    assert metrics["answer_correctness"]["successes"] == 1 and metrics["answer_correctness"]["denominator"] == 3
    assert metrics["answer_correctness"]["breakdown"] == {"correct": 1, "value_unit_error": 1, "not_generated": 1}
    assert metrics["correct_abstention"]["rate"] == 1 and metrics["correct_abstention"]["denominator"] == 1
    assert metrics["supported_claim_ratio"]["successes"] == 1 and metrics["supported_claim_ratio"]["denominator"] == 2
    assert metrics["supported_claim_ratio"]["seed"] == grade.SEED and metrics["supported_claim_ratio"] == grade.metrics(copy.deepcopy(filled), dataset, answers_path, TARGETS)["metrics"]["supported_claim_ratio"]
    assert metrics["citation_id_integrity"] == {"successes": 3, "denominator": 3, "rate": 1.0} and metrics["citation_version_page"]["rate"] == 1.0
    assert metrics["not_generated_questions"] == 1 and metrics["by_language"]["en"]["answer_correctness"]["denominator"] == 1
    for mutate, message in ((lambda value: value["rows"][0]["generation"].update(answer_text="autre"), "donnée automatique"),
                            (lambda value: value["rows"][0]["precheck"].update(all_values_with_unit=False), "donnée automatique"),
                            (lambda value: value["rows"][0]["manual"].update(reviewer=""), "relecteur"),
                            (lambda value: value["rows"][0]["manual"].update(verdict="justified_abstention"), "hors de"),
                            (lambda value: value["rows"][0]["manual"]["assertions"][0].update(citations=[]), "sans citation"),
                            (lambda value: value["rows"][0]["manual"]["assertions"][0].update(citations=["S9"]), "non affiché"),
                            (lambda value: value["rows"][0]["citations"][0]["manual"].update(page_ok=None), "page_ok"),
                            (lambda value: value["rows"][1]["manual"].update(assertions=[]), "assertions documentaires"),
                            (lambda value: value.update(answers_sha256="0" * 64), "autre journal")):
        tampered = copy.deepcopy(filled)
        mutate(tampered)
        with pytest.raises(ValueError, match=message):
            grade.metrics(tampered, dataset, answers_path, TARGETS)


def test_grade_final_status_uses_profile_targets_and_cli_outputs_are_exclusive(tmp_path, monkeypatch):
    dataset, answers_path = graded_run(tmp_path, "final")
    grid = json.loads(json.dumps(grade.build_grid(dataset, answers_path)))
    supported = {"text": "3,1 bar.", "citations": ["S1"], "support": "supported"}
    report = grade.metrics(fill(copy.deepcopy(grid), {"FIN-001": ("correct", [supported]), "FIN-002": ("correct", [{**supported, "citations": ["S1"]}]),
                                                      "FIN-003": ("justified_abstention", [])}), dataset, answers_path, TARGETS)
    # FIN-004 est répondable mais sans génération : il reste au dénominateur (2/3 < 0,85).
    assert report["status"] == "FAIL" and report["targets_met"]["answer_correctness"] is False
    assert grade.load_targets(ROOT / "config/local16.yaml") == TARGETS
    monkeypatch.setattr(grade, "EVALS", tmp_path)
    dataset_path = tmp_path / "final-resolved.json"
    output = tmp_path / "runtime" / "final-grid.json"
    grade.main(["grid", "--dataset", str(dataset_path), "--answers", str(answers_path), "--output", str(output)])
    with pytest.raises(SystemExit):
        grade.main(["grid", "--dataset", str(dataset_path), "--answers", str(answers_path), "--output", str(output)])
    with pytest.raises(SystemExit):
        grade.main(["grid", "--dataset", str(dataset_path), "--answers", str(answers_path), "--output", str(tmp_path / "runtime" / "final.json")])


def test_bootstrap_ratio_groups_assertions_by_question_with_fixed_seed():
    first = grade.bootstrap_ratio([(1, 1), (0, 2), (3, 3), (0, 0)])
    assert first == grade.bootstrap_ratio([(1, 1), (0, 2), (3, 3)]) and first["questions"] == 3
    assert first["successes"] == 4 and first["denominator"] == 6 and first["interval_95"][0] <= first["rate"] <= first["interval_95"][1]
    assert grade.bootstrap_ratio([])["rate"] is None


# --- 6. perf.py ----------------------------------------------------------------------------------------------------

def perf_dataset(tmp_path, split="development"):
    items = [question(f"DEV-00{index}", split=split) for index in range(1, 5)] + [question("DEV-005", followup="DEV-001"), question("DEV-006", resolved=False)]
    return datasets(tmp_path, items, split)[1]


def test_perf_measures_disjoint_searches_and_queries_without_extrapolation(tmp_path):
    dataset = perf_dataset(tmp_path)
    api = FakeApi({"Question DEV-003 ?": answered("3.1 bar [S1].", eval_count=120, load_ns=5_000_000_000),
                   "Question DEV-004 ?": answered("3.1 bar [S1].", eval_count=410, load_ns=20_000_000)})
    output = tmp_path / "runtime" / "perf.json"
    report = perf.run(dataset, output, BASE, 2, 2, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    assert [body["question"] for body in api.searches] == ["Question DEV-001 ?", "Question DEV-002 ?"]
    assert [body["question"] for body in api.posts] == ["Question DEV-003 ?", "Question DEV-004 ?"]
    summary = report["summary"]
    assert summary["search"]["api_elapsed_ms"]["p50"] == 20.0 and summary["search"]["api_elapsed_ms"]["p95"] == pytest.approx(29.0)
    assert summary["queries"]["by_residency"]["cold"]["count"] == 1 and summary["queries"]["by_residency"]["warm"]["count"] == 1
    assert summary["queries"]["by_residency"]["cold"]["load_ms"]["p50"] == 5000.0 and summary["queries"]["eval_count"]["max"] == 410
    assert summary["queries"]["answers_reaching_400_tokens"]["status"] == "OBSERVED" and summary["queries"]["answers_reaching_400_tokens"]["shorter_answer_lengths"] == [120]
    assert report["queries"][0]["decode_tokens_per_s"] == pytest.approx(120 / 0.7, rel=1e-3) and report["status"] == "MEASURED_NOT_QUALIFIED"
    assert json.loads(output.read_text(encoding="utf-8"))["summary"] == summary
    with pytest.raises(ValueError, match="aucun écrasement"):
        perf.run(dataset, output, BASE, 1, 0, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")


def test_perf_reports_unobserved_long_answers_and_refuses_final_or_oversized_requests(tmp_path):
    dataset = perf_dataset(tmp_path)
    api = FakeApi({"Question DEV-001 ?": answered("3.1 bar [S1].", eval_count=90), "Question DEV-002 ?": refused()},
                  identity=[IDENTITY, {**IDENTITY, "profile_sha256": "q" * 64}])
    report = perf.run(dataset, tmp_path / "runtime" / "short.json", BASE, 0, 2, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    assert report["summary"]["queries"]["status_counts"] == {"DONE": 1, "ERROR": 1} and report["summary"]["queries"]["model_generations"] == 1
    assert report["queries"][1]["error_code"] == "resource_admission_denied"
    assert report["summary"]["queries"]["answers_reaching_400_tokens"]["status"] == "NOT_OBSERVED"
    assert report["summary"]["queries"]["answers_reaching_400_tokens"]["client_terminal_ms"]["p95"] is None
    assert report["status"] == "INVALID_API_IDENTITY_DRIFT"
    with pytest.raises(ValueError, match="4 disponibles"):
        perf.run(dataset, tmp_path / "runtime" / "big.json", BASE, 3, 2, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    with pytest.raises(ValueError, match="tenu à l'écart"):
        perf.run(perf_dataset(tmp_path, "final"), tmp_path / "runtime" / "final-perf.json", BASE, 1, 0, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")


# Accélération relue dans /api/v1/diagnostics (W025) : D07 exige le CPU imposé par le profil, effectif et sans repli.
CPU_IMPOSED = {"requested": "cpu", "requested_source": "profile", "mode": "cpu", "reason": "imposed_by_profile", "fallback": None}
GPU_AUTO = {"requested": "auto", "requested_source": "profile", "mode": "gpu", "reason": "gpu_discovered", "fallback": None}
FALLEN_BACK = {**GPU_AUTO, "mode": "cpu", "fallback": {"utc": "2026-10-01T22:00:00+00:00", "http_status": 500, "error": "CUDA error"}}


def with_accelerator(*states):
    return [{**IDENTITY, **({"llm_accelerator": state} if state is not None else {})} for state in states]


def test_perf_marks_a_cpu_imposed_series_d07_eligible_and_keeps_each_answer_execution(tmp_path):
    events = answered("3.1 bar [S1].", eval_count=120)
    events[-1][1]["metrics"]["llm_execution"] = {"mode": "cpu", "fallback": False}
    api = FakeApi({"Question DEV-001 ?": events}, identity=with_accelerator(CPU_IMPOSED, CPU_IMPOSED))
    report = perf.run(perf_dataset(tmp_path), tmp_path / "runtime" / "d07.json", BASE, 0, 1, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    assert (report["status"], report["d07_eligible"], report["d07_ineligible_reason"]) == ("MEASURED_NOT_QUALIFIED", True, None)
    assert report["accelerator"] == {"before": CPU_IMPOSED, "after": CPU_IMPOSED} and api.diagnostics_calls == 2
    assert report["queries"][0]["llm_execution"] == {"mode": "cpu", "fallback": False}
    assert perf.diagnostics_identity({**IDENTITY, "llm_accelerator": GPU_AUTO}) == IDENTITY


@pytest.mark.parametrize("before,after,status,reason", [
    (None, None, "MEASURED_NOT_QUALIFIED", "accelerator_unreported"),
    (GPU_AUTO, GPU_AUTO, "MEASURED_NOT_QUALIFIED", "cpu_not_imposed_by_profile"),
    ({**GPU_AUTO, "mode": "cpu", "reason": "no_gpu_discovered"},) * 2 + ("MEASURED_NOT_QUALIFIED", "cpu_not_imposed_by_profile"),
    ({**CPU_IMPOSED, "requested_source": "legacy_num_gpu", "reason": "legacy_profile_cpu"},) * 2 + ("MEASURED_NOT_QUALIFIED", None),
    (FALLEN_BACK, FALLEN_BACK, "MEASURED_NOT_QUALIFIED", "cpu_not_imposed_by_profile"),
    ({**CPU_IMPOSED, "mode": "gpu"},) * 2 + ("MEASURED_NOT_QUALIFIED", "generation_not_on_cpu"),
    ({**CPU_IMPOSED, "fallback": FALLEN_BACK["fallback"]},) * 2 + ("MEASURED_NOT_QUALIFIED", "gpu_fallback_recorded"),
    (GPU_AUTO, FALLEN_BACK, "INVALID_ACCELERATOR_DRIFT", "accelerator_drift"),
    (GPU_AUTO, {**GPU_AUTO, "mode": "cpu"}, "INVALID_ACCELERATOR_DRIFT", "accelerator_drift"),
    (CPU_IMPOSED, None, "INVALID_ACCELERATOR_DRIFT", "accelerator_drift"),
    (None, CPU_IMPOSED, "INVALID_ACCELERATOR_DRIFT", "accelerator_drift"),
], ids=["api-anterieure", "gpu", "auto-sur-cpu", "forme-anterieure", "repli-avant-la-serie", "incoherent-gpu", "incoherent-repli",
        "repli-pendant-la-serie", "mode-change", "publication-perdue", "publication-apparue"])
def test_perf_d07_eligibility_and_accelerator_drift(tmp_path, before, after, status, reason):
    api = FakeApi({"Question DEV-001 ?": answered("3.1 bar [S1].")}, identity=with_accelerator(before, after))
    report = perf.run(perf_dataset(tmp_path), tmp_path / "runtime" / "series.json", BASE, 0, 1, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    assert (report["status"], report["d07_ineligible_reason"], report["d07_eligible"]) == (status, reason, reason is None)
    assert report["api_identity"] == report["api_identity_after"] == IDENTITY


@pytest.mark.parametrize("before,after", [(GPU_AUTO, FALLEN_BACK), (CPU_IMPOSED, CPU_IMPOSED)], ids=["avec-derive-d-acceleration", "cpu-impose"])
def test_perf_identity_drift_prevails_over_accelerator_drift_and_is_never_d07_eligible(tmp_path, before, after):
    # Une série invalidée n'est jamais éligible, même en CPU imposé : le motif suit la priorité du statut.
    identity = with_accelerator(before, after)
    identity[1]["profile_sha256"] = "q" * 64
    api = FakeApi({"Question DEV-001 ?": answered("3.1 bar [S1].")}, identity=identity)
    report = perf.run(perf_dataset(tmp_path), tmp_path / "runtime" / "both.json", BASE, 0, 1, transport=httpx.MockTransport(api), runtime_root=tmp_path / "runtime")
    assert (report["status"], report["d07_eligible"], report["d07_ineligible_reason"]) == ("INVALID_API_IDENTITY_DRIFT", False, "api_identity_drift")


# --- 8. extra_fixtures.py ------------------------------------------------------------------------------------------

def test_extra_fixtures_are_reproducible_in_temporary_directories_and_match_delivered_files(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    assert set(extra_fixtures.write(first).values()) == {"CREATED"}
    assert set(extra_fixtures.write(first).values()) == {"UNCHANGED"}
    extra_fixtures.write(second)
    assert snapshot_tree(first) == snapshot_tree(second)
    for relative, data in snapshot_tree(first / "fixtures").items():
        assert (ROOT / "fixtures" / relative).read_bytes() == data, relative
    pdf = first / "fixtures/qualification-v2.1/hostile/markup-injection.pdf"
    pdf.write_bytes(pdf.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="autres octets"):
        extra_fixtures.write(first)


def _extra_fixtures_copy(tmp_path):
    """Copie autonome de l'outil (extra_fixtures, generate, corpus_data) et des quatre fichiers livrés : son ROOT est la copie."""
    copy_root = tmp_path / "copie"
    for name in ("extra_fixtures.py", "generate.py", "corpus_data.py"):
        target = copy_root / "tools/qualification" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / "tools/qualification" / name).read_bytes())
    for fixture in extra_fixtures.FIXTURES:
        for relative in (fixture["path"], fixture["path"].removesuffix(".pdf") + ".sidecar.json"):
            target = copy_root / "fixtures" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / "fixtures" / relative).read_bytes())
    return copy_root


@pytest.mark.parametrize(("change", "code", "status"), [(None, 0, "PASS"), ("altered", 1, "FAIL"), ("missing", 1, "FAIL")])
def test_extra_fixtures_check_exit_code_follows_its_status(tmp_path, change, code, status):
    """Rejeu R3 (J8) : `--check` sortait avec le code 0 même quand une fixture livrée ne se reproduisait plus."""
    copy_root = _extra_fixtures_copy(tmp_path)
    pdf = copy_root / "fixtures/qualification-v2.1/hostile/markup-injection.pdf"
    if change == "altered":
        pdf.write_bytes(pdf.read_bytes() + b"\n")
    elif change == "missing":
        pdf.unlink()
    completed = subprocess.run([sys.executable, str(copy_root / "tools/qualification/extra_fixtures.py"), "--check"], cwd=copy_root,
                               capture_output=True, text=True, encoding="utf-8", timeout=300, check=False)
    report = json.loads(completed.stdout)
    assert (completed.returncode, report["status"]) == (code, status), completed.stderr
    assert report["identical"]["qualification-v2.1/hostile/markup-injection.pdf"] is (change is None)
    assert report["identical"]["qualification-v2.1/layouts/long-document-14p.pdf"] is True
    assert not pdf.exists() or change != "missing", "--check n'écrit jamais dans le dossier contrôlé"


@pytest.mark.parametrize(("name", "pages"), [("hostile/markup-injection", 1), ("layouts/long-document-14p", 14)])
def test_extra_fixture_sidecars_describe_real_bytes_pages_and_literal_text(name, pages):
    pdf = ROOT / "fixtures/qualification-v2.1" / f"{name}.pdf"
    sidecar = json.loads((ROOT / "fixtures/qualification-v2.1" / f"{name}.sidecar.json").read_text(encoding="utf-8"))
    assert sidecar["sha256"] == sha(pdf.read_bytes()) and sidecar["bytes"] == pdf.stat().st_size and sidecar["pages"] == pages
    assert sidecar["marking"] == "SYNTHETIQUE" and sidecar["synthetic"] is True and not sidecar["in_manifest"] and not sidecar["in_question_sets"]
    assert b"D:20000101000000" in pdf.read_bytes()
    texts = extra_fixtures.inspect(pdf.read_bytes())
    assert len(texts) == pages and [len(text) for text in texts] == sidecar["native_characters_per_page"]
    text = " ".join(" ".join(page.split()) for page in texts)
    for expected in sidecar["expected_native_strings"]:
        assert expected in text
    manifest = json.loads((evidence_io.EVALS / "manifest.json").read_text(encoding="utf-8"))
    assert f"qualification-v2.1/{name}.pdf" not in {entry["path"] for entry in manifest["entries"]}


def test_protected_names_cannot_be_reached_with_trailing_dot_or_stream(tmp_path):
    for name in ("final.json.", "final.json ", "Final.JSON. .", "notes.json:final.json", "FINAL~1.JSO"):
        with pytest.raises(ValueError):
            evidence_io.checked_output(tmp_path / name, [tmp_path])


def test_resume_reasks_questions_refused_before_any_model_call():
    records = [{"record": "header"},
               {"record": "submitted", "question_id": "DEV-001", "query_id": "q1"},
               {"record": "result", "question_id": "DEV-001", "status": "API_ERROR", "model_called": False},
               {"record": "submitted", "question_id": "DEV-002", "query_id": "q2"},
               {"record": "result", "question_id": "DEV-002", "status": "API_ERROR", "model_called": True}]
    submitted, results = answers.journal_state(records)
    assert "DEV-001" not in results and "DEV-001" not in submitted
    assert results["DEV-002"]["model_called"] is True


# --- 9. Chaîne [EVAL] : sorties hors Git sous .runtime/qa/ ---------------------------------------------------------
# evals/qualification-v2.1/runtime/ est suivi par Git : la campagne Linux J8 (L8) a dû rejouer la chaîne depuis une
# copie du dépôt. Chaque outil accepte aussi .runtime/qa/ ; ses autres règles de sortie restent les mêmes.

def test_eval_chain_tools_default_to_the_runtime_qa_folder():
    assert evidence_io.LOCAL_QA == ROOT / ".runtime" / "qa"
    for module in (check_reproducibility, capture_bindings, merge_bindings, resolve, answers, grade):
        assert module.LOCAL_QA == evidence_io.LOCAL_QA, module.__name__


def test_capture_bindings_accepts_a_new_output_under_runtime_qa(tmp_path, monkeypatch, capsys):
    qa = tmp_path / "qa"
    monkeypatch.setattr(capture_bindings, "LOCAL_QA", qa, raising=False)
    argv = ["capture_bindings.py", "--document-id", "6f1e1c7a-0c6e-4f43-9b52-1d8f3a3e2b10", "--document-key", "cle-absente", "--output"]
    # Sortie acceptée : l'outil passe au contrôle suivant (clé absente du manifeste), avant tout appel HTTP.
    monkeypatch.setattr(sys, "argv", [*argv, str(qa / "2026-10-02-linux-DA-P01-published.json")])
    with pytest.raises(SystemExit):
        capture_bindings.main()
    assert "absent from the controlled manifest" in capsys.readouterr().err
    existing = qa / "deja-capture.json"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"{}")
    for refused in (tmp_path / "ailleurs.json", qa / "manifest.json", existing):
        monkeypatch.setattr(sys, "argv", [*argv, str(refused)])
        with pytest.raises(SystemExit):
            capture_bindings.main()
        assert "absent from the controlled manifest" not in capsys.readouterr().err
    assert existing.read_bytes() == b"{}"


def test_merge_bindings_accepts_snapshots_and_output_under_runtime_qa(tmp_path, monkeypatch):
    qa = tmp_path / "qa"
    qa.mkdir()
    (tmp_path / "manifest.json").write_text(json.dumps({"entries": [{"key": "k1", "sha256": "a" * 64}]}), encoding="utf-8")
    monkeypatch.setattr(merge_bindings, "EVALS", tmp_path)
    monkeypatch.setattr(merge_bindings, "LOCAL_QA", qa, raising=False)
    path, digest = write_snapshot(qa, "k1-published.json", binding_snapshot("k1", "a" * 64))
    outside, outside_digest = write_snapshot(tmp_path, "outside-published.json", binding_snapshot("k1", "a" * 64))
    with pytest.raises(SystemExit):
        merge_bindings.main(["--input", str(outside), outside_digest, "--output", str(qa / "merged.json")])
    output = qa / "2026-10-02-linux-development-bindings.json"
    assert merge_bindings.main(["--input", str(path), digest, "--output", str(output)])["documents"] == ["k1"]
    # La source est désignée par son chemin dans le projet, même quand .runtime est un lien vers un autre volume.
    assert json.loads(output.read_text(encoding="utf-8"))["sources"][0]["path"] == ".runtime/qa/k1-published.json"


def test_resolve_accepts_a_new_output_under_runtime_qa(tmp_path, monkeypatch):
    qa = tmp_path / "qa"
    dataset, bindings = tmp_path / "development.json", tmp_path / "bindings.json"
    dataset.write_text(json.dumps({"questions": []}), encoding="utf-8")
    bindings.write_text(json.dumps({"documents": {}}), encoding="utf-8")
    monkeypatch.setattr(resolve, "EVALS", tmp_path / "evals")
    monkeypatch.setattr(resolve, "LOCAL_QA", qa, raising=False)
    argv = ["--dataset", str(dataset), "--bindings", str(bindings), "--output"]
    output = qa / "2026-10-02-linux-development-resolved.json"
    assert resolve.main([*argv, str(output)])["resolved_questions"] == 0 and output.is_file()
    for refused in (output, qa / "final.json", tmp_path / "resolved.json"):
        with pytest.raises(SystemExit):
            resolve.main([*argv, str(refused)])


def test_answers_and_grade_accept_outputs_under_runtime_qa(tmp_path, monkeypatch):
    qa = tmp_path / "qa"
    items = [question("DEV-001")]
    source, resolved = datasets(tmp_path, items)
    api = FakeApi({"Question DEV-001 ?": answered("La pression de DA-P01 est de 3,1 bar [S1].")})
    for module in (answers, grade):
        monkeypatch.setattr(module, "EVALS", tmp_path / "evals")
        monkeypatch.setattr(module, "LOCAL_QA", qa, raising=False)
    journal_path = qa / "2026-10-02-linux-development-answers.jsonl"
    result = answers.run(resolved, source, journal_path, BASE, "development", transport=httpx.MockTransport(api))
    assert result["complete"] and journal(journal_path)[0]["record"] == "header"
    with pytest.raises(ValueError, match="hors des dossiers"):
        answers.run(resolved, source, tmp_path / "answers.jsonl", BASE, "development", transport=httpx.MockTransport(api))
    grid = qa / "2026-10-02-linux-development-grid.json"
    grade.main(["grid", "--dataset", str(resolved), "--answers", str(journal_path), "--output", str(grid)])
    assert json.loads(grid.read_text(encoding="utf-8"))["rows"][0]["question_id"] == "DEV-001"
    for refused in (grid, tmp_path / "grid.json", qa / "development.json"):
        with pytest.raises(SystemExit):
            grade.main(["grid", "--dataset", str(resolved), "--answers", str(journal_path), "--output", str(refused)])
    assert len(api.posts) == 1
