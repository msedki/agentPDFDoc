"""R26-IDX-02 : couverture dense de l'identité courante (mode dégradé signalé) et nettoyage dans toutes les collections.

SQLite/FTS5 réels. Doubles nommés : `CountingVectors` (comptes par génération enregistrés, échec injectable),
`RecordingQdrant` (serveur Qdrant réduit à la liste des collections et aux suppressions, journal des collections visées,
servi par httpx.MockTransport au vrai QdrantStore), FakeEmbedding et FakeVectors de test_api_storage.
"""
import asyncio
import json

import httpx
import pytest
from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage

from services.api.errors import ApiError
from services.api.reconcile import Reconciler
from services.api.retrieval import DenseCoverage, QdrantStore, SearchService, dense_identity_warning
from services.api.schemas import Scope
from services.api.scope import ScopeResolver


class CountingVectors:
    """Double nommé : points par génération dans la collection courante ; chaque compte est enregistré."""

    def __init__(self, points=None, failing=()):
        self.points, self.failing, self.calls = dict(points or {}), set(failing), []

    async def count_generation(self, generation_id):
        self.calls.append(generation_id)
        if generation_id in self.failing:
            raise ApiError("qdrant_unavailable", "Qdrant muet (double).", 503)
        return self.points.get(generation_id, 0)


def library(storage, texts):
    imported = [import_fixture(storage, path=f"folder/{name}.pdf", text=text)[0] for name, text in texts.items()]
    db = storage[1]
    generations = {item["document_id"]: db.one("SELECT active_generation_id FROM documents WHERE id=?", (item["document_id"],))["active_generation_id"]
                   for item in imported}
    return imported, generations


def test_coverage_counts_each_active_generation_once_and_names_the_documents_without_points(storage):
    imported, generations = library(storage, {"pompe": "Pompe PX-10 24 V", "vanne": "Vanne VX-20 48 V"})
    pump, valve = (item["document_id"] for item in imported)
    vectors = CountingVectors({generations[pump]: 1})
    coverage = DenseCoverage(storage[1], vectors)
    status = asyncio.run(coverage.status())
    assert status["state"] == "dense_migration_incomplete" and status["active_generations"] == 2
    assert status["documents"] == [{"document_id": valve, "document_name": "vanne.pdf", "generation_id": generations[valve]}]
    assert sorted(vectors.calls) == sorted(generations.values())
    # Comptes conservés : une consultation suivante ne recompte rien tant que l'ensemble actif ne change pas.
    asyncio.run(coverage.status())
    assert len(vectors.calls) == 2


def test_coverage_follows_publications_and_forgets_replaced_generations(storage):
    imported, generations = library(storage, {"pompe": "Pompe PX-10 24 V"})
    vectors = CountingVectors()
    coverage = DenseCoverage(storage[1], vectors)
    assert asyncio.run(coverage.status())["state"] == "dense_migration_incomplete"
    # Réimport du même chemin avec un autre contenu : nouvelle génération active, l'ancienne quitte l'ensemble suivi.
    import_fixture(storage, path="folder/pompe.pdf", text="Pompe PX-10 24 V, révision 2")
    current = storage[1].one("SELECT active_generation_id FROM documents WHERE id=?", (imported[0]["document_id"],))["active_generation_id"]
    vectors.points[current] = 1
    status = asyncio.run(coverage.status())
    assert status["state"] == "complete" and status["documents"] == [] and vectors.calls == [generations[imported[0]["document_id"]], current]
    assert set(coverage.points) == {current}


def test_coverage_never_flags_an_active_generation_without_fragments_and_reports_qdrant_failures(storage):
    imported, generations = library(storage, {"pompe": "Pompe PX-10 24 V", "vanne": "Vanne VX-20 48 V"})
    pump, valve = (item["document_id"] for item in imported)
    storage[1].execute("UPDATE index_generations SET actual_chunks=0,expected_chunks=0 WHERE id=?", (generations[pump],))
    vectors = CountingVectors(failing={generations[valve]})
    status = asyncio.run(DenseCoverage(storage[1], vectors).status())
    assert vectors.calls == [generations[valve]]
    assert status["state"] == "unverifiable" and status["documents"] == [] and status["error_code"] == "qdrant_unavailable"
    # Collection courante absente : toute génération active portant des fragments est à réindexer, sans aucun compte.
    vectors = CountingVectors()
    status = asyncio.run(DenseCoverage(storage[1], vectors).status(collection_absent=True))
    assert status["state"] == "dense_migration_incomplete" and [item["document_id"] for item in status["documents"]] == [valve]
    assert vectors.calls == []


