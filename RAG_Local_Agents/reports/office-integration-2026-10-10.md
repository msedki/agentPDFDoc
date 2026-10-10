# Intégration DOCX/XLSX — preuves locales du 10 octobre 2026

**Rôle :** rapport de preuve de l'intégration R28 · **Propriétaire :** intégration et validation · **Statut :** Vivant, contrôles locaux acquis, limites de qualification ouvertes · **Référence :** base `64e191f5d93e7c8e702a3a8b93713a7aac30e458`, sources publiées `57f7f0a6f2feee80adfd35b65bf4d81f6319e74c` et empreintes des sources réellement exécutées · Correctif publié et kit CPU natif vérifié : `22fd828` · **Mis à jour :** 2026-10-10 21:14 (UTC) · **Source de vérité :** reçus natifs cités ci-dessous ; actions dans [PLAN.md](../PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation)

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


### Kit corrigé et recette native terminés — 2026-10-10 16:51 UTC

Le correctif est publié sur `origin/main` au commit `22fd828`. Le nouveau
build web termine à 0 en 62,84 s, avec 243 fichiers et provenance vérifiée.
Les cinq étapes de fabrication, vérification, archive et extraction du kit
`0.1.0+22fd828c8ab0-linux-aarch64-none-2b4b` terminent à 0 en 1 162,656 s.
Archive : 11 185 633 280 octets, SHA `478c48a9`; manifeste GPU `none`,
aucun complément JetPack requis, modèle source 4B par défaut. Ce résultat
sur l’hôte Ubuntu 20.04/glibc 2.31 aarch64 ne qualifie pas les autres Linux.

L’installation initiale refuse proprement la place disponible (code 3,
14,9 Gio pour 15,4 requis). Reçu et diagnostic sont conservés. Après relecture
complète de l’archive historique SHA `298e26bf` (128,512 s), le seul ancien
duplicata de fabrication est retiré : 10,455 Gio récupérés. Archive, six
métadonnées, installation historique, données et preuves du défaut restent
disponibles. Le nouveau duplicata de fabrication avait également été retiré
après relecture de son archive. Les caches recherchés pour débloquer cette installation n’ont pas été supprimés.
Les gardes portent sur les identités QA capturées et les éléments observables ;
les cinq accès hôte inconnus et six zombies préexistants restent hors assertion.

| Contrôle du nouveau kit | Résultat réel |
|---|---|
| Installation sans menu, démarrage ni navigateur | Reprise distincte à 0, 364,780 s ; refus 3 initial préservé. |
| Restauration sous umask 002 | 6,444 s ; racine et contrôle en 0700, clé Qdrant temporaire en 0600 réellement observée. Aucun chmod ni lecture de sa valeur. |
| Profil et services | Copie QA explicite : seuls quatre chemins runtime redirigés vers les nouvelles données ; profils brut/restauré et installé inchangés. Up et doctor conformes, CPU 4B. |
| Permissions des services actifs | Racine et contrôle en 0700, admin-token et qdrant-api-key en 0600, propriétaire et lien unique contrôlés. |
| Données et ancienne exploitation | Schéma4, intégrité ok/FK 0, 31 tables normalisées, originaux/extractions/FTS/générations et 14 citations identiques ; 14 points Qdrant avec payloads/vecteurs/configuration identiques. |
| Relecture API | Deux anciennes réponses DONE/SSE et citations PDF/DOCX/XLSX exactes ; requêtes GET uniquement, zéro nouveau POST de question et zéro nouvel appel modèle. Les métriques de génération sont historiques. |
| Nouvelle sauvegarde | Création et verify à 0, nouvelle racine en 0700 et 31 tables/sources identiques à l’état restauré avant API. |
| Arrêt et conservation | Down conforme, programme 65131 fichiers/1188 liens strictement inchangé ; finish explicite, broker et propriétaire à 0, récolte prouvée et 185 identités capturées absentes au contrôle frais. Capture SQL finale en lecture seule sur hôte, après clôture et hors namespace. |

Reçus : `kit-preflight/permission-kit-22fd828-manufacturer-closeout-01.json`
(`db9d49eb`), `permission-kit-22fd828-archive-readback-01.json` (`d4765219`),
`permission-kit-old-57f7-cleanup-after-01.json` (`cc0f5bcb`),
`permission-native-preflight/native-terminal-01.json` et avis indépendant
`office-permissions-native-terminal-independent-review.json`. Les modes sont qualifiés dans la chaîne native,
en complément des tests source ; aucune nouvelle campagne LLM/UI inchangée.
Typecheck des deux modules modifiés aussi conforme sous `--platform win32`
(4,158 s, reçu `root/mypy-permissions-win32-01.json`), sans recette Windows.
Deux captures rapides ont pour champ exécutable le répertoire du dépôt :
leur absence est établie par ascendance, PID et naissance, sans qualifier
leur exécutable. Le reçu initial est conservé et borné par la revue indépendante.

Sur 359 échantillons hôte : RAM disponible minimum
51 350,68 MiB, RAM totale
62 800,50 MiB, CPU maximum
32,0 %, SD minimum
14,837 Gio et racine minimum
3,151 Gio. Les observations réseau concernent
le namespace QA isolé ; aucun socket non loopback observé. Le DNS SERVFAIL
est un double déclaré et l’échantillonnage peut manquer un socket transitoire.
Ces mesures ne qualifient pas un hôte physique de 16 Go. Source03, son profil,
journal protégé et DoD sont inchangés. Windows, Linux x86-64, qualification
métier/finale et recette stricte NF09 restent des réserves distinctes.
Les textes MIT d’openpyxl/et-xmlfile sont présents dans le kit. L’avis
historique qui les déclarait absents est rectifié par R28-RT-02 ; aucun texte
supplémentaire n’a été téléchargé et les archives sont conservées inchangées.


### R28-RT-02 — rectification des avis Office — 2026-10-10 16:57 UTC

Le manque de textes MIT annoncé durant l’étude était un faux constat :
la sonde `inspect_metadata.py` cherchait « license » et omettait « licence ».
Le générateur `tools/dist/notices.py` reprenait ce constat inconditionnellement.
Le correctif inventorie les noms réels des distributions verrouillées dans
les fichiers du kit, y compris le cache uv, et conserve les autres manques.
Une absence n’est déclarée que pour le paquet sans texte repéré. Les
distributions d’une autre version et licences sans lien sont exclues.

