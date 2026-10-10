"""R26-ANS-01 et R26-ANS-02 : signaux déterministes sur la réponse générée, jamais de réécriture (W037).

Les textes de réponse sont des sorties réelles enregistrées (2B : R25 et R23 ; 4B : DEV-017 du lot L8), recopiées mot pour
mot ; les sources sont leurs textes transmis au modèle. Les tests de QueryService utilisent SQLite réel et des doubles
nommés : génération (ScriptedOllama), tokenizer (CharTokenizer), embeddings (FakeEmbedding) et vecteurs (FakeVectors).
"""
import asyncio
import hashlib
import json

import pytest
from test_api_context import fixture_pages
from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage
from test_retrieval import CharTokenizer

from services.api.claims import answer_warnings, citation_format_warnings, value_warnings
from services.api.context import HISTORY_PREFIX, SYSTEM_INSTRUCTION, ContextBuilder
from services.api.query import QueryService
from services.api.retrieval import SearchService
from services.api.schemas import QueryRequest, Scope
from services.api.scope import ScopeResolver
from services.api.settings import Settings

# R25-LEN-01, question factuelle 2B (native-factuelle-events.json) : « S001 » sans crochets, citations=[].
R25_FACTUAL = ("Selon les preuves fournies, la pression nominale du banc AUTOTEST-R25 est de 3,1 bar. Cette information est extraite "
               "directement de la preuve S001 qui indique : « La pression nominale du banc AUTOTEST-R25 est de 3,1 bar. »\n\nLes autres "
               "preuves disponibles concernent d'autres caractéristiques du banc (le couple de serrage) ou sont des consignes pour un "
               "contrôle documentaire, et ne contiennent pas d'information sur la pression nominale.")
R25_SOURCES = [{"source_id": "S001", "text": "La pression nominale du banc AUTOTEST-R25 est de 3,1 bar."},
               {"source_id": "S002", "text": "Le couple de serrage du banc AUTOTEST-R25 est de 12 N.m."},
               {"source_id": "S003", "text": "Contrôle de l'atelier documentaire."}]
# R23, 2B sur l'index existant (run-r23-2b-existing-index) : « (Source ID: S001) », puis S002 à S004 entre parenthèses.
R23_EXISTING = ("Selon les preuves fournies, la pression de réglage de QV-01 est de **2.7 bar**.\n\nCette assertion est issue du passage "
                "suivant :\n> \"La pression de réglage de QV-01 est de 2.7 bar.\" (Source ID: S001)\n\nLes autres preuves citées (S002, "
                "S003, S004) ne contiennent pas d'information sur la valeur numérique de cette pression ; elles servent uniquement à "
                "identifier le document, sa version ou son contexte technique.")
QV_SOURCES = [{"source_id": "S001", "text": "La pression de réglage de QV-01 est de 2.7 bar."}, {"source_id": "S002", "text": "QV-01 — révision 1"},
              {"source_id": "S003", "text": "DOCUMENT SYNTHÉTIQUE — qualification technique, CC0"}, {"source_id": "S004", "text": "Page 1 / 1"}]
# R23, 2B corrigé (run-r23-2b-corrected) : citation après le guillemet fermant.
R23_CORRECTED = ("La pression de réglage de QV-01 est de 2.7 bar, comme indiqué dans le passage suivant : « La pression de réglage de "
                 "QV-01 est de 2.7 bar. » [S001]")
# R23, témoin 2B d'abstention (native-01.json, « D2 ») : 2.7 bar citée S001 alors qu'elle n'est que dans S002.
D2_TEXT = ("Selon les preuves fournies, il n'est pas possible d'identifier un fabricant pour le modèle QV-01. La seule information "
           "disponible dans les extraits mentionne uniquement la révision (révision 1) et la pression de réglage (2.7 bar), sans nommer "
           "une marque ou une entreprise [S001].\n\nIl n'existe aucune preuve documentant un fabricant pour ce modèle.")
