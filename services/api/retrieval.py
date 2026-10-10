import asyncio
import functools
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import httpx

from .embedding import EmbeddingService
from .errors import ApiError

# Tirets Unicode U+2010 à U+2015 et signe moins U+2212 : même séparateur que « - » (1 caractère pour 1, offsets conservés).
DASHES = str.maketrans(dict.fromkeys(map(chr, [*range(0x2010, 0x2016), 0x2212]), "-"))
IDENTIFIER_SOURCES = (
    r"\b(?:[A-Z]{2,8}[/-])*(?:EN|UIC|ISO|IEC)\s+\d+(?:[-.]\d+)*\b",  # normes : préfixes en majuscules seulement (« en 2020 » exclu)
    r"\b[A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)+(?:\.\d+)*\b",
    r"\b[A-Za-z]{1,12}\d+[A-Za-z0-9]*(?:\.\d+)*\b", r"\b\d+(?:\.\d+)+\b")
# Extraction (rien après « mot- », « mot_ », « mot/ » : P01 n'est pas extrait de DA-P01), identifiant finissant avant un « / », identifiant commençant après.
IDENTIFIER_PATTERNS = ([re.compile(r"(?<!\w[-_/])" + source) for source in IDENTIFIER_SOURCES],
                       [re.compile(r"(?<!\w[-_/])(?:" + source + r")\Z") for source in IDENTIFIER_SOURCES], [re.compile(source) for source in IDENTIFIER_SOURCES])
# Comparaison seulement : préfixe de norme aussi en minuscules (« en 50155 » contient EN 50155), sans masquer « 3.4.2 » dans « en 3.4.2 ».
CASELESS_STANDARD = re.compile(r"(?<!\w[-_/])" + IDENTIFIER_SOURCES[0].replace("(?:EN|UIC|ISO|IEC)", "(?i:EN|UIC|ISO|IEC)"))
STOPWORDS = frozenset("""a au aux avec ce ces cet cette comment dans de des donne donner donnee donnees du elle elles en entre est et etre
    il ils indique indiquer information informations la le les leur leurs ma mes moins mon ne nos notre numero ou par pas plus pour pourquoi
    precise preciser quand que quel quelle quelles quels qui quoi reference references sa sans selon ses son sont sous sur ta tes ton tous tout
    toute toutes tres un une valeur valeurs vos votre combien about and are does for from how many much number of the these this those value
    values what which with""".split())
# Mots qui désignent le périmètre ou le support de la question (« dans le document sélectionné », « in the selected file ») :
# présents dans presque tout contexte (« DOCUMENT SYNTHÉTIQUE », « Page 1 / 2 »), ils ne signalent aucune réponse (J8, L8).
# « section » reste un terme : c'est aussi une grandeur (section d'un câble).
SCOPE_WORDS = frozenset("""document documents dossier dossiers fichier fichiers page pages pdf perimetre selection selectionne
    selectionnee selectionnes selectionnees file files folder folders scope selected""".split())
# Mots-outils propres à chaque langue ; les formes ambiguës entre les deux (« a », « an », « on », « or ») sont écartées.
LANGUAGE_MARKERS = {
    "fr": frozenset("au aux avec ce ces cette dans de des du elle est et il la le les leur leurs ne nous par pas pour quel quelle quelles quels qui sont sur une vous".split()),
    "en": frozenset("and are be by does for from has have how in into is it its not of that the their there these this those to was were what when where which who why with".split()),
}


def normalized_identifier(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).translate(DASHES).strip()).upper()


@functools.lru_cache(maxsize=1024)
def _identifiers_in(text):
    # Mêmes frontières, listes et correspondances maximales que l'index : ce qui est extrait d'un texte y est « contenu ».
    folded = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).translate(DASHES)
    return frozenset(map(normalized_identifier, {folded[start:end] for start, end in identifier_spans(folded)}
                         | {match.group() for match in CASELESS_STANDARD.finditer(folded)}))


def contains_identifier(text, identifier):
    return normalized_identifier(identifier) in _identifiers_in(text)


def identifier_spans(text):
    """Correspondances maximales seulement : une étendue incluse dans une autre (P01 dans DA-P01) est écartée.
    Un « / » entre deux identifiants complets sépare une liste (DA-P01/DA-P02, EN 50155/EN 50121-3-2) ; ailleurs il relie (X/P01, ISO/IEC 27001)."""
    extract, ending, starting = IDENTIFIER_PATTERNS
    folded = text.translate(DASHES)
    for slash in [match.start() for match in re.finditer(r"(?<=\w)/(?=\w)", folded)]:
        if any(pattern.search(folded, max(0, slash - 48), slash) for pattern in ending) and any(pattern.match(folded, slash + 1) for pattern in starting):
            folded = folded[:slash] + "," + folded[slash + 1:]  # 1 caractère pour 1 : offsets conservés
    spans, reached = [], -1
    for start, end in sorted({match.span() for pattern in extract for match in pattern.finditer(folded)}, key=lambda span: (span[0], -span[1])):
        if end > reached:
            spans.append((start, end))
            reached = end
    return spans


