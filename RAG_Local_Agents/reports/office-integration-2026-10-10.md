# Intégration DOCX/XLSX — preuves locales du 10 octobre 2026

**Rôle :** rapport de preuve de l'intégration R28 · **Propriétaire :** intégration et validation · **Statut :** Vivant, contrôles locaux acquis, limites de qualification ouvertes · **Référence :** base `64e191f5d93e7c8e702a3a8b93713a7aac30e458`, sources publiées `57f7f0a6f2feee80adfd35b65bf4d81f6319e74c` et empreintes des sources réellement exécutées · Correctif publié et kit CPU natif vérifié : `22fd828` · **Mis à jour :** 2026-10-10 18:42 (UTC) · **Source de vérité :** reçus natifs cités ci-dessous ; actions dans [PLAN.md](../PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation)

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