D2_SOURCES = [{"source_id": "S001", "text": "QV-01 — révision 1"}, {"source_id": "S002", "text": "La pression de réglage de QV-01 est de 2.7 bar."},
              {"source_id": "S003", "text": "DOCUMENT SYNTHÉTIQUE — qualification technique, CC0"}, {"source_id": "S004", "text": "Page 1 / 1"}]
# DEV-017 (4B, L8) : bornes calculées 2.98 et 3.82 bar, jugées non soutenues par la grille manuelle.
DEV_017 = ("La tolérance de pression indiquée pour l'équipement DA-P04 est de **± 5.0 %**.\n\nCette information est extraite directement "
           "du document S001, page 0, qui spécifie explicitement : « La tolérance de pression de DA-P04 est de ± 5.0 % » [S001].\n\nLe "
           "document S001 précise également que la pression nominale correspondante est de 3.4 bar, ce qui permet de calculer les limites "
           "absolues (2.98 bar à 3.82 bar), bien que seules les valeurs relatives soient explicitement mentionnées comme tolérance "
           "[S001].\n\nAucune contradiction ou insuffisance de preuve n'est relevée concernant cette donnée spécifique dans les documents "
           "fournis.")


def codes(warnings):
    return [warning["code"] for warning in warnings]


def test_answer_without_bracketed_citation_is_signalled_with_the_mentioned_ids():
    warnings = citation_format_warnings(R25_FACTUAL, ["S001", "S002", "S003"])
    assert codes(warnings) == ["answer_without_valid_citation", "source_id_mentioned_without_citation"]
    assert warnings[0] == {"code": "answer_without_valid_citation", "message":
                           "La réponse ne contient aucune citation valide entre crochets : ses affirmations ne sont reliées à aucune "
                           "source vérifiable. Contrôlez-les dans les sources listées avant de les utiliser."}
    assert warnings[1] == {"code": "source_id_mentioned_without_citation", "source_ids": ["S001"], "message":
                           "La réponse nomme S001 sans crochets : cette mention n'est pas une citation et n'ouvre pas la source. "
                           "Retrouvez cette source dans la liste pour vérifier la réponse."}
    existing = citation_format_warnings(R23_EXISTING, ["S001", "S002", "S003", "S004"])
    assert codes(existing) == ["answer_without_valid_citation", "source_id_mentioned_without_citation"]
    assert existing[1]["source_ids"] == ["S001", "S002", "S003", "S004"]
    assert existing[1]["message"] == ("La réponse nomme S001, S002, S003 et S004 sans crochets : ces mentions ne sont pas des citations "
                                      "et n'ouvrent pas les sources. Retrouvez ces sources dans la liste pour vérifier la réponse.")


@pytest.mark.parametrize("text", [R23_CORRECTED, "Pression 2.7 bar [S001] ; S002 donne la révision.", "Voir [S002]."])
def test_answer_with_one_valid_citation_gets_no_citation_signal(text):
    # Une mention nue à côté d'une citation valide n'est pas signalée : la réponse reste vérifiable par sa citation.
    assert citation_format_warnings(text, ["S001", "S002"]) == []


def test_unknown_or_foreign_ids_are_not_valid_citations_nor_listed_mentions():
    assert codes(citation_format_warnings("Tension 72 V [citation inconnue].", ["S001"])) == ["answer_without_valid_citation"]
    assert codes(citation_format_warnings("Voir S009 et TS001.", ["S001", "S002"])) == ["answer_without_valid_citation"]
    assert codes(citation_format_warnings("", ["S001"])) == ["answer_without_valid_citation"]
    assert citation_format_warnings("Voir (S002) et S001.", ["S001", "S002"])[1]["source_ids"] == ["S001", "S002"]


def test_value_cited_from_the_wrong_source_is_signalled_with_its_holder():
    warnings = value_warnings(D2_TEXT, D2_SOURCES)
    assert warnings == [{"code": "cited_value_not_in_cited_sources", "values": [
        {"value": "2.7 bar", "number": "2.7", "unit": "bar", "cited_source_ids": ["S001"], "holder_source_ids": ["S002"]}],
        "message": "Valeur absente des sources citées dans sa phrase mais présente dans d'autres sources retenues : 2.7 bar "
                   "(citée S001, présente dans S002). Vérifiez sa source avant de l'utiliser."}]