Les six nouvelles reproductions échouent avant correction (0,920 s).
La sélection finale passe 13 tests en 2,341 s (commande : 3,497 s), avec
branches Windows-x86-64/Linux-aarch64/Linux-x86-64, sans recette native
des hôtes absents. Ruff termine à 0 en 0,071 s, mypy ciblé en 0,418 s.
Reçu `notices-fix/completion.json`, SHA `53216923` ; aucun test existant
affaibli, aucun changement du pipeline Office ni nouvelle dépendance.

L’inventaire réel des 35 624 fichiers du kit CPU `22fd828` et les trois
petits textes sont contrôlés : openpyxl 3.1.5 et et-xmlfile 2.0.0 contiennent
chacun `LICENCE.rst` (1 131 octets), SHA256
`0c84bb42f5d367e5ebf9fc2dde35b16141df5ee0fdc189250858bc6c5560f69e` ;
et-xmlfile contient aussi `LICENCE.python` (14 688 octets), SHA256
`4ccdaaebc0f44b83720ec0399bb7ab329adce067dd62f73c5535a2dc05628ab2`.
METADATA, RECORD et SHA256SUMS concordent. La notice régénérée depuis
cet inventaire est un artefact QA distinct (SHA `9322c5de`), pas une nouvelle
archive. Le reçu `notices-fix/actual-kit-rectification.json` conserve les
identités/hashes avant-après de l’archive, manifeste et avis original.

Le rectificatif `0.1.0+22fd828c8ab0-linux-aarch64-none-2b4b.LICENCES-RECTIFICATIF.md` est joint dans `delivery/`, hors archive,
avec le SHA256 complet `478c48a928552b6caa913da9c4a5eb70f45bd7737d1b61fded3df014d3b61686`.
Son SHA256 est `85a502a06eccd1b48dbd5901e4e760d4207c04564e9ae4e90fcb2eda47d7e292` ; reçu
`root/notices-addendum-delivery-01.json`. Archive, extrait et installation
ne sont pas modifiés. R28-S09 corrige explicitement le constat historique ;
le journal initial reste conservé. W030 et les autres réserves restent
inchangés. Aucun téléchargement, recalcul, service ni nouvelle fabrication.

Revue indépendante du générateur et des inventaires :
`final-review/office-notice-inventory-source-and-rectification-review.json`,
SHA `71dfe354`, GO ciblé ; temporaires pytest/mypy supprimés après contrôle
(`notices-fix/cleanup-after.json`, SHA `9cbdf1cf`), preuves préservées.

## Migration native SQLite v3→v4 — 10 octobre, 17:48–18:00 UTC

La recette précédente sur le kit `22fd828` restaurait déjà une base v4 ; elle
ne prouvait pas la migration native. La nouvelle cible QA sur SD réutilise
le même programme immuable et le backup R27 synthétique scellé de schéma 3 :
14 documents, 15 versions, 22 citations, quatre historiques et 623 événements.
Aucun corpus privé/final, nouvel import ou nouvelle question n’est utilisé.

Les quinze commandes avant finish passent : inventaire 32,455 s, vérification
du backup 3,464 s, restore CLI 6,737 s, up 12,467 s, doctor 5,173 s, down 6,958 s,
inventaire final 32,783 s et comparaison stricte 1,267 s. La capture avant API
retrouve exactement les 26 tables v3 ; les modes root/control 0700 et jetons 0600
sont réellement observés sous umask 002 sans chmod de QA. Les 60 points Qdrant,
15 originaux, 22 citations et quatre historiques/SSE sont relus ; il n’y a
aucune nouvelle inférence, les métriques des anciens historiques restent
historiques.

Le dispatch de finish est fautif : il publie le wrapper `request` au lieu
de l’objet intérieur `finish:true`. Le broker lève KeyError, le propriétaire
est effectivement récolté à 1. Ce rouge est conservé ; les quinze commandes
réussies ne le rendent pas nominal. Après récolte, les 67 lifetimes capturées
sont absentes au contrôle frais. La capture hôte en lecture seule confirme
31 tables v4, 25 tables héritées et 68 rowids FTS et catalogues inchangés, cinq tables
Office vides et un backup automatique dont les 26 tables v3 sont exactes.
L’idempotence native est encore en attente à ce jalon.

Preuves sous `r28-implementation/v3-native-preflight/` : gel d8586fd8,
`phase1-terminal-01.json`17e2080c (84 entrées liées),
`phase1-finish-dispatch-red-01.json`93c7f3f0,
`phase1-owner-exit-proof-01.json`a483a442,
`phase1-fresh-lifetimes-01.json`e3dfbe71 et
`migration-host-after.json`3a7e913a. Relecture indépendante et préparation
d’une reprise distincte : `final-review/native-v3-phase1-failed-finish-state-and-restart-preparation-review.json`
deab3838 ; template initial inchangé, ancien retour1 non requalifié.

Le runtime réellement observé est CPython 3.12.14, SQLite 3.53.1, psutil 7.2.2,
Linux aarch64/glibc 2.31. `_sqlite3` est built-in sans fichier partagé : il est
lié au SHA du binaire Python réel, pas à un chemin supposé. Première sonde
métadonnée refusée et reprise RO conservées ; `executed-versions-02.json`
17e50835. Cette observation ne qualifie pas SQLite Windows/x86-64,
un crash pendant la transaction ou une machine physique de 16 Go.

## Redémarrage natif et idempotence — 10 octobre, 18:02–18:12 UTC

La reprise utilise un nouveau broker et une recette distincte, sans restore
ni rejouer la migration. L’ancien template exigeant un premier exit0 reste
inchangé ; le nouveau préflight conserve explicitement le premier exit1.
Le dispatcher QA est corrigé : objet finish au bon niveau et publication
atomique du fichier fermé. Le refus indépendant de la première écriture non
atomique et les témoins purs rouge/vert restent conservés. Aucun code produit
ni helper de supervision déjà qualifié n’est modifié.