def identifiers(text):
    return sorted({text[start:end] for start, end in identifier_spans(text)})


@functools.lru_cache(maxsize=128)
def _normalized_offsets(text):
    """NFKC/casse avec offsets dans le texte original, y compris expansions/compositions."""
    folded: list[str] = []
    offsets: list[tuple[int, int]] = []
    position = 0
    while position < len(text):
        start = position
        position += 1
        while position < len(text):
            char = text[position]
            if unicodedata.category(char).startswith("M"):
                position += 1
                continue
            piece = text[start:position]
            if unicodedata.normalize("NFKC", piece + char) == unicodedata.normalize("NFKC", piece) + unicodedata.normalize("NFKC", char):
                break
            position += 1
        for char in unicodedata.normalize("NFKC", text[start:position]).translate(DASHES).upper():
            if char.isspace():
                if folded and folded[-1] == " ":
                    offsets[-1] = (offsets[-1][0], position)
                    continue
                char = " "
            folded.append(char)
            offsets.append((start, position))
    return "".join(folded), offsets


@functools.lru_cache(maxsize=1024)
def reference_spans(text, identifier):
    """Occurrences littérales maximales ; les spans retournés restent en points de code source."""
    target = normalized_identifier(identifier)
    if not target:
        return ()
    folded, offsets = _normalized_offsets(text)
    if target in _identifiers_in(target):
        spans = identifier_spans(folded) + [match.span() for match in CASELESS_STANDARD.finditer(folded)]
        matches = [(lo, hi) for lo, hi in spans if normalized_identifier(folded[lo:hi]) == target]
    else:
        # Une valeur de focus nue n'est pas une sous-référence de ABC-X/ABC_1/X/ABC.
        pattern = re.compile(r"(?<![\w\-_/\.])" + re.escape(target) + r"(?![\w\-_/]|\.\w)")
        matches = [match.span() for match in pattern.finditer(folded)]
    result = []
    for lo, hi in matches:
        start, end = offsets[lo][0], offsets[hi - 1][1]
        if normalized_identifier(text[start:end]) == target:
            result.append((start, end))
    return tuple(sorted(set(result)))


@dataclass(frozen=True)
class ReferenceCandidate:
    raw: str
    normalized: str
    origin: str
    syntax: str
    ambiguous: bool
    question_start: int | None = None
    question_end: int | None = None


@dataclass
class ReferenceResolution:
    """Décision par requête : candidats exacts distincts des obligations de couverture."""
    original_question: str
    candidates: tuple[ReferenceCandidate, ...]
    obligations: dict[str, str]
    occurrences: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def priority(self):
        return {candidate.normalized for candidate in self.candidates}

    def matches(self, text, code):
        return bool(reference_spans(text, code))

    def source_matches(self, source, code):
        blocks = source.get("blocks")
        return any(self.matches(block["text"], code) for block in blocks) if blocks else self.matches(source["text"], code)

    def attest(self, sources, stage):
        occurrences = []
        seen = set()
        for source in sources:
            for block in source.get("blocks", []):
                for code in sorted(self.priority):
                    for start, end in reference_spans(block["text"], code):
                        offset = block.get("start_offset", 0)
                        item = {"identifier": code, "role": "text_occurrence", "version_id": source["version_id"],
                                "generation_id": source["generation_id"], "extraction_revision_id": block["extraction_revision_id"],
                                "block_id": block["id"], "source_text_hash": block["source_text_hash"],
                                "start_offset": offset + start, "end_offset": offset + end,
                                "page_index": block.get("page_index"), "locator": block.get("locator")}
                        key = (code, source["generation_id"], block["id"], offset + start, offset + end)
                        if key not in seen:
                            seen.add(key)
                            occurrences.append(item)
        self.occurrences[stage] = occurrences

    def as_dict(self):
        return {"candidates": [{"raw": item.raw, "normalized": item.normalized, "origin": item.origin,
                                "syntax": item.syntax, "ambiguous": item.ambiguous,
                                "question_start": item.question_start, "question_end": item.question_end}
                               for item in self.candidates],
                "obligations": [{"normalized": code, "reason": reason} for code, reason in sorted(self.obligations.items())],
                "occurrences": {stage: list(items) for stage, items in self.occurrences.items()}}