def test_computed_values_absent_from_every_source_are_signalled():
    sources = [{"source_id": "S001", "text": fixture_pages(4)[0]}, {"source_id": "S002", "text": fixture_pages(4)[1]}]
    warnings = value_warnings(DEV_017, sources)
    assert warnings == [{"code": "value_not_in_context", "values": [
        {"value": "2.98 bar", "number": "2.98", "unit": "bar", "cited_source_ids": ["S001"]},
        {"value": "3.82 bar", "number": "3.82", "unit": "bar", "cited_source_ids": ["S001"]}],
        "message": "Valeurs absentes de toutes les sources transmises au modèle : 2.98 bar et 3.82 bar. Elles peuvent avoir été "
                   "calculées, déduites ou mal reprises ; vérifiez-les avant de les utiliser."}]


@pytest.mark.parametrize("text,sources", [
    (R23_CORRECTED, QV_SOURCES),
    (R23_EXISTING, QV_SOURCES),
    (R25_FACTUAL, R25_SOURCES),
    # Identifiants, mentions de page, numéros de liste et balises masqués ; séparateurs décimaux et de milliers.
    ("1. DA-P02-IN : 14 mm [S001].\n2. Voir la page 2 et les pages 4 et 5 du document S002.", [{"source_id": "S001", "text": "DA-P02-IN | 14 | mm"}, {"source_id": "S002", "text": "x"}]),
    ("Le contrôle intervient toutes les 1 020 h [S001]. La pression est de 3,1 bar [S001].", [{"source_id": "S001", "text": "1020 h ; 3.1 bar"}]),
    ("The check is due every 1,020 hours [S001].", [{"source_id": "S001", "text": "toutes les 1020 h"}]),
    ("Contrôle toutes les 1\u202f020 h et 2\u00a0500 cycles [S001].", [{"source_id": "S001", "text": "1020 h ; 2500 cycles"}]),
    ("La tolérance est de ± 5 % [S001].", [{"source_id": "S001", "text": "± 5.0 %"}]),
])
def test_values_found_in_their_cited_or_retained_sources_raise_nothing(text, sources):
    assert value_warnings(text, sources) == []


def test_a_source_listing_numbers_separated_by_spaces_offers_each_of_them():
    # Revue m1 : « 120 150 180 » se lit aussi comme trois valeurs côté sources (lecture permissive).
    assert value_warnings("Le couple prescrit est de 150 N·m [S001].", [{"source_id": "S001", "text": "Couples : 120 150 180 N·m"}]) == []
    assert value_warnings("Couples 120 150 180 N·m [S001].", [{"source_id": "S001", "text": "Couples : 120 150 180 N·m"}]) == []


@pytest.mark.parametrize("text", [
    "Voir pp. 3-4 du manuel [S001].", "Selon le § 4.3 et le §12 [S001].", "C'est le 2e contrôle, la 3ème étape, le 1er essai et la 2nde série [S001].",
    "Contrôles du 12/03/2024, du 2024-03-12 et du 12.03.2024 [S001].",
])
def test_page_ranges_sections_ordinals_and_dates_are_not_values(text):
    # Revue m2 : références de lecture, rangs et dates ne sont pas des valeurs documentaires.
    assert value_warnings(text, [{"source_id": "S001", "text": "Contrôle du banc."}]) == []


@pytest.mark.parametrize("text,numbers", [("La plage est de 12.5-13.5 bar [S001].", ["12.5", "13.5"]),
                                          ("Jeu de 10.25-10.50 mm [S001].", ["10.25", "10.50"]),
                                          ("Plage 2.5-3.5 bar [S001].", ["2.5", "3.5"])])
def test_a_range_of_decimals_is_not_a_date(text, numbers):
    # Revue N1 : une date garde le même séparateur ; « 12.5-13.5 » est une plage de valeurs, contrôlée comme « 2.5-3.5 ».
    warnings = value_warnings(text, [{"source_id": "S001", "text": "Plage nominale 12 bar."}])
    assert [item["number"] for item in warnings[0]["values"]] == numbers