Les sept commandes réelles passent, puis finish confirme SESSION_FINISHED.
Up 12,042 s, doctor 5,013 s, permissions 0,334 s, relecture GET 3,563 s,
down 7,182 s, inventaire 32,591 s et comparaison 1,247 s : 61,972 s de
commandes cumulées, sans les confondre avec le temps écoulé de la recette.
Le propriétaire et le broker sont réellement récoltés à 0 ; aucun signal de
nettoyage, erreur ni processus restant. Les 53 identités PID/naissance sont
absentes au contrôle frais avec distinction explicite des zombies et inconnues.

Après récolte, la capture hôte retrouve les 31 tables, SQL, FTS, catalogues
d’originaux/extractions et le même backup v3 exactement inchangés. Integrity
est ok, aucune erreur FK. Le backup de 1 875 968 octets conserve son SHA
`112b89c196d9bbf17bcf46990461cb9486c63812cf291ba562924a6471a3d9ca`.
Les 15 originaux, 22 citations, quatre historiques et 623 événements sont
relus sans nouvelle inférence ; les modes restent privés. L’inventaire du
programme retrouve 65 131 fichiers et 1 188 liens sans changement.

Preuves : `v3-native-preflight/recovery-terminal-01.json` (`aa9863f9`),
`restart-host-after.json` (`7fff8c9c`), `recovery-fresh-lifetimes-01.json`
(`12b4e229`) et avis indépendant
`final-review/native-v3-recovery-restart-terminal-independent-review.json`
(`06574cf5`). Sur 65 relevés : RAM disponible minimum 51 430,64 MiB,
CPU maximum 29,6 %, SD minimum 15,108 Gio, racine minimum 3,120 Gio.
Les 26 relevés réseau observent zéro socket non loopback ; l’échantillonnage
et le DNS SERVFAIL double déclaré gardent leurs limites.

Cet acquis clôt la migration et son redémarrage dans ce périmètre Linux
aarch64/CPU. C02 reste ouvert pour crash pendant transaction et SQLite des
hôtes Windows/x86-64 ; C05 versions, C08 classeurs jumeaux, C10 reprise et
runtime volumineux, qualification physique 16 Go et métier/finale restent
distincts. Le diagnostic DEV suivant produit de nouvelles questions et est
séparé de ces captures SQL immuables.

## Diagnostic DEV DA-P01 à preuves constantes — 10 octobre, 18:20–18:35 UTC

Le programme installé `22fd828`, profil CPU/no-think, modèle 4B digest `de8024db`
et original `791b9535` sont liés à un binding réel relu avant exécution. Les
captures C02 sont scellées avant les nouvelles questions. Aucun import, reindex,
restore, retry ou juge modèle supplémentaire. Les trois contextes réels ont
la même matière ordonnée/provenance/signature `794a6219`, les mêmes budgets et
aucune troncation ; les messages diffèrent par la question.

La collecte réelle termine à 0 en 217,340 s avec trois DONE/CPU sans fallback.
Ce retour valide la collecte, pas la qualité. La lecture directe des trois
réponses et des citations donne :

| Question | Résultat observé |
|---|---|
| « Quelle est la intervalle de contrôle indiquée pour DA-P01 ? » | Faux refus : cite dans le texte « toutes les 1020 h » puis nie la valeur et conclut que les preuves manquent. Aucun marqueur de citation valide. DONE `084e660c`. |
| « À quelle périodicité le contrôle de DA-P01 doit-il être réalisé ? » | Réponse affirmative 1020 heures, `[S001]` résout le bloc exact de page 1 et la bonne version/révision. DONE `9f28df8a`. |
| « What is the inspection interval specified for DA-P01? » | Réponse en français, conformément au système, affirmative 1020 heures avec la même citation exacte. DONE `9727ec64`. |

Le passage source est « Le contrôle périodique de DA-P01 intervient toutes les
1020 h. » ; ses offsets sont 0–62 sur le bloc autoritaire. Les comptes
prompt/sortie sont 764/270, 766/81 et 761/73 ; TTFT respectifs 52,601 s,
38,972 s et 37,408 s. Ces trois mesures ne qualifient ni D07, ni un hôte
physique de 16 Go, ni un taux de qualité métier/final.

Ce témoin exclut un manque de récupération de la preuve pour ces trois
questions et montre une sensibilité au libellé dans cette exécution. Il ne
prouve ni une cause générale liée à la langue, ni la cause racine du modèle
ou de l’instruction. Le refus connu 4B reste une réserve à traiter ; aucune
correction produit ou amélioration de score n’est revendiquée.

Preuves sous `frontend-semantic-da-p01-20261010/fresh-run-01/` : résumé
`0af5cde7`, comparaison `d9adad9b`, DONE/SSE/citations conservés. Lecture ROOT :
`root/semantic-da-p01-root-adjudication-01.json`, SHA `0c310e1f`.
Le résumé copie une ancienne limite « préparation seulement, zéro appel »
de l’oracle de préparation ; cette limite est périmée pour l’exécution et ne
contredit pas les trois métriques model_called/SSE observées. L’original reste
inchangé, cette rectification distingue préparation et exécution.

Revue sémantique indépendante :
`final-review/da-p01-three-formulations-semantic-adjudication.json`
(`b609eebe`) concorde avec la lecture ROOT. Résultat qualité global de ce
seul diagnostic : échec, un faux refus ; deux réponses correctes ne le rendent
pas conforme. Les critères généraux et les réserves D06 restent inchangés.

La clôture technique distincte est validée indépendamment :
`v3-native-preflight/semantic-terminal-01.json` (`567dd57a`) et
`final-review/da-p01-native-terminal-cleanup-independent-review.json`
(`051545af`). Sept commandes à 0, finish réel, propriétaire/broker récoltés à
0 et 79 identités absentes au contrôle frais. Les cinq tables de questions,
conversations, messages, événements et citations changent conformément aux
trois questions ; les 26 autres tables, originaux/extractions, backup C02 et
programme restent exacts. Les relevés observent CPU maximum 89,2 %, RAM
minimum 47 094 MiB et SD minimum 15,093 Gio. Ce succès technique préserve
l’échec sémantique décrit ci-dessus.