def resolve_references(question, focus_identifier=None, focus_origin="focus.identifier"):
    candidates = []
    obligations = {}
    for start, end in identifier_spans(question):
        raw = question[start:end]
        code = normalized_identifier(raw)
        structured = any(char.isdecimal() for char in code)
        candidates.append(ReferenceCandidate(raw, code, "question", "structured" if structured else "alphabetic_compound",
                                             not structured, start, end))
        if structured:
            obligations[code] = "structured_syntax"
    if focus_identifier and (code := normalized_identifier(focus_identifier)):
        candidates.append(ReferenceCandidate(focus_identifier, code, focus_origin, "explicit_nomination", False))
        obligations[code] = focus_origin
    return ReferenceResolution(question, tuple(candidates), obligations)


def _folded_words(text):
    return re.findall(r"[^\W_]+", "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char)))


def _term_keys(text, excluded=STOPWORDS):
    return {word[:5] for word in _folded_words(text) if len(word) >= 3 and word not in excluded}


def answer_terms(question):
    """Termes contextuels de la question : hors identifiants, mots-outils et mots du périmètre, réduits à 5 caractères
    (heuristique lexicale)."""
    parts, cursor = [], 0
    for start, end in identifier_spans(question):
        parts.append(question[cursor:start])
        cursor = max(cursor, end)
    return _term_keys(" ".join(parts + [question[cursor:]]), STOPWORDS | SCOPE_WORDS)


def has_answer_terms(text, terms):
    # Sans terme contextuel (« Quelle valeur pour DA-P01 ? »), l'occurrence de l'identifiant suffit.
    return not terms or bool(terms & _term_keys(text))


def text_language(text):
    """« fr » ou « en » quand les mots-outils d'une langue dominent nettement le texte ; None pour un texte court, mixte
    ou dans une autre langue."""
    words = _folded_words(text)
    counts = {language: sum(word in markers for word in words) for language, markers in LANGUAGE_MARKERS.items()}
    (language, high), (_, low) = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return language if high >= 2 and high > 2 * low else None


def answer_terms_comparable(question, text):
    """Faux quand la question et le texte ont chacun une langue reconnue et qu'elles diffèrent : l'absence de termes
    communs ne dit alors rien de la réponse (question anglaise sur une preuve française, J8, L8)."""
    asked, written = text_language(question), text_language(text)
    return asked is None or written is None or asked == written


def match_expression(text):
    terms = re.findall(r"[^\W_]+", text, flags=re.UNICODE)[:64]
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


# Méthodes d'extraction d'un bloc dont le texte vient, au moins en partie, de la reconnaissance de caractères (ingestion).
OCR_METHODS = frozenset({"ocr", "mixed"})
# Valable pour une recherche comme pour une question : aucune mention de « la réponse ».
PARTIAL_EXTRACTION_MESSAGE = ("Extraction partielle : des pages ou des régions de ce document sont absentes de l'extraction ou ont été lues "
                              "avec une confiance insuffisante. Des informations peuvent manquer ; vérifiez les passages retrouvés sur la "
                              "page originale.")


def ocr_evidence_warnings(sources):
    """Un avertissement par document dont une source porte un bloc lu par OCR (méthode ocr ou mixed), dans l'ordre des sources.

    Une méthode `unknown` ou `native` n'en déclenche pas. `source_ids` liste les sources concernées quand elles ont un
    identifiant (sources d'une question) ; il est vide pour une recherche, qui n'en attribue pas."""
    documents: dict[str, dict[str, Any]] = {}
    for source in sources:
        methods = OCR_METHODS.intersection(source.get("extraction_methods") or [])
        if not methods:
            continue
        entry = documents.setdefault(source["document_id"], {"name": source.get("document_name"), "methods": set(), "source_ids": []})
        entry["methods"].update(methods)
        if source.get("source_id"):
            entry["source_ids"].append(source["source_id"])
    return [{"code": "ocr_evidence", "document_id": document_id, "document_name": entry["name"], "extraction_methods": sorted(entry["methods"]),
             "source_ids": entry["source_ids"],
             "message": ("Passages de « " + entry["name"] + " »" if entry["name"] else "Passages de ce document") +
                        " lus par reconnaissance optique de caractères (OCR) : des signes, unités ou références peuvent être faux même "
                        "sans alerte de faible confiance. Comparez les valeurs utilisées avec la page originale."}
            for document_id, entry in documents.items()]


def dense_identity_warning(documents):
    """Documents du périmètre dont la génération active n'a aucun point dans la collection de l'identité dense courante."""
    names = [item["document_name"] for item in documents]
    quoted = [f"« {name} »" for name in names[:5]]
    listing = quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " et " + quoted[-1]
    if len(names) > 5:
        rest = len(names) - 5
        listing = ", ".join(quoted) + f" et {rest} autre" + ("s" if rest > 1 else "")
    message = ("Recherche sémantique incomplète : " + listing + " n'a pas d'index sémantique pour le modèle d'embedding actuel. "
               "La recherche par mots peut encore le retrouver ; réindexez-le pour rétablir la recherche sémantique." if len(names) == 1 else
               f"Recherche sémantique incomplète : {len(names)} documents n'ont pas d'index sémantique pour le modèle d'embedding actuel "
               f"({listing}). La recherche par mots peut encore les retrouver ; réindexez-les pour rétablir la recherche sémantique.")
    return {"code": "dense_identity_mismatch", "document_ids": [item["document_id"] for item in documents], "document_names": names,
            "message": message}


class DenseCoverage:
    """Générations actives sans aucun point dans la collection de l'identité dense courante (R26-IDX-02).

    Mode dégradé signalé, non bloquant : la branche lexicale reste servie, la recherche et les questions avertissent et
    /readiness nomme l'état. Le compte d'une génération active vient de `count_generation` (collection courante) ; il est
    gardé pour la vie du processus, car une génération publiée ne gagne ni ne perd de points et l'identité ne change qu'au
    redémarrage. L'ensemble actif est relu dans SQLite à chaque consultation : une publication y entre à la lecture
    suivante, une génération remplacée ou nettoyée en sort. Aucune écriture SQLite."""

    def __init__(self, db, vectors):
        self.db, self.vectors = db, vectors
        self.points: dict[str, int] = {}
        self.present: bool | None = None
        self._lock = asyncio.Lock()

    async def status(self, collection_absent=None):
        """État `complete`, `dense_migration_incomplete`, `unverifiable` (liste ou compte en échec) ou `not_applicable`
        (double de test sans compte), avec les documents à réindexer connus et l'état de la collection courante :
        `present`, `absent` (comme `absent_*` de /readiness, sans erreur Qdrant) ou `unverified`. /readiness fournit
        `collection_absent` ; sinon, avant de compter une génération nouvelle, la liste des collections du projet dit si
        la collection courante existe. Absente : toute génération active portant des fragments est à réindexer, sans compte.
        L'ensemble actif est lu sous le verrou, avec les comptes qu'il met à jour."""
        if not hasattr(self.vectors, "count_generation"):
            return {"state": "not_applicable", "collection": "unverified", "documents": [], "active_generations": None, "error_code": None}
        error_code = None
        async with self._lock:
            rows = await asyncio.to_thread(self.db.rows, "SELECT g.id AS generation_id,d.id AS document_id,d.name AS document_name,"
                                          "COALESCE(g.actual_chunks,g.expected_chunks,0) AS chunks FROM documents d "
                                          "JOIN index_generations g ON g.id=d.active_generation_id WHERE d.deleted_at IS NULL ORDER BY d.relative_path")
            active = {row["generation_id"] for row in rows}
            self.points = {generation: count for generation, count in self.points.items() if generation in active}
            pending = [row for row in rows if row["chunks"] and row["generation_id"] not in self.points]
            if collection_absent is not None:
                self.present = not collection_absent
            elif pending and hasattr(self.vectors, "project_collections"):
                try:
                    self.present = self.vectors.collection in await self.vectors.project_collections()
                except ApiError as error:
                    error_code = error.code
            if self.present is False:
                missing = [row for row in rows if row["chunks"]]
            else:
                for row in pending if error_code is None else []:
                    try:
                        self.points[row["generation_id"]] = await self.vectors.count_generation(row["generation_id"])
                    except ApiError as error:
                        error_code = error.code
                        break
                missing = [row for row in rows if row["chunks"] and self.points.get(row["generation_id"]) == 0]
            collection = "unverified" if self.present is None else "present" if self.present else "absent"
        state = "dense_migration_incomplete" if missing else "unverifiable" if error_code else "complete"
        return {"state": state, "collection": collection, "active_generations": len(rows), "error_code": error_code,
                "documents": [{"document_id": row["document_id"], "document_name": row["document_name"], "generation_id": row["generation_id"]}
                              for row in missing]}


def rrf(lexical, dense, k=60):
    scores: dict[str, float] = {}
    for ranking in (lexical, dense):
        for rank, chunk_id in enumerate(dict.fromkeys(ranking), 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def placement_matches(effective):
    """Placement mémoire relu après création (W017) : vecteurs et payload `cold`, graphe HNSW `cached`.

    Qdrant 1.19.1 déprécie `on_disk` et `on_disk_payload` au profit de `memory`, qui prévaut quand les deux sont présents.
    Une collection créée avant W017 ne porte que l'ancienne forme, dont les valeurs par défaut documentées sont les mêmes
    (`on_disk: true` = `cold`, HNSW `on_disk: false` = `cached`, `on_disk_payload: true` = `cold`)."""
    params = effective["params"]
    dense = params["vectors"].get("dense", {})
    hnsw = effective.get("hnsw_config", {})
    payload = params.get("payload") or {}
    vectors_cold = dense["memory"] == "cold" if dense.get("memory") else dense.get("on_disk") is True
    payload_cold = payload["memory"] == "cold" if payload.get("memory") else params.get("on_disk_payload") is True
    graph_cached = hnsw["memory"] == "cached" if hnsw.get("memory") else hnsw.get("on_disk") is False
    return vectors_cold and payload_cold and graph_cached


class QdrantStore:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = settings.value("qdrant", "url", "http://127.0.0.1:6333").rstrip("/")
        self.collection_prefix = settings.value("qdrant", "collection", "pdf_chunks_e5small_v1")
        self._identity = None
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", self.collection_prefix):
            raise ApiError("invalid_profile", "Nom de collection invalide.")
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=settings.qdrant_headers, timeout=60, trust_env=False)

    @property
    def identity(self):
        if self._identity is None:
            self._identity = EmbeddingService(self.settings).identity()
        return dict(self._identity)

    @property
    def collection(self):
        return self.collection_prefix + "_" + self.identity["fingerprint"][:16]

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, **kwargs):
        try:
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status()
            result = response.json()
            if result.get("status") not in {"ok", None}:
                raise ApiError("qdrant_failure", "Qdrant n'a pas confirmé l'opération.", 503)
            return result.get("result", result)
        except (httpx.HTTPError, ValueError) as error:
            raise ApiError("qdrant_unavailable", "Serveur Qdrant local indisponible.", 503) from error

    async def ensure_collection(self):
        response = await self.client.get(f"/collections/{self.collection}")
        if response.status_code == 404:
            # Configuration runtime sous config/ (copie documentaire contrôlée par verify_pack) : aucun fichier du dossier de chantier.
            config = json.loads((self.settings.root / "config/qdrant.collection.json").read_text(encoding="utf-8"))
            await self.request("PUT", f"/collections/{self.collection}", json=config)
        actual = await self.request("GET", f"/collections/{self.collection}")
        effective = actual["config"]
        params = effective["params"]
        dense = params["vectors"].get("dense", {})
        if (dense.get("size") != 384 or dense.get("distance", "").lower() != "cosine" or not placement_matches(effective)
                or params.get("replication_factor") != 1
                or effective.get("optimizer_config", effective.get("optimizers_config", {})).get("max_optimization_threads") != 1):
            raise ApiError("incompatible_collection", "Paramètres effectifs Qdrant incompatibles avec le profil CPU et l'identité dense.", 503)
        for name, field_type in (("generation_id", "keyword"), ("version_id", "keyword"), ("document_id", "keyword"), ("page_indices", "integer"), ("block_ids", "keyword")):
            await self.request("PUT", f"/collections/{self.collection}/index", params={"wait": "true"}, json={"field_name": name, "field_schema": field_type})

    async def query(self, vector, snapshot, limit=24):
        if not snapshot.generations:
            return []
        body = {"query": vector, "using": "dense", "filter": snapshot.vector_filter(),
                "params": {"hnsw_ef": self.settings.value("retrieval", "hnsw_ef", 64)},
                "limit": limit, "with_payload": True, "with_vector": False}
        result = await self.request("POST", f"/collections/{self.collection}/points/query", json=body)
        points = result.get("points", []) if isinstance(result, dict) else result
        return [str(point["id"]) for point in points]

    async def upsert(self, points):
        await self.request("PUT", f"/collections/{self.collection}/points", params={"wait": "true"}, json={"points": points})

    async def verify(self, expected):
        if not expected:
            return
        points = await self.request("POST", f"/collections/{self.collection}/points", json={"ids": list(expected), "with_payload": True, "with_vector": False})
        actual = {str(point["id"]): point["payload"].get("text_hash") for point in points}
        if actual != expected:
            raise ApiError("vector_integrity_failure", "Les vecteurs attendus ne sont pas tous confirmés.", 503)

    async def project_collections(self):
        """Collections de ce projet : préfixe du profil suivi des 16 premiers caractères hexadécimaux d'une empreinte
        d'identité dense, courante ou précédente. Une liste illisible est refusée, sans rien supprimer."""
        listing = await self.request("GET", "/collections")
        names = listing.get("collections") if isinstance(listing, dict) else None
        if not isinstance(names, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in names):
            raise ApiError("qdrant_unavailable", "Liste des collections Qdrant invalide.", 503)
        pattern = re.compile(re.escape(self.collection_prefix) + r"_[0-9a-f]{16}")
        return sorted(item["name"] for item in names if pattern.fullmatch(item["name"]))

    async def delete_generation(self, generation_id):
        """Points d'une génération retirés de toutes les collections du projet (R26-IDX-02) : une génération remplacée a pu
        être indexée sous une identité dense précédente. Le filtre ne vise que cette génération. Renvoie les collections."""
        collections = await self.project_collections()
        for collection in collections:
            await self.request("POST", f"/collections/{collection}/points/delete", params={"wait": "true"},
                               json={"filter": {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}})
        return collections

    async def count_generation(self, generation_id):
        """Comptage exact des points d'une génération, pour le diagnostic de cohérence avec les fragments SQLite."""
        result = await self.request("POST", f"/collections/{self.collection}/points/count",
                                    json={"filter": {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}, "exact": True})
        return int(result["count"])


