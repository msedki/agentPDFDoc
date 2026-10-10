# Intégration DOCX/XLSX — preuves locales du 10 octobre 2026

**Rôle :** rapport de preuve de l'intégration R28 · **Propriétaire :** intégration et validation · **Statut :** Vivant, contrôles locaux acquis, limites de qualification ouvertes · **Référence :** base `64e191f5d93e7c8e702a3a8b93713a7aac30e458`, sources publiées `57f7f0a6f2feee80adfd35b65bf4d81f6319e74c` et empreintes des sources réellement exécutées · **Mis à jour :** 2026-10-10 15:14 UTC · **Source de vérité :** reçus natifs cités ci-dessous ; actions dans [PLAN.md](../PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation)

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
DEV synthétique, jamais un corpus métier/final. Extraction seule mesurée : DOCX3000 paragraphes2,265s/46,63Mio ; XLSX10k5,294s/182,74Mio et100k46,978s/1265,25Mio. Le XLSX1M est refusé en8,360s/28,66Mio par `OFFICE_LIMIT_EXCEEDED`, sans extrait publié. Oracles/adresses/valeurs/ordre et SHA des originaux vérifiés4/4 ; quotas inchangés. `native/scale-01/{summary,verification,evidence-manifest}.json` conserve aussi l’erreur de présentation du script QA (state/status), corrigée sur les résultats natifs sans nouvelle extraction. Le kit Office est désormais fabriqué et transporté ; sa recette d’installation
est en cours (voir le jalon de livraison ci-dessous). L’absence des textes MIT
openpyxl/et-xmlfile dans leurs distributions installées reste explicitement
déclarée, sans licence inventée.
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


## Publication et suite de livraison Linux

Le commit `57f7f0a` est poussé sur `origin/main` :97 fichiers vérifiés,
identité et parent conformes, aucun corpus/runtime/secret livré. Le journal
local du2octobre reste exclu et inchangé. Les reçus indépendants
`final-review/office-publication-whitespace-delta-review.json` et
`office-postpublication-review.json` confrontent les97 blobs au gel
`root/delivery-manifest-abc43c2832c6f7b6b0e46707d0bc0380d74bada1efa40320b47b190371e5eea3.json`.
Le contrôle indexé a révélé un LF vide final dans trois nouveaux fichiers :
seul ce suffixe est retiré, les autres octets sont conservés ; preuves
rouge/vert et SHA gardés, sans attribuer les nouveaux octets aux anciens
builds natifs. Les validations fonctionnelles gardent leur provenance.

Le nouveau kit Linuxaarch64 CPU4B/2B est préparé sur cible neuve SD depuis
ce commit ; sa fabrication exige un export avec commit identique et sources
propres. L’export historique4825 est conservé, aucune provenance réécrite.
Préflight metadata/cache/disque dans `kit-preflight/` ; installation,
fonctionnement hors réseau et sauvegarde/restauration restent NOT_RUN à ce
jalon. Cette préparation ne qualifie aucun hôte supplémentaire.


## Kit CPU Office : fabrication et transport exécutés

Les cinq étapes du kit `0.1.0+57f7f0a6f2fe-linux-aarch64-none-2b4b` terminent
avec code 0 et statuts attendus : ready, built, verified, archived, extracted.
Durées respectives : 138,060 / 134,197 / 29,524 / 398,010 / 403,169 s,
soit 1 102,960 s. Archive PAX de 11 185 633 280 octets, SHA-256
`298e26bf4a3debd377f5f82efcbf631409c567e57de3d8c97e0ca147d23edeff`.
L’export postcommit a pris 26,42 s ; provenance `0210d67e…`, liée au
commit `57f7f0a`, sources propres. Les sept modules Office du kit fabriqué
et extrait correspondent aux blobs du commit. Variante GPU none, aucune
bibliothèque Ollama GPU ni exigence L4T : ce kit ne dépend pas de Jetson.
Son installation n’est pour autant pas qualifiée sur un autre Linux.

Preuve terminale : `kit-preflight/office-kit-manufacturer-closeout.json`,
SHA-256 `baf96b9dd3e5401734e2eacb6a781bce441ccf1995f39ccfddcb27ad29790b2a`.
Les 80 identités de processus suivies sont absentes après arrêt ; driver
et observateur récoltés. Sur 214 échantillons, minimum RAM disponible
47 271 MiB et SD 35,842 Gio, maximum CPU hôte 34,1 % ; ce sont des
échantillons de fabrication, pas une qualification D07 physique 16 Go.