## DA-P01 — localisation des causes, 10 octobre 20:29–20:36 UTC

Lecture ciblée des trois réponses DEV existantes, sans nouveau modèle, API,
corpus ou test : les cinq modules `context.py`, `query.py`, `retrieval.py`,
`claims.py` et `ollama.py` sont identiques au programme installé `22fd828`.
Le motif de `retrieval.py:19` accepte tout composé alphabétique avec tiret.
Ainsi « doit-il » devient DOIT-IL requis ; seule DA-P01 est couverte, d'où
0,5 et deux avertissements injustifiés. Cette question a pourtant reçu une
réponse correcte. Le faux refus historique avait une couverture de 1,0 :
les deux défauts sont distincts, sans lien causal établi.

Les cinq preuves sont conservées et intégralement transmises ; le refus
figure dans le texte réellement généré. Les avertissements sont des
métadonnées SSE, pas des messages injectés au modèle. Le vérificateur de
citations/nombres ne prouve pas la relation sémantique ni sa négation.
La cause interne précise du refus reste inconnue ; modifier le prompt,
la température ou la seed n'est pas un correctif démontré. W037 reste
applicable, sans filtre de réponse, synonymie forcée ni boucle de tuning.

Proposition distincte, non implémentée : séparer candidats textuels et
références obligatoires avec une classification commune. Exiger partout
un chiffre supprimerait aussi de vrais AB-CD. L’utilisateur confirme une
codification hétérogène, lettres/chiffres et séparateurs `-`, `_`, `/` ;
une occurrence de mot composé ne prouve toutefois pas son rôle métier.
Normes, sections, limites exactes, tirets
Unicode, codes alphabétiques reconnus et focus doivent être conservés.
Les sources officielles expliquent regex et paramètres de génération,
sans définir la grammaire métier ni garantir la qualité d'une réponse.

Préparation ciblée `reference-resolution-preparation-01.json` (`c3f4d0eb`),
18 sources épinglées, puis témoin sur code courant `current-code-terminal-01.json`
(`2b1a1438`) : six observations, dont trois rouges de comportement. DOIT-IL
fausse la couverture ; focus ABC et abc inconnu sont acceptés mais n’apparaissent
ni dans les obligations ni dans les exacts. Contrôles acquis à préserver :
AB-CD/aa-il réellement présents dans le contexte final malgré six passages
écartés par budget, candidat alphabétique empêchant un nouvel héritage
implicite, DA-P99 obligatoire et absent. SQLite/FTS/index/Scope/Search/Context
sont réels ; embedding, moteur vectoriel, tokenizer et extraction sont des
doubles explicitement déclarés. Exécution 4,382 s, enfant réellement récolté
et fraîchement absent. Exit0 signifie collecte de défauts, aucun PASS du
correctif ni qualification native ; source produit encore inchangée.

Diagnostic conservé :
`frontend-semantic-da-p01-20261010/source-diagnosis-20261010/source-cause-and-corrections-01.json`
(`12ce5024`) ; revue indépendante en lecture seule
`final-review/da-p01-source-diagnosis-independent-review.json` (`868d888f`),
14 empreintes exactes et mêmes cinq preuves/provenances. Aucune correction
produit ni nouvelle mesure de qualité n'est revendiquée.

## Crash pendant migration SQLite — 10 octobre, 18:34 UTC

Une base synthétique minimale v3 isolée réutilise la fixture versionnée
`legacy_database`, sans importer tout le module de tests. Le module DB et
la migration sont ceux du programme installé `22fd828`, sans SQL/source
modifié. Le seul dispositif QA est une synchronisation sys.settrace sur la
ligne réelle avant `ALTER TABLE blocks_v4 RENAME TO blocks`.

Le marqueur positif observe transaction active, schéma 3, ancien `blocks`
déjà supprimé et `blocks_v4` contenant une ligne. L’enfant PID/naissance
possédé reçoit SIGKILL, est réellement récolté à -9 et devient absent.
Parent et enfant sont UID/EUID 1000, sans capacités. La commande termine à 0
en 2,069 s. Les descripteurs, pipes et connexions SQLite sont fermés ; aucune
erreur primaire ou de nettoyage, aucune API, service ou génération.

Les fichiers de crash sont conservés avant la connexion normale de reprise :
DB 229 376 octets, SHM 32 768 et WAL **0 octet**. Il s’agit d’un vrai arrêt
pendant la transaction ; il ne démontre pas la récupération de pages déjà
écrites dans un WAL non vide, ni une panne électrique. Les 26 tables v3,
FTS, identités/citation et original sont exacts après reprise. Initialize
réel atteint 31 tables v4 ; les 25 héritées sont exactes, les cinq Office
vides, defaults PDF conformes. Une seconde initialisation ne change ni tables
ni backups. Deux backups v3 complets sont attendus : un avant le crash, le
second au redémarrage encore en v3 ; ils ont les mêmes contenus et SHA,
sans imposer artificiellement un backup unique.

Preuves : `root/c02-crash-command-01.json` (`50e69d91`),
`root/c02-crash-native-01/completion.json` (`7c70792e`), marqueur `ed63520a`,
cleanup `47214348` et snapshots avant/reprise/migration. Préparation relue
`final-review/c02-crash-sqlite-preparation-independent-review.json`
(`72bc2b7e`). R28-S20 donne la référence SQLite officielle, pas une preuve
supplémentaire d’exécution. La portée reste cette petite base native Linux
aarch64 ; SQLite des autres hôtes, volumétrie et qualification 16 Go restent
ouverts. Revue terminale indépendante acquise :
`final-review/c02-crash-sqlite-terminal-independent-review.json`
(`aae6ec0d`), avec relecture exacte des tables/FTS/backups et absence fraîche
du parent et de l’enfant. Les limites WAL vide et autres plateformes sont
explicitement maintenues.

## WAL validé non vide et crash de migration — 10 octobre 20:50–20:55 UTC

Cette variante distincte réutilise la petite fixture v3 publique et le
programme installé `22fd828`. Python 3.12.14 et SQLite 3.53.1 sont réellement
exécutés ; ni module DB, ni migration produit, ni original ne sont modifiés.
Un lecteur QA conserve son ancienne transaction. Un écrivain QA valide
uniquement un marqueur dans `documents.name`, sans changer le texte source,
son hash ou les citations, avec autocheckpoint désactivé dans sa connexion.