class SearchService:
    def __init__(self, db, resolver, embedding, vectors, settings, dense=None, projector=None):
        self.db, self.resolver, self.embedding, self.vectors, self.settings = db, resolver, embedding, vectors, settings
        self.dense = dense
        self.projector = projector

    def lexical(self, question, snapshot, references=None):
        references = references or resolve_references(question)
        if snapshot.scope["kind"] == "cell_range":
            from .office_search import lexical_projection, projection_fragments
            sources = projection_fragments(self.db, snapshot, self.embedding)
            ranked, exact = lexical_projection(question, sources, self.settings.value("retrieval", "lexical_top_k", 24), references)
            return [sources[i]["chunk_id"] for i in ranked], [sources[i]["chunk_id"] for i in exact]
        clause, parameters = snapshot.sql_filter()
        limit = self.settings.value("retrieval", "lexical_top_k", 24)
        exact = []
        codes = sorted(references.priority)
        expression = match_expression(question)
        if codes:
            # Un seul passage FTS5 : BM25 de la question pour classer les occurrences exactes (NULL en dernier),
            # puis revérification des frontières sur le texte (lignes d'identifiants d'un index antérieur).
            sql = (f"SELECT DISTINCT i.normalized code,c.chunk_uuid,c.text,f.score FROM identifiers i JOIN chunks c ON c.chunk_uuid=i.chunk_uuid "
                   f"LEFT JOIN (SELECT rowid id,bm25(chunks_fts,2.0,1.0) score FROM chunks_fts WHERE chunks_fts MATCH ?) f ON f.id=c.id "
                   f"WHERE {clause} AND i.normalized IN ({','.join('?' for _ in codes)}) ORDER BY f.score IS NULL,f.score ASC,c.chunk_uuid ASC")
            per_code: dict[str, list[Any]] = {code: [] for code in codes}
            for row in self.db.rows(sql, [expression] + parameters + codes):
                if len(per_code[row["code"]]) < limit and references.matches(row["text"], row["code"]):
                    per_code[row["code"]].append(row["chunk_uuid"])
            focused = {item.normalized for item in references.candidates if item.origin != "question"}
            if focused:
                # unicode61 n'est pas un préfiltre complet de NFKC (ﬁ/fi, Ａ/Ａ, ß/SS).
                # Parcours scoped paginé en mémoire, sans coupe avant preuve exacte autorisée.
                scan = (f"SELECT c.*,f.score FROM chunks c LEFT JOIN (SELECT rowid id,bm25(chunks_fts,2.0,1.0) score "
                        f"FROM chunks_fts WHERE chunks_fts MATCH ?) f ON f.id=c.id WHERE {clause} "
                        "ORDER BY f.score IS NULL,f.score ASC,c.chunk_uuid ASC")
                focused_matches: dict[str, list[str]] = {code: [] for code in focused}
                with self.db.connect() as connection:
                    cursor = connection.execute(scan, [expression] + parameters)
                    while rows := cursor.fetchmany(128):
                        for row in rows:
                            if all(len(items) >= limit for items in focused_matches.values()):
                                break
                            # Les sources sont des sous-chaînes des blocs de ce fragment (jointes par LF).
                            # Une occurrence attestée dans un bloc doit donc aussi être une sous-chaîne
                            # normalisée du fragment. Aucun test de frontières avant la projection.
                            raw = normalized_identifier(row["text"])
                            pending = [code for code in focused if len(focused_matches[code]) < limit and code in raw]
                            if not pending:
                                continue
                            source = self.resolver.source_for_chunk(dict(row), snapshot)
                            if source is None:
                                continue
                            for code in pending:
                                if references.source_matches(source, code):
                                    focused_matches[code].append(row["chunk_uuid"])
                        if all(len(items) >= limit for items in focused_matches.values()):
                            break
                for code in focused:
                    per_code[code] = focused_matches[code]
            exact = list(dict.fromkeys(chunk for position in range(limit) for matches in per_code.values() for chunk in matches[position:position + 1]))[:limit]
        ranked = []
        if expression:
            sql = f"SELECT c.chunk_uuid,bm25(chunks_fts,2.0,1.0) score FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid WHERE {clause} AND chunks_fts MATCH ? ORDER BY score ASC,c.chunk_uuid ASC LIMIT ?"
            ranked = [row["chunk_uuid"] for row in self.db.rows(sql, parameters + [expression, limit])]
        return list(dict.fromkeys(exact + ranked))[:limit], exact

    async def _candidates(self, question, snapshot, dense_available=True, references=None):
        if snapshot.scope["kind"] == "cell_range":
            return await self._projected_candidates(question, snapshot, references)
        lexical_task = asyncio.create_task(asyncio.to_thread(self.lexical, question, snapshot, references))
        try:
            dense = []
            if dense_available:
                vector = (await asyncio.to_thread(self.embedding.embed, [question], False))[0]
                dense = await self.vectors.query(vector, snapshot, self.settings.value("retrieval", "dense_top_k", 24))
            lexical, exact = await lexical_task
        except BaseException:
            lexical_task.cancel()
            await asyncio.gather(lexical_task, return_exceptions=True)
            raise
        scores = rrf(lexical, dense, self.settings.value("retrieval", "rrf_k", 60))
        # Exact identifiers are deliberately retained before the rank fusion pool.
        exact_set = set(exact)
        scores.sort(key=lambda pair: (pair[0] not in exact_set, -pair[1], pair[0]))
        return await asyncio.to_thread(self.source_candidates, scores, exact_set, snapshot)

    async def _projected_candidates(self, question, snapshot, references=None):
        from .office_search import lexical_projection, projection_fragments
        sources = await asyncio.to_thread(projection_fragments, self.db, snapshot, self.embedding)
        if not sources:
            return []
        lexical, exact = await asyncio.to_thread(lexical_projection, question, sources, self.settings.value("retrieval", "lexical_top_k", 24), references)
        query = (await asyncio.to_thread(self.embedding.embed, [question], False))[0]
        if self.projector is not None:
            vectors = await asyncio.to_thread(self.projector.cached_embeddings, sources)
        else:
            vectors = await asyncio.to_thread(self.embedding.embed, [source["text"] for source in sources])
        dense = sorted(range(len(sources)), key=lambda i: (-sum(a * b for a, b in zip(query, vectors[i], strict=True)), i))[:self.settings.value("retrieval", "dense_top_k", 24)]
        scores = rrf(lexical, dense, self.settings.value("retrieval", "rrf_k", 60))
        scores.sort(key=lambda pair: (pair[0] not in exact, -pair[1], pair[0]))
        return [{**sources[index], "score": score, "exact_identifier": index in exact} for index, score in scores]

    def source_candidates(self, scores, exact_set, snapshot):
        """Toutes les relectures de provenance d'un lot restent hors de la boucle de requêtes."""
        candidates = []
        for chunk_id, score in scores:
            chunk = self.db.one("SELECT * FROM chunks WHERE chunk_uuid=?", (chunk_id,))
            if not chunk:
                continue
            source = self.resolver.source_for_chunk(chunk, snapshot)
            if source:
                source.update({"score": score, "exact_identifier": chunk_id in exact_set})
                generation = self.db.one("SELECT state,coverage_json,warnings_json FROM index_generations WHERE id=?", (chunk["generation_id"],))
                source.update({"coverage": json.loads(generation["coverage_json"]), "extraction_state": generation["state"], "extraction_warnings": json.loads(generation["warnings_json"])})
                candidates.append(source)
        return candidates

    def decorate_sources(self, results):
        documents = {}
        for source in results:
            document_id = source["document_id"]
            if document_id not in documents:
                document = self.db.one("SELECT name,relative_path,deleted_at FROM documents WHERE id=?", (document_id,))
                if not document or document["deleted_at"]:
                    raise ApiError("source_removed", "Source absente ou supprimée.", 404)
                documents[document_id] = document
            document = documents[document_id]
            if not source["page_indices"]:
                source.update({"name": document["name"], "document_name": document["name"], "relative_path": document["relative_path"],
                               "page_index": None, "page_number": None, "label": None})
                continue
            page_index = source["page_indices"][0]
            page = next(block["page"] for block in source["blocks"] if block["page_index"] == page_index)
            source.update({"name": document["name"], "document_name": document["name"],
                           "relative_path": document["relative_path"], "page_index": page_index,
                           "page_number": page_index + 1, "label": page.get("label")})

    async def search(self, question, snapshot, mode="question", references=None):
        references = references or resolve_references(question)
        start = time.perf_counter()
        warnings = []
        dense_available = True
        if self.dense is not None and snapshot.scope["kind"] not in {"selection", "cell_range"} and snapshot.generations:
            # Avertissement de périmètre : documents servis par la seule branche lexicale (identité dense changée, R26-IDX-02).
            scoped = set(snapshot.generations)
            coverage = await self.dense.status()
            # Seule une absence confirmée autorise le repli : une panne Qdrant ne devient pas un succès lexical.
            dense_available = coverage["collection"] != "absent" or coverage["error_code"] is not None
            missing = [item for item in coverage["documents"] if item["generation_id"] in scoped]
            if missing:
                warnings.append(dense_identity_warning(missing))
        if snapshot.scope["kind"] == "selection":
            results = await asyncio.to_thread(self.resolver.selected_sources, snapshot)
        elif not snapshot.generations:
            results = []
        elif mode == "comparison":
            per_document = []
            for document_id in dict.fromkeys(snapshot.documents.values()):
                candidates = await self._candidates(question, snapshot.narrowed(document_id), dense_available, references)
                if not candidates:
                    warnings.append({"code": "comparison_gap", "document_id": document_id, "message": "Aucun passage retrouvé pour ce document."})
                per_document.append(candidates)
            results = []
            for position in range(24):
                for candidates in per_document:
                    if position < len(candidates):
                        results.append(candidates[position])
        else:
            results = await self._candidates(question, snapshot, dense_available, references)
        await asyncio.to_thread(self.decorate_sources, results)
        top10 = list(results[:10])
        priority = references.priority
        required = set(references.obligations)
        terms = answer_terms(references.original_question)
        mandatory = []
        covered: set[str] = set()
        mandatory_ids = set()
        # Preuve réservée par identifiant : d'abord un passage portant aussi un terme de la question, sinon toute occurrence.
        for answer_only in (True, False):
            for source in results:
                if id(source) in mandatory_ids or (answer_only and not has_answer_terms(source["text"], terms)):
                    continue
                newly_covered = {code for code in priority - covered if references.source_matches(source, code)}
                if newly_covered:
                    source["required_identifiers"] = sorted(newly_covered & required)
                    source["exact_identifiers"] = sorted(newly_covered)
                    mandatory.append(source)
                    mandatory_ids.add(id(source))
                    covered.update(newly_covered)
        for code in required - covered:
            warnings.append({"code": "identifier_not_found_in_scope", "identifier": code, "message": "Référence non retrouvée dans les passages de ce périmètre."})
        results = mandatory + [source for source in results if id(source) not in mandatory_ids]
        unique = []
        parents = set()
        texts = set()
        retained_identifiers: set[str] = set()
        maximum = self.settings.value("retrieval", "constrained_max_fragments", 8) if mode == "comparison" or len(priority) > 1 else self.settings.value("retrieval", "final_max_fragments", 6)
        for source in results:
            key = (source["version_id"], source.get("parent_id") or source.get("chunk_id"))
            # Texte identique (en-tête répété sur plusieurs pages) : un seul fragment, par document en comparaison.
            text_key = (source.get("document_id") if mode == "comparison" else None, hashlib.sha256(source["text"].encode("utf-8")).hexdigest())
            newly_covered = {code for code in priority - retained_identifiers if references.source_matches(source, code)}
            if (key in parents or text_key in texts) and not newly_covered:
                continue
            parents.add(key)
            texts.add(text_key)
            retained_identifiers.update(newly_covered)
            unique.append(source)
            if len(unique) >= maximum:
                break
        for document_id in {source["document_id"] for source in unique if source.get("extraction_state") == "ready_partial"}:
            warnings.append({"code": "partial_extraction", "document_id": document_id, "message": PARTIAL_EXTRACTION_MESSAGE})
        # Recherche seule (POST /search, évaluation) : passages finals ; une question le recalcule sur les sources retenues.
        warnings.extend(ocr_evidence_warnings(unique))
        references.attest(top10, "retrieval_top10")
        references.attest(unique, "retrieval_final")
        return {"results": unique, "top10": top10, "scope_snapshot": snapshot.as_dict(), "warnings": warnings,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2), "reference_resolution": references.as_dict()}