À ce jalon, aucune installation ni import/API du kit n’a été exécuté.
La recette prévoit un dataset neuf, les trois originaux DEV, six contextes
annotés et deux générations CPU 4B, puis sauvegarde/vérification/restauration
vers une autre racine neuve et une question C2 supplémentaire. Source03
reste arrêtée. La revue pré-exécution a identifié une absence de nettoyage
sur erreur du nouveau wrapper QA ; correction et témoins inoffensifs sont
en cours avant son premier démarrage. Aucun défaut produit n’en est déduit.


## Kit installé et restauré : recette fonctionnelle réelle — 15:14 UTC

Le programme exécuté vient du kit publié `57f7f0a` décrit ci-dessus, export web
0210d67e. Installation standard sans menu, sans démarrage et sans choix
explicite de modèle : source 4B sélectionnée par défaut, texte 4B réellement
servi. Profil principal généré intact ; seul le profil QA impose CPU.
Compte 1000, capacités effectives/permitted/ambient nulles, namespace réseau
`net:[4026535233]` avec boucle locale seule. Une connexion locale fonctionne,
la sonde extérieure échoue ENETUNREACH ; aucun socket extérieur observé.
Le résolveur SERVFAIL de contrôle est un double déclaré, aucun appel DNS
observé. Les services et données principaux n’ont pas été utilisés.

| Contrôle exécuté | Résultat et preuve native sous `.runtime/qa/r28-implementation/` |
|---|---|
| Installation et démarrage | Install135,551 s, up12,208 s et doctor5,331 s, codes0 ; `kit-runtime/source-{up,doctor}-01.json`, rapport d’installation dans la racine QA. La précompilation est annoncée par l’installateur avec code1 non bloquant ; aucune réussite complète de compileall déduite. |
| Imports et recherche | Trois formats ready, originaux SHA exacts, structures DOCX/fusion/image et XLSX/type/formule/cache conformes ;6 questions DEV/8 faits, Recall@10 et Context8/8. `kit-api-qa/before-02/summary.json` et reçu des preuves conservées. |
| Générations avant backup | Comparaison PDF/DOCX72V, Critique XLSX littérale72V/B2, CPU4B réel sans fallback ; sources épinglées et SSE DONE. La reprise ne réimporte rien et relit la comparaison sans la régénérer ; un seul nouvel appel Critique. Revue `final-review/office-kit-before-backup-terminal-review.json`. |
| Sauvegarde et restauration | Backup5,527 s, verify2,814 s, down9,030 s, restore5,982 s, tous0 ;41 fichiers vérifiés,3 versions/révisions/générations,31 tables normalisées identiques,14 citations et2 questions conservées, SQLite intègre/FK0. `backup-preflight/{backup,restored}-invariants-01.json`, revue `office-kit-backup-restore-terminal-review.json`. |
| Vecteurs restaurés |14 points Qdrant1.19.1, IDs/payloads/vecteurs/config exacts, hash canonique22a0b2ba ; collection physique `pdf_chunks_e5small_v1_53cac40518d0dec0`. `kit-runtime/qdrant-{before-02,after-01}.json`. |
| RAG après restauration | Up12,318 s, doctor5,174 s ;2 anciennes réponses/SSE/citations identiques sans régénération,1 nouvelle réponse C2/LEN(A2)/cache absent, collector0/68,306 s. `kit-api-qa/after-01/`, revue `office-kit-restored-api-terminal-review.json`. La phrase LLM « jamais exécutées » n’est pas une preuve de l’historique du classeur ; seul le pipeline ne recalcule pas et le cache observé est absent. |
| Lecteurs et anciennes citations |1 E2E PASS/29,835 s ;9 captures originales aux2tailles et3anciennes sources PDF/DOCX/XLSX, bitmap PDF peint, élément DOCX etB2 exacts.La trace du scénario lecteur compte 126 requêtes GET/HEAD vers l’origine 8795, aucune requête externe ou mutante, ni erreur de page ; la préparation a ouvert une session isolée autorisée.9 PNG vus par propriétaire ; imageDOCX chargée selon DOM, horsviewport des PNG. `kit-ui/restored-readers-01-final-review.json`. Authstate seul supprimé après SHA, preuves conservées. |
| Immutabilité et arrêt |2 instances down,3 jobs ready et2/3 questions done,14/15 citations, intégrité/FK/originaux conformes ;65131 fichiers et1188 liens du programme inchangés.199 lifetimes capturées absentes au contrôle frais. `kit-runtime/office-runtime-terminal-01.json`, `program-comparison-host-01.json`, captures finales `backup-preflight/*-stopped-invariants-01.json`. |