Le WAL conservé contient **4 152 octets**, dont une frame de 4 096 octets
validée. Le témoin base seule ne contient pas le marqueur ; la connexion
normale DB+WAL et la sauvegarde SQLite en ligne le contiennent. Le checkpoint
PASSIVE QA est une opération explicite, non une lecture : résultat `[0,1,0]`,
aucune frame recopiée en présence de l'ancien lecteur. Un marqueur de trace
positif observe ensuite la migration réelle après DROP et avant RENAME/COMMIT.
L'enfant migration reçoit SIGKILL et est réellement récolté à −9.

DB, WAL et SHM sont conservés avant fermeture des deux autres acteurs.
La reprise à froid utilise une copie DB+WAL et une connexion SQLite normale,
sans `immutable=1` ; le SHM est reconstruit. Les 26 tables v3 et le marqueur
validé sont exacts. L'initialisation réelle aboutit à 31 tables v4, avec les
25 tables héritées préservées et les cinq tables Office vides. Deux backups
v3 complets contiennent le marqueur ; une nouvelle initialisation laisse
schéma, données et backups inchangés. Intégrité, FK et FTS sont vérifiés.

Exécution native **3,141 s**, enveloppe possédée **3,840 s**, exit 0,
erreurs primaire/nettoyage absentes. Les quatre identités PID/naissance
(parent et trois acteurs) sont absentes après récolte. Le témoin antérieur
avec WAL vide reste conservé dans sa portée propre. Aucun service, API ou
LLM n'est lancé pour ce contrôle.

Preuves sous `c02-wal-nonempty-preparation/` : préparation `bd6a1b26`,
GO ROOT `80738fba`, `execution-terminal-01.json` (`e2d99957`),
`scratch-01/wal-before-migration.json` (`82a38b2f`),
`scratch-01/completion.json` (`35f52cc8`) et `terminal-handoff-01.json`
(`5e049ee6`), 33 fichiers/1 614 190 octets conservés. Revue indépendante
`final-review/c02-committed-nonempty-wal-terminal-independent-review.json`
(`b80460f0`) : empreintes, quatre absences fraîches et cinq bases arrêtées
relues, schémas/lignes/backups/FTS exacts. R28-S20/S26 donnent les contrats
officiels ; la récupération logique constitue la preuve d'exécution.

Portée : petite fixture DEV Linux aarch64, une frame de métadonnée validée
et un SIGKILL synchronisé. Ni débordement WAL de données non validées,
ni panne électrique, grosse base, hôte physique de 16 Go, Windows ou Linux
x86-64 ne sont qualifiés par cet essai. C02 global reste partiel.

## Classeurs jumeaux et classement autorisé C08 — 10 octobre 18:52–19:10 UTC

F exécute une nouvelle recette native sur le programme installé `22fd828` et
un dataset neuf. Les deux XLSX synthétiques sont identiques sur A2:A4 et
A2:A10 ; ils ne diffèrent que par les cellules hors plage B2:B10. Original1
SHA `cc3c7a14`, original2 SHA `08bb14c5`. GO préparatoire `2c5d964b`, ROOT
stage1 `2497e08d` ; quatre commandes à 0, binding réel `74b4d346`, revue
`b3fb172c` et ROOT stage2 `85ad988f`. Recette stage2 `5e4f8565` : seule
substitution du SHA de binding dans le modèle, pas un oracle modifié.

Deux imports et quatre contextes réels terminent à 0 en 19,905 s. Dans les
12 ensembles top10/final/contexte, la preuve positive A2/CCU-21/72 V est
présente. Rang, scores, textes, adresses et offsets autorisés sont identiques
entre classeurs pour chaque plage. Les UUID, révisions et hashes intégraux
interversions ne sont pas artificiellement comparés : chaque source garde
sa provenance propre vérifiée. Valeurs hors plage absentes des preuves.

Le classement utilise les projections autorisées/FTS5 du code réellement
épinglé et E5 CPU local ; aucun SQL par requête n’est tracé. Sur les quatre
contextes, les compteurs indiquent six exécutions ONNX achevées : quatre
inputs query et neuf inputs passage. Après le premier classeur, le second
réutilise ses trois puis neuf projections par cache ; aucun nouvel input
passage pour ces deux appels, mais le query E5 est réellement exécuté.
Qdrant sert à l’indexation et aux diagnostics, aucune recherche de classement
Qdrant n’est prétendue pour ces plages. Zéro nouvelle requête RAG et zéro
inférence LLM ; cela ne signifie pas une absence d’embeddings E5.

Down 8,447 s, pré-finish 0,605 s, inventaire 33,067 s et comparaison 1,278 s
passent, puis vrai finish et propriétaire de la session 54120 récolté à 0. Post-down
`dcf0c590` : deux documents, deux versions/générations, zéro query/citation/event.
Closeout `9d1bf83a` : 90 identités, propriétaire inclus, absentes au contrôle
frais ; programme 65 131 fichiers/1 188 liens inchangé. Terminal `aac17d5d`
lie 87 preuves. Revue indépendante terminale `1c70c806` : hashes, sources,
12 ensembles positifs, compteurs E5/cache, SQL/FK et 90 absences vérifiés.

Deux limites héritées de préparation dans le résumé sont périmées après
l’exécution ; l’original est conservé et le compagnon terminal rectifie
explicitement ce texte. Une garde ROOT initiale comparait le hash du fichier
profil au hash canonique API : rouge QA conservé et contrats distincts
corrigés, sans mutation produit ou appel API supplémentaire.

120 observations : CPU max 37,7 %, RAM disponible minimum 50 970,61 MiB,
SD minimum 15,064 Gio, RAM physique 62 800,5 MiB. Vingt-cinq observations
réseau ne trouvent aucun trafic non loopback observé ; pas de capture réseau
exhaustive. Le token a été retiré par down : motifs inspectés sans fuite,
sans prétendre à un scan littéral du secret indisponible. Données/originaux
conservés, aucun corpus utilisateur touché. Preuves sous
`.runtime/qa/r28-implementation/frontend-c08-twins-preparation-20261010/`.

