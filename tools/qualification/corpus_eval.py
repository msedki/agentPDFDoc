"""Évaluation de la recherche et du contexte sur le corpus réel, sans modèle de réponse (R21).

Protocole : `RAG_Local_Agents/reports/evaluation-methodology-sources-2026-09-30.md` §3 et décision W013.

`build` tire des questions des blocs publiés de l'instance : valeur avec unité (sujet + « est de »),
identifiant, hors périmètre (identifiant d'un document interrogé sur un autre) et sans réponse
(identifiant voisin absent de tout le corpus). La vérité terrain est le bloc d'origine ; les autres
blocs qui portent la même valeur ou le même identifiant sont déclarés comme alternatives. Le jeu
contient du texte du corpus privé : il reste sous `.runtime/` et n'est jamais affiché.

`run` interroge `POST /api/v1/admin/evaluation/context` (jeton de contrôle, aucun appel au modèle) et
calcule Success@10, rang réciproque, couverture du contexte final, abstention de recherche et fuite
de périmètre, avec intervalles de Wilson. Le rapport ne contient que des identifiants et des agrégats.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.retrieval import identifiers, normalized_identifier  # noqa: E402
from services.runtime.supervisor import app_origin, control_headers, data_path, load_profile  # noqa: E402

# Unités usuelles des notices techniques ; les plus longues d'abord, pour que « N·m » ne s'arrête pas à « N ».
UNIT_NAMES = ["bar", "mbar", "kPa", "MPa", "Pa", "V", "kV", "mV", "A", "mA", "kA", "W", "kW", "MW", "VA", "kVA", "Hz", "kHz", "°C", "°", "K",
              "mm", "cm", "m", "km", "mm²", "m²", "m³", "l", "L", "kg", "g", "t", "N", "kN", "N·m", "N.m", "Nm", "daN", "s", "ms", "min", "h",
              "%", "tr/min", "rpm", "km/h", "m/s"]
UNITS = "(?:" + "|".join(re.escape(unit) for unit in sorted(UNIT_NAMES, key=len, reverse=True)) + ")"
VALUE_SENTENCE = re.compile(
    r"(?P<subject>(?:La|Le|Les|L['’])\s?[^.;:!?\n]{3,90}?)\s(?:est|sont|vaut|valent)\s(?:de|d['’]|égale?s? à|fixée?s? à|réglée?s? à|limitée?s? à|comprise?s? entre)?\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s?(?P<unit>" + UNITS + r")(?![\w/])")
IDENTIFIER_TEMPLATES = ("Que précise le document au sujet de {code} ?", "Quelles informations sont données pour {code} ?",
                        "À quoi correspond {code} dans la documentation ?")


def fold(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))


def terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[^\W_]{3,}", fold(text))}


# Mots des gabarits : exclus du recouvrement, qui ne mesure que les mots porteurs repris du bloc.
TEMPLATE_TERMS = {"quelle", "quelles", "valeur", "est", "sont", "indiquee", "pour", "que", "precise", "document", "sujet",
                  "informations", "donnees", "correspond", "dans", "documentation", "les", "des"}


# Bornes [basse, haute[ ; la dernière tranche ne contient que les questions reprenant tous leurs mots porteurs.
OVERLAP_BANDS = (("faible", 0.0, 0.5), ("partiel", 0.5, 1.0), ("complet", 1.0, 1.01))


def lexical_overlap(question: str, block_text: str) -> float:
    """Part des mots porteurs de la question présents dans le bloc (fuite lexicale, protocole §2.7)."""
    asked = terms(question) - TEMPLATE_TERMS
    return round(len(asked & terms(block_text)) / len(asked), 3) if asked else 0.0


def normalize_value(value: str, unit: str) -> str:
    return f"{value.replace(',', '.')} {unit.replace('N.m', 'N·m').replace('Nm', 'N·m')}"


VALUE_WITH_UNIT = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s?(?P<unit>" + UNITS + r")(?![\w/])")
STOP_CONTEXT = {"de", "du", "des", "la", "le", "les", "l", "d", "à", "a", "au", "aux", "et", "ou", "en", "est", "sont", "par", "pour", "sur", "un", "une"}


def context_value_questions(block: dict[str, Any]) -> list[dict[str, Any]]:
    """Valeur avec unité précédée d'au moins trois mots porteurs dans la même proposition (listes, consignes)."""
    found = []
    text = block.get("text") or ""
    for match in VALUE_WITH_UNIT.finditer(text):
        clause = re.split(r"[.;:!?\n()|]", text[:match.start()])[-1]
        # Lettres Unicode (« manœuvre » reste un mot), chiffres exclus ; apostrophes et traits d'union internes gardés.
        words = re.findall(r"[^\W\d_](?:[^\W\d_]|['’-])+", clause)
        carriers = [word for word in words if fold(word) not in STOP_CONTEXT]
        if len(carriers) < 3:
            continue
        subject = " ".join(words[-8:])
        found.append({"category": "valeur", "question": f"Quelle valeur est indiquée pour « {subject} » ?",
                      "expected_value": normalize_value(match.group("value"), match.group("unit")), "template": "contexte_precedent",
                      "reduced_cue": " ".join(carriers[:3])})
    return found


