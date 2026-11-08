"""Parcours I4 en HTTP/SSE réel, avec sessions et composants natifs non substitués.

Lancer par run_grounded_native.py --transport http pour posséder les services.
Le serveur Uvicorn écoute sur un socket loopback réservé ; le client HTTPX parle
au réseau, sans ASGITransport ni appel de QueryService par le pilote. Les lectures
SQLite/traces servent uniquement à vérifier l'ordre de publication observé.
Les verdicts documentaires restent une relecture séparée des sources gelées.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx
import psutil
import uvicorn


def save(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    path.chmod(0o600)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_sse_frame(lines: list[str]) -> dict | None:
    """Ne filtre aucun type : un événement privé publié doit rendre le contrôle rouge."""
    fields: dict[str, str] = {}
    data: list[str] = []
    for line in lines:
        if not line or line.startswith(":"):
            continue
        name, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if name == "data":
            data.append(value)
        elif name in {"event", "id"}:
            fields[name] = value
    if not data:
        return None
    return {"id": int(fields["id"]), "type": fields.get("event", "message"),
            "data": json.loads("\n".join(data))}


async def read_public_stream(client: httpx.AsyncClient, query_id: str, output: Path,
                             *, after: int | None = None) -> list[dict]:
    headers = {"Last-Event-ID": str(after)} if after is not None else {}
    rows = []
    with output.open("x", encoding="utf-8") as saved:
        output.chmod(0o600)
        async with client.stream("GET", f"/api/v1/queries/{query_id}/events", headers=headers) as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("text/event-stream"):
                raise ValueError("La route publique n'a pas renvoyé un flux SSE.")
            frame: list[str] = []
            async for line in response.aiter_lines():
                if line:
                    frame.append(line)
                    continue
                event = parse_sse_frame(frame)
                frame = []
                if event is None:
                    continue
                event.update(arrived_utc=datetime.now(UTC).isoformat(), arrived_monotonic_ns=time.monotonic_ns())
                rows.append(event)
                saved.write(json.dumps(event, ensure_ascii=False) + "\n")
                saved.flush()
            if frame:
                # Une trame tronquée n'est pas réinterprétée comme un événement complet.
                raise ValueError("Le flux SSE se termine au milieu d'une trame.")
    return rows


def publication_checks(run: dict, public: list[dict], stored: list[dict], trace: list[dict], identity: dict) -> dict:
    """Preuve d'ordre et d'intégrité du transport, jamais oracle de sens documentaire."""
    validations = [row for row in trace if row["phase"] == "answer.support_validation"]
    deltas = [row for row in public if row["type"] == "delta"]
    stored_by_id = {row["id"]: row for row in stored}
    validation_time = datetime.fromisoformat(validations[-1]["utc"]) if validations else None
    ordered = bool(validation_time is not None and deltas)
    for delta in deltas:
        persisted = stored_by_id.get(delta["id"])
        if persisted is None or validation_time is None:
            ordered = False
            continue
        ordered = ordered and (validation_time <= datetime.fromisoformat(persisted["created_at"])
                               <= datetime.fromisoformat(delta["arrived_utc"]))
        ordered = ordered and json.loads(persisted["data_json"]) == delta["data"]
    terminals = [row for row in public if row["type"] in {"done", "error", "cancelled"}]
    phases = {row["phase"] for row in trace}
    received_done = any(row["phase"] == "llm.response" and row.get("data", {}).get("received_done")
                        for row in trace)
    requests = [row["data"] for row in trace if row["phase"] == "llm.request"]
    validation = validations[-1].get("data", {}) if validations else {}
    checks = {
        "query_done": run["state"] == "done",
        "actual_model_exchange": run.get("metrics", {}).get("model_called") is True
                                 and "llm.request" in phases and received_done,
        "locked_4b_identity_observed": bool(requests) and all(
            request.get("body", {}).get("model") == identity["name"]
            and request.get("verified_model_identity", {}).get("digest") == identity["digest"]
            and request.get("verified_model_identity", {}).get("manifest_sha256") == identity["manifest_sha256"]
            for request in requests),
        "render_guard_commits_exact_answer": validation.get("status") == "passed"
            and validation.get("unsupported_characters") == 0
            and validation.get("answer_sha256") == hashlib.sha256(run["answer"].encode()).hexdigest(),
        "public_deltas_after_verified_render": bool(ordered),
        "no_private_structured_event": not any(row["type"] in {"structured_delta", "structured_answer"}
                                                for row in public),
        "exactly_one_success_terminal": len(terminals) == 1 and terminals[0]["type"] == "done",
        "public_delta_matches_stored_answer": bool(deltas) and "".join(
            row["data"].get("text", "") for row in deltas) == run["answer"],
        "monotonic_unique_public_ids": [row["id"] for row in public] == sorted({row["id"] for row in public}),
    }
    return {"checks": checks, "passed": all(checks.values()),
            "meaning": "transport and publication ordering only; source support requires independent review"}


async def json_request(client: httpx.AsyncClient, method: str, path: str, **kwargs) -> dict:
    response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


async def open_session(client: httpx.AsyncClient, control: str) -> None:
    link = await json_request(client, "POST", "/api/v1/admin/session-links", headers={"X-RAG-Control-Token": control})
    # Le lien à usage unique et les cookies ne sont jamais consignés dans les preuves.
    try:
        opened = await client.get(link["path"], follow_redirects=False)
    except httpx.HTTPError:
        raise RuntimeError("Transport interrompu pendant l'ouverture de session.") from None
    if opened.status_code != 303 or opened.headers.get("location") != "/workspace/":
        raise ValueError("L'ouverture authentifiée de la session a échoué.")
    csrf = client.cookies.get("rag_csrf")
    if not csrf:
        raise ValueError("Cookie CSRF de développement absent.")
    client.headers["X-CSRF-Token"] = csrf


async def import_document(client: httpx.AsyncClient, specification: dict, inputs: Path, output: Path) -> dict:
    original = Path(specification["path"])
    original = (original if original.is_absolute() else inputs.parent / original).resolve(strict=True)
    if sha256(original) != specification["sha256"]:
        raise ValueError("Original différent du manifeste HTTP.")
    started = time.monotonic()
    with original.open("rb") as source:
        imported = await json_request(client, "POST", "/api/v1/documents/import",
                                      files={"files": (original.name, source, "application/octet-stream")},
                                      data={"relative_paths": json.dumps([specification["relative_path"]])})
    observations: list[dict] = []
    try:
        while True:
            state = await json_request(client, "GET", "/api/v1/jobs", params={"limit": 200})
            job = next(item for item in state["jobs"] if item["id"] == imported["job_id"])
            if not observations or observations[-1]["state"] != job["state"]:
                observations.append({"state": job["state"], "elapsed_seconds": time.monotonic() - started,
                                     "job": job})
            if job["state"] in {"error", "cancelled", "ready_partial", "paused"}:
                raise ValueError("Import HTTP non prêt : " + job["state"])
            if job["state"] == "ready":
                detail = await json_request(client, "GET", "/api/v1/documents/" + imported["document_id"])
                if detail["active_version_id"] != imported["version_id"] or not detail["active_generation_id"]:
                    raise ValueError("Le travail prêt n'est pas la version publiée attendue.")
                return {**imported, "document": detail}
            if time.monotonic() - started > 180:
                raise TimeoutError("Import HTTP non terminé en 180 secondes.")
            await asyncio.sleep(0.2)
    finally:
        save(output, {"import": imported, "observations": observations,
                      "elapsed_seconds": time.monotonic() - started})


async def citation_snapshot(client: httpx.AsyncClient, query_id: str, source_ids: list[str]) -> dict:
    return {source_id: await json_request(client, "GET", f"/api/v1/citations/{query_id}/{source_id}")
            for source_id in source_ids}


async def original_hash(client: httpx.AsyncClient, version_id: str) -> str:
    response = await client.get(f"/api/v1/versions/{version_id}/file")
    response.raise_for_status()
    return hashlib.sha256(response.content).hexdigest()


async def campaign(args, application) -> int:
    dataset = json.loads(args.inputs.read_text(encoding="utf-8"))
    if dataset.get("protocol") != "production-I4-HTTP-SSE-v1" or len(dataset["cases"]) != 1:
        raise ValueError("Un seul parcours HTTP figé est attendu.")
    if args.case_id and args.case_id != [dataset["cases"][0]["id"]]:
        raise ValueError("Identifiant de parcours HTTP inconnu ou répété.")
    if any(os.environ.get(key) for key in ("RAG_DATA_DIR", "RAG_DB_PATH")):
        raise ValueError("Stockage externe interdit dans cette campagne isolée.")
    args.output.mkdir(parents=True, exist_ok=False)
    args.output.chmod(0o700)
    settings = application.Settings.load(args.profile)
    if settings.value("llm", "model") != "qwen3-4b-enhanced:q4km":
        raise ValueError("Le générateur doit être le 4B verrouillé.")
    if settings.value("security", "environment") != "development":
        raise ValueError("Ce parcours loopback qualifie le profil de développement, sans changer sa sécurité.")
    if settings.value("enhanced", "answer_contract") is not True:
        raise ValueError("Le contrôle de fidélité doit rester actif.")
    settings.profile["app"]["data_dir"] = str(args.output / "data")
    settings.profile["sqlite"]["path"] = str(args.output / "data/app.sqlite3")
    settings.profile["trace"].update(mode="full", max_files=512, max_total_bytes=268435456,
                                    max_bytes_per_query=8388608)
    manifest_path = settings.path(settings.value("llm", "model_manifest"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["model"]
    identity = {"name": manifest.get("name", manifest.get("model")), "digest": manifest["digest"],
                "manifest_sha256": sha256(manifest_path), "details": manifest["details"]}
    if (identity["name"] != "qwen3-4b-enhanced:q4km" or identity["details"].get("parameter_size") != "4.0B"
            or identity["details"].get("family") != "qwen3" or identity["details"].get("quantization_level") != "Q4_K_M"):
        raise ValueError("Identité provisionnée hors du générateur 4B quantifié autorisé.")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    settings.profile["app"]["port"] = listener.getsockname()[1]
    control = secrets.token_urlsafe(32)
    previous_control = os.environ.get("RAG_CONTROL_TOKEN")
    os.environ["RAG_CONTROL_TOKEN"] = control
    monitor = application.MemorySampler(args.output / "memory.jsonl", args.service_pid)
    harness = Path(__file__).resolve()
    (args.output / "measurement-harness.py").write_bytes(harness.read_bytes())
    (args.output / "source-diff.patch").write_bytes(subprocess.check_output(
        ["git", "diff", "HEAD", "--binary"], cwd=args.application_root))
    (args.output / "source-status.txt").write_bytes(subprocess.check_output(
        ["git", "status", "--short"], cwd=args.application_root))
    save(args.output / "protocol-frozen.json", {
        "created_utc": datetime.now(UTC).isoformat(), "dataset": dataset,
        "inputs_sha256": sha256(args.inputs), "profile_file_sha256": sha256(args.profile),
        "profile": settings.profile, "source_code": application.freeze_code(args.output),
        "locked_generator_identity": identity,
        "application_root": str(args.application_root), "revision_label": args.revision_label,
        "measurement_harness_sha256": sha256(harness), "transport": "real loopback HTTP and SSE",
        "component_substitutions": [], "browser_exercised": False,
        "query_timeout_seconds": 600, "import_timeout_seconds": 180,
        "order": "one frozen question; no automatic retry; original-version check after replacement",
        "environment": {"platform": platform.platform(), "python": sys.version,
                        "libraries": {name: version(name) for name in (
                            "httpx", "uvicorn", "fastapi", "tokenizers", "onnxruntime", "python-docx")},
                        "physical_memory_bytes": psutil.virtual_memory().total,
                        "logical_cpus": os.cpu_count()},
    })
    monitor.thread.start()
    server = None
    server_task = None
    stage = "application_start"
    outcome = 1
    final = None
    try:
        app = application.create_app(settings=settings, start_jobs=True)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=settings.profile["app"]["port"],
                                log_level="warning", access_log=False, timeout_graceful_shutdown=30))
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        origin = f"http://127.0.0.1:{settings.profile['app']['port']}"
        async with httpx.AsyncClient(base_url=origin, trust_env=False, timeout=httpx.Timeout(60)) as client:
            deadline = time.monotonic() + 45
            while not server.started:
                if server_task.done():
                    await server_task
                    raise RuntimeError("L'API native s'est arrêtée avant disponibilité.")
                if time.monotonic() > deadline:
                    raise TimeoutError("L'API native n'est pas prête en 45 secondes.")
                await asyncio.sleep(0.1)
            await json_request(client, "GET", "/api/v1/health")
            stage = "session"
            await open_session(client, control)
            stage = "ingestion"
            monitor.label = stage
            await json_request(client, "POST", "/api/v1/runtime/mode", json={"mode": "ingestion"})
            documents = {}
            for specification in dataset["documents"]:
                documents[specification["key"]] = await import_document(
                    client, specification, args.inputs, args.output / (specification["key"] + "-import.json"))
            save(args.output / "bindings-before.json", documents)
            case = dataset["cases"][0]
            scope = {"kind": "documents", "documentIds": [documents[key]["document_id"]
                     for key in case["scope"]["document_keys"]]}
            stage = "query"
            monitor.label = stage
            started = time.monotonic()
            created = await json_request(client, "POST", "/api/v1/queries",
                                         json={"question": case["question"], "scope": scope, "mode": "question"})
            query_id = created["query_id"]
            save(args.output / "attempt-start.json", {"case_id": case["id"], "query_id": query_id,
                                                     "created_utc": datetime.now(UTC).isoformat(), "scope": scope})
            timed_out = False
            try:
                public = await asyncio.wait_for(read_public_stream(client, query_id, args.output / "public-sse.jsonl"), 600)
            except TimeoutError:
                timed_out = True
                await json_request(client, "POST", f"/api/v1/queries/{query_id}/cancel")
                public = [json.loads(line) for line in (args.output / "public-sse.jsonl").read_text().splitlines()]
            run = await json_request(client, "GET", f"/api/v1/queries/{query_id}")
            # Observation seule : laisser la trace capturer le terminal HTTP déjà reçu.
            deadline = time.monotonic() + 5
            while query_id in app.state.queries.tasks and not app.state.queries.tasks[query_id].done():
                if time.monotonic() > deadline:
                    raise TimeoutError("Le travail HTTP ne s'est pas libéré après son terminal.")
                await asyncio.sleep(0.02)
            from services.api.execution_trace import read_verified_trace

            trace_path = settings.data_dir / settings.value("trace", "directory", "traces") / (query_id + ".jsonl")
            trace = read_verified_trace(trace_path)
            stored = app.state.db.rows("SELECT * FROM events WHERE query_id=? ORDER BY id", (query_id,))
            # Seules les citations effectivement publiées exercent la persistance.
            # Un passage retenu mais absent de la réponse ne suffit pas à ce contrôle.
            source_ids = sorted({span["source_id"] for row in public if row["type"] == "delta"
                                 for span in row["data"].get("citation_spans", [])})
            citations_before = await citation_snapshot(client, query_id, source_ids)
            checks = publication_checks(run, public, stored, trace, identity)
            save(args.output / "query.json", {"case_id": case["id"], "variant": args.revision_label,
                 "run": run, "harness_timeout": timed_out, "elapsed_seconds": time.monotonic() - started,
                 "public_events": public, "stored_events": stored, "citations": citations_before,
                 "trace_sha256": sha256(trace_path), "publication": checks,
                 "judgment": "Documentary meaning unreviewed; no contract status used as oracle."})
            stage = "version_update"
            monitor.label = stage
            old_hashes = {key: await original_hash(client, value["version_id"]) for key, value in documents.items()}
            replacement = dataset["replacement"]
            await json_request(client, "POST", "/api/v1/runtime/mode", json={"mode": "ingestion"})
            new_document = await import_document(client, replacement, args.inputs, args.output / "replacement-import.json")
            old_after = {key: await original_hash(client, value["version_id"]) for key, value in documents.items()}
            new_hash = await original_hash(client, new_document["version_id"])
            citations_after = await citation_snapshot(client, query_id, source_ids)
            run_after = await json_request(client, "GET", f"/api/v1/queries/{query_id}")
            replacement_key = next(spec["key"] for spec in dataset["documents"]
                                   if spec["relative_path"] == replacement["relative_path"])
            versions = {
                "same_document_new_version": new_document["document_id"] == documents[replacement_key]["document_id"]
                                             and new_document["version_id"] != documents[replacement_key]["version_id"],
                "old_original_hashes_unchanged": old_hashes == old_after and all(
                    old_hashes[spec["key"]] == spec["sha256"] for spec in dataset["documents"]),
                "new_original_matches_frozen_replacement": new_hash == replacement["sha256"],
                "old_citations_unchanged": bool(citations_before) and citations_before == citations_after,
                "old_query_unchanged": run_after == run,
                "published_citation_affected_by_replacement": any(
                    citation.get("version_id") == documents[replacement_key]["version_id"]
                    and citation.get("document_id") == documents[replacement_key]["document_id"]
                    for citation in citations_before.values()),
                "old_citations_bound_to_original_versions": bool(citations_before) and all(
                    citation.get("version_id") in {value["version_id"] for value in documents.values()}
                    for citation in citations_before.values()),
            }
            save(args.output / "version-persistence.json", {"checks": versions,
                 "passed": all(versions.values()), "before_hashes": old_hashes, "after_hashes": old_after,
                 "replacement_hash": new_hash, "replacement_binding": new_document,
                 "citations_before": citations_before, "citations_after": citations_after})
            last_id = public[-1]["id"] if public else 0
            replay = await asyncio.wait_for(read_public_stream(client, query_id, args.output / "resume-sse.jsonl",
                                                               after=last_id), 30)
            telemetry = app.state.jobs.diagnostics()
            final = {"publication_passed": checks["passed"], "versions_passed": all(versions.values()),
                     "resume_after_terminal_is_empty": not replay, "harness_timeout": timed_out,
                     "ingestion": telemetry, "native_ingestion_verified": telemetry["native_worker_launches"] == 3
                     and telemetry["injected_runner_calls"] == 0, "documentary_judgment": "not automatically scored"}
            final["operational_passed"] = (final["publication_passed"] and final["versions_passed"]
                                           and final["resume_after_terminal_is_empty"] and not timed_out
                                           and final["native_ingestion_verified"])
            outcome = 0 if final["operational_passed"] else 1
    except Exception as error:
        # HTTP exceptions can carry session URLs; never persist their rendered message.
        save(args.output / "block-failure.json", {"stage": stage, "error_type": type(error).__name__,
             "failed_utc": datetime.now(UTC).isoformat(), "outputs_preserved": True,
             "kind": "harness_or_application_exception; no favorable retry"})
        raise
    finally:
        stopped = False
        stop_error = None
        if server is not None and server_task is not None:
            server.should_exit = True
            try:
                await asyncio.wait_for(asyncio.shield(server_task), 35)
                stopped = True
            except TimeoutError:
                stop_error = "shutdown_timeout"
                server.force_exit = True
                server_task.cancel()
                await asyncio.gather(server_task, return_exceptions=True)
            except Exception as error:
                stop_error = type(error).__name__
        listener.close()
        monitor.close()
        if previous_control is None:
            os.environ.pop("RAG_CONTROL_TOKEN", None)
        else:
            os.environ["RAG_CONTROL_TOKEN"] = previous_control
        save(args.output / "api-stop.json", {"api_stopped_gracefully": stopped,
             "listener_closed": listener.fileno() == -1, "shutdown_error_type": stop_error,
             "native_services_owned_by_parent_launcher": args.service_pid})
        save(args.output / "memory-peaks.json", monitor.peaks)
        frozen = json.loads((args.output / "code-manifest.json").read_text())
        changed = [name for name, checksum in frozen["files"].items() if not (args.application_root / name).is_file()
                   or sha256(args.application_root / name) != checksum]
        save(args.output / "source-stability.json", {"changed_since_freeze": changed})
        if changed or (server_task is not None and not stopped):
            raise RuntimeError("Code modifié pendant le parcours ou arrêt API non confirmé.")
    if final is not None:
        final.update(api_stopped_gracefully=stopped, source_unchanged=not changed,
                     operational_scope="API path; parent http-final-result.json also checks native service cleanup")
        final["operational_passed"] = final["operational_passed"] and stopped and not changed
        save(args.output / "transport-result.json", final)
        print(json.dumps({key: value for key, value in final.items() if key != "ingestion"}), flush=True)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--revision-label", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--service-pid", type=int, action="append", default=[])
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    args.application_root = args.application_root.resolve(strict=True)
    args.inputs = args.inputs.resolve(strict=True)
    args.output = args.output.resolve()
    from revision_campaign import load_application

    application = load_application(args.application_root)
    return asyncio.run(campaign(args, application))


if __name__ == "__main__":
    raise SystemExit(main())