Qualification limitée à ce cas natif Linux aarch64. Autres scénarios C08,
qualité LLM, NF09, métier/final, Windows, x86-64 et physique 16 Go restent
hors de cette preuve. C05 démarre ensuite dans sa propre restauration.

## Persistance des citations Office C05 — 10 octobre, depuis 19:05 UTC

Une nouvelle restauration du backup Office scellé est exécutée sur le
programme installé `22fd828`, dans son propre dataset et espace réseau.
Elle conserve trois documents PDF/DOCX/XLSX, deux réponses enregistrées,
14 citations dont 13 Office et 14 points Qdrant. Aucun corpus utilisateur
n'est modifié. Les anciennes citations ne sont pas régénérées par un LLM.

Le premier contrôle QA11 termine à 1 avant toute réindexation ou import.
Il compare à tort le repère de ligne complet du lecteur XLSX au repère de
cellule projeté de la citation. Les six cas réels ont un bloc, une version,
une révision, un hash et une tranche Unicode conformes ; la cellule citée
est comprise dans la ligne source. Aucun défaut produit n'est établi.
Le rouge `6e06e042`, le gel `1da8e03f` et la sortie partielle restent
conservés. Une copie QA distincte `428b82b0` conserve les 66 assertions et
le finally antérieurs, puis vérifie les coordonnées, le binding littéral
unique, le texte exact, la valeur typée et l’inclusion du repère XLSX.
L'égalité stricte DOCX reste exigée. Six cas réels et 14 contre-exemples,
avis indépendant `7bfd9d41` ; GO ROOT `f675b171` sur les entrées fraîches.

La commande corrigée s'exécute une seule fois dans la session possédée,
sans nouveau restore/up : sortie distincte `api-persistence-02`, résultat
`21c9728e`, code 0 en 21,366 s. Deux réindexations des mêmes versions sont
suivies de deux imports V2 réels. Les quatre jobs sont prêts et publiés.
Les 13 citations Office et les deux réponses enregistrées restent exactes
aux trois phases baseline/après réindexation/après V2. Le matériau des
lecteurs anciens garde le même hash canonique `3c363439`. L'ancien B2 reste
à 72 V ; le nouveau B2 contient 73 V. C2 conserve `LEN(A2)` sans valeur
calculée en cache. Les originaux restent exacts.

Les points Qdrant passent de 14 à 14 puis 16 ; chaque ensemble actif est
contrôlé contre les UUID et payloads SQL, avec vecteurs présents. Le
nettoyage des générations remplacées est automatique et les points PDF
restent exacts. E5 indexe réellement les documents ; zéro POST de nouvelle
requête et zéro nouvel appel LLM. Mode initial rétabli, erreurs primaire
et de nettoyage nulles. Résumé `29ecfa3f`, reçu natif `c76a2362` liant
116 fichiers ; preuves sous `.runtime/qa/r28-implementation/c05-native-preflight/`.

La commande navigateur réelle termine à 0 en **26,489 s** (`dd5d1c12`) :
un test réussi, zéro skip/retry/flaky/unexpected. Elle ouvre 13 citations
anciennes (7 DOCX/6 XLSX), vérifie DOM/API/hash/slices/repères et exerce
deux retours depuis la version courante V2 vers l'ancienne source.
Les 282 requêtes de page sont des GET, sans mutation, destination externe
ou erreur de page ; le bootstrap d'authentification distinct est déclaré.
Le panneau d'analyse ne recharge pas les anciens chats : aucun clic de
bouton historique ni nouvelle question n'est simulé. Ce périmètre ne
clôture pas à lui seul tous les scénarios du critère C05.

Six PNG originaux sont réellement examinés par le propriétaire, ROOT et
le relecteur indépendant : S002 DOCX/tableau CCU-21/72 V et S004 XLSX/Mesures
B2/72 V à 1366×768 et 1920×1080, puis leurs retours à 1366×768. Les identités
anciennes restent visibles après publication V2. Les autres citations
sont contrôlées par DOM et preuves natives, sans prétendre à 13 captures.
Avis pixels/contrats/privacy `4ebf8a99`, terminal UI `ea4b3c11`.

La première vérification de l'authstate refuse son mode **0664** avant
lecture. Son parent est 0700 ; le propriétaire corrige le fichier exact
par descripteur en 0600 (`dd32c3ff`). Le scan borné compare trois secrets
connus en mémoire contre huit sorties et deux corps décodés, sans résultat
positif (`9379bee0`) ; ce contrôle n'est pas une revue de sécurité exhaustive.
Après fin native, seul cet authstate de 554 octets logiques est supprimé
(`b100723a`) ; six PNG et rapport restent identiques. Le compagnon fermé
`06fdf9f9` complète les reçus historiques sans les réécrire. La cause QA
source writeFile sans mode est reproduite sur fichier synthétique réel
(`254ff340`) ; son correctif R28-QA-01 est vérifié ci-dessous, sans changement du produit.

Arrêt **7,398 s**, inventaire **29,994 s**, comparaison **1,381 s**, tous à 0 ;
finish natif puis propriétaire 83739 effectivement récolté à 0 (`f32cb035`).
Les 208 couples PID/naissance sont fraîchement absents, sans accepter de
zombie ou d'accès inconnu (`d504a360`). Trois captures d'exécutable sont
bornées à l'ascendance/PID/naissance : le champ contient le répertoire du
repo, pas un fichier exécutable. Aucune identité restante connue.
Programme inchangé ; terminal `58c04ed3` lie 247 preuves, revue finale
indépendante `a9e6344d` acquise après fermeture et unlink. La capture hôte
SQLite en lecture seule après arrêt (`07ec179f`) confirme 31 tables,
intégrité ok, zéro erreur FK, WAL vide, cinq historiques exacts et anciens
originaux conservés ; cinq versions/révisions et sept générations.
Les points Qdrant sont prouvés avant down, aucune lecture live après arrêt.