def value_questions(block: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for match in VALUE_SENTENCE.finditer(block.get("text") or ""):
        subject = re.sub(r"\s+", " ", match.group("subject")).strip()
        subject = subject[0].lower() + subject[1:]
        if len(terms(subject)) < 2:
            continue
        found.append({"category": "valeur", "question": f"Quelle est {subject} ?" if not subject.startswith("les ") else f"Quelles sont {subject} ?",
                      "expected_value": normalize_value(match.group("value"), match.group("unit")), "template": "sujet_est_de"})
    # Gabarit de repli, mesuré à part (recouvrement lexical plus fort) : seulement sans phrase « sujet est de ».
    return found or context_value_questions(block)


def mutate_identifier(code: str, known: set[str], rng: random.Random) -> str | None:
    """Identifiant voisin plausible (un chiffre modifié), absent de tout le corpus."""
    positions = [index for index, char in enumerate(code) if char.isdigit()]
    rng.shuffle(positions)
    for index in positions:
        for digit in rng.sample("0123456789", 10):
            candidate = code[:index] + digit + code[index + 1:]
            if candidate != code and normalized_identifier(candidate) not in known:
                return candidate
    return None


def build_dataset(blocks: list[dict[str, Any]], *, seed: int = 20260930, max_per_category: dict[str, int] | None = None,
                  exclude: dict[str, set[str]] | None = None) -> dict[str, Any]:
    """Jeu déterministe à partir de blocs publiés : chaque bloc porte document_id, version_id, page_index, id, text, route.

    `exclude` écarte les blocs attendus (`block_ids`) et les identifiants (`identifiers`) d'une série précédente,
    pour qu'une série de confirmation ne réutilise aucune question déjà analysée."""
    limits = {"valeur": 40, "identifiant": 20, "hors_perimetre": 10, "sans_reponse": 10, **(max_per_category or {})}
    excluded_blocks = set((exclude or {}).get("block_ids", set()))
    excluded_codes = set((exclude or {}).get("identifiers", set()))
    rng = random.Random(seed)
    by_identifier: dict[str, list[dict[str, Any]]] = {}
    for block in blocks:
        for code in identifiers(block.get("text") or ""):
            by_identifier.setdefault(normalized_identifier(code), []).append({**block, "code": code})
    known = set(by_identifier)
    documents = sorted({block["document_id"] for block in blocks})
    candidates: dict[str, list[dict[str, Any]]] = {name: [] for name in limits}
    for block in blocks:
        if block["id"] in excluded_blocks:
            continue
        for item in value_questions(block):
            same_value = [other["id"] for other in blocks if other["id"] != block["id"] and item["expected_value"].split()[0] in (other.get("text") or "").replace(",", ".")]
            candidates["valeur"].append({**item, "scope": {"kind": "documents", "documentIds": [block["document_id"]]},
                                         "expected_block_ids": [block["id"]], "alternative_block_ids": same_value[:20], "source": block})
    for holders in by_identifier.values():
        # Identifiant discriminant : défini dans un ou deux blocs, un seul document ; codes courts ou numériques purs écartés.
        code = holders[0]["code"]
        if len(holders) > 2 or len({holder["document_id"] for holder in holders}) != 1 or len(code) < 4 or not re.search(r"[A-Za-z]", code):
            continue
        if normalized_identifier(code) in excluded_codes or any(holder["id"] in excluded_blocks for holder in holders):
            continue
        source = holders[0]
        candidates["identifiant"].append({"category": "identifiant", "question": rng.choice(IDENTIFIER_TEMPLATES).format(code=code),
                                          "scope": {"kind": "documents", "documentIds": [source["document_id"]]}, "expected_block_ids": [holder["id"] for holder in holders],
                                          "alternative_block_ids": [], "identifier": code, "source": source})
        others = [document for document in documents if document != source["document_id"]]
        if others:
            candidates["hors_perimetre"].append({"category": "hors_perimetre", "question": rng.choice(IDENTIFIER_TEMPLATES).format(code=code),
                                                 "scope": {"kind": "documents", "documentIds": [rng.choice(others)]}, "expected_block_ids": [],
                                                 "alternative_block_ids": [], "identifier": code, "expected_abstention": True, "source": source})
        absent = mutate_identifier(code, known, rng)
        if absent:
            candidates["sans_reponse"].append({"category": "sans_reponse", "question": rng.choice(IDENTIFIER_TEMPLATES).format(code=absent),
                                               "scope": {"kind": "library"}, "expected_block_ids": [], "alternative_block_ids": [], "identifier": absent,
                                               "expected_abstention": True, "source": source})
    questions = []
    for category, limit in limits.items():
        pool = candidates[category]
        rng.shuffle(pool)
        # Quota des pages lues par OCR (protocole §2.9) : jusqu'au quart de la catégorie, puis le reste dans l'ordre tiré.
        ocr_first = [item for item in pool if item["source"].get("route") == "regional_ocr"][: max(1, limit // 4)]
        pool = ocr_first + [item for item in pool if item not in ocr_first]
        for item in pool[:limit]:
            source = item.pop("source")
            item.update({"document_id": source["document_id"], "page_index": source["page_index"], "route": source.get("route"),
                         "lexical_overlap": lexical_overlap(item["question"], source.get("text") or ""), "source_text": source.get("text") or ""})
            questions.append(item)
    # Variantes (série 2) : même question sur toute la bibliothèque ; indices réduits pour les valeurs.
    variants = []
    for item in questions:
        if item["category"] not in {"valeur", "identifiant"}:
            continue
        variants.append({**item, "variant": "portee_bibliotheque", "scope": {"kind": "library"}})
        if item.get("reduced_cue"):
            variants.append({**item, "variant": "indices_reduits", "question": f"Quelle valeur pour {item['reduced_cue']} ?", "scope": {"kind": "library"},
                             "lexical_overlap": None})
    for item in variants:
        if item["lexical_overlap"] is None:
            item["lexical_overlap"] = lexical_overlap(item["question"], item["source_text"])
    for item in questions:
        item.setdefault("variant", "reference")
    questions += variants
    for item in questions:
        item.pop("source_text", None)
    # Séparation par document (protocole §3.4) : un document entier en développement ou tenu à l'écart.
    holdout = {document for index, document in enumerate(sorted(documents, key=lambda value: hashlib.sha256(value.encode()).hexdigest())) if index % 2}
    for index, item in enumerate(questions):
        item["id"] = f"q{index + 1:03d}"
        item["split"] = "holdout" if item["document_id"] in holdout else "development"
    return {"format": "corpus-eval-v1", "seed": seed, "documents": len(documents), "blocks": len(blocks), "questions": questions,
            "candidates_available": {name: len(pool) for name, pool in candidates.items()}}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    phat = successes / total
    center = (phat + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0.0, center - radius), 3), round(min(1.0, center + radius), 3)]


def block_ids(source: dict[str, Any]) -> set[str]:
    return {block["id"] for block in source.get("blocks", []) if block.get("id")} | set(source.get("block_ids") or [])


def score(question: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Mesures d'une question à partir de la réponse de l'évaluation de contexte (aucun texte conservé)."""
    wanted = set(question["expected_block_ids"]) | set(question.get("alternative_block_ids", []))
    top10 = [block_ids(source) for source in result.get("retrieval_top10", [])]
    final = [block_ids(source) for source in result.get("retrieval_final", [])]
    context = [block_ids(source) for source in result.get("context_sources", [])]
    rank = next((position for position, ids in enumerate(top10, 1) if ids & wanted), None)
    row: dict[str, Any] = {"id": question["id"], "category": question["category"], "variant": question.get("variant", "reference"),
                           "split": question["split"], "route": question.get("route"),
                           "lexical_overlap": question.get("lexical_overlap"), "state": result.get("state")}
    if question.get("expected_abstention"):
        code = normalized_identifier(question["identifier"])
        leaked = [source.get("document_id") for source in result.get("retrieval_final", [])
                  if code in normalized_identifier(source.get("text") or "") and source.get("document_id") not in question["scope"].get("documentIds", [source.get("document_id")])]
        warned = any(warning.get("code") == "identifier_not_found_in_scope" for warning in result.get("warnings", []) if isinstance(warning, dict))
        row.update({"search_abstention": warned, "scope_leakage": len(leaked)})
        return row
    row.update({"success_at_10": rank is not None, "reciprocal_rank": round(1 / rank, 4) if rank else 0.0,
                "in_final": any(ids & wanted for ids in final), "in_context": any(ids & wanted for ids in context)})
    return row


def rate(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [item[key] for item in items if key in item]
    hits = sum(bool(value) for value in values)
    return {"numerator": hits, "denominator": len(values), "rate": round(hits / len(values), 3) if values else None, "wilson95": wilson(hits, len(values))}


def rate_table(items: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: rate(items, key) for key in keys}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows if "success_at_10" in row]
    unanswerable = [row for row in rows if "search_abstention" in row]
    report: dict[str, Any] = {
        "answerable": {"success_at_10": rate(answerable, "success_at_10"), "in_final": rate(answerable, "in_final"), "in_context": rate(answerable, "in_context"),
                       "mrr_at_10": round(sum(row["reciprocal_rank"] for row in answerable) / len(answerable), 4) if answerable else None},
        "unanswerable": {"search_abstention": rate(unanswerable, "search_abstention"),
                         "scope_leakage_total": sum(row["scope_leakage"] for row in unanswerable)},
        "by_category": {}, "by_split": {}, "by_overlap_band": {}, "by_route": {}, "by_variant": {}}
    for field, target in (("category", "by_category"), ("split", "by_split"), ("route", "by_route"), ("variant", "by_variant")):
        for value in sorted({str(row.get(field)) for row in answerable}):
            subset = [row for row in answerable if str(row.get(field)) == value]
            report[target][value] = {"success_at_10": rate(subset, "success_at_10"), "in_context": rate(subset, "in_context")}
    # Tranches fixes (protocole §2.7) : des terciles se confondent dès que la plupart des questions reprennent tous leurs mots porteurs.
    for name, low, high in OVERLAP_BANDS:
        subset = [row for row in answerable if row.get("lexical_overlap") is not None and low <= row["lexical_overlap"] < high]
        report["by_overlap_band"][name] = {"success_at_10": rate(subset, "success_at_10"), "in_context": rate(subset, "in_context")}
    report["overlap_bands"] = {name: [low, min(high, 1.0)] for name, low, high in OVERLAP_BANDS}
    return report


def reaggregate(path: Path) -> dict[str, Any]:
    """Recalcule les mesures d'un rapport à partir de ses lignes, sans rejouer les requêtes."""
    report = json.loads(path.read_text(encoding="utf-8"))
    report["metrics"] = aggregate([row for row in report["rows"] if "error" not in row])
    report["metrics_recomputed_utc"] = dt.datetime.now(dt.UTC).isoformat()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def instance(profile_path: Path) -> tuple[str, str | bool, dict[str, str]]:
    profile = load_profile(profile_path)
    headers = control_headers(data_path(profile))
    if not headers:
        raise SystemExit("Jeton de contrôle absent : démarrer l'instance du profil (.\\rag.ps1 up)")
    origin, verify = app_origin(profile)
    return origin, verify, headers


def fetch_blocks(client: httpx.Client, exclude_sha256: set[str]) -> list[dict[str, Any]]:
    tree = client.get("/api/v1/library/tree", params={"limit": 200}).json()
    blocks = []
    for document in tree["documents"]:
        if not document.get("active_generation_id") or document.get("sha256") in exclude_sha256:
            continue
        version = document.get("active_version_id") or document.get("version_id")
        for page_index in range(int(document.get("page_count") or 0)):
            response = client.get(f"/api/v1/versions/{version}/pages/{page_index}/blocks")
            if response.status_code != 200:
                continue
            page = response.json()
            route = (page.get("page") or {}).get("extraction_route")
            for block in page["blocks"]:
                if block.get("type") in {"text", "heading", "caption", "table", "list_item"} and (block.get("text") or "").strip():
                    blocks.append({"id": block["id"], "document_id": document["id"], "version_id": version, "page_index": page_index,
                                   "text": block["text"], "route": route})
    return blocks


def fixture_hashes() -> set[str]:
    manifest = ROOT / "evals/qualification-v2.1/manifest.json"
    if not manifest.is_file():
        return set()
    entries = json.loads(manifest.read_text(encoding="utf-8")).get("entries", [])
    return {entry.get("sha256") for entry in entries if entry.get("sha256")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output", type=Path, required=True, help="Jeu à écrire sous .runtime/ (contient du texte du corpus)")
    build.add_argument("--seed", type=int, default=20260930)
    build.add_argument("--exclude-dataset", type=Path, action="append", default=[],
                       help="Jeu précédent dont les blocs attendus et les identifiants sont écartés (série de confirmation)")
    run = sub.add_parser("run")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--report", type=Path, required=True, help="Rapport agrégé, sans texte du corpus")
    recompute = sub.add_parser("reaggregate", help="Recalculer les mesures d'un rapport existant à partir de ses lignes")
    recompute.add_argument("--report", type=Path, required=True)
    for command in (build, run):
        command.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    args = parser.parse_args()
    if args.command == "reaggregate":
        metrics = reaggregate(args.report.resolve())["metrics"]
        print(json.dumps({"answerable": metrics["answerable"], "by_overlap_band": metrics["by_overlap_band"]}, ensure_ascii=False))
        return 0
    origin, verify, headers = instance(args.profile)
    with httpx.Client(base_url=origin, headers={"Origin": origin, **headers}, verify=verify, trust_env=False, timeout=httpx.Timeout(300, connect=10)) as client:
        if args.command == "build":
            output = args.output.resolve()
            if not output.is_relative_to((ROOT / ".runtime").resolve()) or output.exists():
                raise SystemExit("Le jeu contient du texte du corpus : nouveau fichier sous .runtime/ exigé")
            exclude: dict[str, set[str]] = {"block_ids": set(), "identifiers": set()}
            for previous in args.exclude_dataset:
                for item in json.loads(previous.read_text(encoding="utf-8"))["questions"]:
                    exclude["block_ids"].update(item.get("expected_block_ids") or [])
                    if item.get("identifier"):
                        exclude["identifiers"].add(normalized_identifier(item["identifier"]))
            dataset = build_dataset(fetch_blocks(client, fixture_hashes()), seed=args.seed, exclude=exclude)
            dataset["excluded_datasets_sha256"] = [hashlib.sha256(previous.read_bytes()).hexdigest() for previous in args.exclude_dataset]
            dataset["created_utc"] = dt.datetime.now(dt.UTC).isoformat()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            dataset_sha = hashlib.sha256(output.read_bytes()).hexdigest()
            print(json.dumps({"questions": Counter(item["category"] for item in dataset["questions"]), "documents": dataset["documents"],
                              "blocks": dataset["blocks"], "available": dataset["candidates_available"], "sha256": dataset_sha}, ensure_ascii=False))
            return 0
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = []
        failures: Counter[str] = Counter()
        for question in dataset["questions"]:
            body = {"question": question["question"], "scope": question["scope"], "mode": "question"}
            response = client.post("/api/v1/admin/evaluation/context", json=body)
            if response.status_code != 200:
                failures[str(response.json().get("code", response.status_code))] += 1
                rows.append({"id": question["id"], "category": question["category"], "split": question["split"], "error": response.status_code})
                continue
            rows.append(score(question, response.json()))
        scored = [row for row in rows if "error" not in row]
        report: dict[str, Any] = {"format": "corpus-eval-report-v1", "utc": dt.datetime.now(dt.UTC).isoformat(),
                  "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(), "questions": len(dataset["questions"]),
                  "scored": len(scored), "request_failures": dict(failures), "method": "POST /api/v1/admin/evaluation/context (aucun appel au modèle)",
                  "metrics": aggregate(scored), "rows": rows}
        target = args.report.resolve()
        if target.exists():
            raise SystemExit("Rapport existant : choisir un nouveau fichier")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(report["metrics"]["answerable"], ensure_ascii=False))
        print(json.dumps(report["metrics"]["unanswerable"], ensure_ascii=False))
        return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
