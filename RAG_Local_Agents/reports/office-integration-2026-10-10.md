# Intégration DOCX/XLSX — preuves locales du 10 octobre 2026

**Rôle :** rapport de preuve de l'intégration R28 · **Propriétaire :** intégration et validation · **Statut :** Vivant, contrôles locaux acquis, limites de qualification ouvertes · **Référence :** base `64e191f5d93e7c8e702a3a8b93713a7aac30e458`, sources publiées `57f7f0a6f2feee80adfd35b65bf4d81f6319e74c` et empreintes des sources réellement exécutées · Correctif publié et kit CPU natif vérifié : `22fd828` · Livraison propre CPU `52abb94b`, fermeture récupérée et retrait du transport revus indépendamment · Sources publiées `f14d87a`, livraison et froid C07 partiel réels, entretien terminé le 11 octobre · **Mis à jour :** 2026-10-11 17:14 (UTC) · **Source de vérité :** reçus natifs cités ci-dessous ; actions dans [PLAN.md](../PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation)

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

## R28-RAG-01 — résolution partagée des références

**État au 2026-10-10 23:00 UTC :** correctif local sur base `18dc8f8`, contrat
`9885a5e6`, gel03 `3b44fbf8`. Le contre-exemple de langue est corrigé et vérifié ;
les neuf cas isolés ont été repris sur le gel actuel et les neuf contrôles HTTP
natifs ont réussi sans LLM. Recette fermée, revue indépendante favorable et source publiée `1af9c0f`
à 22:58 UTC, distant confirmé. Le programme installé `22fd828` ne contient pas ce correctif ;
il est conservé inchangé. Les diagnostics précédents restent historiques.

Le scénario initial, question ordinaire contenant « doit-il » et DA-P01,
créait une obligation DOIT-IL absente et faussait la couverture. Les sources
`services/api/retrieval.py`, `context.py`, `query.py`, `office_search.py`,
`main.py` et `comparison.py` partagent maintenant `ReferenceResolution` :

- les candidats lexicaux conservent leur priorité exacte ; un composé
  alphabétique ambigu ne devient pas automatiquement une obligation ;
- les familles structurées déjà prises en charge restent obligatoires ; un
  focus explicite normalisé non vide nomme une obligation, même alphabétique
  ou inconnue, après validation du périmètre ;
- les occurrences sont reliées à un bloc autorisé, version, génération,
  révision, empreinte et offsets du texte original. Deux fragments assemblés
  ne peuvent fabriquer une occurrence ;
- le matching NFKC, casse et tirets conserve les coordonnées originales.
  Le fallback scoped parcourt par buffers de 128, préteste le texte avant sa
  reconstruction. Chaque référence focalisée est plafonnée par
  `retrieval.lexical_top_k` (24 dans les profils livrés) ; un identifiant absent
  peut demander tout le parcours du périmètre, sans coût constant prétendu ;
- les quatre voies Query/Search/évaluation/comparaison partagent cette
  résolution. Search n’hérite pas d’un référent implicite ; un focus hors
  périmètre est refusé avant création de question. Aucun schéma DB, index,
  réextraction, modèle, prompt ou paramètre de génération n’est modifié.