406 observations hôte : CPU max 48,4 %, RAM disponible minimum 50 474,57 MiB,
SD minimum 15,020 GiB, disque système minimum 3,094 GiB. Hôte physique
62 800,5 MiB, Linux aarch64, fixtures synthétiques DEV : aucune qualification
CPU 16 Go, Windows, x86-64 ou métier/finale. C10 runtime complet utilise
les fixtures scale-01 existantes, sans nouveau benchmark de parsing ;
la recette locale distincte ci-dessous n’est pas une qualification CPU 16 Go.


## R28-QA-01 — session des recettes web, 10 octobre 20:11–20:16 UTC

La cause du mode 0664 est corrigée dans
`apps/web/tests/e2e/storage-state.ts` et `tests/global-setup.ts` : obtenir
l'état Playwright en mémoire, sérialiser avant création, ouvrir un temporaire
exclusif privé dès sa création POSIX (0600), fermer l'écriture complète puis
remplacer la cible propre. Liens symboliques, entrées étrangères ou non régulières,
parent modifiable par d'autres comptes et changement observé de la cible
sont refusés. Une erreur secondaire de fermeture ou de retrait est rapportée
avec l'erreur initiale, conservée comme cause d'AggregateError. La résolution
du chemin, le bootstrap et le finally de disposal existants sont conservés.

Le témoin vérifie réellement le mode dès open sous umask 002 et la
conservation de l'ancien inode pendant son remplacement. Les pannes
partielles/rename/close/unlink sont injectées explicitement sur fichiers et
descripteurs réels ; le propriétaire étranger est un double de métadonnées
UID. Ces substitutions ne sont pas des essais d'accès entre deux comptes.
18 tests ciblés et 467 unités web passent, aucun échec ni skip ; lint et
typecheck sont conformes. Durées monotones des contrôles : 0,723 s,
10,027 s, 3,788 s et 15,045 s respectivement. Le minuscule champ de durée du
diagnostic initial est invalide et n'est pas utilisé quantitativement.

Preuves conservées sous
`.runtime/qa/r28-implementation/frontend-authstate-mode-diagnostic-20261010/` :
`qa-authstate-completion-01.json` (`94677871`), logs et reçus des quatre
contrôles, préimages des deux helpers avant changement (`7fd5a350`),
reproductions rouges et diff (`252ff655`). Revue indépendante en lecture
seule : `final-review/qa-authstate-source-independent-review.json`
(`f2bbbc13`), 31 empreintes exactes et aucun défaut bloquant identifié.

Les dix TMPDIR de ces contrôles sont retirés après leurs résultats terminaux :
17 751 096 octets logiques de caches dérivés, 36 preuves rehashées identiques
(`check-temps-cleanup-after-01.json`, `8ba96581`). Huit producteurs Node
sont récoltés et leur /proc absent ; les deux premiers dossiers vides sont
bornés à leurs retours terminaux sans PID historique reconstruit. Le delta
libre du volume est une observation globale et ne mesure pas seul l'espace
physique récupéré par ce nettoyage.

Preuve Linux aarch64/Node 24.16.0 ; code POSIX et voie Windows distincts,
aucune garantie d'ACL Windows, de résistance à une course d'un même UID,
d'exclusivité NFS ou de durabilité par fsync. La garantie d'erreurs couvre
le writer et ses FD/temp ; la double panne API/setup plus disposal n'est
pas testée. Aucun build, navigateur, recette C05 ou runtime produit n'est
rejoué : les sources fonctionnelles et le kit `22fd828` sont inchangés.
Publication acquise `4e8f6b637edeebc69d4aed0bc554e646b6309763` à 20:26 UTC
(21:26 Casablanca) : dix fichiers exacts, quatre commandes Git à 0 et
propriétaire 20665 réellement récolté à 0. Reçu `root/final-publication-authstate-docs-01.json`
(`cdef5658`) ; contrelecture `final-review/qa-authstate-ten-files-postpublication-independent-review.json`
(`10387418`). DoD, 89 critères et journal Oct2 protégés ; seule la
modification préexistante de ce dernier reste hors lot.


## C10 — volumétrie, reprises et quotas natifs — 10 octobre 20:11–21:00 UTC

Le kit installé `22fd828`, son profil CPU et les fixtures publiques scale-01
sont gelés avant essai. Une seule stack QA Linux aarch64 est restaurée puis
démarrée hors réseau dans son espace réseau dédié. Aucun corpus privé,
nouvelle question RAG ou appel LLM ne participe à cette recette.

| Entrée | Résultat réellement observé | Durée et portée |
|---|---|---|
| DOCX 3 000 paragraphes | READY, 3 000 blocs et fragments publiés, sources exactes | 82,742 s selon le reçu de publication. |
| XLSX 10 000 cellules présentes | READY, 5 000 blocs/fragments, 10 000 cellules | 153,479 s selon le reçu de publication. |
| XLSX 100 000 cellules présentes | Même job et version ; une génération publiée à l’essai4, READY après crash/pause/annulation et reprises ; 50 000 blocs/fragments et 100 000 cellules | Création→publication 1 472,124 s, soit 24 min 32,124 s, interruptions comprises. |
| XLSX 1 000 000 cellules présentes | Refus HTTP 400 avant création de job/version/original ; code `office_limit_exceeded` effectivement capturé sur la deuxième requête | 9,921 s pour cette requête distincte. Taille refusée, aucune ingestion/indexation 1M qualifiée. |

Le job 100k `63bbba77-08b2-435d-ad67-30ccedf1d694`, version
`8b49daf4-6bd0-4997-8087-6326020e1469`, publie la génération
`2685a461-a183-43ca-b536-460a1b7f2dd8` à 20:46:09,557 UTC.
Crash→resume→pause→resume→cancel→resume produit quatre essais sans nouvelle
version ni duplication. Les unités achevées peuvent être réutilisées ; une
feuille interrompue est rejouée entière. Il n’existe pas ici de checkpoint
par cellule. Le débit global est 33,965 fragments/s, interruptions comprises ;
le débit ponctuel observé d’environ 35,4/s et le cache disponible ne prouvent
pas une campagne purement froide d’embedding. L’attente distincte finale de
0,114 s observe READY et n’est jamais utilisée comme durée du pipeline.