@pytest.mark.parametrize("text", ["Contrôle du 12-03-2024 [S001].", "Contrôle du 12/03/24 [S001].", "Contrôle du 2024-03-12 [S001]."])
def test_dates_with_one_repeated_separator_stay_masked(text):
    assert value_warnings(text, [{"source_id": "S001", "text": "Contrôle du banc."}]) == []


# Campagne 2B DEV (r26-2b-dev-20261006T204546Z), DEV-038 : la citation qui ouvre une puce appartient à cette puce.
DEV_038 = ('Selon les preuves fournies, la pression nominale de la référence DA-P03 est de **3.3 bar**.\n\nCette information est '
           'extraite directement du texte des preuves documentaires :\n*   [S001] indique explicitement : "La pression nominale de '
           'DA-P03 est de 3.3 bar."\n*   [S002] confirme que les valeurs concernent uniquement DA-P03, bien qu\'il ne donne pas la '
           'valeur numérique dans le texte fourni.\n\nLes autres preuves ([S003], [S004], [S005]) fournissent des données relatives '
           'à d\'autres références (DA-P03-IN, DA-P03-OUT, DA-P03-LEAK) ou sont des tableaux non spécifiés, et ne contiennent pas de '
           'valeur pour la pression nominale.')
DEV_038_SOURCES = [{"source_id": "S001", "text": "DA-P03 — banc pneumatique synthétique Atelier 3.\nLa pression nominale de DA-P03 est de 3.3 bar."},
                   {"source_id": "S002", "text": "Mesures de contrôle — DA-P03\nLes valeurs de ce tableau concernent uniquement DA-P03."},
                   {"source_id": "S003", "text": "Référence | Valeur | Unité\nDA-P03-IN | 15 | mm\nDA-P03-OUT | 11 | mm\nDA-P03-LEAK | 0.3 | L/min"},
                   {"source_id": "S004", "text": "Tableau de contrôle"}, {"source_id": "S005", "text": "Page 2 / 2"}]


def test_a_citation_opening_a_bullet_belongs_to_that_bullet():
    assert value_warnings(DEV_038, DEV_038_SOURCES) == []
    # Contre-épreuve : la valeur attribuée à la mauvaise source dans sa propre puce reste signalée.
    swapped = DEV_038.replace("*   [S001] indique", "*   [S002] indique")
    assert codes(value_warnings(swapped, DEV_038_SOURCES)) == ["cited_value_not_in_cited_sources"]
    # Une citation seule sur sa ligne, ou placée après une fin de phrase sur la même ligne, conclut toujours la phrase précédente.
    sources = [{"source_id": "S001", "text": "Pression 3,1 bar"}, {"source_id": "S002", "text": "Couple 12 N·m"}]
    assert value_warnings("La pression est de 3,1 bar.\n[S001]", sources) == []
    assert value_warnings("La pression est de 3,1 bar. [S001] Le couple est de 12 N·m [S002].", sources) == []


def test_an_isolated_letter_is_not_shown_as_a_unit_unless_it_is_a_unit_symbol():
    shown = value_warnings("Point 7 b et tension 9 V [S001].", [{"source_id": "S001", "text": "Contrôle du banc."}])[0]["values"]
    assert [(item["value"], item["unit"]) for item in shown] == [("7", None), ("9 V", "V")]


def test_an_uncited_sentence_may_repeat_a_number_of_the_question():
    # Revue m2 : abstention sans citation qui reprend la condition de la question ; une phrase citée reste contrôlée.
    question = "Quelle est la pression du banc à 20 °C ?"
    abstention = "Les sources ne donnent pas la pression du banc à 20 °C."
    sources = [{"source_id": "S001", "text": "Pression nominale 3 bar."}]
    assert value_warnings(abstention, sources, question) == []
    assert codes(value_warnings(abstention, sources)) == ["value_not_in_context"]
    cited = value_warnings("La pression à 20 °C est de 3 bar [S001].", sources, question)
    assert [item["value"] for item in cited[0]["values"]] == ["20 °C"]
    assert codes(answer_warnings(abstention, sources, question)) == ["answer_without_valid_citation"]