def test_a_test_double_without_counts_leaves_the_coverage_not_applicable(storage):
    library(storage, {"pompe": "Pompe PX-10 24 V"})
    assert asyncio.run(DenseCoverage(storage[1], object()).status())["state"] == "not_applicable"


def test_search_warns_only_for_missing_documents_of_the_scope_and_never_for_a_selection(storage):
    imported, generations = library(storage, {"pompe": "Pompe PX-10 tension 24 V", "vanne": "Vanne VX-20 tension 48 V"})
    pump, valve = (item["document_id"] for item in imported)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    vectors.count_generation = CountingVectors({generations[pump]: 1}).count_generation
    search = SearchService(db, resolver, FakeEmbedding(), vectors, settings, dense=DenseCoverage(db, vectors))

    def warnings(scope):
        return [warning for warning in asyncio.run(search.search("tension", resolver.resolve(scope)))["warnings"]
                if warning["code"] == "dense_identity_mismatch"]
    assert warnings(Scope(kind="library")) == [dense_identity_warning([{"document_id": valve, "document_name": "vanne.pdf"}])]
    assert warnings(Scope(kind="documents", documentIds=[pump])) == []
    block = db.one("SELECT id,extraction_revision_id,source_text_hash FROM blocks WHERE generation_id=?", (generations[valve],))
    selection = Scope(kind="selection", versionId=imported[1]["version_id"], spans=[{
        "extractionRevisionId": block["extraction_revision_id"], "blockId": block["id"], "blockTextSha256": block["source_text_hash"],
        "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": 5}])
    assert warnings(selection) == []


def test_dense_warning_text_names_the_documents_and_the_action():
    one = dense_identity_warning([{"document_id": "d1", "document_name": "vanne.pdf"}])
    assert one == {"code": "dense_identity_mismatch", "document_ids": ["d1"], "document_names": ["vanne.pdf"], "message":
                   "Recherche sémantique incomplète : « vanne.pdf » n'a pas d'index sémantique pour le modèle d'embedding actuel. "
                   "La recherche par mots peut encore le retrouver ; réindexez-le pour rétablir la recherche sémantique."}
    many = dense_identity_warning([{"document_id": f"d{index}", "document_name": f"n{index}.pdf"} for index in range(7)])
    assert many["message"] == ("Recherche sémantique incomplète : 7 documents n'ont pas d'index sémantique pour le modèle d'embedding "
                               "actuel (« n0.pdf », « n1.pdf », « n2.pdf », « n3.pdf », « n4.pdf » et 2 autres). La recherche par "
                               "mots peut encore les retrouver ; réindexez-les pour rétablir la recherche sémantique.")


class RecordingQdrant:
    """Double nommé du serveur Qdrant : liste de collections fixée, suppressions enregistrées (collection, filtre)."""

    def __init__(self, names):
        self.names, self.deletes, self.requests = names, [], []

    def __call__(self, request):
        self.requests.append((request.method, request.url.path))
        if request.url.path == "/collections":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": [{"name": name} for name in self.names]}})
        if request.url.path.endswith("/points/delete"):
            self.deletes.append((request.url.path.split("/")[2], json.loads(request.content)["filter"]))
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})
        raise AssertionError(f"Requête inattendue : {request.method} {request.url.path}")


def recording_store(settings, server):
    store = QdrantStore(settings)
    store._identity = {"fingerprint": "b" * 64}
    store.client = httpx.AsyncClient(base_url="http://qdrant.test", transport=httpx.MockTransport(server), timeout=5)
    return store


PROJECT = ["pdf_chunks_e5small_v1_" + "a" * 16, "pdf_chunks_e5small_v1_" + "b" * 16]
FOREIGN = ["autre_projet_" + "a" * 16, "pdf_chunks_e5small_v1_" + "A" * 16, "pdf_chunks_e5small_v1_court", "pdf_chunks_e5small_v1_" + "c" * 17]


def test_cleanup_deletes_one_generation_in_every_project_collection_and_nowhere_else(storage):
    server = RecordingQdrant(FOREIGN[:2] + PROJECT + FOREIGN[2:])
    store = recording_store(storage[0], server)
    assert asyncio.run(store.delete_generation("g-remplacée")) == PROJECT
    expected = {"must": [{"key": "generation_id", "match": {"value": "g-remplacée"}}]}
    assert server.deletes == [(PROJECT[0], expected), (PROJECT[1], expected)]


@pytest.mark.parametrize("listing", [{}, {"collections": None}, {"collections": [{"name": 3}]}, {"collections": [None]}])
def test_cleanup_refuses_an_invalid_collection_listing_without_deleting(storage, listing):
    def handler(request):
        return httpx.Response(200, json={"status": "ok", "result": listing})
    store = QdrantStore(storage[0])
    store._identity = {"fingerprint": "b" * 64}
    store.client = httpx.AsyncClient(base_url="http://qdrant.test", transport=httpx.MockTransport(handler), timeout=5)
    with pytest.raises(ApiError) as refused:
        asyncio.run(store.delete_generation("g"))
    assert refused.value.code == "qdrant_unavailable"


