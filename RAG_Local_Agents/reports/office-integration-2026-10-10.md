# Intégration DOCX/XLSX — preuves locales du 10 octobre 2026

**Rôle :** rapport de preuve de l'intégration R28 · **Propriétaire :** intégration et validation · **Statut :** Vivant, contrôles locaux acquis, limites de qualification ouvertes · **Référence :** base `64e191f5d93e7c8e702a3a8b93713a7aac30e458` et empreintes des sources réellement exécutées · **Mis à jour :** 2026-10-10 13:44 UTC · **Source de vérité :** reçus natifs cités ci-dessous ; actions dans [PLAN.md](../PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation)

La phase d'étude a précédé l'implémentation. DOCX et XLSX complètent maintenant
PDF dans l'import, l'extraction, les représentations, la recherche et les
citations. Les choix sont consignés dans [W055](../DECISIONS.md#w055-intégration-office-après-clôture-de-son-étude-préalable).
La référence technique est l'[architecture Office](../../docs/architecture/ARCHITECTURE.md#41-documents-docx-et-xlsx), le contrat est la [référence HTTP](../../docs/interfaces/API.md#44-versions-et-lecture).

## Implémentation examinée

- `services/ingestion/office/` : préflight OPC/XML borné, DOCX Strict/Transitional dans l'ordre documentaire et XLSX streaming sparse, types/formules/caches séparés, unités complètes reprenables. Ni réseau ni recalcul ; objets non interprétés signalés.
- `services/api/migrations/004_office_documents.sql`, `db.py`, `office.py` : schéma4, sauvegarde SQLite/WAL avant migration, unités/cellules/bindings et métadonnées immuables par génération ; représentations, cellules et assets enregistrés épinglés à la révision.
- `indexing.py`, `office_search.py`, `scope.py`, `context.py` : FTS/Qdrant/E5 existants, projections autorisées avant classement pour les plages, sources précises sans pseudo-page PDF, faits typés et limites des formules explicites.
- `apps/web/src/components/office-*reader.tsx` et helpers : même bibliothèque et panneaux d'analyse, lecteur DOCX structuré, grille XLSX bornée, sections/feuilles/plages, inspecteur et liens de citations. PDF.js demeure réservé aux PDF.
- Quatorze fichiers de la voie PDF sont byte-identiques à la base. Les129 paquets non projet du verrou conservent leurs versions ; quatre dépendances Office déjà verrouillées deviennent directes.

## Contrôles acquis

Les artefacts sont conservés sur la carte SD sous `.runtime/qa/`, ignorés par Git.
Ils comprennent commandes, logs, oracles, manifestes SHA, captures et reçus de revue.
Les nombres de suites qui se recouvrent ne sont jamais additionnés comme cas uniques.

| Contrôle | Résultat observé | Preuve |
|---|---|---|
| Régression Python large, hors3 modules documentaires | 2760PASS,20SKIP Windows,0FAIL ;1405,95s ; un avertissement Starlette/httpx | `r28-implementation/root/unit-final-01/{results.xml,output.log,summary.json}` |
| API HTTP/session/TLS | 88PASS,1SKIP jonction Windows ; sockets TLS/cookies/session réels, modèles doublés explicitement | `r28-implementation/root/api-integration-final/` |
| Extraction DOCX/XLSX | DOCX30PASS, XLSX61PASS ; Strict, types exacts, caches vides/absents, ST_Xstring et reprise | `r28-docx-20261010/`, `r28-implementation/xlsx-refine/` |
| Indexation/pipeline/API/stockage | Indexation Office19/PDF27 ; pipeline/API/PDF76 ; publication, migration, FK, archives et limites vérifiées sur cibles isolées | `r28-office/`, `r28-implementation/integration/` |
| Revue indépendante des huit défauts initiaux | Reproductions conservées ;12 contrecontrôles conformes,155 puis72 tests verts dans suites recouvrantes | `r28-implementation/review/review-final.{json,md}` |
| Frontend final | 454 unités, lint/typage/build3 ; export242 fichiers et provenance explicite | `r28-20261010/frontend/office-frontend-final-proof.json` |
| Imports et lecteurs natifs | Trois originaux synthétiques SHA inchangés, jobs ready ; DOCX image/table fusionnée/sélection, XLSX grille/plage, PDF pixels/rotation/zoom | `r28-20261010/frontend/e2e-office-1/`, `e2e-office-3/` |
| Citations et générations réelles | Question DOCX, Critique XLSX, comparaison PDF/DOCX ; citations enregistrées puis ouvertes sur élément/cellule exacts | `r28-20261010/frontend/e2e-office-3-persisted-generations.json`, `e2e-office-4/` |
| Retrieval et contexte DEV | Six questions, huit faits gelés : Recall@10=8/8, Coverage@Context=8/8 ;0 fuite observée ; aucun LLM pour ce contrôle | `r28-implementation/native/dev-evaluation-01/` puis `dev-evaluation-03/` sur source03 |
| Notices/kit, tests de sélection et compatibilité | 115PASS ; inclusion des sources/dépendances sur trois plateformes testée, notices manquantes signalées | `r28-implementation/root/notices-01/`, `review/` |

Les premières campagnes navigateur ont exposé deux erreurs d'oracle (fusion
de3 colonnes et nom accessible du sélecteur). La troisième a subi SIGTERM143
sans assertion de défaut produit ; deux générations avaient terminé et sont
restées enregistrées. La reprise4 passe réellement, sans les régénérer,
et ajoute seulement la comparaison manquante. Aucun run interrompu n'est
requalifié globalement PASS.

