"""Capture read-only loopback API bindings for one already published controlled fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Binding JSON endpoints must not redirect away from the authorized loopback request")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8785")
    parser.add_argument("--document-id", type=UUID, required=True)
    parser.add_argument("--document-key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-published-partial", action="store_true",
                        help="accepter une extraction partielle publiée explicitement ; son état est consigné dans la capture")
    args = parser.parse_args()
    origin = urlparse(args.base_url)
    if origin.scheme != "http" or origin.hostname not in {"127.0.0.1", "localhost"} or origin.username or origin.password or origin.path not in {"", "/"} or origin.query or origin.fragment:
        parser.error("Only the supervisor-authorized HTTP loopback API origin is accepted")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "evals" / "qualification-v2.1" / "runtime") or output.exists():
        parser.error("Use a new file under evals/qualification-v2.1/runtime; evidence is never overwritten")
    manifest = json.loads((ROOT / "evals/qualification-v2.1/manifest.json").read_text(encoding="utf-8"))
    descriptor = next((entry for entry in manifest["entries"] if entry["key"] == args.document_key), None)
    if not descriptor:
        parser.error("The document key is absent from the controlled manifest")
    original = (ROOT / "fixtures" / descriptor["path"]).resolve()
    if not original.is_relative_to(ROOT / "fixtures" / "qualification-v2.1") or hashlib.sha256(original.read_bytes()).hexdigest() != descriptor["sha256"]:
        raise ValueError("Controlled original diverges from the existing frozen manifest")
    opener = build_opener(ProxyHandler({}), NoRedirect())

    # Session locale (W011) : jeton de contrôle de l'instance transmis par l'environnement, jamais en argument.
    token = os.environ.get("RAG_CONTROL_TOKEN")

    def read(route: str) -> dict:
        request = Request(args.base_url.rstrip("/") + "/api/v1" + route, headers={"x-rag-control-token": token} if token else {})
        with opener.open(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    document = read(f"/documents/{args.document_id}")
    version_id = document.get("active_version_id")
    accepted = {"ready", "ready_partial"} if args.allow_published_partial else {"ready"}
    if document.get("state") not in accepted or not version_id or not document.get("active_generation_id") or not document.get("extraction_revision_id"):
        raise ValueError("A fully ready published generation with real version and revision is required")
    version_id = str(UUID(version_id))
    version = next((value for value in document.get("versions", []) if value["id"] == version_id), None)
    if not version or version["sha256"] != descriptor["sha256"] or version["page_count"] != descriptor["expected_pages"]:
        raise ValueError("Published original SHA/page count does not match the controlled fixture")
    pages = [read(f"/versions/{version_id}/pages/{index}/blocks") for index in range(version["page_count"])]
    for index, page in enumerate(pages):
        if page.get("version_id") != version_id or page.get("page", {}).get("page_index") != index:
            raise ValueError("A returned page does not match the requested immutable version/page")
        for block in page.get("blocks", []):
            raw = block.get("raw_text")
            if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != block.get("source_text_hash"):
                raise ValueError("Exact API raw_text/hash is absent or divergent")
            if block.get("extraction_revision_id") != document["extraction_revision_id"]:
                raise ValueError("Returned block revision diverges from the published generation")
    snapshot = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "method": "Read-only loopback GET document detail and immutable version pages; UTF-8 JSON decoded explicitly; no retrieval/model/import.",
        "documents": {args.document_key: {
            "document_id": document["id"], "version_id": version_id,
            "extraction_revision_id": document["extraction_revision_id"],
            "generation_id": document["active_generation_id"],
            "file_sha256": version["sha256"], "document_state": document.get("state"), "document": document, "pages": pages,
        }},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "document_id": document["id"], "version_id": version_id, "pages": len(pages), "blocks": sum(len(page["blocks"]) for page in pages)}))


if __name__ == "__main__":
    main()