Trois résultats QA rouges sont conservés séparément. Le premier oracle
attendait une liste brute de vecteurs au lieu de `dense` nommé (384/Cosine,
pas de sparse) : échec avant import. Son correctif QA est revu `f52759c7` et
la même stack continue, sans restore/up supplémentaires. Le second run atteint
la borne QA de 1 200 s alors que le même job100k indexe encore ; reçu rouge
`4906d890` et résumé `5cb0ecde` restent inchangés. D07 ne définit pas une
borne universelle d’indexation à 1 200 s ; cette observation ultérieure ne
transforme donc ni le rouge en PASS, ni la durée en qualification D07.

Le troisième run observe READY puis échoue parce que le runner attendait
un job en erreur pour 1M. Le code réel valide le paquet OOXML avant de
déplacer l’original et de l’enregistrer. La première réponse HTTP400 est
prouvée, mais son corps n’a pas été conservé : son code exact reste inconnu.
Diagnostic indépendant `83c988ef`, aucune reconstruction du corps historique.
Le gel suivant autorise une seule deuxième requête1M, sans réindexation100k.
Sa réponse de 161 octets est conservée avant assertion : code
`office_limit_exceeded`, message « Le document dépasse une limite d’ingestion
Office. », détails vides, request_id UUID. La fixture contient 2 500 002
éléments XML, au-delà du quota inchangé de 2 000 000 ; aucune limite n’est
augmentée pour obtenir un résultat vert. Refus `f75263cc`, capture `e02363ab`.

Oracles finaux réellement passés (`c709247a`, 135,546 s d’enveloppe ; résumé
`8a293c2d`, 133,617 s) : **58 014 points actifs** exactement égaux aux UUID
SQL, vecteurs `dense` finis en dimension384 et payloads sources épinglés ;
14 anciens vecteurs/payloads inchangés. Les six originaux stockés sont
hachés depuis leurs chemins DB, les trois nouveaux correspondent aux
fixtures ; le refus1M ne crée aucun septième original. Avant/après refus,
31 comptes de tables, six versions/jobs/générations, historiques de deux
requêtes et 14 citations restent identiques, uploads vides. Les plages
A1 et XFD1 sont réellement contrôlées sans matérialiser le rectangle vide.
Le nombre initial attendu de sept originaux était une hypothèse QA erronée,
corrigée par le contrat de refus avant enregistrement.

Les trois reprises autorisées gardent leurs gels, revues et contrôles ROOT :
`ad23f045` pour le vecteur nommé, `fc122160` pour l’observation distincte
900 s du même job, `6a802b39` pour la seconde réponse quota et les oracles.
La surveillance propre à chaque étape est stoppée sans erreur : 45 439
échantillons au run avec timeout, 292 à l’observation suivante, 3 848 aux
oracles finaux. Il existe un intervalle entre ces surveillances ; aucune
couverture continue de tout le pipeline n’est revendiquée.

Fermeture continue 12–15 réellement effectuée, sans nouveau GO de routine :
down exit0 en 7,675 s (`b529c1a2`), inventaire `f71e`, comparaison stricte
`2a1f`, finish `82036`, puis handle possédé17629 réellement récolté à 0
(chunk `32efcf`, reçu `69657426`). Les 196 identités PID/naissance observées
sont absentes lors du contrôle frais, sans considérer un zombie comme absent.
La capture hôte arrêtée `host-stopped-01.json` (`2d6945e8`, 19,479 s)
confirme 31 tables, intégrité ok, zéro erreur FK, WAL vide, six versions
et générations, deux requêtes terminées/14 citations et six originaux.
Aucune lecture Qdrant live après down : ses valeurs sont celles conservées
avant arrêt. Les 65 131 fichiers et 1 188 liens du programme installé
sont strictement inchangés. Terminal `native-terminal-01.json` (`bf5910b8`),
382 empreintes gelées avec protections DoD/Oct2/sources/fixtures/backups ;
revue terminale indépendante acquise : `final-review/c10-final-native-closure-independent-review.json` (`20e35df4`), 38 pièces nouvelles confrontées et 196 absences fraîches indépendantes. Les quatre captures où exe est un répertoire restent bornées à ascendance/PID/naissance ; aucun exécutable fictif n’est déduit.

Ressources hôte, 573 observations pendant le broker possédé : CPU maximum
68,4 %, RAM disponible minimum50 028,27 MiB, SD minimum13,937 GiB,
racine minimum3,055 GiB. Ces valeurs incluent les autres tâches du poste.
RSS maximum échantillonné : API1 148,96 MiB, worker100k1 251,28 MiB,
Qdrant513,79 MiB, sans somme des pages partagées ni pic noyau certifié.
Les intervalles entre moniteurs par processus sont explicitement conservés :
337,834 s,251,900 s et536,376 s ; le suivi des ressources hôte est distinct.
Observation réseau :134 lignes de sockets, aucune hors boucle locale dans
l’espace QA ; DNS substitué explicitement par SERVFAIL, pas une résolution
DNS réelle. La capture SQL finale s’effectue sur l’hôte après fermeture.

Portée locale DEV CPU/Linux aarch64, mémoire physique 62 800,5 MiB.
Les preuves ci-dessus démontrent publication, reprise et refus borné,
sans qualifier Windows, Linux x86-64, un CPU physique de 16 Go, les questions
de performance D07 ou le corpus métier/final. Les rouges QA restent ouverts
comme résultats historiques explicables, pas comme une réussite globale.


Après fermeture réelle, seul le cache Node du TMPDIR QA est retiré :
un fichier dérivé, 101 884 octets logiques et 102 400 octets alloués au
fichier, puis ses deux répertoires vides. Contrôles de chemin/propriétaire,
fichier ordinaire sans lien et 196 absences fraîches ; les 382 empreintes
restent exactes avant/après, terminal et programme inchangés.
Compagnon distinct `node-compile-cache-cleanup-01.json` (`a28cf6eb`),
revue ciblée `final-review/c10-derived-cache-cleanup-companion-independent-review.json`
(`e1d2f540`) : cible absente, terminal et avis C10 inchangés.
Aucune variation globale d’espace libre SD n’est attribuée à ce seul retrait.
DB, WAL, backups, originaux, extractions, logs et preuves restent conservés.