La racine restaurée est directement la cible neuve, pas son sous-dossier
`data/`. Les champs runtime (cache HF, verrou lourd, sauvegardes) restent
sous la racine QA source : comportement du rebasing vérifié, hors programme.
La source03 précédente reste arrêtée, DB/profil SHA identiques ; journalOct2
protégé et89 critères DoD inchangés.

Les deux premiers collecteurs ont échoué sur des hypothèses QA : champ
`format` absent du contrat historique PDF, puis nom configuré de collection
pris pour son nom physique. Rouges immuables conservés, causes corrigées
dans les collecteurs après revue, aucun contrat produit affaibli. Le broker
et son propriétaire reçoivent SIGTERM15 après les deux arrêts et l’inventaire
final, cause inconnue ; exit1 et enfant-15 conservés. La comparaison RO seule
est ensuite exécutée sur hôte, pas dans le namespace fermé. Ce résultat
fonctionnel ne devient pas une réussite terminale globale du broker.

Sur382 relevés espacés de5 s : RAM disponible minimum46612,67 MiB,
RAM totale62800,5 MiB, CPU hôte maximum80,3%, SD minimum25,305 Gio,
racine minimum3,170 Gio ; swap utilisée maximum4695,69 MiB. Ces observations
ne qualifient aucune machine physique16 Go.

### Défaut de permissions confirmé et correctif en cours

`restore_backup()` crée sa racine sans mode explicite ; sous umask002,
racine etcontrol sont0775, admin-token0664. Les ancêtres de ce poste limitent
l’accès des autres comptes, mais cette protection n’est pas portable et le
groupe peut traverser : défaut réel de confidentialité du stockage restauré.
Les écritures de jetons par défaut dans `supervisor.py` ont la même cause.
Huit reproductions filesystem rouges et témoin Windows simulé conservés
sous `permission-fix/`. Le correctif R28-RT-01 est en cours, sans chmod manuel
de la recette, sans modification du programme installé57f ni du système.
Ce kit conserve ses résultats fonctionnels et sa réserve de permissions ;
aucun kit corrigé n’est anticipé.


### Correctif de permissions : source et tests vérifiés — 15:23 UTC

La cause commune est corrigée dans `backup.py` et `supervisor.py` : les
nouvelles racines de sauvegarde/restauration et dossiers de contrôle sont
créés en mode POSIX 0700. Les jetons sont créés exclusivement en 0600 dans
un fichier temporaire, puis remplacés atomiquement. Une cible liée, non
régulière ou détenue par un autre compte est refusée sans lire ni altérer
sa destination. Le nettoyage POSIX porte uniquement sur les jetons émis
pendant la tentative. La rotation des fichiers réguliers et le comportement
Windows sont conservés. Le produit ne modifie ni l’umask ni les permissions
des dossiers existants.

Huit échecs initiaux (4,68 s) et deux échecs supplémentaires sur la sauvegarde
(2,43 s) sont conservés. Une première reprise a échoué sur un oracle de test :
la lecture du hash actualisait atime. L’oracle corrigé vérifie identité,
contenu, mode, mtime et ctime. La suite de régression passe 93 tests, avec
un cas sauté (19,27 s) ; le delta final passe 18 tests (7,68 s). Ces suites
se recouvrent. Ruff et mypy ciblé sur les deux modules sont conformes.
Les fichiers, SQLite et copies sont réels ; processus et HTTP sont doublés.
Les sources PSF Python 3.12 sont consignées sous R28-S19 ; le runtime est
3.12.14 et la documentation consultée est 3.12.15.

Empreintes figées : `backup.py` a45e699f, `supervisor.py` 12ef304e et
`test_runtime_private_permissions.py` 6b840042. Reçus privés :
`permission-fix/summary.json` 1e4cd4a2, `completion.json` 4e078fc8 et
avis indépendant `office-runtime-private-permissions-source-review.json`
bbbccdaa. Sept dossiers temporaires de tests ont été supprimés après relevé
de leurs métadonnées ; preuves rouges/vertes et snapshots sont conservés.
Le kit `57f7f0a` reste intact avec son défaut. La recette d’un nouveau kit
corrigé est encore NOT_RUN à ce jalon.