## Vérifications finales et limites

La Critique initiale affirmait à tort que toutes les valeurs venaient du cache,
alors que A2/B2 sont littérales et C2 est hors scope. Le texte erroné est conservé.
Les faits contextuels distinguent désormais `literal`, `empty`, `formula_cache`
et `formula_without_cache`, y compris une sélection de texte, sans modifier les
preuves PDF. Les15 tests RAG et23 contrats passent après cette précision. Le rejeu natif
`5c9380f8` termine en136,318s avec72V cité surB2/A2 et la distinction
littérale correcte, confirmée par la revue indépendante ; aucune généralisation
erronée au cache. Sa réponse et les citations sont persistées et concordantes
avec le SSE. Le collecteur termine néanmoins avecSIGTERM143 après son
rapport complet : cause inconnue, statut conservé ; aucun PASS du collecteur
inventé, aucune régénération pour masquer cet incident.
Le badge `office_native` interprété comme inconnu est aussi corrigé : neuf
tests ciblés puis454 unités, build3 et recette réelle source03 à1366×768/
1920×1080 passent ; quatre captures propres relues par le propriétaire, avec contrôle
indépendant des empreintes et de deux rendus ; aucune alerte de provenance
erronée. `e2e-office-5/` garde ces preuves séparées.

L'hôte réellement exercé est Linux aarch64,61,329Gio physiques, avec CPU4B
imposé et aucun GPU employé pour les générations. Il ne qualifie pas Windows,
Linux x86-64 ou le runtime complet sur CPU physique16Go. Le micro-corpus est
DEV synthétique, jamais un corpus métier/final. Extraction seule mesurée : DOCX3000 paragraphes2,265s/46,63Mio ; XLSX10k5,294s/182,74Mio et100k46,978s/1265,25Mio. Le XLSX1M est refusé en8,360s/28,66Mio par `OFFICE_LIMIT_EXCEEDED`, sans extrait publié. Oracles/adresses/valeurs/ordre et SHA des originaux vérifiés4/4 ; quotas inchangés. `native/scale-01/{summary,verification,evidence-manifest}.json` conserve aussi l’erreur de présentation du script QA (state/status), corrigée sur les résultats natifs sans nouvelle extraction. Le nouveau kit Office n'est pas encore
fabriqué/installé ; l'absence des textes MIT openpyxl/et-xmlfile dans leurs
distributions installées est explicitement déclarée, sans licence inventée.
Les89 critères de la DoD sont inchangés et la qualification globale demeure ouverte.

Dernier contrôle natif : C2 seule, oracle figé avant appel, réponse4B
`88b301ef` en69,808s : formule `=LEN(A2)`, absence de résultat calculé
explicitement annoncée, citationS001 résolue surC2 exacte. Le collecteur
isolé dans sa propre session termine réellement0 ; aucune formule exécutée.
`native/cache-absence-01/{oracle,summary,collector-result}.json` lie sources,
contexte, modèle et ressources. Ce cas unique ne qualifie pas toutes les
abstentions métier. Avant arrêt :5 questions DONE,3 générations ready,
integrity/FK conformes, modèle chargé avecsize_vram0. La seule instanceQA
source03 est ensuite arrêtée ;4 identités et groupes de service absents,
jetonQA retiré, données et originaux conservés, runtime principal intact
(`native/{pre-disposition-03,disposition-final-03}.json`).

Contrôles documentaires : deux incohérences préexistantes sur HEAD corrigées
(date figée du7octobre, références vivantes hors kit dans ses procédures).
La date est confrontée à la révision UTC des quatre sources déclarées ;
les liens de preuve sont conservés hors des sections embarquées. Garde
portable et liste blanche inchangées. Les62 contrôles documentaires généraux
et43 tests des procédures du kit passent ;7/7 contrôles docs et11/11 pack,
brief synchronisé et diagrammes conformes. Les deux rouges et leur
contrevalidation restent séparés (`root/docs-final-01/`, `docs-final-02/`).