def test_reconciler_reports_the_collections_cleaned_for_each_replaced_generation(storage):
    imported, generations = library(storage, {"pompe": "Pompe PX-10 24 V"})
    db = storage[1]
    import_fixture(storage, path="folder/pompe.pdf", text="Pompe PX-10 24 V, révision 2")
    replaced = generations[imported[0]["document_id"]]
    assert db.one("SELECT state,reason FROM vector_cleanup WHERE generation_id=?", (replaced,)) == {"state": "pending", "reason": "superseded"}
    server = RecordingQdrant(PROJECT)
    result = asyncio.run(Reconciler(db, recording_store(storage[0], server)).run_once())
    assert result["completed"] == [replaced] and result["collections"] == {replaced: PROJECT}
    assert [collection for collection, _ in server.deletes] == PROJECT
    assert db.one("SELECT state FROM vector_cleanup WHERE generation_id=?", (replaced,))["state"] == "complete"
    # Échec d'une suppression : la génération remplacée reste en attente, avec son code, pour une reprise idempotente.
    second = db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported[0]["document_id"],))["active_generation_id"]
    import_fixture(storage, path="folder/pompe.pdf", text="Pompe PX-10 24 V, révision 3")

    def failing(request):
        if request.url.path == "/collections":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": [{"name": name} for name in PROJECT]}})
        return httpx.Response(500, json={"status": {"error": "panne"}})
    store = QdrantStore(storage[0])
    store._identity = {"fingerprint": "b" * 64}
    store.client = httpx.AsyncClient(base_url="http://qdrant.test", transport=httpx.MockTransport(failing), timeout=5)
    result = asyncio.run(Reconciler(db, store).run_once())
    assert result["completed"] == [] and db.one("SELECT state,error_code FROM vector_cleanup WHERE generation_id=?", (second,)) == {
        "state": "pending", "error_code": "qdrant_unavailable"}


def absent_collection_store(settings, requests):
    """Vrai QdrantStore dont l'identité courante (empreinte « b… ») n'a pas de collection : seule une autre y figure."""
    def handler(request):
        requests.append((request.method, request.url.path))
        if request.url.path == "/collections":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": [{"name": PROJECT[0]}]}})
        return httpx.Response(404, json={"status": {"error": "Not found"}})
    store = QdrantStore(settings)
    store._identity = {"fingerprint": "b" * 64}
    store.client = httpx.AsyncClient(base_url="http://qdrant.test", transport=httpx.MockTransport(handler), timeout=5)
    return store


def test_an_absent_current_collection_is_named_like_readiness_not_as_an_unreachable_qdrant(storage):
    # Revue m3 : au démarrage d'une nouvelle identité, la collection courante n'existe pas encore.
    imported, _ = library(storage, {"pompe": "Pompe PX-10 24 V", "vanne": "Vanne VX-20 48 V"})
    requests = []
    status = asyncio.run(DenseCoverage(storage[1], absent_collection_store(storage[0], requests)).status())
    assert status["state"] == "dense_migration_incomplete" and status["collection"] == "absent" and status["error_code"] is None
    assert [item["document_id"] for item in status["documents"]] == [item["document_id"] for item in imported]
    assert requests == [("GET", "/collections")]
    present = asyncio.run(DenseCoverage(storage[1], CountingVectors({})).status())
    assert present["collection"] == "unverified" and present["state"] == "dense_migration_incomplete"


def test_the_startup_coverage_task_logs_its_outcome_and_any_exception(caplog):
    from services.api.main import log_dense_coverage

    async def finished(result=None, error=None):
        task = asyncio.get_running_loop().create_future()
        task.set_exception(error) if error else task.set_result(result)
        log_dense_coverage(task)
    with caplog.at_level("WARNING", logger="rag.api"):
        asyncio.run(finished(error=RuntimeError("base verrouillée")))
        asyncio.run(finished({"state": "dense_migration_incomplete", "collection": "absent", "documents": [{}, {}], "error_code": None}))
        asyncio.run(finished({"state": "unverifiable", "collection": "unverified", "documents": [], "error_code": "qdrant_unavailable"}))
    messages = [record.getMessage() for record in caplog.records]
    assert any("Couverture dense non établie au démarrage" in message and "RuntimeError" in message for message in messages)
    assert any("collection de l'identité dense courante absente" in message and "2 document(s)" in message for message in messages)
    assert any("non vérifiée au démarrage (qdrant_unavailable)" in message for message in messages)
