import asyncio
import functools
import hashlib
import json
import re
import time
import unicodedata
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

    async def delete_generation(self, generation_id):
        await self.request("POST", f"/collections/{self.collection}/points/delete", params={"wait": "true"}, json={"filter": {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}})

    async def count_generation(self, generation_id):
        """Comptage exact des points d'une génération, pour le diagnostic de cohérence avec les fragments SQLite."""
        result = await self.request("POST", f"/collections/{self.collection}/points/count",
                                    json={"filter": {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}, "exact": True})
        return int(result["count"])


class SearchService:
    def __init__(self, db, resolver, embedding, vectors, settings):
        self.db, self.resolver, self.embedding, self.vectors, self.settings = db, resolver, embedding, vectors, settings

    def lexical(self, question, snapshot):
        clause, parameters = snapshot.sql_filter()
        limit = self.settings.value("retrieval", "lexical_top_k", 24)
        exact = []
        codes = sorted({normalized_identifier(value) for value in identifiers(question)})
        expression = match_expression(question)
        if codes:
            # Un seul passage FTS5 : BM25 de la question pour classer les occurrences exactes (NULL en dernier),
            # puis revérification des frontières sur le texte (lignes d'identifiants d'un index antérieur).
            sql = (f"SELECT DISTINCT i.normalized code,c.chunk_uuid,c.text,f.score FROM identifiers i JOIN chunks c ON c.chunk_uuid=i.chunk_uuid "
                   f"LEFT JOIN (SELECT rowid id,bm25(chunks_fts,2.0,1.0) score FROM chunks_fts WHERE chunks_fts MATCH ?) f ON f.id=c.id "
                   f"WHERE {clause} AND i.normalized IN ({','.join('?' for _ in codes)}) ORDER BY f.score IS NULL,f.score ASC,c.chunk_uuid ASC")
            per_code: dict[str, list[Any]] = {code: [] for code in codes}
            for row in self.db.rows(sql, [expression] + parameters + codes):
                if len(per_code[row["code"]]) < limit and contains_identifier(row["text"], row["code"]):
                    per_code[row["code"]].append(row["chunk_uuid"])
            exact = list(dict.fromkeys(chunk for position in range(limit) for matches in per_code.values() for chunk in matches[position:position + 1]))[:limit]
        ranked = []
        if expression:
            sql = f"SELECT c.chunk_uuid,bm25(chunks_fts,2.0,1.0) score FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid WHERE {clause} AND chunks_fts MATCH ? ORDER BY score ASC,c.chunk_uuid ASC LIMIT ?"
            ranked = [row["chunk_uuid"] for row in self.db.rows(sql, parameters + [expression, limit])]
        return list(dict.fromkeys(exact + ranked))[:limit], exact

    async def _candidates(self, question, snapshot):
        lexical_task = asyncio.create_task(asyncio.to_thread(self.lexical, question, snapshot))
        try:
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

    async def search(self, question, snapshot, mode="question"):
        start = time.perf_counter()
        warnings = []
        if snapshot.scope["kind"] == "selection":
            results = self.resolver.selected_sources(snapshot)
        elif not snapshot.generations:
            results = []
        elif mode == "comparison":
            per_document = []
            for document_id in dict.fromkeys(snapshot.documents.values()):
                candidates = await self._candidates(question, snapshot.narrowed(document_id))
                if not candidates:
                    warnings.append({"code": "comparison_gap", "document_id": document_id, "message": "Aucun passage retrouvé pour ce document."})
                per_document.append(candidates)
            results = []
            for position in range(24):
                for candidates in per_document:
                    if position < len(candidates):
                        results.append(candidates[position])
        else:
            results = await self._candidates(question, snapshot)
        documents = {}
        for source in results:
            document_id = source["document_id"]
            if document_id not in documents:
                document = self.db.one("SELECT name,relative_path,deleted_at FROM documents WHERE id=?", (document_id,))
                if not document or document["deleted_at"]:
                    raise ApiError("source_removed", "Source absente ou supprimée.", 404)
                documents[document_id] = document
            document = documents[document_id]
            page_index = source["page_indices"][0]
            page = next(block["page"] for block in source["blocks"] if block["page_index"] == page_index)
            source.update({"name": document["name"], "document_name": document["name"],
                           "relative_path": document["relative_path"], "page_index": page_index,
                           "page_number": page_index + 1, "label": page.get("label")})
        top10 = list(results[:10])
        required = {normalized_identifier(value) for value in identifiers(question)}
        terms = answer_terms(question)
        mandatory = []
        covered: set[str] = set()
        mandatory_ids = set()
        # Preuve réservée par identifiant : d'abord un passage portant aussi un terme de la question, sinon toute occurrence.
        for answer_only in (True, False):
            for source in results:
                if id(source) in mandatory_ids or (answer_only and not has_answer_terms(source["text"], terms)):
                    continue
                newly_covered = {code for code in required - covered if contains_identifier(source["text"], code)}
                if newly_covered:
                    source["required_identifiers"] = sorted(newly_covered)
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
        maximum = self.settings.value("retrieval", "constrained_max_fragments", 8) if mode == "comparison" or len(required) > 1 else self.settings.value("retrieval", "final_max_fragments", 6)
        for source in results:
            key = (source["version_id"], source.get("parent_id") or source.get("chunk_id"))
            # Texte identique (en-tête répété sur plusieurs pages) : un seul fragment, par document en comparaison.
            text_key = (source.get("document_id") if mode == "comparison" else None, hashlib.sha256(source["text"].encode("utf-8")).hexdigest())
            newly_covered = {code for code in required - retained_identifiers if contains_identifier(source["text"], code)}
            if (key in parents or text_key in texts) and not newly_covered:
                continue
            parents.add(key)
            texts.add(text_key)
            retained_identifiers.update(newly_covered)
            unique.append(source)
            if len(unique) >= maximum:
                break
        for document_id in {source["document_id"] for source in unique if source.get("extraction_state") == "ready_partial"}:
            warnings.append({"code": "partial_extraction", "document_id": document_id, "message": "Extraction partielle ; les régions ou pages non extraites ne constituent pas des preuves."})
        return {"results": unique, "top10": top10, "scope_snapshot": snapshot.as_dict(), "warnings": warnings,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2)}