def test_numbers_inside_identifiers_are_not_values():
    # « QV-01 » de la réponse n'est pas lu comme la valeur 1 (identifiant masqué) ; côté sources, tous les nombres comptent.
    warnings = value_warnings("QV-01 fonctionne à 1 bar [S001].", [{"source_id": "S001", "text": "Révision de QV-02 : 3 bar"}])
    assert codes(warnings) == ["value_not_in_context"] and [item["value"] for item in warnings[0]["values"]] == ["1 bar"]


def test_answer_checks_combine_both_families_without_touching_the_text():
    text = "Selon S002, la pression est de 2.7 bar."
    warnings = answer_warnings(text, D2_SOURCES)
    assert codes(warnings) == ["answer_without_valid_citation", "source_id_mentioned_without_citation"]
    assert answer_warnings(D2_TEXT, D2_SOURCES)[0]["code"] == "cited_value_not_in_cited_sources"


# Empreintes calculées sur le code HEAD 011a817 avant R26 (context.py SHA 24db2d77…), consignées dans la racine QA r26-backend.
SYSTEM_INSTRUCTION_SHA256 = "ae9651574f646572dacdfccc57d68f5c7be11a25fe982204405dc8b1e29f36e8"
HISTORY_PREFIX_SHA256 = "a4822c788b3204b9e36189310282e45562a6e919e97ec35072d661cadae23f9c"
MESSAGES_SHA256 = "2d2d0a20f4ce2b17ffadbd35ed8a31502ff785b4d0a55db7e51ef0103657fd20"


def test_prompt_sent_to_the_model_is_byte_identical_to_the_pre_r26_prompt(tmp_path):
    assert hashlib.sha256(SYSTEM_INSTRUCTION.encode()).hexdigest() == SYSTEM_INSTRUCTION_SHA256
    assert hashlib.sha256(HISTORY_PREFIX.encode()).hexdigest() == HISTORY_PREFIX_SHA256
    # Sources synthétiques : mêmes textes que la référence, provenance complète du contrat ScopeResolver.
    # Génération, révision, hash et offsets servent à l'attestation ; le prompt historique n'en porte rien.
    texts = ["La tolérance de pression de DA-P02 est de + 3.0 %.",
             "Le couple de serrage prescrit pour DA-P02 est de 14 N-m."]
    methods = ["ocr", "unknown"]
    sources = []
    for index, text in enumerate(texts):
        block = {"id": f"b{index}", "block_id": f"b{index}", "page_index": index, "text": text,
                 "start_offset": 0, "end_offset": len(text), "bbox": None, "precision": "block", "type": "paragraph", "page": {},
                 "extraction_revision_id": "synthetic-revision-A", "source_text_hash": hashlib.sha256(text.encode()).hexdigest(),
                 "extraction_method": methods[index]}
        sources.append({"version_id": "v-A", "document_id": "A", "chunk_id": f"A-{index}", "page_indices": [index],
                        "generation_id": "synthetic-generation-A", "extraction_revision_id": "synthetic-revision-A",
                        "text": text, "extraction_methods": [methods[index]], "blocks": [block], "parent_id": None,
                        **({"exact_identifier": True} if index == 0 else {})})
    history = [{"role": "user", "content": "Quelle pression DA-P02 ?"}, {"role": "assistant", "content": "3.2 bar [S001]"}]
    messages, _, _, _ = ContextBuilder(Settings(tmp_path), CharTokenizer()).build("Quelle est la tolérance de pression de DA-P02 ?", sources, history=history)
    assert hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == MESSAGES_SHA256


class ScriptedOllama:
    """Double de génération : rejoue un texte fixé, sans modèle ni réseau."""
    def __init__(self, text):
        self.text, self.calls = text, 0

    async def stream(self, messages, cancelled, output_tokens):
        self.calls += 1
        yield {"type": "delta", "text": self.text}
        yield {"type": "done", "finish_reason": "stop", "metrics": {}}