La décision [W056](../DECISIONS.md#w056-références-candidates-et-obligations-de-couverture-distinctes)
relie le choix aux références officielles S24/S25 : Python3.12, Unicode UAX15
et SQLiteFTS5, confrontés aux versions installées. Ces sources expliquent les
mécanismes ; elles ne définissent aucune grammaire métier universelle et ne
prouvent pas une supériorité SOTA. Le faux refus génératif français observé
précédemment avait déjà une couverture de 1,0 et reste ouvert.

Preuves privées sous `.runtime/qa/r28-implementation/` :

| Frontière | Résultat réellement acquis | Preuve et limite |
|---|---|---|
| API/contextes et régressions, gel02 historique | Union 767 PASS + 1 SKIP Windows/768, dont TLS 4 PASS | F `source-diagnosis-20261010/implementation-01/completion-01.json`, `11601dc0` ; impact05 et reprise06 conservés séparément |
| Typage configuré, gel02 historique | Linux 109 fichiers PASS 14,316 s ; Win32 statique 109 PASS 156,857 s | Même completion ; pas de qualification Windows native |
| Neuf cas × quatre voies, gel02 historique | 36 évaluations PASS 27,384 s | X `rag-reference-validation-20261010/black-box-terminal-01.json`, `51215a70` ; SQLite/FTS/ASGI réels, extraction/embedding/vectoriel/tokenizer/flux de génération substitués explicitement |
| Deux procédures Linux présumées rouges |2PASS15,71 s pytest/16,932 s enveloppe | ROOT `root/rag-doc-procedure-regression-01/execution.json`, log `31bfb378` ; programmes et installateurs simulés, aucune installation native |
| Revue préparatoire et périmètre | Sources/wrappers sans défaut matériel relevé,30 fichiers de tests proportionnés | R `14b53254`/`cb2897f6` ; antérieur au contre-exemple supplémentaire de langue |

La première suite générale reste rouge/incomplète : borne QA de 1200 s, exit−9
à 1205,374 s, quatre F dans le journal, aucun JUnit ni nombre de tests réussis
reconstitué. Deux fixtures réellement reproduites sont corrigées : signature
du double lexical et provenance incomplète du témoin de prompt. Toutes les
assertions et l’empreinte historique du prompt sont conservées. Les deux
positions restantes du journal étaient seulement une orientation ; leurs
reprises fraîches réussissent sans correction produit ni cause inventée.

Le contrôle supplémentaire ROOT porte sur « What are the performances? »,
focus LE-LE-LE et texte français de température : la note ajoutée change la
langue détectée et produit un état de couverture inadapté. La correction
limitée utilise la question originale pour la comparaison de langue, comme
pour les termes contextuels. Le témoin avant correction donne 1FAIL/2PASS ;
la reprise complète du module contexte et de l’empreinte du prompt donne
23PASS en 3,033s. Les trois variantes couvrent langues différentes sans terme
commun, même langue sans terme commun et terme commun réellement présent.
Gel03 `3b44fbf8`, seul delta produit `context.py` (`1987577e`) ; les treize
autres empreintes du gel02 sont inchangées. Les nouveaux contrôles sont des
preuves distinctes, sans attribuer la suite historique au nouveau gel.
Le contrôle actuel du delta est `language-delta-completion-01.json`,
`d143f3fd` : 21 empreintes de preuves et 15 sources, typage configuré de 109
fichiers Linux en 155,169 s et Win32 statique en 157,730 s, lint/diff réussis.
La revue indépendante du delta et des preuves isolées est `4e18fdc6`.

La reprise B02, `black-box-terminal-02.json` (`e7c6ce18`), donne 36 évaluations
réussies sur neuf cas et quatre voies, en 20,401 s ; les doubles restent ceux
annoncés au tableau. Le manifeste actuel `source-manifest-02.json` (`74fd4172`)
contient 69 sources : six modules modifiés, 61 supports et deux helpers QA.
Les propriétaires sont réellement récoltés et les neuf jetons QA retirés,
sans lire leurs valeurs. Cette durée n’est pas un benchmark d’amélioration.

Le terminal `native-terminal-01.json` (`63be302f`) lie 241 empreintes à ce même
manifeste, au binding réel de l’API (`969c2819`) et à la recette de 14 étapes
(`7274103a`). Les neuf oracles HTTP réels sont réussis : focus exact, « doit-il »
sans obligation parasite, code alphabétique présent, focus pleine largeur,
code proche refusé, plage XLSX sans preuve extérieure, deux refus de focus
hors périmètre et comparaison équilibrée. Aucun appel LLM, import, réindexation
ou action de job ; la seule question HTTP est un refus 409 avant persistance.
Une question positive et la qualité de réponse ne sont donc pas qualifiées.

Les propriétaires 85204 et 11185 sont réellement récoltés, exit 0. Les 61
lifetimes capturées sont absentes lors du contrôle hôte frais ; un champ
exécutable capturé comme répertoire ne prouve que l’ascendance/PID/naissance,
pas l’identité d’un binaire. Après arrêt, les 31 tables sont identiques,
avec trois versions, deux questions DONE et 14 citations. Les 14 points denses
ont été contrôlés inchangés avant l’arrêt de Qdrant ; aucune connexion à Qdrant
arrêté n’est prétendue. Le programme installé reste strictement identique.

Ressources : 80 échantillons de l’hôte, CPU maximal observé 36,7 %, RAM disponible
minimale 50 482,73 Mio, carte SD libre minimale 12,412 Gio, intervalle maximal
5,627 s. Ces mesures portent sur l’hôte de 62 800,5 Mio physiques ; elles ne
qualifient ni un CPU/16 Gio, ni Windows, ni Linux x86-64, ni le corpus final.
Le réseau est un namespace isolé avec loopback et double DNS SERVFAIL déclaré,
sans qualification réseau générale.


La revue native indépendante `reference-resolution-native-terminal-independent-review-01.json`
(`57883f9e`) contrôle 90 nouvelles preuves, les 69 sources, les 67 services
sélectionnés dans le manifeste runtime, les neuf réponses et leurs occurrences,
les 31 tables, les 14 points Qdrant et l’inventaire du programme installé
(65 131 fichiers, 1 188 liens). Verdict : GO natif local, sans LLM ni qualification
globale. Les protocoles et sources inchangés ne sont pas réaudités.

Le nettoyage des neuf basetemps/cache privés F est réellement terminé en
16,464 s, reçu `temporary-disposition-cleanup-01.json` (`c2ab683e`), clôture
acteur `76bb6988`. Racines/inodes/UID et absence de producteurs recontrôlés,
suppression par descripteurs parents sans suivre les liens. Les neuf racines
sont absentes et 17 empreintes de preuves, l’archive d’échecs de 8 273 920 octets
et le gel03 restent identiques. Gain libre SD observé 1 532 559 360 octets,
soit environ 1,427 Gio ; ce relevé de filesystem n’attribue pas toutes les
écritures de l’hôte. Aucun modèle, jeu de données ou original retiré.


QA documentaire ROOT : 62 tests PASS/5,95 s pytest (7,020 s enveloppe),
`root/rag-reference-documentation-01/execution.json` (`60dba2d9`), propriétaire
88080 réellement récolté exit 0. Brief déterministe, liens/métadonnées, schémas
SVG, pack et diff vérifiés (`cli-completion.json`, `917a0508`) ; le pack conserve
12 avertissements de fichiers tiers mal rangés dans `.agents/skills/`, sans
les masquer ni les assimiler à une qualification produit. Deux basetemps
ROOT supplémentaires, correspondant aux seuls tests documentaires 2 + 62 PASS,
sont retirés sans suivre les liens ; 24 preuves conservées (`2075fd98`).
Aucun fichier de source ou preuve native n’est retiré.


Clôture du lot local : revue finale de l’index exact de 24 fichiers `95ee9445`
(source15 + documentation9), nettoyage F contre-validé `bea63c95`. Publication
normale `1af9c0fd9590e4968073405c3d3f945a7cc9ad4d` réellement récoltée,
identité auteur/committer conforme, 15 blobs de source identiques au gel03 et
`origin/main` confirmé ; reçu ROOT `0643357d`, contrelecture indépendante
postpublication `65fe0d24`. Aucun corpus, runtime, secret,
DoD ni modification étrangère du journal du 2 octobre dans ce commit.
Le reliquat C05 du chat après reload est seulement préparé en lecture seule
(`f67e7967`) ; il requiert une liste de métadonnées et une restauration des tours dans le chat
avant une nouvelle recette.

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


## R28-C05-01 — restauration des questions enregistrées

**Portée :** base publiée `16690eb` et sources locales C05 ; backend gel `19eb4f38`, web final `edf34b53`, contrat additif v3. Linux aarch64, CPU, hôte physique 62 800,5 MiB. Deux réponses synthétiques DEV existantes ; aucun corpus utilisateur, nouvelle question, inférence, import, réindexation ou installation. Ce complément ne requalifie pas les anciennes réponses.

Le diagnostic `f67e7967` a confirmé une limite réelle : le panneau ne conservait que les tours de la session React. L’implémentation ajoute deux GET authentifiés et réutilise les tables et le SSE existants. La sélection restaure un seul tour et ses citations après reload ; elle garde le périmètre actif, remet à zéro les pointeurs locaux de continuation et affiche le mode ancien comme inconnu. Contrat précis dans l’[API](../../docs/interfaces/API.md#45-recherche-questions-et-citations), choix [W057](../DECISIONS.md#w057-consultation-des-anciens-tours-par-lecture-des-preuves-persistées).

| Contrôle effectué | Résultat et preuve | Portée |
|---|---|---|
| Backend | **71 PASS**, 54,44 s pytest ; Ruff et typage configuré Linux/Win32, **109 fichiers** par cible ; terminal `1361b0ab`, revue non-auteur `8976f965` | Historique/auth/pagination/scopes/SSE et consommateurs existants ; Win32 est statique, pas Windows natif |
| Frontend | **480 PASS** sur gel initial, puis **45 affectés PASS** après correction d’une branche résiduelle de replay ; **18 gardes CSS PASS** après `display:block`, lint/types conformes | Contrôles recouvrants, pas additionnés. Hooks/transport doubles explicités ; courses discriminées rouge/vert et gardes existantes conservées |
| Export final | **243 fichiers**, build réellement récolté à 0 en **24,064 s**, provenance `fcd78663`, inventaire `c269bb5f`, terminal web `c282bb5d` | Source locale modifiée, base `16690eb` ; aucun nouveau kit propre fabriqué |
| Copie isolée arrêtée | Préparation `6626be39`, revue `4c89de4f` : backup SQLite et rebasage des seuls chemins connus, 31 tables normalisées exactes ; originaux/extractions identiques | Copie QA Qdrant sur source arrêtée/verrouillée, pas qualification de la sauvegarde produit |
| Première recette navigateur | **FAILED**, 244,138 s ; QA cherchait le libellé Office « Retour » dans le lecteur PDF qui utilise « Revenir ». Terminal `8903bc16` conserve erreur, captures et clôture | Aucun bug produit déduit de ce sélecteur, aucune promotion en PASS. Typographie de deux mentions collées observée et corrigée séparément |
| Recette actuelle QA02 | **1 PASS**, zéro skip/retry/flaky/unexpected ; **12,939 s** enveloppe navigateur, **11,243 s** Playwright, **9,171 s** test ; terminal `cc5384a8` | API réelle/cookies réels, aucun mock de réponse. Setup de session isolée autorisé ; lectures du parcours sans mutation documentaire |
| Conservation et arrêt | Avant/après : **2 DONE, 14 citations, 167 événements, 7 jobs, 16 vecteurs actifs** exacts. Après down/finish et récolte du propriétaire : **31 tables** intègres/FK conformes et fichiers sources inchangés | Les 42 chunks SQL incluent les archives ; l’oracle Qdrant compare les seules générations actives, dimension 384, distance Cosine et valeurs finies |

Les deux réponses sont choisies dans « Anciennes questions », relues puis rechargées. La recette clique les **quatre paires `(query_id, source_id)` réellement inscrites dans leur texte**, distinctes des 13 citations Office enregistrées historiquement :

| Tour | Citation littérale | Passage réellement ouvert |
|---|---|---|
| `ffa89ebe-d207-41db-a8a6-e51c2b721f49` | S001 | XLSX, feuille Mesures, **A2 = CCU-21**, version/révision anciennes |
| même tour | S004 | XLSX, **B2 = 72 V**, même version/révision anciennes |
| `a90947b4-88d3-4c10-a09a-3fd6a129349f` | S001 | PDF, page 1, bloc source de la tension nominale |
| même tour | S002 | DOCX, tableau des conditions applicables, **Tension = 72 V** |

Après chaque clic, le retour au passage précédent garde le tour et le périmètre actif « Toute la bibliothèque ». Les sources gardent l’identité du registre ancien ; aucune substitution par les versions plus récentes. Les **six PNG Office** à 1366×768 et 1920×1080 sont les captures originales réellement vues par ROOT : cellule/adresse et tableau correctement surlignés, mentions historiques séparées, aucun débordement horizontal. La capture PDF de l’échec initial n’est pas comptée comme une capture de la recette réussie. Revue indépendante finale du natif, des sources et des six images acquise `520fe2a4`. La sélection et le rechargement de la question sont vérifiés par les assertions DOM réelles ; son texte entier n’est pas toujours visible dans les captures. Le retour PDF de QA02 est vérifié dans le DOM, sans PNG PDF de cette recette.

Lancement actuel : **36,008 s** ; contrôles natifs avant **1,522 s**, après **1,181 s** ; down **4,088 s** : les six commandes ont un code de sortie 0. La septième étape répond `SESSION_FINISHED`, sans code numérique. Propriétaire ROOT, handle 43178, réellement récolté à 0 (`4ce9a6`) ; inspection hôte arrêtée, handle 70686, réellement récoltée à 0 (`3f24f9`). Le wrapper ne signale aucun autre processus : il attend seulement ses zombies capturés dont naissance et PPID correspondent exactement, puis prouve l’absence fraîche de 37 identités de processus, propriétaire compris. Les 38 empreintes du terminal conservent résultats, scripts, sources, logs, provenance, échec initial et six images.

**Ressources :** 25 observations hôte durant QA02, CPU maximum 42,1 %, RAM disponible minimum 50 676,44 MiB, SD minimum 13,538 GiB, système minimum 3,012 GiB. Ce poste physique de 62 800,5 MiB ne qualifie pas CPU physique de 16 Go maximum. Les deux petits fichiers privés `storageState` expirés sont retirés après fermeture, avec métadonnées et empreintes conservées, sans lecture publiée de cookies. Le nettoyage backend de trois dérivés retire 144 748 544 octets alloués ; gain de volume observé 144 658 432 octets, borné par l’activité concurrente, reçu `e24d3871`. Sources/gels/logs/XML et refus de garde initiaux restent exacts.

**Réserves :** autre corpus/qualité des réponses, variantes C05 non exercées, Windows natif, Linux x86-64, CPU physique de 16 Go maximum et nouveau kit des sources actuelles restent distincts. Le faux refus génératif antérieur reste ouvert. Aucun critère DoD modifié ni PASS global ; les sources officielles établissent des mécanismes, pas une supériorité SOTA comparative.

**Documentation et préparation de publication (11 octobre UTC) :** revue indépendante des 12 documents gelés acquise `d1f7f629`. Cinq commandes réellement terminées à 0 : brief synchronisé, `check_docs` 7/7, SVG conformes, **62 tests PASS** sans erreur/échec/skip (6,025 s pytest ; 7,283 s enveloppe), `verify_pack` 11/11. Les 12 avertissements préexistants de classement des fichiers tiers de skills sont conservés ; ils ne constituent pas un nouvel écart C05. Les 14 identités QA capturées sont fraîchement absentes. Le seul `pytest-tmp` a été retiré après récolte, avec 19 preuves conservées : 3 911 680 octets alloués retirés, gain SD observé 3 633 152 octets borné, reçu `ca5f7df4`.

La garde Git brute signalait 65 CR de fin de ligne du panneau TSX historiquement mixte, sans autre blanc fautif. Un attribut `whitespace` ciblé reconnaît ces fins CRLF en conservant les gardes des espaces terminaux et avant tabulation ; aucun octet des 13 sources produit n’est modifié. `git diff --check` brut passe ensuite à 0 ; premier refus conservé et reçu `b47462b0`. L’addendum documentaire fait l’objet des contrôles de structure et d’un contrôle indépendant du gel indexé, sans rejouer les suites produit ou les 62 tests inchangés.


## Livraison du kit CPU 52abb94b — 11 octobre 2026

**Périmètre :** livraison `0.1.0+52abb94b2505-linux-aarch64-none-2b4b`,
source `52abb94b250500a9584a9cce5e84e348e5fc2d2a`, incluant RAG-01 et C05
publiés. Linux aarch64 natif, variante GPU `none` ; poste physique 62 800,5 MiB.
Le futur commit de suivi ne change pas cette provenance. L’export local
sur `16690eb` décrit plus haut demeure une preuve historique distincte.

| Contrôle réel | Résultat | Preuve sous `.runtime/qa/r28-implementation/` |
|---|---|---|
| Export propre |243 fichiers/6 616 966 octets ; build 20,676 s/retour 0 | `c05-next-kit/web-build-01/closed-export-receipt-01.json`,464aae3d ; provenance 9071edb7, revue815d |
| Fabrication/archive |5 commandes à 0 ; dry 144,535/build 118,733/verify 31,158/archive 611,571/readback 128,021 s | `c05-next-kit/factory-01/distribution-office-52abb94b2505-build-archive-01/progress.json`,5c91925a ; owner fermé 4e7cd528 |
| Transport/extraction | readback 64,742 s et extraction 124,123 s, retours 0 ; cumul 7 commandes : 1 222,883 s, pas temps mural | `c05-next-kit/factory-01/distribution-office-52abb94b2505-extract-01/progress.json`,5f154734 ; owner fermé 3f027cda |
| Archive |11 185 684 480 octets ; deux lectures complètes réelles conservées | SHA-256 `4a066afb7ffa0aa669a13ab9ab1705e1c6eca65ad3bbb64a1cbbc745fb35f094` ; revue 57e9a36b |
| Installation/restore/up | retours 0,136,742/27,260/10,805 s ; programme 52, profil322ae38c et manifeste a9823cd7 | `c05-next-kit/installation-preparation-01/runtime52/` ; UUID0247630fadad4a6a89862eb5fd4b4fb2, sources live0f4390f5 |
| Recherche réelle |1 POST search,1 embedding CPU dense E5 ONNX complet ; 72 V cité sur **B2** avec parent/hash/offsets exacts | `runtime52` ci-dessus : recherche 13–18 admise 8620972d ; aucun POST queries/LLM/import/reindex |
| Lecteurs/historique | navigateur : 1 PASS, 0 skip/retry/flaky ; 122 GET, 4 paires littérales ; 6 PNG Office 1366×768/1920×1080 réellement vus | mêmes preuves `runtime52`, pixels/privacy76b4875d ; ROOT 957b77d3, revue 5358f6c5 |
| Incident initial |18 étapes à 0 puis lanceur 68366 réellement récolté à 1 ; SIGTERM 15 d’origine UNKNOWN | `runtime52/owner-interruption-01.json`,18c52183 ; cleanup rouge d7459615 conservé, aucune clôture nominale inventée |
| Arrêt récupéré | down nominal produit 0, 8,054 s, même UUID/profil ; services connus arrêtés | `runtime52/recovery-01/down.json`, deb50e6a ; actual-start/wait et nominal-stop-handoff e4a96ed5 |
| Contrôles froids |31 tables exactes, intégrité/FK ; 3 versions, 2 DONE/14 citations ; 14 vecteurs égaux à la référence avant down | `runtime52/recovery-01/host-final.json`, c4760d6b ; aucune lecture live Qdrant après arrêt |
| Programme/conservation |65 131 fichiers/1 188 liens strictement inchangés ; originaux/extractions/historiques exacts | `runtime52/recovery-01/strict-program-compare.json` et captures avant/après |
| Clôture indépendante | récupération sans appel supplémentaire API/search/LLM ; 159 identités hôte, 161 terminal et 162 revue, périmètres distincts | `runtime52/recovery-01/terminal-handoff-01.json`,43f15f2b ; revue 4ecb8637 |
| Retrait transport 52 | seule copie extraite inutile absente ; 26,343 s/outil 6522 réellement 0 ; archive/programme/DATA protégés | `c05-next-kit/transport52-recovery-retirement-01/root-owner-closed-01.json`, b9051d4f ; after 5d7423d5, revue a48e1664 |

Les quatre citations littérales sont celles du tableau C05 ci-dessus : XLSX
A2/CCU-21 et B2/72 V, PDF page 1 et tableau DOCX « Tension = 72 V », avec version/révision anciennes.
Le retour et le reload sont contrôlés dans le DOM réel. Six captures Office
montrent les cellules/adresses/table aux deux tailles ; le PDF est vérifié
par le DOM et le journal de navigation, pas par une capture PDF réussie.
Les 2 DONE/14 citations proviennent du backup produit `22fd`, avec 14 points Qdrant
actifs : ce dataset diffère du clone C05 à 16 points. Cette recette ne mesure
pas la qualité d’une nouvelle réponse et ne lève pas le faux refus 4B historique.

La clôture récupérée garde original_owner_exit = 1 et nominal_broker_completion
faux. Le lanceur original n’a ni ended, ni finish, ni owner-closed ; l’arrêt
coopératif du superviseur utilise le mécanisme nominal du produit. Les erreurs
QA de sélecteur/texte source ont été corrigées avant exécution ; la publication
récupérée corrige la seule clé elapsed_seconds vers elapsed_s après un refus
conservé. La revue de retrait garde son AssertionError sur un champ supposé,
puis contrôle status ABSENT_FRESH/pid_exists False réels. Aucun garde affaibli,
rejeu fonctionnel ou signal vers un processus étranger pour obtenir le vert.

**Nettoyage et ressources :** les duplicatas transport 22/usine 52 et ancienne
installation QA57 ont déjà leurs clôtures distinctes. Le cache `.next` retiré
libère 194 068 480 octets observés sur racine, zéro sur SD ; export propre conservé.
Transport 52 contient 35 626 fichiers/1 184 liens internes/4 585 sous-répertoires,
11 226 185 728 octets alloués. Son retrait par `rmtree` à parentfd vérifié
observe 11 225 931 776 octets libres supplémentaires, sans attribution exclusive
sur un poste actif. SD avant 3 263 823 872/après 14 489 755 648 octets ;
racine après 3 379 273 728 octets. RAM disponible aux deux mesures : 51 587,5 et 51 807,9 MiB,
CPU 31,4/22,2 % : observations ponctuelles, pas pics certifiés ni surveillance
continue de toute la récupération. Seul storageState QA expiré 554 octets est
retiré après absence des producteurs, preuve a4816a7e. Archives 52/57/22,
installation 52/22, données, sauvegardes, 28 sources, DoD, Oct2 et preuves gardées.
Dix identités étrangères/28 champs restent UNKNOWN bornés, sans absence
globale revendiquée ni signal/adoption de ces processus.

**Références et portée :** standards ECMA-376/SpreadsheetML, code exact des
bibliothèques installées et sources R28-S01→09/KIT11/R28-S27 dans
[SOURCES](../SOURCES.md) étayent les mécanismes. Formule/cache/type/localisateur
restent distincts ; aucune formule exécutée. Les benchmarks d’étude comparent
les candidats sur leur micro-corpus, sans supériorité SOTA générale déduite.
Linux reste une cible générale sous prérequis documentés, avec recette réelle
limitée à aarch64 ici. Windows natif/Linux x86-64/CPU physique ≤ 16 Go/corpus
métier-final, NF09 strict et réserve générative restent ouverts. I-08 PARTIEL,
89 critères DoD inchangés ; aucune qualification 2B/4B depuis le seul packaging.

**Suivi documentaire du 11 octobre, 02:11 UTC :** brief conforme, liens 7/7,
pack 11/11 et diff brut à 0 ; sorties réelles dans
`c05-next-kit/documentation-closure-01/actual-checks-01.json` (`e1c4b256`).
Les 12 avertissements tiers historiques demeurent distincts. Aucun outil
ou SVG modifié : les 62 tests documentaires précédents sont conservés comme
preuve historique, sans nouveau total inventé ni rejeu produit.

## C09 — trois refus natifs de conteneurs Office — 11 octobre 2026

**Portée :** programme CPU installé `52abb94b`, sources produit inchangées,
suivi repris sur `e6328dce`. Instance neuve et données isolées sur SD,
namespace réseau limité au loopback ; aucun document valide, génération,
recherche ou corpus privé. Python 3.12.14, SQLite 3.53.1, Linux aarch64,
UID 1000 et capacités effectives nulles. L'hôte physique de
65 851 092 992 octets ne qualifie pas la limite de 16 Go.

Trois fichiers synthétiques sont réellement soumis à l'import authentifié :
DOCX avec CRC erroné, XLSX avec membre `xl/workbook.xml` dupliqué, DOCX avec
DTD en UTF-16. Les trois réponses sont HTTP 400, avec codes et messages
attendus ; durées respectives des cas complets 0,362 / 0,023 / 0,024 s.
Les seules requêtes HTTP durent 0,199 / 0,017 / 0,017 s. Après chaque
refus et à froid, les 31 tables et le schéma restent égaux à la référence,
l'intégrité et les FK sont conformes. Aucun document, original, version ou
job persistant n'est créé. Le temporaire d'upload est retiré ; cela ne
signifie pas qu'aucune allocation temporaire n'a eu lieu.

Le premier contrôle de liaison a échoué avant tout import : un cache de
compilation Node est observé dans le temporaire du broker durant `doctor`.
Son horodatage et l'activation du cache par les wrappers Corepack/pnpm
étayent cette attribution ; le PID individuel du writer n'est pas acquis.
Le fichier
de 101 892 octets et ses deux dossiers sont épinglés séparément ; l'oracle
documentaire reste strictement vide. Le gel QA distinct vérifie ce cache
exact avant/après chaque refus, sans modifier l'environnement ni relancer
la stack. Le premier retour 1 reste conservé ; les commandes suivantes
ont été réellement récoltées à 0, puis `SESSION_FINISHED` et le wait du
propriétaire ROOT à 0 sont acquis. Le finaliseur froid a aussi un vrai
retour 0 et une absence fraîche.

Preuves sous `.runtime/qa/r28-implementation/c09-native-preparation-20261011/` :
`imports-summary-01.json` (`8a7aabc4`),
`actual-owner-harvest-01.json` (`2c65fd0f`), `host-final-01.json` (`18a819a1`)
et `external-terminal-01.json` (`bb2d03a9`). Revue indépendante finale
`.runtime/qa/r28-implementation/c05-history/review/c09-native-independent-final-review-04.json`
(`b7c78e41`) : 123 identités connues absentes, programme inchangé
(65 131 fichiers et 1 188 liens), données documentaires vides et cache exact.
Le contrôle des cinq littéraux secrets porte sur 102 fichiers avant down,
avec exclusions des fichiers de contrôle explicitement recensées ; il
ne vaut pas audit de tous les fichiers ultérieurement produits.

Après fermeture, le seul cache devenu inutile est retiré : fichier
101 892 octets puis ses deux dossiers vides, UID/inodes/modes/empreinte
recontrôlés. Opération ROOT `7379cb/0`, opérateur fraîchement absent,
TMP gardé vide ; preuves inchangées. Allocation retirée et gain libre
observé : 110 592 octets, ce dernier borné par l'activité du volume.
Reçus `node-cache-retirement-after-01.json` (`344d73aa`) et
`node-cache-retirement-external-terminal-01.json` (`446c664c`) dans le
même dossier C09. L'observation antérieure « cache conservé inchangé »
reste une preuve historique exacte, distincte de ce retrait ultérieur.
Revue indépendante finale du retrait :
`.runtime/qa/r28-implementation/c05-history/review/c09-node-cache-retirement-independent-final-review-06.json`
(`7dba29f2`).

**Limites :** trois cas adverses acquis, sans qualification de toute C09 :
macros, bombes, traversal, lectures arbitraires et toutes les variantes
de quotas restent distincts. Aucun PASS d'une plateforme absente ni de
la DoD globale. Les contrats de ZIP/XML et du cache Node sont reliés dans
[SOURCES](../SOURCES.md), notamment R28-S30 ; ils ne remplacent pas ces essais.

## C02 — spill WAL non validé et récupération — 11 octobre 2026

**Portée :** même programme installé, `db.py` (`a2093fa2`) et migration004
(`9f9091f6`) identiques au repo. Fixture SQLite synthétique neuve sur SD :
10 000 blocs supplémentaires de 8 192 octets, 10 001 blocs au total,
base de 87 625 728 octets. Le petit marqueur original est un blob `%PDF`,
pas un PDF valide ni une preuve de rendu. Paramètres livrés conservés :
cache 32 Mio, `busy_timeout=5000`, spill naturel, sans abaissement artificiel.

Après un commit témoin et pendant la transaction de migration, le WAL
passe de 4 152 à 58 652 352 octets : 14 235 nouvelles frames, sans nouveau
marqueur de commit. Préfixe, salts et checksums sont vérifiés. Au point
d'interruption, schéma 3, transaction active, 10 001 lignes dans la table
de remplacement et ancienne table supprimée dans la transaction.
Le processus de migration est réellement arrêté par SIGKILL et récolté
à −9 ; lecteur et writer sont récoltés à 0.

La copie brute DB/WAL/SHM est conservée avant récupération. SQLite rejoue
à froid le seul commit validé et retrouve les 26 tables v3 exactes.
La migration réelle retrouve ensuite 31 tables, conserve les 25 tables
historiques comparées (hors changement de `schema_version`), avec les
normalisations PDF attendues, et laisse les cinq tables Office neuves vides.
Deux sauvegardes v3 logiques restaurables et égales sont acquises ; le
second `initialize` ne change pas la base et ne crée pas de troisième backup.

L'exécution native de 52,750 s acquiert ces oracles, puis échoue à la
composition du reçu final : le pilote QA suppose `_sqlite3.__file__`,
alors que ce module est intégré à l'interpréteur livré. Les retours 1 du
probe et du wrapper, la trace et l'absence de `completion.json` restent
conservés. Un finaliseur distinct vérifie les preuves et les empreintes,
sans connexion DB ni rejeu de fixture/migration/backup. Il lie le module
builtin à l'interpréteur réellement exécuté, SHA `2fdbcf7d`, et termine
à 0 en 0,578 s ; ROOT récolte le vrai handle 84639 et constate son absence.
Ce reçu ne transforme pas la tentative initiale en succès nominal.

Preuves sous `.runtime/qa/r28-implementation/c02-wal-spill-preparation-20261011/` :
`attempt-02/execution-terminal.json` (`3e6b2b00`),
`finalization-03/verification.json` (`73937418`) et
`finalization-03/actual-external-terminal-03.json` (`38b87d1a`).
Récolte externe sous `.runtime/qa/r28-implementation/` :
`root/c02-spill-20261011/attempt-02-external-harvest.json` (`536c4838`).
Les oracles DB/WAL sont dans `/media/safae/devsave1/r28-c02-wal-spill-20261011-01/` :
`uncommitted-spill-before-kill.json` (`6f90d7d7`),
`cold-base-and-wal-recovery.json` (`03a4a003`),
`migration-and-idempotence.json` (`01cfab54`) et
`ownership-cleanup.json` (`5675171d`). Revue préparatoire distincte
`.runtime/qa/r28-implementation/c05-history/review/c02-wal-spill-distinct-finalization-independent-preparation-review-04.json`
(`cf38e8b1`) ; avis fonctionnel indépendant final
`.runtime/qa/r28-implementation/c05-history/review/c02-wal-spill-independent-functional-final-review-05.json`
(`a4fe8b0e`) acquis après récolte et absence du finaliseur.

**Ressources et limites :** 11 mesures, pic RSS d'un processus observé
75 907 072 octets, CPU hôte maximum échantillonné 24,1 %, RAM disponible
minimum 54 397 534 208 octets ; allocation maximale de la cible
760 389 632 octets, SD libre minimum 13 700 554 752 octets. Le RSS mesuré
n'est pas une preuve de fonctionnement sur un hôte physique de 16 Go.
Cette variante étend la preuve locale C02 ; panne électrique, bases
arbitraires et SQLite des autres cibles restent non qualifiés.
Références officielles R28-S28/S29/S31 dans [SOURCES](../SOURCES.md).


## C07 — comparaison de trois documents et correctif d’identité — 11 octobre 2026

**Cible et portée :** programme CPU `52abb94b` inchangé, Linux aarch64,
compte1000, namespace réseau privé ; copie fraîche du backup `22fd828`.
Trois originaux DEV synthétiques, 14 points Qdrant, CPU4B Qwen/E5 réels.
L’hôte possède environ61,3 Gio de RAM physique ; ce cas ne qualifie ni
CPU16Go, ni Windows/x86-64, ni tout C07. Sources et contrôles natifs :
`r28-implementation/c07-comparison-preparation-20261011/native-02/`.

Une préparation initiale distinguait mal le SHA YAML du profil et son SHA
canonique API ; elle n’a pas été exécutée. Dans native02, l’étape8 QA
termine réellement à1 sur `KeyError: storage_dir`, avant up et génération.
Une récupération distincte conserve l’option absente et utilise le fallback
réel du superviseur ; seuls chemins et ports changent. Original rouge
`8056b9ae`, gel distinct `dab52381`, revue `944e8273` et admission ROOT
`0f522c63` conservés ; étapes1–7 inchangées, étape8 distincte puis9–15.

Une seule question comparative a réellement été exécutée
(`b1e09a2d-a52c-44fc-82a9-4ab20f2be94f`) : commande191,382 s,
trace API189,511 s, 267 événements dont1done et262deltas. Avant génération,
le contexte protégé couvre les trois documents, 2319 tokens de preuve
sur4864, avec fragments/littéraux72V et ancrages exacts. Réponse et
citations conservées : DONE `84a94fbd`, context `d96538bd`, SSE `5760bf00`.
L’unique nouvelle query ajoute8 citations enregistrées ; quatre sont
effectivement citées dans le texte : S001 PDF page1, S002 XLSX A2:C2
(littéral B2, offsets33–37), S003 tableau DOCX9 et S005 paragraphe du
**même** DOCX. C2 porte une formule sans cache ; aucun recalcul n’a eu lieu.

**Échec sémantique prouvé :** la réponse appelle ces quatre passages
« quatre documents » alors que leurs document_id n’en désignent que
trois ; elle ne respecte pas une phrase par document. Faits72V et
attributions sont corrects, ce qui ne valide pas le résultat entier.
Revue indépendante `b6a61bac` : FAIL cardinalité et format demandé.
Ni réponse, ni DONE, ni ancien reçu technique n’ont été réécrits.

**Diagnostic et correction RAG-02 :** la recherche assure la couverture
documentaire ; le rendu de ContextBuilder exposait une liste plate de
passages et des version_id opaques. Ce manque de représentation est
confirmé, sans prétendre expliquer seul le comportement du modèle.
Le mode comparison rend désormais des groupes par document_id réel,
avec leur liste de source_id et leurs extraits intacts ; document_count
est dérivé des groupes retenus. Le budget compte toute l’enveloppe et
chaque coupe reconstruit groupes et mapping. Le système, les quotas et
les octets de preuve des modes question/analysis restent inchangés.
Fichiers : `services/api/context.py`, `tests/unit/test_api_context.py`,
`test_api_queries.py`, `test_development_instruction_isolation.py`.
Gel `semantic-identity-implementation-01/frozen-final-01.json` (`13f44fb5`).
224 tests uniques affectés au vert :223 de la passe large puis8 isolation,
dont7 recouvrants ; six nouveaux cas, Ruff4fichiers et mypy ciblé conformes.
Doubles tokenizer/embedding/vecteurs/Ollama explicitement nommés. Préimages
et vrais rouges conservés ; revue indépendante source acquise `cff07393`.
**À ce gel source, l’effet sur une réponse réelle n’était pas mesuré.**
La recette distincte sur la source publiée est consignée ci-dessous.

**Recette navigateur, résultats distincts :** READERS_ONLY, zéro nouvelle
question/import/indexation/inférence. UI01 échoue avant tout clic sur
un attendu scope minimal au lieu du DTO complet persisté. UI02 utilise
l’égalité stricte des15champs et13valeurs par défaut puis échoue sur un
snapshot de deux boutons pendant le rejeu SSE. Le DOM final conservé
montre déjà S001/S002/S003/S005 : absence permanente non démontrée.
Diagnostic `ui02-citation-snapshot-diagnosis-01.md` (`80667f7c`) et attente
stricte préparée selon [R15S31](../SOURCES.md).
Deux captures d’échec sont gardées, zéro capture de succès lecteur.
Scan exact des14fichiers de sortie contre les secrets disponibles :
`privacy-two-failures-01.json` (`034bb8b8`), authstates600 exclus précisément,
aucune valeur exposée ; limite non exhaustive et ticket consommé inconnu.

**Arrêt réellement acquis :** down12/0, inventaire13/0, comparaison14/0,
finish15 réel puis propriétaire ROOT51336 récolté à0 (`e94997`).
65 131 fichiers/1 188 liens du programme inchangés. Finaliseur hôte distinct
à0 (`e230cc`) :31tables froides égales au post-query réel, trois originaux
exacts, 14points avant/après exacts. `host-final.json` (`1845113b`),
`root-external-cold-closure-02.json` (`c38f9e92`) :202 identités PID/naissance distinctes sur 206 enregistrements
contrôlés, fraîchement absentes, aucun succès sémantique ni navigateur reconstruit.
Revue terminale indépendante `f66635d5` acquise.
Une assertion externe QA avait comparé le wrapper de capture au mapping
SQL brut ; échec1 conservé avec diagnostic de formats, distinct des
oracles exacts du finaliseur. Après revue `56dec477` et GO ROOT `48e13f4e`,
retrait réellement acquis `3c7a43/0` :37 fichiers (2auth,3Node,32JS/map)
et19 dossiers cache vides supprimés, trois racines privées conservées
vides ; aucun rmtree. Reçu `temporary-retirement-after-02.json` (`832455b2`),
externe `e874388e` : opérateur2003858 fraîchement absent,202 producteurs
connus absents,42preuves/sources épinglées intactes. Durée0,059s ;
564431octets logiques/720896 alloués sélectionnés, variation libre du
volume observée+720896octets, sans attribution générale. DATA, programme,
originaux, deux captures d’échec et preuves conservés.
Revue finale indépendante du retrait `65f2227e` acquise.

## C07 — recette RAG-02 sur la source publiée — 11 octobre 2026

**Portée :** une comparaison DEV réelle sur Linux aarch64, UID 1000, modèle 4B sur CPU,
réseau privé et les trois originaux synthétiques PDF/DOCX/XLSX déjà utilisés.
Les fichiers du dépôt publié `821f0726` sont réellement exécutés ;
`context.py` SHA `c6db9fa1…`. L’installation `52abb94b` n’est pas modifiée
et conserve son ancien contexte ; cette recette ne livre pas un nouveau kit.
Hôte physique d’environ 61,3 Gio : aucune preuve Windows/x86-64/16 Go déduite.

Racine native : `.runtime/qa/r28-implementation/c07-comparison-preparation-20261011/rag02-native-01/`.
Racine lecteur : `.runtime/qa/r28-implementation/c07-browser-preparation-20261011/rag02-readers-01/`.
Revues indépendantes : `c05-history/review/` sous la même racine QA.

**Exécution et reprise QA :** l’étape 11 initiale termine réellement à 1
(`c99954`) avant tout POST : le runner indexait `['points']` sur une
référence Qdrant réellement représentée par une liste de 14 objets. Les
snapshots historiques et nouveaux sont identiques ; aucun défaut produit
n’est déduit de cette erreur QA. Original et rouge conservés. Runner distinct
`run-recovery-01/` : lecteur strict de cette liste, IDs uniques, trois
contre-oracles rejetés, seules sortie et lecture de référence adaptées.
Gel `ae313237`, revue préalable `1971871a`, admission réelle puis reprise
`4bebc3`/`cacdc9`, code 0, 228,115 s ; trace API 227,627 s. Aucun nouveau
restore/up et une seule nouvelle question exécutée.

**Faits observés :** query `59dbb726-f5da-4d4b-83dc-2f7991084e98`,
136 événements SSE dont un done, huit citations enregistrées et trois
littéralement présentes dans la réponse. Les huit sources retenues sont
les mêmes que dans l’ancien cas, regroupées en trois document_id réels ;
2523/4864 tokens de preuve, 2728 tokens de prompt et 140 tokens produits.
Qwen modèle 4B sur CPU réel, sans fallback ; formule C2 non évaluée et cache absent.
Réponse : une phrase pour chacun des trois documents puis concordance
sur72V. Revue sémantique indépendante `rag02-comparison3-independent-semantic-review-19.json`
SHA `28654c1e…` : PASS pour ce cas et son format demandé. L’ancien FAIL
`b6a61bac` demeure inchangé ; ni causalité universelle ni supériorité SOTA
comparative ne sont établies par une seule inférence.

| Citation littérale | Source exacte observée | Limite |
|---|---|---|
| S001 | PDF, page physique1/index0,72V | Page originale, aucune pseudo-page Office. |
| S002 | XLSX A2:C2, valeur littérale B2=72V, offsets33–37 | Citation de plage ; C2=`=LEN(A2)`, cache absent, pas de recalcul ni précision cellule inventée. |
| S003 | DOCX tableau `/document[1]/body[1]/tbl[9]`, lignes1–2/colonnes1–3,72V | Ancrage structurel, aucune pagination Word garantie. |

**Lecteurs réels :** DTO complet égal au scope SQL, rejeu SSE attendu
jusqu’au texte DONE et à l’ordre final des trois boutons. Un test Playwright
réel PASS, zéro retry,69 requêtes GET observées, aucun POST/import/indexation
ou nouveau LLM. Trois clics/citations avec retour au chat et scope courant
conservé. Six PNG originales à 1366×768 et 1920×1080 examinées par ROOT puis
indépendamment par R : page PDF peinte/surlignée, tableau Word 9, plage XLSX
A2:C2/B2=72/f en C2. À 1366, conclusion sous la ligne de flottaison ; son
texte complet est vérifié dans le DOM, sans prétendre qu’il est visible
sur la capture. Avis `rag02-readers-pixels-privacy-independent-review-21.json`,
SHA `9ecd7c72…`. Scan des 11 artefacts contre les secrets disponibles sans
fuite, état d’authentification 600 exclu précisément ; contrôle non exhaustif.
« Mode non enregistré » correspond au contrat historique `mode:null`,
non à un défaut lecteur (`history-mode-contract-observation-01.json`, `48356c8e`).

**Arrêt et conservation :** down 12 `b60a89/0`, inventaire 13 `6d92a9/0`,
comparaison 14 `2563f6/0`, finish 15 `e2c0ce/0`. Propriétaire/session15449
réellement récolté `60430e/0` ;126 identités PID/naissance distinctes sur 130
enregistrements acquis, fraîchement absentes. Capture SQLite en lecture
seule puis finaliseur distinct `d4ba34/0` :31 tables froides exactement
égales au post-query, anciennes lignes/citations conservées, trois originaux
et14 points Qdrant exacts. Programme52 :65 131 fichiers/1 188 liens inchangés.
`host-final-recovery-01.json` SHA `12ada0ab…`, récolte `2fdff9cb…`, externe
`root-external-cold-closure-01.json` SHA `5e5fd7b0…` ; revue indépendante
`rag02-comparison3-independent-native-closed-review-22.json` SHA `4ab58681…`.
Le finaliseur réellement terminé n’a pas de PID/naissance capturés : aucune
absence nominative reconstruite. L’étape 11 initiale reste à 1, sans transformer
les 15 étapes originales en PASS. Les corrections de lecture de métadonnées
QA sont distinguées des invariants produit.

**Ressources et artefacts dérivés :** seul cache mypy devenu inutile retiré
après vérification des producteurs et revue :18 fichiers,
122 745 056 octets logiques/122 769 408 alloués sélectionnés ; preuve externe
`mypy-cache-retirement-preparation-01/root-external-after-01.json` SHA `10ac7ed3…`,
revue `a9325d95…`. Six basetemps/191 liens restent conservés faute de ledger
complet ; 22 observations préexistantes UNKNOWN restent UNKNOWN. Les dix
préimages dérivées de reconstruction documentaire, devenues inutiles après
publication, sont retirées séparément ; diffs, gels et erreurs originaux
conservés (`redundant-reconstruction-retirement-01.json`). La récupération
des fins de ligne du gel04 vers05 est conservée, sans normalisation générale.
Relevé froid à 05:30 UTC :CPU 19 %, RAM disponible 51 473 Mio, SD 12,726 Gio
libres ; aucune attribution du delta global aux seuls retraits.

**Références et limites :** les choix applicables sont vérifiés dans les
sources officielles [R28-S03/S05/S06 et R28-S32](../SOURCES.md#r28-s32--relecture-des-contrats-office-et-attente-du-rejeu-historique), avec versions/limites
explicites. Documentation ≠ preuve d’exécution. Ce résultat ne ferme pas
la matrice C07 complète, le cas à quatre documents, les analyses métier,
les gros corpus/final, Windows, Linux x86-64, CPU physique≤16 Go ni NF09.
RAG-02 est validé localement ; I-07/I-08 et la DoD restent partiels.

**Retrait froid de cette nouvelle recette :** gel `71776ef4`, GO indépendant
`e05eb166`, GO ROOT `bb6460ce`. Commande réellement terminée `87e92b/0`
en 0,205 s :32 fichiers (un état d’authentification de 553 octets, trois fichiers Node, 104 196 octets,28 JS/map, 358 140 octets)
et 17 dossiers cache vides retirés par chemins/inodes/hash épinglés, sans
rmtree. Deux racines TMP/auth restent privées et vides ; six PNG de succès,
logs, gels, DATA, originaux et programme conservés. Reçu
`temporary-retirement-after-03.json` SHA `faff0a5f…` ; contrôle externe
`root-external-temporary-retirement-03.json` SHA `e960b0fc…` :49 entrées
absentes,43 pins conservés intacts,126 producteurs acquis et opérateur
2044723/1791696732.74 fraîchement absents. Sélection :462 889 octets logiques,
598 016 alloués ; delta libre observé+598 016 octets distinct du bilan global.
Aucune suppression générale de caches, sources, preuves ou données.

Revue finale indépendante de ce retrait acquise :
`rag02-cold-temporary-retirement-independent-final-review-24.json`,
SHA `0c8e4b3d…`, PASS borné.


## Export37e, stockage et fabrication suivante — 11 octobre 2026

**Rôle :** bilan de preuves locales. **Statut :** export, usine et retraits
revus et fermés ; C09 complémentaire exécuté et fermé dans son périmètre
local après correction d’un oracle QA. Extraction37 réellement fermée,
revue terminale R41 acquise ; TAR52 retiré et revu post-actual R52,
installation37 nominale réellement récoltée à 0 et revue R53, inventaire
froid37 acquis ; baseline C07 de quatre documents obtenue après reprise QA ; première query
Q-MIX exécutée avec FAIL sémantique indépendant et arrêt/conservation froids
revus. Les trois autres cas restent non exécutés, C07 non qualifié. **Source :**
`37e8726c7f97`, contexte RAG-02 `c6db9fa1`, installation52 inchangée.

L’export web est réellement reconstruit et récolté à 0 en 64,462 s :
243 fichiers, 6 616 966 octets, provenance `3b7b3964`. Les 14 identités
capturées sont fraîches absentes ; deux observations ZombieProcess
transitoires restent des erreurs. Reçu `root/rag02-export-37e8726-20261011/completion-01.json`
SHA `cd440134`, revue indépendante R29 `ed3d5f65`. Les 80 entrées source
et l’export historique52 sont conservés. Un build ne mesure pas la qualité
générative ni le fonctionnement du nouveau kit.

Seuls 565 fichiers et 9 dossiers de caches sont retirés : 122 662 126 octets
logiques et 123 916 288 octets d’allocations sélectionnées. Ce dernier total
inclut les entrées des racines conservées ; il ne mesure pas les seuls
octets physiquement supprimés. Gains libres observés : SD+5 107 712,
volume racine+118 411 264 octets, sans attribution exclusive. Deux racines
privées vides et 579 pins de conservation restent exacts.

Le seul TAR57 remplacé est retiré :
`/media/safae/devsave1/r28-office-cpu-57f7f0a6f2fe/delivery/0.1.0+57f7f0a6f2fe-linux-aarch64-none-2b4b.tar`.
Reçu `root/archive57-retirement-20261011/retirement-actual-01.json` SHA
`61bfce16`, vrai harvest `e4b370/0`, revue R32 `1993d223`. Sélection :
11 185 633 280 octets logiques et 11 185 639 424 alloués ; gain SD observé
+11 185 639 424 octets distinct d’une attribution générale. L’extraction
et la réinstallation exacte du kit57 sont désormais perdues. Les six
métadonnées57, guide, somme et preuves restent gardés ; les archives22/52,
installation52 et sauvegardeDEV22 sont préservées. Quatre-vingts identités
historiques et l’opérateur sont constatés absents ; cinq accès FD étrangers
restent UNKNOWN, sans affirmation d’absence ou d’usage globale.

| Étape usine37e | Résultat réellement récolté | Durée |
|---|---|---|
| Dry-run | 0 | 83,418 s |
| Build | 0 | 99,781 s |
| Verify | 0 | 30,346 s |
| Archive | 0 | 469,403 s |
| Relecture complète de la somme | 0 | 120,004 s |

Le dry-run mesure 11 114 770 730 octets ; garde réel 24 377 025 108 octets
(`2 × bytes + 2 Gio`), sans abaissement. Le propriétaire `62885` est
réellement récolté `3bffa1/0`, reçu `16896f70`, progress `acf4320c` ;
80 identités acquises fraîchement absentes, 47 sources exactes après
récolte. Archive de 11 185 684 480 octets, SHA
`ff510738814383f3b69d92de5df4174e8d6a69f2212b134a9ca5f0f3719ef5f7`.
Revue usine R35 `e44ede0a`, puis retrait exact de sa seule copie `/kit`
réellement récolté `93597`→`9bff38/0` en 24,649 s : reçu
`root/rag02-kit-retirement-37e8726-20261011/after.json` SHA `e518c5d0`,
harvest `49384694`, revue R36. 35 626 fichiers, 1 184 liens, 4 585 dossiers
sous racine ; sélection de 11 120 562 520 octets logiques et
11 226 181 632 alloués. Gain SD observé de 11 226 050 560 octets,
libre frais 13 634 785 280 octets ; ces volumes ne constituent ni une
attribution exclusive ni une admission de capacité ultérieure. Six
métadonnées, archive37e complète, guide et somme restent conservés,
ainsi que les installations22/52, données, modèles, sauvegardes et preuves.
Aucune faculté de réinstallation exacte37e n’est perdue tant que l’archive
vérifiée est gardée. Les 80 identités acquises sont constatées absentes
dans le garde de retrait ; son propriétaire PID2091989, naissance1791700223.5,
est récolté à 0 puis absent frais. Les 28 gaps étrangers restent UNKNOWN,
sans conclusion d’absence globale. Source47, DoD et journalOct2 exacts.

L’extraction37 est réellement terminée sous admission distincte :
relecture complète de la somme d’archive à 0 en 65,383 s puis extraction à 0
en 120,195 s. Outil 63530, démarrage `e013fc`, vrai harvest `6ed5e6/0` ;
propriétaire PID2111702/naissance1791701605.11 fraîchement absent.
Progress `4e5d705b`, harvest `03df409a`, 36 échantillons, observateur
réellement récolté à 0, erreurs de nettoyage vides et signal reçu null.
Archive/guide/somme conservés ; source47 et journalOct2 exacts. La revue
terminale R41 `2ac49f07` est acquise : 35 624 fichiers réguliers et
1 184 liens déclarés vérifiés, quatre identités connues fraîches absentes
(propriétaire inclus). Le TERM prévu de l’observateur est distinct d’un
signal reçu par le pilote ; aucune absence universelle de signal affirmée. Le kit extrait est
`/media/safae/devsave1/r28-rag02-cpu-37e8726c7f97/transport/0.1.0+37e8726c7f97-linux-aarch64-none-2b4b` ;
aucun programme installé ou service applicatif démarré par ce pilote.
Libre SD signalé par ROOT : 2 371 108 864 octets ; installation NO_GO
au point postextraction, recette native37 non acquise. Les admissions et budgets restent distincts,
sans attribution exclusive d’espace ni abaissement de garde.

### Installation22 : garde QA refusé puis reprise HOST réelle

Le garde nominal initial termine à 1 avant désinstallation, dont aucun
résultat n’existe. Le namespace fait apparaître 173 observations UNKNOWN
contre 11 dans la référence HOST ; une relecture du même PID/naissance côté
hôte discrimine la visibilité des métadonnées. Revue R43
`installed22-original-namespace-guard-refusal-and-host-recovery-proposal-review-43.json`
SHA `8b0421b2` : refus correct au regard des observations, cause QA de
périmètre et non échec produit de désinstallation. L’installation22 reste
présente au point de cette preuve. La session initiale est réellement
fermée, propriétaire `93511`→`6b8429/0`, 58 identités capturées absentes
(reçu `b0eddee2`) ; R44 `f51ecc7c` confirme 59 identités distinctes
avec propriétaire. Garde initial1 et absence de désinstallation conservés. Aucune inconnue convertie en absence
ni généralisation depuis cette unique relecture.

Au jalon R43, la reprise HOST était une voie distincte préparée/proposée,
sans exécution acquise : conserver les 11 UNKNOWN de référence et refuser toute nouvelle
inconnue ou tout usage observé ; préserver l’ancien rouge et obtenir
propre admission, vraie récolte et contrôle froid. La capacité physique
après un retrait futur restait à relever ; installation37 et recette
requièrent leurs gardes complets propres, aucune garde abaissée.

### C09 adverse : refus et contenus inertes sur Linux aarch64

Douze refus HTTP 400 réellement capturés : ZIP illisible, XML malformé,
faux format, membre traversal, membre symlink, relation traversal, macro
déclarée et cinq quotas livrés (membres, profondeur, ratio, partie, total).
Les codes sont distincts : `office_invalid_package`×5,
`office_limit_exceeded`×5, `office_format_mismatch`×1 et
`office_macros_unsupported`×1. Commande10 réellement à 0 en 3,667 s ;
statut/corps bruts/erreurs de parsing conservés avant adjudication.
Les cas partie/total exploitent des métadonnées ZIP hostiles : aucune
performance de décompression légitime 64/256 Mio n’en est déduite.
Les trois anciens refus et quota XML2M restent liés à leurs preuves
antérieures, sans nouvelle exécution.

| Preuve native inerte | Commande réellement récoltée | Interprétation |
|---|---|---|
| DOCX sortie 01 | 1, worker à 0 | Oracle QA `parser_complete` non conforme au contrat par format ; rouge conservé |
| DOCX sortie 02, reprise 17 | 0 en 1,224 s | `ready_partial`, texte littéral et hash SVG exacts, lien/image externes non chargés |
| XLSX sortie 01 | 0 en 2,145 s | `ready_partial`, quatre cellules exactes, formules/cache 72 contradictoire non évalués, lien externe métadonnée |

Seul l’oracle QA est corrigé après revue R38 `eeab66e3`. Le résultat
worker DOCX est identique entre les deux sorties ; aucune source produit
modifiée. Ces extractions natives ne prouvent pas une ingestion positive
API, une publication d’index ou un job READY. Douze invocations d’import
refusées ; aucune nouvelle question ni appel modèle par les clients.

Les contrôles positifs observent de vraies opérations autorisées : lecture
du sentinel synthétique, socket créé/fermé sans connexion, sous-processus
Python possédé attendu/récolté à 0 puis absent. Les événements positifs sont
séparés et le relevé remis à zéro avant le worker ; zéro événement CPython
observé dans chaque worker. Ce hook n’est ni un sandbox ni un traceur de
syscalls ; les appels natifs non audités et l’absence de toute tentative
externe ne sont pas démontrés par ce seul résultat.

Down à 0 en 4,702 s ; inventaires PROGRAM52 avant 85,341/après 34,293 s,
comparaison externe au dernier état froid avant restore à 0 en 1,248 s,
comparaison stricte à 0 en 1,244 s. 65 131 fichiers/1 188 liens exacts avant
et après. Le propriétaire PID2098910 (session outil `85208`) est réellement
récolté `e51f00/0`
(reçu `5690799c`), puis checker froid réellement récolté à 0 (`a0ef9225`).
Reçu hôte `root/c09-final-matrix-20261011/host-final.json` SHA `1df0a485` :
RAW31 exacts, deux tours DONE, 14 citations, 167 événements, 3 jobs,
3 versions et trois originaux inchangés ; Qdrant LIST14 exact avant/après,
77 sources produit vérifiées à froid. 81 relevés hôte couvrent
77 identités PID/naissance strictement absentes ; checker froid absent
séparément. Aucun zombie ou UNKNOWN transformé en absence.

Revue terminale R39
`c05-history/review/c09-final-matrix-independent-recovered-terminal-review-39.json`
SHA `a114a5e2` : clôture fonctionnelle récupérée et bornée. L’ancien
résultat DOCX à 1 est préservé, sans reconstruction de tous les résultats
nominaux à 0. Aucun PASS C09 global ni clôture I05/C07 complet, I07/I08 ou
DoD globale. Windows, Linux x86-64, CPU physique ≤ 16 Go, métier/final,
réserve générative et NF09 strict restent distincts.

Reconsultation officielle : `root/official-source-check-20261011T0600Z.json`,
reçu enregistré le 11/10/2026 à 06:02:21.032078 UTC. python-docx 1.2.0 et
OpenXML relus ; documentation openpyxl 3.1.3 versus version installée 3.1.5
explicitement distinctes. Mise à jour de trace/date uniquement, sans
nouvelle décision, benchmark, preuve native ou supériorité SOTA générale.

La reprise HOST retire nominalement l’installation22, sans suppression
manuelle : garde0 en 0,988627 s, désinstallation0 en 34,417176 s, propriétaire
réellement récolté `4292`→`dd580f/0`, 18 identités possédées absentes puis
checker froid absent. Reçus harvest `0177fb2c`, completion `dd4ac4e5`,
host-final `ed805c95`, harvest froid `1118a37a` ; revue R47 `45e009d2`
acquise. Aucun namespace hors ligne n’est revendiqué pour cette voie HOST.
Ancien refus1/no-UNINSTALL et diagnostic de visibilité sont conservés ;
archives22/52, programme52 de repli, données, sauvegardes et preuves restent
gardés. Gain SD observé 11 246 563 328 octets, non exclusivement attribué au
retrait ; libre après 13 613 858 816 octets. Mesure fraîche suivante
13 613 846 528 octets contre garde install37 de 14 335 994 149 octets :
déficit exact 722 147 621 octets, installation37 toujours NO_GO à ce point.
À ce checkpoint, aucun cache éligible d’au moins 1 Gio n’était identifié ;
la seule archive52 restait à classer. Son retrait réel suivant est décrit
ci-dessous et ne requalifie pas le déficit antérieur. La version du
noyau réellement relevée est `5.10.120-tegra`, distincte des man-pages6.19 ;
les sources officielles expliquent un mécanisme, pas une preuve de recette.


### Retrait précis du TAR52 — résultat réel du 11 octobre, 07:57 UTC

Le seul TAR52 de `r28-office-cpu-52abb94b2505/delivery` est ensuite retiré
par une copie QA02 byte-identique du pilote, sans changer la garde de
300 s. L’inspection01 périmée reste conservée ; nouvelle inspection
`85ee6c/0`, reçus `b5ddba6f`/`dd703c77`, après avis préparatoire R51
`2dd79f4d`. Retrait session80575 réellement récolté `5dbd39/0`,
contrôle froid `2cf241/0`, reçus `39d6b522`/`5d1f0142` ; opérateur
PID2162871/naissance1791705455.98 absent frais. Revue post-actual R52 `4b01ae32` acquise :
88 identités connues absentes et 70 petits pins conservés. Chronologie conservée : R51
préparatoire, inspection QA02 réellement récoltée, admission ROOT dans
la garde de 300 s, retrait réel, puis revue R52 post-actual. Cette dernière
ne reconstitue aucune approbation antérieure. Sélection : 11 185 684 480 octets logiques et
11 185 688 576 alloués ; gain SD observé 11 185 688 576 octets, sans
attribution exclusive. À 07:57:55 UTC, SD libre 24 798 777 344 octets et
volume racine libre 3 252 469 760 octets. Ce checkpoint dépasse les seuils
préparés d’installation37 ; il ne constitue ni admission ni installation.
PROGRAM52 de repli, données, sauvegardes, archives22/37, transport37,
guide, somme, six métadonnées et preuves restent conservés. La nouvelle
extraction, réparation et réinstallation exactes52 sont désormais perdues ;
aucune reconstruction bit-identique du TAR52 n’est promise. Les cinq gaps
FD étrangers restent UNKNOWN, sans conclusion d’absence globale. I08 et C07 complet demeurent ouverts ;
l’installation nominale37 est consignée séparément ci-dessous.


L’installation37 nominale est désormais réellement terminée, sans start ni
navigateur : garde0 en 0,805 s, verifier0 en 6,129 s puis install0 en
339,293 s (`4182`→`2e6954`). Finish `2226ac/0`, propriétaire16647 réellement
récolté `48c4e4/0` ; reçu `e2f4c39e`, 57 identités connues absentes. Checker
froid `0b9652/0`, host-final `ce3c6259`, harvest `57fdf061`. Rapport nominal
`121bb007`, pointeur `4a2a2f08` ; programme `37e8726c7f97`, profil4B par
défaut, aucun traitement lancé sur les données. DATA sélectionnée :
17 211 octets logiques/28 672 alloués, mesure ponctuelle ; SD libre
13 551 702 016 octets, volume racine libre 3 247 861 760 octets. Revue R53
`bfe17d2e` acquise, 59 identités connues absentes, 38 petits pins et six
métadonnées exacts. Inventaire froid37 réellement récolté `13698`→`3424f1/0`,
opérateur PID2172274 absent frais : 65 131 fichiers/1 188 liens, baseline
`01f5afb6`, harvest `75926eeb`, référence37 des recettes suivantes. Le rapport
signale `compileall, code1` comme précompilation non bloquante ; cause précise
UNKNOWN historiquement, aucune réussite de compilation de tous les fichiers
revendiquée. Aucun restore, API, LLM ou parcours C07 acquis par cette
installation ; I08 reste partiel jusqu’à sa recette utile.


### C07 : baseline réelle après reprise QA, cas encore attendus — 08:32 UTC

L’étape11 initiale échoue à 1 avant le premier POST/import, lecture de
jetons ou écriture du résumé : la QA exigeait à tort les 77 fichiers de
sa garde dans le manifeste canonique du runtime. Ce dernier sélectionne
88 fichiers ; 75 des 77 gardes y appartiennent, deux sont volontairement
hors contrat (`tools/dist/program_inventory.py` et configuration du tokenizer).
Variante03/revue R54 `31e4f654` : couverture88 exacte contre inventaire
froid37, empreinte liée à up, unicité et complément77 maintenus, sans skip
arbitraire. Ancien0011/1 `902d836b` conservé ; reprise17 distincte réellement
à 0 en 72,582 s (`451afc`, résultat `b7484aa5`). Un seul POST/import DEV
public, zéro POST/query et zéro appel LLM par cette étape. Baseline obtenue :
quatre documents distincts et 19 points Qdrant, dont les 14 points antérieurs
préservés ; les deux anciennes réponses et 14 citations restent exactes.
Résumé `7a048947`, preuve de projection `a1c08cf6`. Les quatre cas C07 et
leur fermeture froide ne sont pas acquis par cette baseline.

L’observabilité de la précompilation est corrigée dans la source de
`tools/dist/linux_install.py`, avec ses tests ciblés : code retour,
premiers 4 096 caractères de stdout/stderr et troncature explicite conservés
au rapport ; résultat non nul signalé incomplet, installation non bloquante
inchangée. Trois témoins rouges puis cinq tests ciblés verts, Ruff et mypy
Linux/Win32 ciblés à 0, huit producteurs connus absents. Compileur substitué
par des doubles nommés, opérations de copie/profil/pointeur sur fixtures
isolées réelles ; aucune compilation native37 rejouée. Completion `f323a440`,
revue R55 `cd4160d5`. Cette source corrigée n’est pas incluse dans PROGRAM37
immuable : ancien code1 et stderr non récupérable conservés, cause précise
UNKNOWN, aucune explication rétroactive inventée. La référence officielle
compileall/-q est documentaire, pas une preuve d’exécution ou de qualité.

### C07 Q-MIX : échec sémantique et clôture partielle — 08:50–09:04 UTC

Après admission des quatre bindings (R56 `00bbcc75`), le premier contrôle
QA échoue avant tout POST/query : il attendait `=LEN(A2)` dans le DTO
cellule, tandis que le XML source et le parseur conservent `LEN(A2)`.
Ce résultat `665bcd6a/1` et le résumé FAIL demeurent intacts. Le XML C2
est `<f>LEN(A2)</f><v/>`, B2 vaut littéralement 72V et le cache C2 est absent.
Variante QA03 : une seule égalité stricte corrigée ; questions, contexte
humain `=LEN(A2)`, paramètres et oracles sémantiques inchangés. Trois
mutations du témoin cellule restent refusées ; revue R57 `76cd9506` et
admission complémentaire `8aebed49` acquises avant l’unique reprise.

Q-MIX03 termine réellement à 0 en 221,273 s, wait `626faf`, résultat
`0a12c4a8`, résumé `0427aef6`, query `e5070234-7f75-4566-abc4-08424088e41b`.
Le contrôle mécanique passe : cinq citations résolues vers trois documents,
versions/révisions/ancrages exacts. Le verdict sémantique **FAIL** est
indépendamment confirmé par R58 `00c64a6b` :

- Les S001/S003/S005 partagent le même document_id DOCX, mais la réponse les
  présente comme trois documents, plus S006 PDF. Elle n’attribue pas
  séparément B2 au classeur dans sa liste nominale.
- Elle avance « soit 6 » pour LEN alors que S002 indique un cache absent,
  puis affirme que ce 6 ne peut être confirmé. Le warning natif
  `value_not_in_context` signale déjà cette valeur. Aucune preuve d’une
  exécution ou d’un recalcul de formule : le défaut est dans la réponse.

Le sérialiseur installé `c6db9fa1` regroupe document_id uniquement en mode
comparison ; question/analysis restent plats sans document_id ni nom documentaire ; version_id reste transmis.
La limitation XLSX était déjà transmise. Ces écarts justifient R28-RAG-03,
correction commune du contexte et de ses consignes engagée à ce jalon :
aucune cause interne du modèle ni correction native acquise n’est inventée.
Les trois autres queries sont suspendues pour traiter ces causes avant
une nouvelle recette ; aucune génération identique n’est relancée.

Arrêt nominal13 réel0 en9,174s (`3b6777`), snapshot14 réel0 en33,09s
(`a11507`), comparaison15 réelle0 en1,298s (`de2767`), finish16 réel0
(`286baf`). Propriétaire97359 réellement récolté `c68968/0`.
Collecte froide `9eab01/0`, puis collecteur2217103 absent vérifié
`0caae2/0` : 297 vies connues absentes, RAW31 exactement égal à sql-afterQ,
3 questions/21 citations avec anciens 2/14 conservés, quatre originaux exacts,
inventaire programme65 131 fichiers/1 188 liens inchangé. Les19 points
avaient été vérifiés à la baseline pré-Q ; aucune mesure post-Q des
vecteurs n’est déduite de la seule conservation SQL.

Preuves dans `root/c07-runtime-companion-37-20261011/` :
`actual-owner-harvest-partial-01.json` (`f14713fb`),
`host-partial-failure-final-01.json` (`82a1a5ba`),
`cold-partial-harvest-01.json` (`1f1b504b`). Revue froide R59 `ed2f2195`
indépendante, 297 vies connues plus collecteur contrôlés absents.
Étape12, handoff quatre cas et finalizer quatre cas non exécutés ; aucun
PASS de matrice C07, CPU16Go physique, autre plateforme ou DoD globale.

Nettoyage des tests compileall : seules les trois cibles privées
red-01/basetemp, green-02/basetemp et mypy-cache retirées, preuve `642da4f5`
après outil `47ad20/0`. 5 505 621octets logiques/24 489 984alloués supprimés,
gain libre observé24 436 736 octets sur volume partagé ; neuf rapports de
fixtures et les preuves RED/GREEN conservés. Vérification indépendante
acquise. Préparation lecteurs quatre cas interrompue, reçu `6e6dcd6b` :
aucune API, aucun navigateur ni POST/query exécuté par cet agent.

### R28-RAG-03 : correction commune vérifiée au niveau source — 09:18 UTC

`services/api/context.py` (`3454f1a5`) expose document_count, document_id,
document_name réel, source_ids et extraits regroupés dans tous les modes.
L’enveloppe entière est comptée avant admission, après coupe et dans les
métriques ; quotas, priorités et couverture restent inchangés. L’instruction
commune distingue citations et documents, interdit calcul/exécution et
inférence d’une valeur sans cache ; un cache présent garde une fraîcheur
inconnue. Aucun cas LEN spécifique, masquage de sortie ou recalcul ajouté.
`evidence()`, historique, locators et `validate_answer()` restent identiques
par AST. La représentation envoyée au modèle évolue volontairement ; ni
schéma DB, ni contrat de citations persistées, ni extraction ne changent.

Gel source/tests :
`root/rag03-document-formula-context-20261011/frozen.json` (`d51ebd76`),
rapport et codes réellement récoltés dans ce dossier. RED initial 8 FAIL ;
union 174 PASS/1 FAIL en 103,80 s, seul golden historique affecté, rouge
conservé. Reprise du golden : PASS, anciennes trois empreintes pré-R26
littérales reconstruites indépendamment ; contrôle final du golden et de
deux gardes renforcées : 3 PASS en 3,57 s. Les 175 cas uniques de l’union
sont donc couverts, les reprises ne s’ajoutent pas au nombre de cas.
Budget 120 maintenu avec témoin négatif du passage long ; cache stale C4=1
conservé sans recalcul, absence de cache toujours sans valeur. Ruff six
fichiers et mypy context seul avec imports ignorés Linux/Win32 statique PASS.

Revue indépendante R60
`c05-history/review/rag03-common-document-formula-context-independent-source-final-review-60.json`
(`c5f2dd7f`) : 45 pins exacts, contrôle AST et goldens indépendants, GO source.
Transport Ollama, PDF/E5/vecteurs/tokenizer simulés dans les tests concernés ;
aucune qualification LLM/Windows/x86-64/CPU16Go/final corpus. Les retours
d’outils de tests ne prouvent pas tous descendants absents. Décision W058.
La source est validée, l’efficacité native du nouveau kit reste à vérifier ;
Q-MIX03 FAIL, R58/R59 et PROGRAM37 sont conservés sans altération.

## Livraison f14, arrêt C07 et nettoyage des essais — 11 octobre 2026

**Portée :** source commune publiée `f14d87a05dfee315515db9cc53dd6be8bf18fd40`,
kit Linux aarch64 CPU et fixtures DEV synthétiques. Les tableaux antérieurs
restent des jalons historiques ; leurs échecs et reprises ne sont pas réécrits.
Aucune qualification Windows, Linux x86-64, CPU physique ≤ 16 Go ou métier/final.

### Livrable et arrêt partiel réellement acquis

Usine f14 fermée à 0 : `root/rag03-kit-f14d87a-20261011/`
`factory-actual-owner-closed-01.json` (`ab4914a0`), progress `152ea63e`.
Archive : 11 185 684 480 octets, SHA-256
`c8665b8bad62bb52a37a89228548b7a58d10f94b3e9163fba172e01e336b3812`,
relecture complète acquise. Extraction réellement récoltée à 0, progress
`d8f37279`, clôture `2489c7eb`. Installation nominale f14 terminée à 0,
`root/rag03-install-preparation-20261011/actual-owner-harvest.json`
(`70f2fa16`) et `host-final.json` (`648d5b55`). Le code1 de précompilation
reste un avertissement non bloquant ; aucun PASS de tous les fichiers compilés.
Le programme installé et l’archive f14 restent les livrables conservés.

Une seule query Q-MIX est exécutée : 1 POST queries et 1 appel LLM observé,
**FAIL sémantique maintenu**. A-MIX, A-BOUNDED-TOTAL et CMP4 restent
**NOT_DISPATCHED**, avec zéro POST pour ces trois cas. Down/finish et vraie
récolte du propriétaire terminent à 0 ; le froid est explicitement partiel,
sans handoff ou réussite quatre cas. RAW31 conserve 3 queries/20 citations,
les anciennes 2 queries/14 citations et quatre originaux exacts ; comparaison
stricte du programme conforme. Les 19 points sont la baseline préquery ;
aucune mesure Qdrant postquery n’est déduite de la conservation SQL.

Preuves : `root/c07-rag03-runtime-activation-20261011/runtime/`
`host-partial-failure-final-01.json` (`0816ed3b`),
`actual-owner-harvest-partial-01.json` (`750c31d9`) et
`cold-partial-actual-harvest-01.json` (`0c82e187`). Revue R93
`c05-history/review/c07-rag03-qmix-partial-cold-and-final-generated-cleanup-independent-review-93.json`
(`db88f805`) : clôture partielle et préparation du nettoyage exact revues ;
222 durées de vie absentes indépendamment contrôlées. Ce verdict ne valide
pas la réponse, ni toute la matrice C07.

### Retraits effectifs et traces conservées

PROGRAM52 est désinstallé nominalement en HOST, revue terminale R88
`d9d4c74d` ; les deux refus antérieurs restent documentés, sans élargissement
arbitraire des inconnues. Le seul TAR37 est ensuite retiré réellement à 0,
`c7755f`→`2eb7e6`, clôture intégrée R90 `cc950299` ; PROGRAM37 est conservé
comme repli installé, sans promesse de réinstallation exacte depuis ce TAR.

Sous `root/post-c07-generated-cleanup-preparation-20261011/` :

| Opération réelle | Résultat et gain libre observé | Preuve compacte |
| --- | --- | --- |
| Quatre payloads kit/transport R27 | 0, 82,713 s ; 48 285 548 544 octets | `actual-cleanup-01/after.json` (`59bfcd5e`), harvest (`478c3aaf`) ; six métadonnées originales par cible gardées |
| 34 cibles anciennes | 0, 27,835 s ; 37 492 858 880 octets | `actual-final-cleanup-01/after.json` (`3113bec2`), `root-actual-harvest.json` (`b3d9a1b9`), outil `45777f/0` et propriétaire frais absent |

Le second lot comprend 16 clones synthétiques, 11 basetemps pytest, deux TAR
R27, quatre inventaires bruts et le payload du transport f14. Les protections
avant/après sont égales. Au checkpoint final : 99 101 138 944 octets libres
sur SD, soit 92,29 Gio ; les gains sur ce volume partagé restent des observations
distinctes, non une attribution exclusive ni une estimation de performance.

Cinq pertes explicitement acceptées :

1. Les anciens clones DB/index/extractions, dont les DB/WAL/SHM de crash C02
   et leurs backups, ne sont plus disponibles pour réinspection binaire.
   Les oracles natifs compacts et les échecs d’origine sont conservés.
2. Les deux TAR R27 retirés ne permettent plus leur extraction/réinstallation
   exacte ; aucune reconstruction bit-identique promise. Livrable f14,
   PROGRAM37 de repli et archive22 conservés.
3. Les 11 basetemps générés sont retirés ; préimages, logs, goldens, résumés
   et gels source sont conservés. Les 191 liens historiques n’ont jamais été suivis.
4. Les quatre inventaires bruts R27 sont retirés après conservation de résumés,
   stat et SHA, revue indépendante acquise ; l’énumération initiale complète
   n’est plus conservée.
5. Le transport f14 reste composé des six métadonnées originales et de leurs
   parents ; il n’est plus un kit vérifiable ou exécutable. Archive et programme
   f14 conservés ; toute reprise exige une extraction fraîche distincte,
   sans overlay sur ces métadonnées.

Revue finale après opération R94
`c05-history/review/final-generated-34-target-cleanup-independent-actual-review-94.json`
(`f31a0e56`) : **nettoyage validé dans ce périmètre**. 34 cibles exactes,
33 absentes et transport f14 réduit aux métadonnées ; 30 métadonnées originales,
13 copies C02, quatre inventaires compactés, 117 sources et 115 protections
avant/après conformes, propriétaire absent. Le GO avait recontrôlé 625 durées
de vie connues. L’observateur relève 30 UNKNOWN après opération contre 31
auparavant ; ces limites ne deviennent ni identités absentes ni preuve globale
d’innocuité. Aucune validation de toute la carte SD ou du système n’est ajoutée.

Les 13 petites preuves C02 sont conservées dans
`actual-final-cleanup-01/retained-compact-trace/c02/` ; la compaction R27,
les rapports, échecs, préimages source et preuves d’arrêt restent hors des
cibles retirées. DATA actuelle C07, originaux, corpus privé, modèles/runtimes
canoniques, backup DEV22 et archive22 sont conservés. Les UNKNOWN étrangers
restent bornés ; aucune absence ou innocuité globale n’est affirmée.

### Politique SYSTEM et préparation DEV — 13:27 UTC

La politique commune `4303c85a` est implémentée : attribuer les faits à chaque
document et ne fournir aucun résultat numérique de formule sans cache.
Ancienne instruction rétablie seulement en mémoire : six tests réellement
rouges ; puis 126 tests ciblés PASS, Ruff quatre fichiers et mypy context PASS.
Huit durées de vie des contrôles sont fraîchement absentes. Completion
`root/qmix-document-formula-context-20261011/completion-01.json` (`bc7de96b`),
revue R95 `qmix-context-policy-source-and-dev-gpu-preparation-independent-review-95.json`
(`632f0859`). Transport/tokenizer et autres doubles restent ceux des tests ;
aucune efficacité native du modèle ni réussite GPU ne découle de ce résultat.
Le programme f14 installé conserve sa source antérieure inchangée.

Trois dérivés de ces tests retirés à 0 (`903ee5`), 128 552 305 octets logiques ;
preuves, préimages et journaux conservés. `cleanup-after-01.json` (`09cdcc14`)
et `cleanup-harvest-01.json` (`107dbd99`) dans le même dossier. Cette mesure
logique est distincte du gain libre observé et ne qualifie pas la DoD.

Préparation DEV sous `dev-gpu-01/` : premier backup refusé (`0d5abd44`)
conservé ; remède de support nominal depuis le programme installé,
up→backup→down réellement récolté `c19c5c`/40204→`1c2d9f/0`. Backup
`support-f14-backup-01.json` (`a623e291`) : quatre documents, trois queries et
20 citations. Garde `support-cold-guard-01.json` (`8e5f301b`) : RAW31 exact,
zombie possédé2480913 non exécutant, récolte finale encore en attente.
Aucune absence de ce zombie ni fermeture complète du support n’est déduite.

### DEV source : réponse tronquée et fermeture réelle — 13:42 UTC

La query `84057a66-bc9d-452e-bc53-c26ef552f641` est réellement exécutée,
`a6289f`/10006→`ae0225/1`, résultat `ca50fde0`, durée 154,453 s,
1 POST queries et 1 appel LLM. DONE `d3770506` : état `length_limited`,
768 jetons, texte terminé par « il y a une insuff ». Les trois documents
DOCX/XLSX/PDF sont correctement attribués et cités avec 72 V ; aucun résultat
numérique LEN n’est avancé. **FAIL conservé : la réponse n’est pas complète.**
Les trois autres cas sont non dispatchés et les lecteurs non exécutés.

Revue R97
`c05-history/review/c07-dev-gpu-qmix-length-limited-independent-actual-adjudication-review-97.json`
(`c9198597`) : concordance sémantique et citations vérifiées, sans PASS global.
Les métriques déclarent `llm_execution.mode=gpu`, `fallback=false` ; le runner
s’arrête avant observation `/api/ps`. La résidence GPU n’est donc pas prouvée,
ni une mesure comparable de performance matérielle.

Le premier contrôle froid (`da981ad5`) refuse correctement le zombie possédé
avant finish. Cet ordre QA initial erroné est corrigé sans faux code0 et sans
attribuer un échec d’arrêt au produit. Après vraie récolte du propriétaire
75739→`034c62/0`, capture hôte correcte `689aed` (`0393cad69`), finaliseur
`10490a/0` : `dev-gpu-01/host-final-dev.json` (`ad31d6c7`) conserve RAW31,
4 queries/26 citations, anciennes 3/20 exactes, quatre originaux et 77 sources/
export exacts. 130 durées de vie fraîches absentes, dont le zombie support.
`root-owner-harvest-01.json` (`7a8229bf`) et
`root-cold-harvest-01.json` (`e2fd206e`) lient les vrais codes0 ; opérateur froid
2500539 frais absent (`73bcea/0`). Cette fermeture reste partielle et conserve
le FAIL, les trois cas non exécutés et les limites Qdrant postquery.

### Concision source verte et reprise DEV Q2 — 14:11 UTC

La fermeture Q1 est revue indépendamment R98
`c07-dev-gpu-partial-cold-closure-independent-terminal-review-98.json`
(`1def4d5c`) : PASS froid partiel, échec de réponse et trois cas non exécutés
conservés, aucune réussite quatre cas.

Correction cumulative Question/factuel `f4996d22` implémentée : 101 PASS
ciblés réellement récoltés (`57a39b/0`), mypy context (`10bfe6/0`) et Ruff
(`0cd1c0/0`). Completion `question-brief-02/completion-01.json` (`9e63bb6c`)
sous `root/qmix-document-formula-context-20261011/` ; revue R99
`question-brief-source-and-dev-existing-data-q2-preparation-independent-review-99.json`
(`fde6833d`) : source/transport verts, efficacité native en attente.
Les doubles de tokenizer restent explicites ; pas de nouvel invariant de
qualité déduit des unités. Trois temporaires retirés, 128 072 250 octets
logiques ; preuves conservées, `cleanup-after-01.json` (`8b112e73`) et
`cleanup-harvest-01.json` (`b2afc249`).

Q2, sous `dev-gpu-02/`, réutilise la même DATA : quatre documents,
quatre queries/26 citations et 19 points à la baseline, aucun import ou
clone supplémentaire. Deux échecs de readiness QA avant démarrage et appel
modèle sont conservés : confinement d’un helper Q1 réemployé vers Q2,
puis `ModuleNotFoundError` dans le namespace. Correction bornée : copies
exactes des quatre modules Q1 nécessaires, confinement maintenu et
ownership03 neuf. Aucune réponse ou query de ces tentatives n’est fabriquée.

Démarrage/doctor/baseline en lecture seule réellement récoltés `289e92/0`,
session69141 : quatre étapes à 0, durées mesurées 35,054/2,130/0,787 s.
`binding-core.json` (`3cdf9b49`) lie les 77 sources, contexte `f4996d22`,
fingerprint `e1e921f5` et instance `6bfdb88a`. Handle propriétaire25599 en cours ;
aucune nouvelle query ou inférence à ce checkpoint. La préparation/cœur
réel ne constitue pas un verdict natif. **Suite :** poursuivre le cas admis,
puis revue de réponse/lecteurs et arrêt selon son résultat. Estimation locale
courante : 15 h 45 Casablanca, conditionnée au cas réel ; aucun PASS GPU
ou de réponse complète anticipé. Estimation locale courante : 15 h 45 Casablanca, selon le cas ; globale : 40–90 heures effectives après T0 et disponibilité des
hôtes/corpus requis. C07/I05, I07/I08, NF09 et la DoD restent ouverts.

### DEV Q2 : deux résultats et fermeture partielle — 14:34 UTC

Q-MIX query `61a7a24c-f0c3-4045-ac77-f6a13cc296c8`, `644013/0`,
87,194 s, DONE `2ed457a2` (`done/stop`, 185 jetons) : **PASS sur ce cas seul**,
revue R101 `befa2e40`. Les trois documents DOCX/XLSX/PDF portent 72 V avec
attribution propre ; B2 reste littéral et C2 formule sans cache, sans valeur
numérique inventée. Six citations persistent, cinq sont réellement employées.
Résidence Ollama GPU observée après génération : digest exact,
`size_vram=3107811491`, aucun repli ; aucune qualification matérielle déduite.

A-MIX query `6b56af3c-e960-4c22-9c14-2170c8f21472`, `babe6d/0`,
109,508 s, DONE/stop/927 jetons : collecte mécanique réussie mais **FAIL
sémantique**, R102 `fbdd1a18`. L'absence de cache ne prouve ni formule inactive
ni historique d'exécution ; les consignes locales ne sont pas des faits du
document et des valeurs concordantes ne prouvent pas l'indépendance des sources.
Deux POST et deux appels LLM observés au total, GPU résident observé pour
les deux cas ; A-BOUNDED-TOTAL et CMP4 non dispatchés, lecteurs non exécutés.
Les résultats historiques DONE et le Q1 `84057a66` tronqué restent inchangés.

Clôture réelle : down/finish puis owner25599→`e3e6d6/0`, capture HOST et
finalisation froide. `dev-gpu-02/host-final-dev.json` (`d63455f0`),
`root-cold-harvest-01.json` (`9c9971f9`) et revue R103
`c07-dev-gpu-q2-partial-cold-closure-independent-terminal-review-103.json`
(`8e90c03e`) lient RAW31, 6 queries/40 citations, anciennes4/26,
quatre originaux et source77/export exacts à froid. 192 durées de vie connues
fraîches absentes ; aucune absence globale revendiquée. Qdrant19 est la
baseline préquery, sans mesure postquery inventée.

Premier finaliseur QA `aaafe8/1` conservé : un `launcher.log` épinglé est lu
comme JSON, avant les nouveaux reçus froids ; opérateur frais absent. Préimage
et `root-finalization-failure-01.json` (`4f968914`) gardées. La correction
hash seul conserve toutes les gardes ; finaliseur distinct `a83e4c/0`, aucune
mutation produit ou données, aucun reclassement du rouge en réussite.

### Cache et limites locales : source vérifiée, Q3 préparé — 14:34 UTC

Après la fermeture Q2, correction cumulative contexte `73140f92` : trois
chaînes précisent résultat calculé indisponible vs activation/historique
inconnus, limites de cette application vs assertions du document, et
concordance vs indépendance des preuves. Groupes, citations, locators,
valeurs/formules sources, scopes, budgets et quotas restent inchangés.
Completion `cache-semantics-03/completion-01.json` (`2755f95e`) :
10 RED attendus avec la préimage puis 111 PASS (`572e06/0`), Ruff `a685c1/0`.
Mypy réel R99 est réutilisé explicitement : AST/types/flux inchangés hors
les trois constantes chaîne (`typecheck-reuse-01.json`, `2ccb46d3`) ; aucun
nouveau mypy revendiqué. Goldens historiques stricts conservés, six durées
de vie de producteurs fraîches absentes. Revue R104
`cache-local-limits-source-independent-review-104.json` (`1f452278`) :
**GO source/transport, efficacité native en attente**. Référence Microsoft
SpreadsheetML reconsultée par ROOT, [R28-S06](../SOURCES.md), contrat cache
et limite documentaire ; ce n'est pas une preuve d'obéissance du modèle.

Deux basetemps dérivés seulement retirés : 5 811 346 octets logiques,
6 168 576 octets alloués ; gain SD observé 7 208 960 octets, activité concurrente
incluse. `cleanup-after-01.json` (`e86a1be3`) et récolte `8a1f7f7b` conservent
preuves, préimages, RED/GREEN et goldens.

Q3 `dev-gpu-03/preparation.json` (`2386171f`) et préparation lecteurs
`readers/` (`18f5b9a1`) sont préparés, sans nouvelle inférence/API/navigateur
revendiqué. Même DATA froide Q2 6/40 et 4 documents/19 points, profils/ports
inchangés ; quatre modules, runner et oracles byte-exacts. Source77 actuelle,
admission et bindings réels ROOT/R restent requis ; chaque verdict réel
précède le cas suivant. ETA 16 h 10 Casablanca conditionnelle aux quatre
cas, lecteurs et publication source/suivi. Dernier kit corrigé/CPU local
restent distincts ; C07/I05, I07/I08, NF09 et DoD ouverts. Global :
40–90 heures effectives après T0 et disponibilité des hôtes/corpus requis,
autres réserves locales et externes conservées.

### DEV Q3–Q5 : frontière des preuves et deux cas validés — 15:47 UTC

Q3 échoue avant query : un fait PDF requis manque au contexte final,
`query_id=null`, 0 POST/0 appel modèle. `dev-gpu-03/root-prequery-failure-01.json`
(`bb66eea9`) conserve ce résultat. Froid réel `host-final-dev.json`
(`1970c4ee`) et récolte `c1fe7456` : RAW31 6 queries/40 citations inchangé,
quatre originaux/source77/export exacts, 284 vies connues absentes.

Q4 Q-MIX `5dc9f94e-ed6c-408d-8bb8-4d223fb0f80b` est DONE/stop/255 jetons,
96,269 s, 1 POST/1 modèle ; **FAIL sémantique**, car le cache absent ne prouve
pas que la formule « n'a pas été exécutée ». ROOT `4220d918`, revue R109
`c07-dev-gpu-q4-qmix-independent-actual-adjudication-review-109.json`
(`801a1c87`). Trois cas non dispatchés. Down/finish puis vrai wait owner0,
capture HOST/finaliseur0 : `dev-gpu-04/host-final-dev.json` (`b0e67a96`) et
`root-cold-harvest-01.json` (`55f5f156`), RAW31 7 queries/46 citations,
anciennes6/40 exactes, quatre originaux/source77/export inchangés ; 335 vies
connues absentes, sans absence globale. Source exécutée `2e75e418` conservée.

Après ce froid, correction structurelle `72fd5175` : les limites applicatives
ne sont plus insérées dans les extraits documentaires ; les politiques restent
SYSTEM. Aucun champ public de source supprimé, ni changement des textes,
faits cellule, locators, citations, modèles ou quotas. Completion
`evidence-data-boundary-05/completion-01.json` (`7e73dfd1`) : 14 RED sur la
préimage puis 112 PASS ciblés, Ruff0, mypy context courant0 sur cache neuf ;
douze vies connues de ces contrôles fraîches absentes. Replay du contexte
Q4 avec tokenizer réel, sans API/modèle : 1 524→1 482 jetons, budget 1 536
inchangé. Source appliquée et replay causal concordent ; preuve de séparation
données/consignes, aucune cause interne LLM unique affirmée. R110
`document-evidence-data-boundary-source-and-q4-partial-cold-independent-review-110.json`
(`0ba76574`) valide source et froid Q4 ; décision W058 actualisée par ROOT.
Trois dérivés privés seulement retirés : 133 112 056 octets logiques,
134 844 416 octets alloués ; gain libre observé 134 713 344 octets non exclusif.
`cleanup-after-01.json` (`7f30e1bc`), vraie récolte `404f3b/0`, opérateur frais
absent ; préimages, RED/GREEN, replays et goldens conservés.

Q5 sous `root/qmix-document-formula-context-20261011/dev-gpu-05/` réutilise
la DATA froide Q4 (7/46, quatre documents/19 points), sans import ni clone.
**Q-MIX PASS sur ce cas seul**, query `71859cd3-ff8c-44b5-8d16-c72478fbd042`,
97,900 s, DONE/stop/255 jetons. Trois documents nommés et 72 V attribués,
B2 littérale/C2 formule sans cache ; aucun résultat calculé, historique
ni fraîcheur inventé. ROOT `cb401aac`, R112
`c07-dev-gpu-q5-qmix-independent-actual-adjudication-review-112.json`
(`8bb46309`). **A-MIX PASS sur ce cas seul**, query
`eaba7542-e1e3-42f1-916e-7f82665f0ba1`, 112,060 s, DONE/stop/947 jetons ;
faits, concordance et limites correctement séparés, indépendance non déduite.
ROOT `cbe14062`, R113
`c07-dev-gpu-q5-amix-independent-actual-adjudication-review-113.json`
(`475670ef`). SSE/DONE/texte/SQL égaux ; deux POST/2 appels modèle au total,
mode GPU sans repli et résidence observée `size_vram=3107811491`.
Après A-MIX : 9 queries/60 citations, anciennes7/46 exactes.

A-BOUNDED-TOTAL : premier helper QA refuse `KeyError: bindings`
(`9e2672/1`) avant query/modèle ; original conservé, reprise distincte encore
en préparation. CMP4 non dispatché, lecteurs et froid Q5 non acquis.
Les anciens FAIL restent des preuves historiques, aucun PASS C07 global
ni matériel/CPU physique ≤ 16 Go/Windows/x86-64/corpus final déduit. Nouveau
kit corrigé et recette CPU locale nécessaires après publication ; estimation
locale à réviser après les cas restants, globale : 40–90 h effectives après T0
et disponibilité des hôtes/corpus requis.

### DEV Q5 : total borné erroné et fermeture froide — 16:13 UTC

Le checkpoint 15:47 ci-dessus reste historique. Après les PASS Q-MIX/A-MIX,
A-BOUNDED-TOTAL01 échoue avant query sur le helper QA, `KeyError: bindings` :
`root-bounded-prequery-failure-01.json` (`c6c60a1e`), summary01 (`ac93125c`),
résultat1 (`170fb085`), 0 query POST/0 modèle. Les projections cellule ne
portent pas les bindings du bloc parent ; aucun défaut produit établi.
Adaptateur QA02 strict, parent hashé/identité/cellule/offsets/exclusion B3
conservés : trois contextes enregistrés PASS et huit mutations refusées,
preuve pure `1d26dca5`, R114
`c07-dev-gpu-q5-bounded-prequery-failure-and-projected-bindings-qa-retry-independent-review-114.json`
(`89f456af`). Ancien runner/échec01 conservés, source72fd et oracles inchangés.

Reprise02 unique sur la même instance/DATA : query
`053f0b3a-b167-462a-a347-b23fbe7f3ba9`, 145,039 s, DONE/stop/768 jetons,
1 POST/1 appel modèle ; SSE/DONE/SQL égaux, collecte mécanique réussie.
**FAIL sémantique** : résultat théorique LEN=6 donné malgré cache absent,
capacités d'exécution/simulation attribuées au document sans preuve. Absence
de total global correctement reconnue, sans compenser ces défauts. ROOT
`root-bounded-semantic-02.json` (`2beb7eec`), R115
`c07-dev-gpu-q5-bounded-retry02-independent-actual-adjudication-review-115.json`
(`7d1b1410`). Deux PASS/1 FAIL au total ; CMP4/lecteurs non dispatchés.
Cause interne du générateur inconnue, aucun recalcul moteur prouvé.

Fermeture nominale : down/finish, owner20285 réellement récolté `35511a/0`,
puis capture HOST `59023d/0` et finaliseur distinct `2f73ba/0` (0,477 s).
`dev-gpu-05/host-final-dev.json` (`f6fbd5b7`),
`root-cold-harvest-01.json` (`01ff084d`) et RAW31
`sql-host-stopped-dev-raw31.json` (`205fbf79`) lient 31 tables,
10 queries/63 citations, anciens7/46 et quatre originaux/source77/export
exacts ; RAW égal au dernier snapshot du cas02. 521 vies connues fraîches
absentes, plus opérateur froid2621858/birth1791734824.56 absent après son
vrai retour0 : 522 total, aucune absence globale. Qdrant19 reste la baseline
préquery, sans mesure postquery inventée. Finaliseur initial `5d022a23`
conservé ; version02 `96586781` raccorde le cas02 et garde explicitement
l'échec01/0query/0modèle avec SQL9/60 égale à A-MIX-after/retry-before.

Prochaine action proposée, sans implémentation anticipée : correction
candidate des consignes sur les formules, puis Q6 réutilisant la DATA10/63.
Total borné d'abord ; les trois autres cas ne suivent que si ROOT valide
la réponse, revue indépendante consolidée avant lecteurs. Aucun changement
des oracles/questions/quotas, aucune grille de paramètres. Estimation ROOT
17 h 50–18 h 10 Casablanca correction/recette, puis kit corrigé/CPU
18 h 50–19 h 20 **si vert**. Ces fenêtres sont conditionnelles ; livraison
finale, C07/I05, I07/I08, NF09, DoD et plateformes/corpus absents restent
ouverts. Global : 40–90 h effectives après T0/hôtes/corpus requis ; aucune date
absolue fiable sans ces préconditions.

### DEV Q6 : échec du total borné et fermeture froide

Relevé du 11 octobre à 16:51 UTC. La proposition du checkpoint Q5 est
réellement exécutée sous la source `6324f457`, sans modification des faits,
questions, scopes, modèles ou quotas. R117
`affirmative-typed-cell-policy-source-and-q6-common-conditional-independent-review-117.json`
valide le remplacement SYSTEM général et ses contrôles : 23 RED attendus sur
29 tests de l’ancienne instruction, puis 112 PASS ciblés et Ruff0 ; mypy
antérieur explicitement réutilisé sur preuve AST/types, aucun nouveau mypy
revendiqué. Replay corrigé sur les contextes capturés : seules les consignes
SYSTEM changent, métriques utilisateur/extraits/citations inchangés et budget
maintenu. L’échec du premier helper de replay reste conservé.

Une seule génération Q6, dossier
`.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/dev-gpu-06/` :
A-BOUNDED-TOTAL query `19a0902a-0067-4122-a514-c3c792f30599`, 176,221 s,
DONE/stop/1 032 jetons sur budget 1 536, 1 POST/1 appel modèle. GPU/fallback
false, résidence observée 3 107 811 491 octets VRAM. SSE/DONE/answer/message
SQL concordants. **FAIL sémantique** : « CCU-21 » présenté comme cinq
caractères, résultat LEN=5 non enregistré et formule dite active à partir de
sa seule présence. Le total global est correctement refusé, B2 littérale
72 V et C2/cache absent sont conservés, B3 hors scope non transmis ; ces
faits conformes ne compensent pas les affirmations inventées. Aucun recalcul
moteur ni cause interne unique du générateur démontrés. ROOT
`root-bounded-semantic-01.json` (`d5d4e2ea`), R118
`c07-dev-gpu-q6-bounded-actual-and-typed-contract-independent-review-118.json`
(`ef00da7b`) conservent ce FAIL. Q-MIX/A-MIX/CMP4 et lecteurs non dispatchés.
L’avertissement sur la valeur5 correspond au défaut observé ; la valeur2
est une coordonnée de ligne, faux positif d’avertissement distinct à corriger.
Les warnings n’altèrent pas la réponse générée.

Fermeture nominale : down `2cda36/0` (7,359 s), finish `bc9f88/0`, owner82422
réellement récolté `0193c1/0`, puis capture HOST `ec0386/0` et finaliseur
`0c1e10/0` (0,399 s). Aucun nouveau patch du finaliseur acquis `cb649c1f`.
`host-final-dev.json` (`72c27b25`), RAW31
`sql-host-stopped-dev-raw31.json` (`40e2edc9`), manifeste réel
`cold-manifest-actual-01.json` (`14ab3a37`) et récolte froide
`root-cold-harvest-01.json` (`d45c9a61`) : 31 tables, 11 queries/66 citations,
anciens10/63 exacts, quatre originaux/77 sources6324/export exacts à froid,
RAW égal au dernier snapshot du cas. Union586 vies connues fraîches absentes,
collecteur compris ; opérateur froid2654893/birth1791737241.4 réellement
revenu0 puis fraîchement absent : **587 total**, aucune absence globale.
Qdrant19 est la baseline préquery ; aucune mesure postquery inventée.
Le statut `DEV_PARTIAL_COLD_CLOSURE_NOT_FOUR_CASE_PASS` qualifie l’arrêt
et la conservation, sans requalifier la réponse ni les cas non exécutés.

**Suite proposée :** plus de variant de consigne. R118 recommande une
restitution dont les références sont validées et les valeurs/états rendus
depuis les faits typés autoritaires. Le nouveau contrat de réponse, son
streaming/stockage/interface et sa qualification nécessitent un arbitrage
explicite au regard de W037 ; aucune réécriture cachée de la prose ni
requalification des FAIL historiques. Le faux positif d’avertissement sur
le numéro de ligne constitue un correctif indépendant, non réalisé à ce
checkpoint. Dernier kit et CPU suspendus ; C07/I05, I07/I08, NF09, DoD et
plateformes/corpus absents restent ouverts. Cible ROOT du jalon : 17 h 50
Casablanca. Global : 40–90 h effectives après T0/hôtes et corpus requis,
sans date absolue fiable ni échéance de kit confirmée avant arbitrage.

### Retour SYSTEM et correction des avertissements de coordonnées

Relevé du 11 octobre à 17:14 UTC. Après la fermeture Q6, retrait exact du
seul candidat SYSTEM `6324f457` et de ses quatre attentes de tests : contexte
restauré `72fd5175`, reçu `rollback-01.json` (`13142690`). Les corrections
structurelles déjà vérifiées restent présentes. Le FAIL Q6, sa réponse,
SSE, citations, données, sources exécutées et reçus froids restent inchangés.
L’addendum froid indépendant R118 (`011d8d43`) confirme cette fermeture
partielle, sans requalifier la réponse.

Correction additive dans `services/api/claims.py`, source finale
`aa858413`, tests answerchecks `d46d622c` : les coordonnées de ligne XLSX
admises sont distinguées des quantités ; les alertes sur les valeurs non
étayées demeurent. Replay pur de Q6, sans API ni modèle : anciennes alertes
2/5, nouvelle alerte 5 seule ; texte/DONE/SSE/citations/contexte et objets
sources exacts. La correction ne supprime ni ne réécrit l’affirmation erronée
LEN=5 ou l’activité inventée de la formule, et ne transforme pas Q6 en PASS.

Preuves sous
`.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/row-coordinate-warning-fix-08/` :
completion `0a47cb37`, replay final03 `16042f/0`, revue source R119
`typed-row-warning-fix-and-exact-system-rollback-independent-review-119.json`
(`0a8de5cc`). Première implémentation : **173 PASS** sur cinq suites ciblées,
dont 16 nouveaux cas, Ruff0. Refus mypy initial `238cd2/1` conservé ;
raffinement de type du seul garde, puis mypy final `2bb25c/0` (3,001 s),
Ruff final `3c2671/0` et **16 PASS recouvrants** `848e03/0`. 10 000
combinaisons du prédicat équivalentes et AST hors helper identique
(`87453a/0`) justifient le réemploi des contrôles inchangés ; **pas 189 tests
uniques**, pas typage backend/Win32 entier revendiqué. Premiers contrôles
rouges et échecs de replay sont conservés séparément.

Nettoyage F réellement récolté `e6377a/0` : quatre dérivés privés retirés,
138 809 965 octets logiques ; gain libre observé 140 832 768 octets sur volume
partagé, sans attribution exclusive. 22 producteurs connus et opérateur
2672828 fraîchement absents ; sources, préimages, journaux et preuves utiles
retenus, aucune absence globale affirmée. Aucun nouveau runtime ni kit.

**État suivant :** le prototype de restitution XLSX est accepté
explicitement par l'utilisateur. W059 est acquise ; R28-RAG-04 doit
implémenter et vérifier le contrat, sans requalifier Q6. Lectures ciblées
backend et transport/frontend commencées, aucune modification fonctionnelle
de ce mode encore réalisée. Cible 22 h 30 Casablanca pour contrat/recettes,
puis 23 h 30 pour kit/CPU si verts. R28-LLM-01/W060 ajoutent la demande de
profil haute mémoire : comparer aussi d'autres familles que Qwen, identifier,
qualifier puis sélectionner automatiquement les seuls modèles validés.
C07/I05, I07/I08, NF09, DoD et hôtes/corpus absents restent ouverts.

Contrôles documentaires ROOT du 11 octobre, 17:15 UTC : 62 tests PASS
(6,72 s), liens et structure PASS, cinq SVG conformes, brief synchronisé
et pack PASS. Les 12 avertissements sur le rangement de fichiers tiers
des skills restent conservés. Preuves sous `root-final-docs-07/` au même
emplacement QA : JUnit, rapports de contrôles et récolte ROOT ; les
fixtures temporaires sont retirées après récolte, sans supprimer les preuves.
Ces contrôles ne constituent pas une qualification RAG ni une clôture DoD.