def run_query(storage, answer, text="CCU-21 tension nominale 72 V."):
    import_fixture(storage, text=text)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    gateway = ScriptedOllama(answer)
    service = QueryService(db, resolver, SearchService(db, resolver, FakeEmbedding(), vectors, settings),
                           ContextBuilder(settings, CharTokenizer()), gateway, settings)

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library")))["query_id"]
        await service.tasks[query_id]
        return query_id
    query_id = asyncio.run(scenario())
    events = [(row["type"], json.loads(row["data_json"])) for row in db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))]
    stored = db.one("SELECT answer,warnings_json FROM query_runs WHERE id=?", (query_id,))
    return gateway, events, stored


def test_query_adds_citation_signals_to_done_only_with_text_citations_and_sse_order_unchanged(storage):
    gateway, events, stored = run_query(storage, "Selon S001, la tension nominale est de 72 V.")
    kinds = [kind for kind, _ in events]
    assert gateway.calls == 1
    assert kinds == ["status", "status", "sources", "status", "delta", "done"]
    done = events[-1][1]
    assert done["text"] == done["message"] == stored["answer"] == "Selon S001, la tension nominale est de 72 V."
    assert done["citations"] == [] and done["status"] == "done"
    assert codes(done["warnings"]) == ["answer_without_valid_citation", "source_id_mentioned_without_citation"]
    assert json.loads(stored["warnings_json"]) == done["warnings"]


def test_query_with_a_valid_citation_keeps_the_same_events_and_no_signal(storage):
    _, events, _ = run_query(storage, "La tension nominale est de 72 V [S001].")
    assert [kind for kind, _ in events] == ["status", "status", "sources", "status", "delta", "done"]
    done = events[-1][1]
    assert [citation["source_id"] for citation in done["citations"]] == ["S001"] and done["warnings"] == []


def test_query_signals_a_value_absent_from_the_context_without_rewriting(storage):
    _, events, _ = run_query(storage, "La tension nominale est de 110 V [S001].")
    done = events[-1][1]
    assert done["text"] == "La tension nominale est de 110 V [S001]." and [citation["source_id"] for citation in done["citations"]] == ["S001"]
    assert done["warnings"] == [{"code": "value_not_in_context", "values": [
        {"value": "110 V", "number": "110", "unit": "V", "cited_source_ids": ["S001"]}],
        "message": "Valeur absente de toutes les sources transmises au modèle : 110 V. Elle peut avoir été calculée, déduite ou "
                   "mal reprise ; vérifiez-la avant de l'utiliser."}]


def test_query_passes_the_question_so_an_abstention_repeating_its_number_is_not_a_missing_value(storage):
    import_fixture(storage, text="CCU-21 tension nominale 72 V.")
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    gateway = ScriptedOllama("Les sources ne donnent pas la tension de CCU-21 sous 230 V.")
    service = QueryService(db, resolver, SearchService(db, resolver, FakeEmbedding(), vectors, settings),
                           ContextBuilder(settings, CharTokenizer()), gateway, settings)

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 sous 230 V ?", scope=Scope(kind="library")))["query_id"]
        await service.tasks[query_id]
        return query_id
    query_id = asyncio.run(scenario())
    done = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query_id,))["data_json"])
    assert codes(done["warnings"]) == ["answer_without_valid_citation"]


def test_abstention_without_model_call_gets_no_answer_signal(storage):
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    gateway = ScriptedOllama("jamais appelé")
    service = QueryService(db, resolver, SearchService(db, resolver, FakeEmbedding(), vectors, settings),
                           ContextBuilder(settings, CharTokenizer()), gateway, settings)

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension ?", scope=Scope(kind="library")))["query_id"]
        await service.tasks[query_id]
        return query_id
    query_id = asyncio.run(scenario())
    done = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query_id,))["data_json"])
    assert gateway.calls == 0 and done["metrics"]["model_called"] is False and done["warnings"] == []
