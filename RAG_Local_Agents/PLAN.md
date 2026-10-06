# Plan de réalisation vivant — application réalisée en partie, recette D01–D11 non close

**Rôle :** suivi canonique des travaux autorisés, résultats, blocages et prochaines actions · **Propriétaire :** intégration du chantier · **Statut :** Vivant, chantier en cours · **Référence :** base publiée `461c1f0` et complément daté ci-dessous ; historique W029 conservé · **Mis à jour :** 2026-10-06 05:00 (UTC) · **Source de vérité :** ce plan pour les actions ; [DoD](DEFINITION_OF_DONE.md) pour les critères et [journal](journal/README.md) pour les exécutions

**Objectif actif depuis le `/goal` du 30 septembre 2026 :** réaliser, intégrer et qualifier l'application RAG PDF locale sur Windows natif, sans WSL ni Docker, jusqu'aux critères exacts du plan et de DEFINITION_OF_DONE. L'inspection préalable reste conservée comme référence ; elle n'est pas répétée. Étendu le 1er octobre 2026 à Linux natif (W018) et à l'accélération GPU de la génération (W024, W025).

**Périmètre daté :** inspection des 29/30 septembre 2026 puis réalisation autorisée le 30 septembre, UTC. Brief actif RAG-LOCAL-16 V2.1 (archive vérifiée) et décision utilisateur W001 : **Windows natif, sans WSL ni Docker**, orchestration locale comparable à Docker Compose. Sources, configuration et corpus identifiés par empreintes ; aucun dépôt Git lors de l'inspection (dépôt créé à 08:50, W005). Provisionnement isolé, téléchargements officiels, services locaux, OCR, builds et tests du chantier sont désormais autorisés. Exclusions conservées : modification globale de configuration système, destruction des originaux ou données étrangères, arrêt de services étrangers et déploiement externe. Depuis 08:50 UTC (W005), Git est initialisé et commit/push sont autorisés uniquement vers le remote privé `origin` https://github.com/msedki/agentPDFDoc.git, après chaque travail substantiel vérifié ; corpus, runtimes, modèles, données et secrets restent exclus du dépôt. Résultat attendu : application réelle, preuves de recette et documentation fidèle.

**État initial du brief conservé :** brief et configurations disponibles ; aucun code applicatif à la remise. L'inspection préalable ne valide ni le lot A complet ni D01–D11. Les états courants des lots sont actualisés ci-dessous, sans effacer cette baseline.

## R14/R15 — relecture documentaire et reprise QA, relevé du 4 octobre à 11:05 UTC

**R15-3-Q09 — D06.6 Linux couvert par les preuves existantes, relevé du 6 octobre à 05:00 UTC.**
Sélection native et actions page/bloc : final31/E04 fermé ; sélection OCR :
Q07 ; action de section : Q08. Rapports directs relus ROOT et non-auteur,
captures examinées et continuité des contrats vérifiée contre le code.
F05 change la disposition et la navigation, pas la sémantique de sélection
ou des scopes ; aucun nouveau geste de sélection après F05 n'est revendiqué.
Revue indépendante favorable. Critère de ce lot : synchroniser le statut
Linux et contrôler le suivi, sans nouvelle recette. État : VERIFIED borné,
contrôles documentaires 7/7 et 11/11 PASS, revue finale favorable acceptée.
Windows, ancres à 95 % et DoD globale restent ouverts.
[Preuves et méthodes](journal/2026-10-06.md#r15-3-q09--sélection-et-actions-réconciliation-des-preuves).

**R11-LNX-01 — D09.4 couvert par la migration de pipeline W029, réconciliation du 6 octobre à 04:50 UTC.**
Le critère demande une migration de schéma **ou de pipeline**, une nouvelle
génération contrôlée et un retour arrière documenté. Les métadonnées fermées
de W029 prouvent déjà un changement d'empreinte sur la même version, une
nouvelle génération active et la conservation des anciennes citations.
Lecture ROOT et vérification indépendante concordantes ; politique de
publication inchangée depuis cette preuve. Le motif Linux « absence de
sauvegarde au schéma 2 » ne bloque donc plus D09.4 ; une migration SQLite
sous Linux reste non exécutée. Aucun service, corpus ou test applicatif relancé.
Critère de ce lot : relier le statut Linux à ces preuves exactes, contrôler
le suivi modifié et obtenir sa relecture finale avant publication. État :
VERIFIED borné — suivi synchronisé, contrôles 7/7 et 11/11 PASS, avis final
indépendant favorable accepté ; publication du seul lot, DoD globale ouverte.
[Preuves et limites](journal/2026-10-06.md#r11-lnx-01--migration-de-pipeline-déjà-prouvée).

**R15-3-Q08 — action de section VALIDATED_BOUNDED le 6 octobre à 04:40 UTC.**
Un seul parcours sommaire → action explicite → recherche UI, deux recherches
réelles : témoin bibliothèque avec 18 blocs QLONG distincts hors section ;
section avec six passages et 21 fragments correspondant aux 21 blocs admis.
Scope, version, génération, révision, hashes et offsets vérifiés ; captures
aux deux tailles vues ROOT. Aucune question, import, OCR ou réextraction.
Source relue indépendamment, lint et typage ciblés verts ; build livré
inchangé, non reconstruit. Instance arrêtée et données conservées.
Revue native indépendante favorable ; actions page/bloc/OCR non rejouées,
ancres à 95 %, Windows et DoD globale non qualifiés par ce parcours.
[Commandes, identités et limites](journal/2026-10-06.md#r15-3-q08--action-de-section-sur-lextraction-publiée).

**R15-3-F05 — correction de navigation VALIDATED_BOUNDED le 6 octobre à 04:18 UTC.**
Viewport périmé exclu, dimensions provisoires et offsets cohérents,
position conservée quand les mesures changent, défilement manuel préservé.
342 unités, lint, typage et nouvel export conformes ; même parcours réel
S005/page14 → document1 → source14 puis resize 1366→1920 : PASS strict,
neuf overlays et six spans natifs couverts, visibles et peints. Trois captures
vues par ROOT et le vérificateur non-auteur ; avis final natif favorable.
Instance arrêtée, données conservées, deux essais rouges préservés.
D06.5 reste ouvert : une citation ne qualifie pas 95 % du corpus.
[Critère et preuves](journal/2026-10-06.md#r15-3-f05--citation-page-14-déviée-vers-la-page-13).

**Reprise limitée aux travaux nécessaires, demande du 6 octobre.**
Pas de campagne exhaustive, corpus accru, apprentissage supplémentaire ou
rejeu de contrôles applicatifs sur des entrées inchangées. Les autres critères
ouverts restent visibles sans être cochés ni déclencher automatiquement un
lot futur. Les limites OCR P02 et qualité 2B restent celles du diagnostic
clos ci-dessous ; aucune nouvelle tentative justifiée par ce seul correctif.

**R23-OCR-01 — diagnostic ciblé clos le 6 octobre à 03:36 UTC, sans correction prouvée.**
La relecture du code et des sorties P/F confirme l'erreur `DA-PO2`
dans l'OCR brut d'une région entière, sans crop ni reprise de ligne.
Le pilote réussi S utilise des lignes isolées et une segmentation différente ;
il ne qualifie pas ce chemin PDF. Aucun défaut de chargement du candidat
n'est établi. Le contexte et la segmentation restent une hypothèse, pas
une cause démontrée ni un correctif acquis. Refus d'adoption conservé,
R23-OCR-01/D02 ouverts. Ce constat ne justifie ni nouvelle campagne
ni apprentissage. Les contrôles applicatifs déjà acquis sur des
sources inchangées ne sont pas rejoués.
[Frontière vérifiée et limites](journal/2026-10-06.md#r23-ocr-01--limite-du-pilote-ligne-et-fin-du-diagnostic).

**R23 — candidat éditorial 2B refusé le 6 octobre à 03:23:45 UTC.**
Une question originale, quatre preuves gelées, un seul chat GPU : 503 tokens
locaux/réels, sortie complète de 87 tokens. Le jugement de fiabilité disparaît,
mais la réponse ajoute révision/pression hors demande et cite S001, qui ne
porte pas la pression. Critère éditorial non satisfait, confirmé indépendamment.
Les deux phrases candidates sont retirées ; consigne produit inchangée.
Garde de synonymie QueryService et frontières de contexte renforcées conservées,
28 tests livrés PASS. Pas de deuxième chat, corpus ou apprentissage.
R23/D05 restent ouverts ; ne pas engager une campagne pour ce seul essai.
[Décision W037](DECISIONS.md#w037-candidat-éditorial-2b-refusé-après-un-témoin-unique) ;
[preuve et limites](journal/2026-10-06.md#r23--correction-ciblée-du-jugement-2b).

**R23 — admission froide 2B mesurée le 6 octobre à 02:56 UTC.**
Un seul pilote CPU fermé, trois conditions intégrées et 349 sondes :
baisse hôte maximale 3418,793 Mio. Ancienne marge de 37,207 Mio insuffisante ;
borne du seul profil 2B portée à 3584 Mio, marge 165,207 et réserve 1536
conservée. Profil 4B inchangé, chaud 512 toujours provisoire. Trois essais
à 2959/64 tokens, identités et arrêt relus indépendamment ; 83 unités PASS
sur sélection, admission et documentation. Pas de D07, plateforme Windows,
GPU ou qualité DEV qualifiés. Défaut OCR P02 et jugement injustifié du 2B
restent ouverts ; aucune nouvelle campagne ou boucle de prompts admise ici.
[Décision W036](DECISIONS.md#w036-admission-froide-du-2b-fondée-sur-un-pilote-cpu-local) ;
[preuves et reprise](journal/2026-10-06.md#r23--mesure-cpu-2b-bornée-admission-du-6-octobre-à-0253-utc).

**R23-OCR-01 — discriminant de langue fermé en refus le 6 octobre à 02:37:18 UTC.**
Un seul essai P02, candidat/PDF/rasters/moteur/seuils conservés, `fra` seul.
Les signes « ± » et « N·m » sont rétablis, mais quatre références narratives
restent incorrectes et les trois références du tableau régressent. Un fait
complet exact sur cinq, douze régions faibles : `ready_partial`, aucune
adoption. Changement global de langue écarté, profil bilingue conservé.
Relecture, arrêt et ressources conformes. Diagnostic des mots fermé :
une reprise des seuls mots faibles laisserait plusieurs références erronées.
Pas de correctif prouvé ; prochain lot indépendant : admission mémoire R23
à partir des mesures existantes. Aucun corpus accru, apprentissage ou nouveau passage
natif admis ici ; R23-OCR-01/D02 restent ouverts.
[Comparaison et reprise](journal/2026-10-06.md#discriminant-de-langue-p02--préparation-distincte).

**R23-OCR-01 — contrôle P02 fermé en refus le 6 octobre à 02:20:56 UTC.**
Une seule extraction des deux pages gelées, avec le candidat isolé et les
paramètres d'ingestion conservés. Worker EXIT0, mais `ready_partial` :
cinq régions sous le seuil de confiance, « ± » devient « + », « N·m »
devient « N-m » et quatre références DA-P02 sont altérées. Tableau exact,
entrées et nominal conservés ; aucun artefact adopté. R23-OCR-03 qualifie
les lignes du pilote, pas l'ingestion PDF. Relecture et diagnostic des
sorties existantes terminés ; sérialisation écartée, cause OCR non établie.
Piste identifiée à ce relevé : distinguer `fra` de `fra+eng` sur ce même
témoin avant toute correction, sans admission native acquise ici.
Aucun nouvel apprentissage, corpus accru, seuil abaissé
ou rejeu applicatif inchangé ; R23-OCR-01/D02 restent ouverts.
[Résultats et reprise](journal/2026-10-06.md#r23-ocr-01--p02-avec-le-candidat-isolé).

**R23-OCR-03 — pilote qualifié le 6 octobre à 01:57:09 UTC.**
Un seul taux changé à 0,001, 500 itérations et données existantes conservées ;
aucune préparation supplémentaire. Neuf tests ciblés, Ruff/mypy et relecture
source conformes. Dix premières sorties sans refus certain, puis 400 variantes
réelles par bras : tous les critères d'origine PASS. Recalcul indépendant
des 800 sorties conforme ; deux omissions de « ± » subsistent à 28 px, sans
abaissement du seuil. Pilote seulement `VALIDATED_BOUNDED`, sans adoption.
Action identifiée à ce relevé dans R23-OCR-01 : extraire les deux pages du
P02 synthétique gelé avec le candidat isolé et contrôler littéralement les
signes, faits, tables et provenance, avant toute utilisation nominale.
Pas de nouvel apprentissage, volume accru ou rejeu applicatif inchangé.
[Résultat, limites et reprise](journal/2026-10-06.md#r23-ocr-03--taux-mainteneur-et-refus-anticipé).

**R23-OCR-03 — essai sur préparation réutilisée fermé le 6 octobre à 01:00 UTC, candidat refusé.**
Raccord privé G fermé : 25 tests PASS, Ruff/mypy conformes et avis
indépendant `GO_SOURCE_PREPARED_REUSE_ONLY` accepté. La préparation L
complète reste une entrée immuable ; checkpoint échoué exclu, sorties G
neuves, superviseur et critères inchangés. Préflight ROOT frais conforme.
Admission limitée à une invocation du parent existant, avec revalidation
des entrées sous verrou, puis train/export/évaluation. Aucun gain ou
succès natif anticipé ; aucune suite frontend inchangée rejouée.
Cette invocation s'est fermée avant enfant à 00:47:10 UTC : le scanner
refuse deux liens de répertoire temporaire créés par pytest dans G.
Pas d'OCR lancé dans G. QA native G2 sans fixtures, raccord relu et
préflight/admission distincts conformes ; passage fermé en 387,158 s.
Préparation réutilisée sans régénération ; train réel 323/500/500, export
et 400 évaluations par bras exécutés. 810 commandes EXIT0, mais critère
scientifique refusé : aucun « ± » ou « · » reconnu, aux deux tailles.
CER global candidat 1,54 %, non-régression conforme : ces succès ne
valident pas les signes. Modèle nominal conservé, aucune adoption ni
clôture D02/R23 déduite. Résultat et arrêt corroborés indépendamment.
Diagnostic ciblé fermé à 01:22:58 UTC : alphabet/GT conformes ; une seule
commande `lstmeval` sur deux variantes heldout, sans dictionnaire, confirme
les substitutions. Les lexiques ne suffisent pas à expliquer ces deux
échecs ; apprentissage insuffisant plausible, correction non démontrée.
Prochaine action : préparer seulement un réglage de pilote justifié et
relu avant admission distincte ; pas de volume accru, nouvelle campagne,
rejeu des tests verts ou critères abaissés.
[Admission et preuves](journal/2026-10-06.md#r23-ocr-03--réutilisation-de-la-préparation-complète).
[Diagnostic minimal](journal/2026-10-06.md#r23-ocr-03--diagnostic-minimal-des-signes).

**R23-OCR-03 — correctif CLI et ordre, source/tests validés le 6 octobre.**
Booléens train/export corrigés ; vue d'apprentissage interlacée par groupes,
sans modifier les listes canoniques, les 1 600/400 membres, les critères ou
les budgets. 34 tests ciblés PASS, Ruff et mypy conformes. ROOT a contrôlé
la vue sur les métadonnées réellement préparées : cinq familles et les
signes dès les 100 premiers exemples. Revue non-auteur
`GO_SOURCE_CLI_ORDER_ONLY` acceptée, pas de nouvelle préparation ou
d'apprentissage. Le correctif privé n'est pas un raccord natif complet.
Témoin du parseur réel PASS : anciens arguments refusés avant toute
écriture, nouveaux réglages tous pris en compte par l'aide, sans poids.
Prochaine action : raccord minimal utilisant en lecture seule les entrées
complètes déjà vérifiées ; revue puis admission distincte avant un pilote.
Aucun build/E2E inchangé à rejouer, volume supplémentaire ou régénération
des 2 000 entrées justifiés par ce correctif.
[Résultats, limites et reprise](journal/2026-10-06.md#r23-ocr-03--correctif-cli-et-ordre-des-exemples).

**R23-OCR-03 — passage unique fermé en échec le 5 octobre à 23:49:24 UTC.**
Décision distincte ROOT après avis indépendant de proportionnalité et
préflight frais : un seul pilote corrigé dans la cible L neuve, sans nouvelle
méthode, réduction des critères ni relance automatique. Le volume gelé est
réutilisé, pas déclaré indispensable. Application et modèle nominal inchangés.
Parent existant lancé une fois (`e98934`/`6be975 EXIT1`, handle `99697`).
Préparation complète en moins de 900 s, 2 000 LSTMF vérifiés ; commande
d'apprentissage EXIT0 mais garde refusée : compteur `learning` nul et taux
différent du réglage demandé. Causes établies : booléen séparé interrompant
le parseur CLI, puis premières lignes sans les signes visés dans la liste
groupée. Aucun export, évaluation ou candidat adopté ; 4 003 identités
absentes, verrou libéré, modèle nominal conforme au verrou officiel.
Relecture indépendante favorable à ces constats bornés, pas à la qualité.
Prochaine action nécessaire : corriger la syntaxe des booléens et la seule
vue d'apprentissage, tester ces deux défauts sans changer membres, volume,
seuils ou budgets. Pas de nouvelle exécution native automatiquement admise.
[Admission W035](DECISIONS.md#admission-du-passage-unique--5-octobre-2334-utc),
[préflight, résultat et diagnostic](journal/2026-10-05.md#r23-ocr-03--admission-du-passage-unique-corrigé).

**R23-OCR-03 — reprise limitée, relevé historique du 5 octobre à 23:13 UTC.**
Le défaut « ± » lu « + » bloque la fidélité de ces valeurs, pas la sélection
Q07 désormais validée. Une seule alternative officielle restante examinée :
best/script/Latin, composant 21 seulement, 18 Ko lus ; « ± » absent.
Cette piste est écartée sans téléchargement des poids, OCR ou installation.
La correction est nécessaire pour qualifier ces signes ; le volume de
1 000 groupes / 2 000 variantes n'est pas démontré indispensable.
Pas d'apprentissage admis ni de relance automatique de W035 dans cette
reprise, pas de nouvelle campagne ou de réduction improvisée des critères.
Prochaine action de ce lot : retenir une correction proportionnée au défaut
avant une admission distincte ; le pilote préparé et les échecs sont conservés.
Les critères non vérifiés restent ouverts, aucune clôture globale déduite.
[Résultat et décision de suite](journal/2026-10-05.md#nécessité-de-correction-ocr--contrôle-ciblé-après-q07).

**R15-3-Q07 — sélection OCR D06.6 Linux, VALIDATED_BOUNDED le 5 octobre à 22:56 UTC.**
Manque de preuve traité, aucun défaut produit établi. Test canonique,
méthode/source relues indépendamment, typage/lint ciblés verts. Un seul
scan synthétique importé par l'interface, vraie extraction OCR publiée
avec géométrie. Premier FAIL conservé : oracle QA mélangeant `innerText`
et `textContent`, corrigé sans enlever le contrôle du périmètre.
Second essai sur la même publication, sans réimport/OCR : un PASS strict
sans retry/skip/flaky, souris réelle et captures utiles aux deux tailles,
expression « pression de 3.8 bar » ; révision/hash/offsets Unicode et texte
exact corroborés par deux recherches réelles. Zéro génération, erreur de
garde ou appel externe. Captures vues ROOT, instance arrêtée, 22 PID
possédés absents, ports libres et deux originaux/publications conservés.
Pas de campagne, apprentissage ni rebuild inchangé. Limite qualité :
« ± » devient « + » hors sélection ; aucune qualité OCR métier qualifiée.
Windows, actions page/section, ancres et DoD globale ne sont pas cochés
par ce lot. Avis indépendant natif et de publication favorables acceptés
ROOT ; contrôles documentaires 7/7 et pack 11/11 conformes, brief synchronisé.
Lot fermé dans cette portée ; publication selon la politique du dépôt.
Prochaine action : traiter uniquement un défaut ou manque de preuve nécessaire
à l'usage local, sans campagne inchangée ni apprentissage non justifié.
[Sources](SOURCES.md#q07--sélection-ocr-par-le-navigateur),
[exécution](journal/2026-10-05.md#q07--sélection-dun-texte-ocr-réel).

**R15-3-Q06 — D06.9 Linux, VALIDATED_BOUNDED le 5 octobre.** Sur le PDF
synthétique déjà indexé et le modèle 2B réel : progression visible, vraie
coupure/reprise SSE sans nouvelle question et annulation après génération
effective. Auteur et vérificateur indépendants ; Q05 publié dans `1e20a58`
n'est pas rejoué. Deux FAILED conservés : coupure QA insuffisante, puis
faux diagnostic de collection absente sur erreur de lecture. Correctif
API borné et 29 tests HTTP isolés PASS, typage/lint affectés conformes.
Troisième recette native : un PASS strict sans retry/skip/flaky, reprise
après ID6 sans doublons, réponse limitée puis seconde question annulée ;
activité et bail libérés, GPU sans repli, deux appels modèle seulement.
Avis indépendant `GO_NATIVE_D06_9_LINUX_BOUNDED` accepté ROOT. Préfixe UI
observé avant terminal : « # » ; ce contrôle ne qualifie ni la lisibilité
de la progression, ni la qualité métier ou le temps du premier mot utile.
Instance arrêtée, treize PID possédés absents, ports libres et conservation
bornée vérifiée. Aucun rebuild, import, réindexation ou apprentissage nouveau.
Documentation affectée contrôlée : espace documentaire 7/7, pack 11/11,
brief synchronisé ; relecture documentaire finale acceptée le 5 octobre à 22:35 UTC. Windows,
sélection OCR, ancres métier, D07 et DoD globale restent ouverts.
Lot terminé dans cette portée, publication selon la politique du dépôt.
Prochaine action : traiter uniquement le
prochain défaut ou manque de preuve nécessaire à l'usage local.
[Sources de méthode](SOURCES.md#d069--coupure-réseau-et-observation-du-flux-réel).
[Exécution et prochaine action](journal/2026-10-05.md#d069--flux-progressif-reconnexion-et-annulation).

**État courant Q05 du 5 octobre à 21:36 UTC : VALIDATED_BOUNDED** pour
les pixels, la capture utile à 300 % et le budget du lecteur. Test canonique
corrigé, aucun changement produit ; 20 tests purs d'oracle/cadrage et cinq
de session PASS, typage/lint affectés conformes. Premier essai PASS technique
mais capture blanche : objection ROOT/non-auteur conservée, pas promue.
Second essai après correction du seul cadrage : un PASS sans retry/skip/flaky,
127 lectures peintes, pic de 5 canvases et 21 605 280 pixels, détachés : 0 pixel.
Capture à 300 % réellement vue ROOT/non-auteur, QLONG-P01-1/-2/-3 lisibles ;
identité/version/page/zoom reliés au résultat. Avis indépendant favorable
dans cette portée, arrêt natif conforme et treize PID possédés absents.
Export R23 exact réutilisé, aucun rebuild ni réindexation au second essai.
Les FAILED historiques et leurs causes inconnues sont conservés, sans
promotion ; fin de RenderTask, ancres métier, Windows/poste de 16 Go et DoD non acquis.
Contrôles des documents affectés conformes, relecture finale indépendante
acceptée le même jour à 21:40 UTC ; lot prêt à publication. Reprendre ensuite
le prochain blocage d'usage établi, sans campagne large ni pilote OCR non justifié.
[Commandes, preuves et reprise](journal/2026-10-05.md#q05--oracle-de-peinture-et-recette-canonique-isolée).

**Priorité d'exécution actualisée le 5 octobre à 21:00 UTC :** demande
utilisateur de procéder par étapes et de n'exécuter que le nécessaire,
sans exhaustivité inutile. Réutiliser les preuves encore applicables,
traiter les blocages concrets de l'usage local et leurs non-régressions.
Ne pas ouvrir une campagne large ou un apprentissage sans établir son
utilité pour le résultat demandé. Le pilote L n'est pas lancé : vérifier
d'abord cette nécessité, puis reprendre seulement le lot justifié.
Les critères DoD et les résultats historiques restent inchangés ; une
qualification reportée n'est pas déclarée acquise. Cette priorité remplace
le lancement immédiat proposé à 20:54, pas les preuves de fidélité.

**Complément du 5 octobre à 20:54 UTC :** avis final non-auteur fermé,
lu et accepté ROOT, `GO_RENDER_EQUIVALENCE_FIDELITY_ONLY`. R23-OCR-03-RD :
sources, tests et fidélité de l'échantillon natif validés dans leur portée.
Les dix paires réelles/cinq familles sont corroborées indépendamment,
ainsi que quarante fichiers, pins et fermeture après publication.
Prochaine action : préflight frais et admission distincte du pilote complet,
dans sa cible neuve, sous W035 inchangé. Ni préparation complète en 900 s,
apprentissage, qualité OCR, gain global ou Done acquis.
[Avis final et reprise](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).

**Complément du 5 octobre à 20:48 UTC :** témoin de fidélité exécuté une
fois après avis de méthode accepté et préflight frais. Parent et worker
EXIT0, dix paires/cinq familles, vingt rendus et quarante fichiers PNG/GT
réels identiques ; neuf pins avant/après/actuels conformes, deux threads
morts, ressources et contrôle après publication conformes. Validation finale
non-auteur en cours ; aucun gain extrapolé, préparation complète,
apprentissage ou Done déduit. Prochaine action : fermer cette validation,
puis admission distincte du pilote complet si le résultat est confirmé.
[Exécution, preuves et limites](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).

**Complément du 5 octobre à 20:43 UTC :** témoin de fidélité du rendu
fermé côté auteurs : 28 tests purs worker et 14 tests purs parent/config
PASS, lint et typage ciblés conformes. Sources, configuration et reçus
gelés ; rouge initial du test et refus du composeur AST conservés.
R23-OCR-03-RD reste validé source-only ; la fidélité native reste ouverte.
Prochaine action : lire et accepter la revue non-auteur du témoin, puis
préflight frais et exécution unique bornée si conforme. Aucun PNG/GT
réel nouveau, apprentissage, gain ou Done déduit des doubles.
[Preuves, limites et reprise](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).

**Complément du 5 octobre à 20:18 UTC :** avis non-auteur fermé lu et
accepté ROOT, `GO_RENDER_LANES_SOURCE_ONLY`. R23-OCR-03-RD : source,
raccord et vérification pure validés dans cette portée ; identité des
pixels et préparation native restent non vérifiées. Documentation
7/7, pack 11/11, brief et cinq SVG conformes ; douze avertissements
tiers préexistants conservés. Prochaine action inchangée : fermer les
sources/tests du témoin de fidélité puis sa revue et son admission
distinctes. [Avis, preuves et limites](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).
Aucune clôture du pilote, de l'apprentissage, de P02 ou de la DoD.

**Relevé du 5 octobre à 20:12 UTC :** R23-OCR-03-RD, sources et raccord
gelés ; 27 tests purs de rendu et 14 de raccordement PASS, lint/typage
ciblés verts. Revue indépendante du bundle en fermeture : aucun avis
source encore accepté ROOT à ce relevé. Aucun rendu réel nouveau ou
pilote exécuté. Prochaine action : accepter l'avis fermé, puis préparer
le témoin de fidélité de dix variantes couvrant les cinq familles,
selon [W035](DECISIONS.md#correction-préparatoire-du-rendu--choix-du-5-octobre-1948-utc).
Livrable préalable : sources du témoin, tests et avis non-auteur ; critère
natif distinct : vingt rendus, quarante fichiers, identité PNG/GT et
fermeture conforme sous les bornes. [Preuves et reprise](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).
Le pilote complet, l'apprentissage, l'adoption et la DoD restent ouverts.

**Complément du 5 octobre à 19:48 UTC :** diagnostic de rendu publié dans
`d981638`. Analyse indépendante des reçus fermés lue et acceptée dans sa
portée : première séquence d'images antérieure aux BOX, durée exacte
inconnue, pas de gain extrapolé. Action **R23-OCR-03-RD**, couche préparation
OCR, **IN_PROGRESS source/tests** : deux lignes de rendu/publication au plus,
collecte canonique, scans et manifeste avant BOX inchangés. Dépendances :
diagnostic fermé et [choix W035](DECISIONS.md#correction-préparatoire-du-rendu--choix-du-5-octobre-1948-utc).
Livrable : sources distinctes, tests discriminants et revue non-auteur ;
validation native séparée requise avant toute affirmation de fidélité ou de
gain. Prochaine action : fermer et relire le correctif, puis son raccord
réel. Ni relance du pilote, ni apprentissage ou Done nouveau acquis.
[Cibles, preuves, ressources et estimation](journal/2026-10-05.md#r23-ocr-03--correction-du-rendu-et-de-la-publication-initiale).

**Complément du 5 octobre à 19:28 UTC :** validation finale indépendante
du témoin acceptée après lecture du rapport fermé et de sa portée. Les
huit paires, mesures et fermetures sont corroborées ; ni pilote complet,
gain de cache ou admission OCR déduits. Prochaine action : analyser les
reçus du pilote interrompu, sans le relancer, pour choisir la correction.
[Avis final et limites](journal/2026-10-05.md#r23-ocr-03--diagnostic-du-rendu-et-de-sa-publication).

**Relevé du 5 octobre à 19:24 UTC :** témoin de rendu exécuté une fois
après revue de méthode et préflight frais. Parent et worker EXIT0 ; huit
paires, seize rendus et 32 fichiers PNG/GT réels identiques, identités
avant-après-actuelles conformes. Contrôles de ressources et après
publication conformes ; validation finale indépendante en cours. Les
mesures ne justifient aucun gain de cache ni extrapolation au pilote.
Prochaine action : fermer cette validation, puis localiser les coûts dans
les reçus du pilote complet avant toute nouvelle correction ou exécution.
[Résultats, limites et reprise](journal/2026-10-05.md#r23-ocr-03--diagnostic-du-rendu-et-de-sa-publication).
Apprentissage, P02 et critères de Done toujours ouverts.

**Relevé du 5 octobre à 19:17 UTC :** sources du témoin de rendu figées
et relues contre leurs originaux. 51 tests purs distincts, lint et typage
ciblés conformes ; erreurs et reprises conservées. Trois anciennes fixtures
négatives sont archivées récupérablement hors de la cible native, sans
changer leurs contenus ou modes. Revue indépendante de méthode en cours ;
aucun rendu réel ou apprentissage acquis. Prochaine action : accepter cette
revue, vérifier ressources et cible fraîches, puis exécuter une fois le
témoin borné si les contrôles passent.
[Sources, contrôles et reprise](journal/2026-10-05.md#r23-ocr-03--diagnostic-du-rendu-et-de-sa-publication).

**Reprise du 5 octobre à 18:45 UTC :** explications sur les données OCR,
l'apprentissage et le CPU/GPU déjà publiées, vérification ciblée non-auteur
en cours. Diagnostic du rendu en préparation dans une QA neuve : huit
variantes comparées à leur version instrumentée, sans cache, reprise de
partiels ou modification des barrières. Sources officielles et versions
relues ; aucun rendu ou résultat natif acquis à ce relevé. Prochaine action :
tests et revue du protocole, puis préflight et lancement borné s'ils passent.
[Périmètre, ressources et estimation](journal/2026-10-05.md#r23-ocr-03--diagnostic-du-rendu-et-de-sa-publication).
Le pilote et les critères de Done restent ouverts. Complément à 18:49 UTC :
revue indépendante de couverture documentaire acceptée, aucun manque
factuel identifié ; elle ne qualifie pas la méthode ou le résultat du témoin.

**Relevé du 5 octobre à 18:17 UTC :** pilote à deux lignes fermé EXIT1
à18:15:03 UTC : `ACTIVE_STAGE_DEADLINE`, 900,46 s, seule étape prepare.
2000 PNG/GT et 1485 BOX/LSTMF sont présents ; cette présence ne valide
pas leur contenu ou une préparation complète. Apprentissage, export,
évaluation et adoption non exécutés. Pins avant/après identiques dans
la clôture ; revue finale non-auteur acceptée à18:28 UTC : qualification
refusée, arrêt/conservation vérifiés dans leur portée bornée. Seuls1483
LSTMF ont un reçu fermé ; deux présences sans reçu ne sont pas admises.
Documentation du lot source/tests et lancement publiée dans `dd5dea6`.
Pas de relance identique ou reprise des partiels : mesurer le coût du
rendu répétitif avant toute nouvelle correction, sans changer données,
seuils, barrières ou budgets. [Fermeture et suite](journal/2026-10-05.md#pilote-à-deux-lignes-arrêté-relevé-1817-utc).

**Relevé du 5 octobre à 18:01 UTC :** correctif de préparation à deux
lignes figé, 51 tests purs et 16 sous-cas conformes ; deux témoins rouges
antérieurs conservés. Le contrôle ROOT de cinq entrées avant/après est
fermé dans une cible distincte après correction d'un collecteur refusant
un journal vide ; aucune assertion affaiblie. Raccord réel de configuration
exécuté, inversion exacte, 32 nouveaux témoins purs et lint/typecheck ciblés
verts. Revue non-auteur du bundle favorable au protocole seulement, lue
et acceptée ROOT. Préflight physique et ressources frais conformes ;
une exécution complète distincte est lancée, session 11165, et doit rester
surveillée sous les bornes W035 inchangées. Aucun apprentissage, gain,
qualité OCR ou critère DoD encore acquis par ce lancement.
[Preuves et suivi de l'exécution](journal/2026-10-05.md#bundle-fermé-et-lancement-unique-relevé-1801-utc).

**Relevé du 5 octobre à 17:32 UTC :** les explications OCR ont été
confrontées au générateur épinglé et relues : W035 précise désormais la
stratification 160/40 par famille et la diversité limitée des cinq gabarits.
Le correctif de préparation à deux lignes au plus est en réalisation
source-only, sans suppression de barrière ou modification du pilote.
Trois sources du parent sont raccordées à une cible neuve avec inversion
exacte ; 11 témoins purs du raccord conformes, composeur et tests contrôlés
par lint/typecheck. La config
et la validation du correctif restent à terminer avant toute exécution.
Le préflight indépendant refuse le parent raccordé : fenêtre TERM avant
capture d'identité. Une nouvelle source avec interruption différée existe ;
11 témoins causaux sur le vrai corps du superviseur avec doubles nommés
passent, ainsi que leur lint/typecheck ciblés. Revue indépendante favorable
au parent dans la portée source/méthode seulement. Premier gel deux lignes
à corriger sur les erreurs de lancement et retours non nuls avant fermeture
raw ; aucun processus natif ou pilote admis. Documentation publiée dans
`c527e6c`, relectures documentaires favorables à leurs snapshots. Ce défaut ne
reconstitue pas la cause des échecs précédents.
[Travail et prochaine reprise](journal/2026-10-05.md#r23-ocr-03--correction-bornée-de-la-préparation-en-cours).
Aucun apprentissage ou critère DoD nouvellement acquis.

**Relevé du 5 octobre à 16:12 UTC :** décomposition raw-close exécutée une
fois après 38 nouveaux tests purs, lint/typecheck verts et revue indépendante
de méthode. Parent EXIT0, reçu fermé et contrôles après publication conformes.
Les intervalles autour de fsync dominent la fenêtre mesurée ; ni cause
matérielle, ni débit du pilote complet, ni gain de performance démontrés.
[Résultat et limites](journal/2026-10-05.md#témoin-exécuté-une-fois-relevé-1612-utc).
Validation finale indépendante acceptée à 16:21 UTC dans la portée
diagnostique ; apprentissage et DoD ouverts.

**Relevé du 5 octobre à 15:09 UTC :** diagnostic OCR distinct exécuté une fois,
EXIT0, huit rendus et seize commandes réussis ; mesures et limites dans le
[journal](journal/2026-10-05.md#diagnostic-exécuté-une-fois-relevé-1509-utc).
Revues native et documentaire non-auteur acceptées dans la portée du lot.
Aucun apprentissage, qualité OCR ou
pilote complet validé. Q05 : composition source-only réelle EXIT0 après
31 tests et revue indépendante préparatoire ; copies réelles relues et
conformes, pas d'instance neuve créée.
[Provenance, frontières et suite](journal/2026-10-05.md#q05--préparation-distincte-de-la-liaison-à-une-cible-neuve).
Les critères D01–D11 restent ouverts selon leurs états propres.

**Relevé du 5 octobre à 02:21 UTC :** correctif causal QA prêt et relu
indépendamment : 10 témoins purs verts après un rouge discriminant, sans
modification du produit ou des anciennes données. Q05 natif reste ouvert :
cible/liaison neuves et préflight requis. Pour P02, procédure d'extension
LSTM rédigée, contrôle de format vert ; avis indépendant de méthode favorable
à la phase outils, sous préconditions, accepté à 01:51 UTC. Sources neuves
conformes au verrou ; protocole figé et relu indépendamment. Configuration
réelle conforme et compilation terminée à 02:09:59 UTC selon W034 :
`PASS_TOOLS_ONLY`, avis final indépendant favorable accepté à 02:21 UTC.
Lot d'outillage seul validé ; aucun entraînement ni adoption.
[Correctif QA](journal/2026-10-05.md#q05--correctif-dentrée-qa-et-témoins-causaux-relevé-0141-utc)
et [phase OCR suivante](journal/2026-10-05.md#r23-ocr-02--procédure-dextension-et-outils-isolés-relevé-0134-utc).

**R23-OCR-01, préflight du 5 octobre à 01:18 UTC :** l'extension LSTM
est documentée, mais les outils ne sont pas construits. ICU/Leptonica sont
présents ; le gate Pango de la configuration standard n'est pas satisfait.
Une construction ciblée sans renderer est une hypothèse tirée du code,
pas un build réussi. Aucun poids, corpus d'entraînement ou candidat adopté.
[Préflight borné et prochaine action](journal/2026-10-05.md#r23-ocr-01--préflight-dextension-lstm-relevé-0118-utc).

**R23-OCR-01, relevé du 5 octobre à 01:04 UTC :** la piste officielle
`tessdata/fra` historique est écartée : les composants 1 et 21 ne couvrent
ni `±` ni `·`. Inspection bornée sans poids, installation ou OCR ; revue
finale favorable au constat et à son préflight, acceptée à 01:28 UTC.
Une extension d'alphabet LSTM n'est qu'une piste
de faisabilité, pas un modèle livré ou un entraînement lancé. Le sous-lot
P03 reste qualifié et publié ; P02 et le gate DEV demeurent non validés.
[Preuves et prochaine action](journal/2026-10-05.md#r23-ocr-01--piste-française-historique-écartée-relevé-0104-utc).

**Publication du 5 octobre à 00:37 UTC :** correctif P03 et preuves publiés
sur `origin/main` dans `d26a3a4`. Extraction, régression d'ingestion, typages
et revue finale sont qualifiés dans leur portée ; pas de republication API
ou de génération DEV anticipée. Prochaine action : voie OCR compatible avec
les signes de P02, puis reprise des jobs affectés et résolution DEV avant
comparaison qualité. [Livraison et conservation](journal/2026-10-05.md#publication-du-sous-lot-p03-relevé-0037-utc).

**R23-OCR-01, validation du 5 octobre à 00:32 UTC :** sous-lot P03
qualifié localement : extraction réelle complète, 236 tests d'ingestion sans
exclusion, lint et typages Linux/win32 verts ; 62 contrôles documentaires,
liens/SVG/brief/dossier conformes. Relecture finale non-auteur favorable
dans cette portée, publication sélective en finalisation. L'erreur de sonde
et les limites des ressources restent conservées. P02, sept publications
DEV, résolution des annotations et qualité 2B/4B restent non validés.
[Validation, preuves et prochaine action](journal/2026-10-05.md#validation-finale-ciblée-relevé-0032-utc).

**R23-OCR-01, relevé du 5 octobre à 00:15 UTC :** contexte de rangée
P03 implémenté, 113 tests avec doubles PASS et extraction native complète
vérifiée : deux pages, aucune région non résolue, tableau littéral exact.
L'erreur initiale de sonde (index supposé) est conservée ; vérification
géométrique séparée réussie, sans réextraction identique. Régression élargie
et relecture indépendante en cours avant livraison. P02 reste non qualifié ;
aucune publication DEV nouvelle ou génération des 100 questions.
[Preuves et reprise](journal/2026-10-05.md#r23-ocr-01--contexte-de-rangée-p03-relevé-0015-utc).

**R23-OCR-01, relevé à 23:56 UTC :** trois essais ciblés sur les rasters DEV
hashés n'ont pas qualifié DA-P02. Le retry ×2 peut même transformer `0`
en `O` malgré une confiance supérieure au seuil. Le contexte de rangée à
densité native restitue correctement les trois cellules contrôlées de P03 ;
son intégration et ses tests sont en cours, pas encore livrés. Une inspection
du contrat officiel et des deux artefacts OCR exacts établit l'absence de
`±` et `·` dans leurs alphabets LSTM : la fidélité P02 ne peut pas être
obtenue par le seul changement de densité ou de PSM. Étude officielle d'une
seule famille de modèles alternatifs en lecture seule ; aucune installation
ni substitution acquise. Pas de génération DEV ou d'assouplissement du gate.
[Essais et limite structurelle](journal/2026-10-04.md#r23-ocr-01--essais-bornés-et-alphabets-relevé-2356-utc).

**Dernier relevé DEV à 23:16 UTC :** gate de publication complète refusé.
Cinq fixtures DEV sont publiées et capturées ; DA-P02 et DA-P03 ont terminé
`ready_partial`, pour confiance OCR insuffisante, sans génération active.
La comparaison des 100 questions n'est pas lancée. QA arrêtée, quatre PID
propres absents et comptes persistants conservés ; aucun seuil ni texte
attendu modifié. Diagnostic indépendant de l'OCR en cours, action R23-OCR-01.
[Défaut et prochaine action](journal/2026-10-04.md#r23--gate-dev-refusé-et-qa-arrêtée-relevé-2316-utc).

**Reprise DEV à 23:07 UTC :** QA conservée redémarrée avec le 2B en mode
GPU ; sept imports synthétiques acceptés, zéro refus. Publications et captures
en cours, aucune génération concurrente. Les 100 annotations et 90 unités
devront être entièrement résolues avant comparaison. Le profil utilisateur
et le corpus privé restent arrêtés. L'outillage documentaire passe 62 tests.
[Exécution](journal/2026-10-04.md#r23--pilotes-gpu-et-préflight-dev-relevé-2258-utc).

**Dernier relevé, 4 octobre à 22:58 UTC :** pilotes GPU séquentiels 2B et
4B terminés, identités verrouillées et arrêts vérifiés puis relus indépendamment.
Pour 2 959 tokens d'entrée : TTFT froid 53,35/67,68 s, prompt répété
0,19/0,23 s, contenu nouveau 4,11/10,54 s. Limite de sortie 64 tokens ;
le 4B s'arrête naturellement à 56 tokens sur le prompt répété. Un essai
par condition seulement : ni p95, ni D07, ni qualification qualité.
Profils et seuils inchangés ; la baisse de mémoire disponible ne mesure
pas exhaustivement les allocations GPU et ne justifie pas de réduire
l'estimation d'admission. Préflight DEV fermé : sept PDF synthétiques,
une famille, cible QA conservée ; publications et 100 annotations à résoudre
avant les deux bras. R23 reste IN_PROGRESS.
[Mesures et limites](journal/2026-10-04.md#r23--pilotes-gpu-et-préflight-dev-relevé-2258-utc).

**Relevé du 4 octobre à 22:33 UTC :** choix au lancement et défaut
2B implémentés ; parcours natifs GPU 2B et 4B réussis sur le même index
synthétique, tokens 466/466, citations, annulation et replay vérifiés.
Cinq E2E Chromium passent par modèle, avec clic de citation et rendu examiné.
Suite backend complète corrigée : 1 510 PASS, 20 SKIP ; deux tests natifs
Tesseract passent séparément. Lint, typage, build et contrôles documentaires
réussis. Instances QA arrêtées, données conservées. Relecture finale
indépendante favorable pour ce sous-lot ; publié sur `origin/main` dans
`a17819a`.
R23 reste IN_PROGRESS pour calibration et qualité
DEV. Le pilote d'abstention 2B ajoute un jugement de fiabilité injustifié,
absent du pilote 4B : limite de qualité prouvée, aucun Done global.
[Preuves](journal/2026-10-04.md#r23--choix-au-lancement-et-parcours-natifs-validés-relevé-2202-utc)
et [relecture finale](journal/2026-10-04.md#relecture-finale-r23-et-publication-du-sous-lot-relevé-2228-utc).

**Relevé du 4 octobre à 21:38 UTC :** le 2B est provisionné et son
contrôle hors ligne passe. Premier nominal GPU sur l'index 4B conservé :
réponse 2,7 bar, tokens 453/453, mais aucun lien de citation reconnu ;
recette FAILED conservée et instance arrêtée (cinq absences strictes).
La première correction de consigne a fait échouer un test de budget ;
version raccourcie sans relèvement de budget, 45 tests context/retrieval
PASS et relecture non-auteur. Suite complète, rejeu natif, Chromium et
non-régression 4B à terminer. Le premier contrôle complet avant ce
correctif avait réellement réussi : 1 508 PASS, 20 SKIP, trois exclusions.
[Détails](journal/2026-10-04.md#r23--premier-2b-rouge-et-correction-du-format-de-citation-relevé-2138-utc).

**Relevé du 4 octobre à 20:33 UTC :** R23 : build physique réussi
après un premier échec de pré-rendu conservé ; contrôles backend affectés
verts (86 ciblés, 62 documentaires et 9 de provenance), Ruff/mypy conformes,
revue finale indépendante D favorable sur code/tests/build seulement.
Les quatre cas Chromium 4B passent, rendus 1366×768 et 1920×1080 examinés.
La réponse native 4B est citée, GPU et tokens 453/453 ; l'annulation aboutit
réellement à `cancelled`, mais la sonde attendait à tort `cancelled` dès le
POST au lieu de `cancel_requested`. Échec de sonde conservé, replay du même
ID à vérifier sans nouvelle question. Poids 2B encore en téléchargement ;
recette 2B, réemploi du même index, arrêt et documentation finale non acquis.
[Détails et prochaine action](journal/2026-10-04.md#r23--contrôles-et-première-recette-native-relevé-2033-utc).

**Relevé du 4 octobre à 20:02 UTC :** Q05 a terminé FAILED avant
l'authentification (`0d254c`, EXIT1) : le lecteur QA exige 0600, le fichier
runtime natif était en 0664. ROOT a arrêté uniquement sa cohorte ; A confirme
onze absences fraîches, runtime arrêté et conservation bornée. Ni Q05 ni
Done global ne sont acquis. Les anciens échecs et les preuves sont conservés.
R23 est maintenant implémenté localement : deux profils réels, 2B par défaut,
choix 4B au démarrage, verrou et tokenizer 2B distincts, modèle affiché depuis
`/jobs`. Revue non-auteur D et correction de compatibilité frontend intégrées.
Frontend : 309 unités, typage et lint réussis ; tokenizer 2B vérifié.
Le premier pull des poids a échoué sur IPv6 ; diagnostic de résolveur borné
en cours, tests backend puis build et recette native restent à terminer.
[Preuves et prochaine action](journal/2026-10-04.md#q05--arrêt-vérifié-et-intégration-r23-relevé-2002-utc).

**Relevé du 4 octobre à 18:56 UTC :** suivi des incréments publié dans
`3e56c75`. Composition C et activation des sept sources relues ROOT/A ;
verrou opératoire neuf à 116 références actives, 195 historiques conservées
sans rouvrir leurs cibles. Préflight réel en lecture seule refusé avant tout
run ou démarrage : la projection SQL du binder garde l'étape à la place du
nombre de tentatives. Le vrai code de conservation et les preuves fermées
établissent la correction ; données cohérentes et critères inchangés.
Correctif ciblé et fixture fidèle en préparation D, puis relecture non-auteur,
nouveau paquet distinct, préflight et admission ROOT avant la recette.
Q05 reste ouvert, l'ancien FAILED reste conservé. R23 reconfirmé : lecture
ciblée du choix de modèle en parallèle, sans bascule ni téléchargement.
[Preuves et prochaine action](journal/2026-10-04.md#q05--préflight-refusé-sur-la-projection-sql-et-demande-r23-reconfirmée).

**Relevé du 4 octobre à 18:06 UTC :** suivi FAILED publié dans `3bdd2d3`.
ROOT accepte séparément C-v2 et D à 18:06:28 UTC après lecture du code, des
preuves et des revues non-auteur A. C-v2 : lecture ROI bornée, drains après
dispose et avant fermeture, rapport de compteurs cohérent, 26 tests purs.
D : vrai descriptor Q05 à 22 champs et union connue de 20 identités, 47 tests
purs ; les observations d'arrêt restent datées, préflight frais encore requis.
Ces incréments ne sont pas une composition ni une recette native. Le lanceur
historique charge encore l'ancien caller : raccord explicite en préparation,
avec restauration des scopes et distinction des verrous historique/courant.
Puis revue indépendante de l'assemblage, verrou opératoire distinct et
admission ROOT avant une seule nouvelle recette corrigée. FAILED/Q05/DoD
inchangés ; R23 différé.
[Preuves et prochaine action](journal/2026-10-04.md#q05--correctifs-qa-acceptés-séparément-relevé-1806-utc).

**Relevé du 4 octobre à 17:22 UTC :** composition et suivi publiés dans
`5092263`. Paquet opératoire accepté après 22 tests purs et revue non-auteur A,
puis une unique recette ROOT `64878/2e222a EXIT1`, achevée à 17:00:31 UTC.
Quatre reçus après checkpoints, deux PNG réellement vues ROOT/A et trois
ancres natives lisibles à 300 %, mais verdict FAILED conservé : warning
console fatal et trois transports échoués après fermeture. Le harnais draine
avant `dispose`, pas au vrai retour ; correction QA distincte en préparation.
C constate fraîchement l'arrêt de l'owner `72fd2e32…`, 20 absences strictes,
neuf jobs ready/query0 et conservation bornée ; revue finale A non-auteur
acceptée ROOT à 17:22:23 UTC, verdict FAILED inchangé.
Ni GO suivant ni Q05/RenderTask/DoD clôturés. R23 reste autorisé mais différé.
[Preuves et prochaine action](journal/2026-10-04.md#q05--recette-courante-rouge-et-diagnostic-borné-relevé-1716-utc).

**Relevé du 4 octobre à 16:12 UTC :** suivi de liaison publié dans
`d49492a` sur `origin/main`. Assemblage diagnostique C accepté ROOT à
16:12:07 UTC après revue indépendante A : deux hunks, 19 tests purs,
25 pièces avec remise et 13 références sûres mesurées ; 13 records hérités
conservés sans ouvrir leurs cibles. Inverses entiers, bindings et gate
byte-identiques. SOURCE_ONLY_NOT_BOUND : aucun verrou opérationnel,
cible ou GO neuf. C prépare maintenant le paquet opératoire distinct ;
revue A/ROOT requise avant toute préparation de cible ou recette.
R23 autorisé mais différé par l'utilisateur après le lot en cours : choix
du modèle et défaut `qwen3.5:2b`, sans bascule actuelle.
[Preuves et prochaine action](journal/2026-10-04.md#composition-q05-acceptée-et-préparation-opératoire-relevé-1612-utc).

**Relevé du 4 octobre à 15:35 UTC :** raccord diagnostique suivi dans
`72ef9e7`, publié sur `origin/main`. Liaison C aux preuves actuelles de qualification 31 et
dernier STOP FBE acceptée ROOT à 15:33:19 UTC après revue non-auteur A :
34 tests purs, 18 pièces et 13 références nommées, inverse entier et gate
byte-identique. Stade SOURCE_ONLY_NOT_BOUND : ni cible ni verrou
opérationnel. L'assemblage avec le diagnostic reste à réaliser puis à
tester et relire ; les 15 et 34 tests séparés ne prouvent pas sa composition.
Indisponibilité du sous-agent B avant démarrage, lot réaffecté à C ; aucun
GO natif ni clôture Q05/RenderTask/DoD. Cause historique et cache hors
périmètre non vérifiés restent distincts.
[Preuves et prochaine action](journal/2026-10-04.md#liaison-q05-acceptée-et-assemblage-à-réaliser-relevé-1535-utc).

**Relevé du 4 octobre à 15:09 UTC :** suivi F01/F03/Q01 publié
par `67bdf32` sur `origin/main`. Raccord diagnostique Q05 accepté au stade
préparatoire : deux hunks, inverse entier, 15 tests purs et revue non-auteur
lus et contrôlés ROOT. Le témoin distingue live d'observe, sans reconstituer
la cause historique. Aucune liaison opérationnelle ni recette Q05 acquise ;
les effets éventuels du cache Ruff historique hors périmètre restent non
vérifiés. Liaison C aux vrais schémas31/dernier STOP en cours, séparée du
raccord B ; revue puis assemblage relu avant tout prepare ou GO.
[Preuves et limites](journal/2026-10-04.md#publication-modale-et-raccord-diagnostique-accepté-relevé-1509-utc).

**Relevé du 4 octobre à 14:36 UTC :** Q01 passe aussi à
`VALIDATED_BOUNDED` après relecture ciblée A du critère exact et arbitrage
ROOT : chaîne31 puis RB5/sonde finale sur les reçus réels du même export.
Les lignes agrégées distinguent désormais FBE courant des arrêts historiques
et les critères acquis des travaux encore ouverts. Q05 reste en cours :
raccord privé du diagnostic existant et témoins purs, avant revue puis
nouvelle liaison ; aucun GO natif. Le refus documentaire neuf 57 PASS/1 FAIL
est corrigé et conservé, reprise 58 PASS. Publication du lot après contrôles
finaux et relecture du snapshot ; aucune clôture globale déduite.
[Arbitrage et contrôles](journal/2026-10-04.md#concordance-du-plan-et-contrôles-documentaires-relevé-1436-utc).

**Clôture bornée, 4 octobre à 14:14 UTC :** ROOT accepte la validation finale
non-auteur A `bb6ab2e2…` / `a86f8940…`, après C actuelle d'arrêt/conservation
et B complémentaire de rendu. F01 et F03 passent à `VALIDATED_BOUNDED` ;
F02 est préservé, Q05 et DoD globale restent ouverts. Nouveau STOP explicite
`fc5278d0…` : FBE, pas CAF ; aucun nouveau GO. Son annotation d'attente A
décrit l'instant de son scellage, antérieur à cet arbitrage ; pièce immuable.
Suite : lecture discriminante du refus Q05 avant auth, sans relance identique,
puis contrôles documentaires et publication du lot.
[Validation et prochaine action](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc).

**Résultat du 4 octobre à 13:55 UTC :** checkpoint documentaire publié
par `548a6c8`. Le cleanup modal et sa liaison au STOP CAF sont préparés,
relus A/ROOT et passés en prepare réel ; C valide les 17 copies historiques.
Une seule nouvelle recette `29568/1dfe36 EXIT0`, terminée à 13:40:08 : cinq
cas RB stricts et sonde modale PASS, sans GET aborté ni console tardive
inattendue. Nouveau propriétaire `fbe0dcc9…` arrêté selon le terminal opérateur.
ROOT voit cinq originales modales et cinq des 13 originales RB relues par B ;
ni 23 captures distinctes ni qualification Q05. La revue C actuelle d'arrêt
et conservation et la validation finale A sont encore en cours : F01/F03
restent ouverts jusqu'à leur acceptation. Le STOP CAF est maintenant historique,
aucun descriptor ancien ne vaut dernier arrêt pour une nouvelle QA.
[Exécution et bornes](journal/2026-10-04.md#cleanup-modal--exécution-verte-revues-finales-en-cours-relevé-1344-utc).

La nouvelle demande documentaire reprend les exigences existantes de R14/R15.
L'espace stabilisé reste dans `docs/`, le suivi vivant dans `RAG_Local_Agents/` ;
aucun second plan n'est créé. La revue éditoriale indépendante a confronté les
ajouts récents aux preuves et les textes frontend concernés à leur consommateur.
Les retouches de lisibilité sont appliquées ; les 58 tests documentaires, Ruff
et les cinq SVG passent. Les procédures non exécutées restent non qualifiées.

**Complément du 4 octobre à 11:29 UTC :** le checkpoint documentaire est publié
sur `origin/main` par `9f6c1bb`. La revue indépendante C du lot cohérent de
20 fichiers frontend est acceptée ; elle confirme les mêmes sources que les
contrôles acquis, sans requalifier F01 ou la DoD. Le diagnostic final B est
préparé, relu indépendamment par A et accepté par ROOT ; il précise l'assertion
et les phases sans modifier les verdicts. B prépare maintenant sa liaison
minimale au dernier arrêt courant `5278b261…`. Aucun nouveau prepare, démarrage
ou PASS modal ; voir le [journal de cette itération](journal/2026-10-04.md#publication-documentaire-et-intégration-du-lot-frontend-relevé-1129-utc).

**Complément du 4 octobre à 12:03 UTC :** le lot cohérent frontend est publié
par `9ccfc68`, sans clôturer F01. La liaison B du diagnostic au STOP courant
est relue indépendamment par A et acceptée ROOT ; treize tests purs sur ses
sources finales passent. Le prepare réel termine par `917ccb EXIT0` : baseline
`96d2cb8a…`, cible `72d0c798…`, pas de démarrage ni nouvelle recette modale.
Contrôle indépendant postprepare en cours, puis essai discriminant ROOT.
La préférence GPU demandée par l'utilisateur est intégrée à
[W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024) :
accélérer les essais compatibles, y compris ceux jusque-là exécutés sur CPU,
sans transférer une mesure GPU à D07 ni présumer des réponses identiques.
Le profil modal gelé est conservé ; ce parcours ne génère pas de réponse.
[Preuves et limites](journal/2026-10-04.md#préférence-gpu-et-préparation-du-diagnostic-modal-relevé-1203-utc).

**Suite réelle, relevé du 4 octobre à 12:22 UTC :** contrôle postprepare C
accepté (`908df59e…` / `1df54a5a…`). Premier run refusé avant checkpoint :
dossier clearances absent, prérequis opératoire corrigé sans modifier le gel.
Nouvelle exécution `10444/190af9 EXIT2`, terminée à 12:13:39 : RB5 strict
5 PASS, sonde toujours FAILED à `FINAL_CONSOLE_ERROR` ; deux consoles tardives
pendant TRACE_STOP, deux GET de nettoyage abortés, relation console/Request
UNKNOWN. Owner courant `caf0b149…` arrêté ; revue finale C en cours. ROOT voit
les cinq nouvelles PNG, pas dix originales. B réalise un seul essai ciblé
de l'ordre du cleanup selon [R15S56](SOURCES.md#r15s56--fermeture-de-la-trace-et-du-contexte-de-test),
avec assertions finales conservées ; aucun nouveau résultat de correction
acquis. [Exécution et prochaine action](journal/2026-10-04.md#diagnostic-modal-réel-et-correction-ciblée-du-nettoyage-relevé-1222-utc).

**Complément du 4 octobre à 12:48 UTC :** revue finale C close et acceptée
ROOT : arrêt/conservation bornés, 33 QA et quatre HOST absents, SQL neuf
jobs ready et aucune query. Les cinq originales sont vues par ROOT et C ;
la modale reste FAILED, sans causalité console/abort établie. Le nouvel arrêt
explicite `da4a7f9b…` désigne CAF, pas le propriétaire historique des 31.
Le correctif de cleanup B est préparé : deux hunks, 12 tests purs PASS,
gardes et assertions inchangées ; revue non-auteur A en cours. B prépare
sa liaison minimale à cet arrêt, sans lancer de services ni navigateur.
Les contrôles documentaires passent : 58 tests, sept contrôles de liens,
onze contrôles du pack, brief et cinq SVG. Ils ne qualifient ni une
procédure réelle ni la modale. [Preuves et prochaine action](journal/2026-10-04.md#arrêt-diagnostique-accepté-et-correctif-cleanup-préparé-relevé-1248-utc).

| Action existante ou constat | État au relevé | Validation restante |
|---|---|---|
| RB5 et sonde modale | Qualité acquise sur le gel `e093c06b…` : 305 unités, typage, lint119 sans erreur/avertissement, build/export `7168111f…` et 31 cas stricts qualifiés ; contrôles inchangés non rejoués. Cleanup ND : 12 tests purs, liaison CB : 21 tests purs ; revues non-auteur A, prepare réel puis revue C des 17 copies acceptés. Nouvelle recette `29568/1dfe36 EXIT0` à 13:40:08 UTC : cinq RB stricts, une tentative/retry0/skip0/flaky0, sonde `PASS_NATIVE_READS_ONE_INTERCEPTED_UI_DELETE`. Arrêt courant `fbe0dcc9…`, runtime `314aece0…` et STOP explicite `fc5278d0…` ; CAF et 5278 historiques | VALIDATED_BOUNDED pour F01/F03, F02 préservé : C `2411ac8a…` / `af6f3eca…` et A finale `bb6ab2e2…` / `a86f8940…` acceptées ROOT. 35 QA et quatre HOST absents, neuf jobs ready/complete/attempt1, query0, conservation bornée. C/ROOT voient les mêmes cinq modales ; B voit 13 RB, dont cinq ROOT incluses. DELETE400 et certains GET sont des substitutions UI déclarées, zéro retrait backend. Anciennes recettes FAILED conservées, causalité console historique inconnue. Q05, parcours métier restants et DoD globale ouverts ; prochaine action : diagnostic discriminant Q05 avant tout replay. [Validation et limites](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc) |
| R15-3-Q05 | V1 refusée au préflight avant tout démarrage : comptage PDF.js erroné. V2 corrige uniquement ce contrat, 202 assets plus manifeste ; 95 tests purs PASS, 19 pièces/72 pins, avis préparatoire C/ROOT favorables. Vrai préflight PASS à 04:59:11 ; recette native `7124 EXIT1`, FAILED avant auth, primaire `PRE_AUTH_NATIVE_REFUSED/ValueError` et secondaire down. Une seule clearance q05-start, aucune capture. ROOT arrête ensuite le seul owner QA `c59e67…` avec le CLI standard `33272 EXIT0` ; C `7d29e8fb…` confirme 12 absences, DB inchangée/query0 et conservation bornée. Sous-prédicat exact inconnu ; ancien descriptor `a747094a…` obsolète | IN_PROGRESS — préparations et refus historiques conservés au journal. Paquet PC accepté ROOT après revue A, 22 tests purs, 99 pins actifs/195 historiques ; parser et seule substitution du chemin physique browser-cache vérifiés. Recette réelle unique `64878/2e222a EXIT1`, summary `9d5b9b09…`, quatre reçus postcheckpoint, owner neuf `72fd2e32…`. LIVE2/DOWN1 sans guardfailure ; caller FAILED : warning console fatal puis trois transports/guards en fermeture. Deux PNG 300 % lisibles vues ROOT/A, sans promotion du verdict. C `349833d4…` / `82bcf358…` : 20 absences strictes fraîches, neuf jobs ready/query0 et conservation bornée ; revue finale non-auteur A `14307b32…` / `4e1af23b…` acceptée ROOT à 17:22:23 UTC, FAILED inchangé. Correctif C-v2 readback/drain et rapport accepté après 26 tests purs ; liaison D au STOP72fd après 47 tests purs, revues non-auteur A et acceptation ROOT à 18:06:28 UTC. Incréments séparés source-only, assemblage du vrai chemin opérateur/caller en cours, pas de nouveau GO. Cause du warning passé inconnue, caches historiques hors portée non requalifiés. [Preuves et prochaine action](journal/2026-10-04.md#q05--correctifs-qa-acceptés-séparément-relevé-1806-utc) |
| R15-3-F04 | VALIDATED_BOUNDED après revue finale A : miroir703 qualifié, E2 terminal `22825 EXIT0`, onze cas stricts/retry0/skip0 ; génération réelle, carte corrompue liée au fichier, seuil64KiB isolé. B : 138 absences datées, trois tuples historiques incomplets conservés, sources/export/marqueurs nommés inchangés. C : dix PNG vus et dix blocs recomputés ; ROOT trois PNG inclus dans ces dix. Ancien E FAILED préservé | Aucun rejeu F04 requis dans ce critère d'action. Les preuves directes ne sont pas une exécution de l'ancien adaptateur GET/cards. Révision distincte non observée, peinture300, modale, ancres, SSE, Windows et DoD globale restent ouverts ; prochaines actions sur leurs lots existants |
| R15-3-E03, incohérence rédactionnelle | VALIDÉ et publié dans `f8cd964` sur `origin/main` à 18:25 UTC : sept tests ciblés, 281 unités sans skip, typage/lint/build isolé conformes. V5 sortie 0, trois contextes UI et captures relus ; neuf processus absents, permissions et conservation vérifiées indépendamment. V1/V2 restent FAILED, cause V2 inconnue ; V4 conserve son wrapper EXIT1 | Aucune correction E03 restante dans cette portée. Session/API doublées : ni publication native, ni peinture PDF, ni recette RAG de bout en bout ; voir le journal pour les preuves |
| R15-3-E04, incohérence rédactionnelle / frontend | VALIDÉ et publié dans `19f483f` sur `origin/main` à 20:09 UTC : aide vers les actions du Suivi et la disponibilité réelle, inverse de la seule phrase byte-exact ; calculs et gates conservés. Rouge préservé, 20 tests frontend ciblés puis 288 complets sans skip conformes ; typage, lint de 118 fichiers et build isolé sortie 0. Huit contextes UI et captures neuves relus par ROOT/C/A ; conservation et quinze absences actuelles vérifiées indépendamment par B | Aucun correctif E04 restant dans cette portée. API/session doublées : ni publication backend, ni peinture PDF, ni recette RAG native ou DoD globale ; aucun défaut visuel bloquant dans les huit captures |
| R15-3-E05, amélioration rédactionnelle / API affichée dans le frontend | VALIDÉ et publié dans `19f483f` sur `origin/main` à 20:09 UTC : traduction fixe après S41, contrat conservé. Rouge ASGI préservé, 16 tests ciblés et 104 de régression PASS ; Ruff et mypy Linux/cible win32 conformes, revue B favorable. Référence API §3 réalignée ; vrai client frontend testé avec fetch doublé. Deux aides 422 lisibles aux deux tailles sur le nouvel export, revues ROOT/C/A et fermeture vérifiée B | Aucun correctif E05 restant dans cette portée. Le navigateur reçoit des 422 doublés sur une petite sélection : le refus de 1 001 éléments est exercé séparément par ASGI isolé avec services doublés, pas par un parcours natif |
| R14-3, clarification du référentiel de conception / documentation | VERIFIED documentaire et publié dans `f8cd964` : rôle normatif explicite, sept flux/responsabilités sans schéma ASCII, renvois à l'architecture et au SVG livré. 58 tests, liens/pack/brief/SVG conformes ; avis final indépendant A favorable et responsabilités conservées | Aucun comportement ou critère V2.1 modifié, aucune procédure qualifiée par ces contrôles ; R14 global reste ouvert |

Les droits d'écriture E03 sont limités au texte de `pdf-viewer.tsx` et à son
témoin `publication.test.ts`. Les autres modifications locales sont préservées.
Les preuves et les commandes sont au
[journal](journal/2026-10-03.md#relecture-documentaire-et-reprise-qa-relevé-1602-utc).
Les preuves E03 sont dans `evidence-review/frontend-publication-copy-20261003C/`
sous la racine QA privée du journal ; la [clôture E03](journal/2026-10-03.md#e03--validation-ciblée-et-clôture-v5-relevé-1809-utc)
distingue le rendu validé des limites de cette recette. Les deux échecs de montage et quatre skips de la première
suite sont conservés : deux supports de test ont été ajoutés à la copie physique,
et quatre tests lisent la référence Git historique, sans mutation Git.
R14, R15, R22, D06 et la DoD globale restent ouverts ; R23 reste NOT_STARTED.

**Complément du 4 octobre à 01:01 UTC :** le suivi précédent est publié par
`bebb8f2`. Le collecteur E a réellement refusé à `nominal-start`, alors que
le contrôleur `32807` attend encore : aucune instance native démarrée.
Cause acquise, défaut du préparateur QA : mode historique `664` non confronté
au callsite `load_guard`. E2 en cours ; les preuves, limites et prochaines
actions sont au [journal](journal/2026-10-04.md#publication-du-suivi-et-refus-du-collecteur-e-relevé-0101-utc).

**Terminal qualifié F04, le 4 octobre à 01:59 UTC :** onze parcours réellement
passés sur E2, arrêt et conservation bornée B, rendu/citation C et opérateur
ROOT, validation finale indépendante A favorables. Le critère exact de
l'action F04 est satisfait ; aucune case DoD globale cochée. L'ancien
adaptateur GET reste non exécuté, remplacé pour la carte par la preuve directe
du scénario canonique corrigé, pas par une réussite reconstruite.
Les [preuves et limites](journal/2026-10-04.md#terminal-f04-e2-et-relectures-relevé-0157-utc)
conservent E refusé et la révision réemployée. Prochaine action : préparer et
faire relire la liaison modale source249/export actuel/HOST arrêté, puis
replay5 nécessaire et sonde diagnostique après contrôles frais par ROOT.
Pas de rebuild des mêmes entrées, de reprise de HOST ni d'activation 2B.

**Reprise modale et Q05, le 4 octobre à 03:28 UTC :** F04 et son suivi
sont publiés par `9b14e22`, push EXIT0 observé à 02:09:18. La préparation
modale V2 termine EXIT0, puis son premier run refuse avant toute action
native : le contrôle metadata rejette l'identité arrêtée que la composition
interdit à juste titre pour un futur owner. Diagnostic par appels réels
`assembled`, `lockcheck`, `target_contract`, sans `execute` ni `g.command`.
C3 est un correctif QA en cours, pas encore livré ou validé. Le gel Q05
est préparé et relu, jamais exécuté ; il attend cette fermeture modale.
Les [preuves, refus et prochaine frontière](journal/2026-10-04.md#préparation-modale-et-refus-précheckpoint-relevé-0328-utc)
conservent les versions précédentes. Une seule charge native lourde sera
autorisée par ROOT après revue ; aucun critère ou seuil DoD ne change.

**Reprise F04 à 20:21 UTC :** nouvelle copie QA et qualification des 31 en
préparation sur les sources actuelles, sans nouvelle exécution à ce relevé.
L'ancien programme, son export et ses preuves restent immuables. L'export
E04 déjà construit sera réemployé après contrôle byte-exact et reçu explicite,
pas présenté comme un nouveau build. Relecture indépendante : l'oracle
`lifecycle.spec.ts` recherche encore globalement le message d'un job ; une
carte précédente peut donc satisfaire l'assertion du fichier courant.
Correction ciblée de cet oracle en cours avant fermeture du nouveau gel.
Les gardes d'identité, d'arrêt et de restauration Q01/Q04 restent obligatoires.

**Complément F04 à 20:40 UTC :** oracle corrigé et contrôlé isolément,
relecture indépendante A favorable. Le test exige la carte unique du document
courant, son état d'échec et son propre message visible ; IDs du job, du
document et de la version liés à l'import. Treize témoins ROOT PASS sans skip,
puis régression web complète ROOT : 301 PASS, zéro failure/error/skipped ;
lint ciblé et typage conformes selon les sorties originales B. Aucun code
produit modifié et aucun nouveau build. La copie neuve doit intégrer ces deux
seuls chemins de test par un delta explicite : 249 sources nommées, pas un
changement silencieux du dénominateur. Les cartes natives restent non vérifiées ;
F04 demeure en cours.

**Qualification des 31 à 21:04 UTC :** correctif de test publié dans
`d1ab706`, puis copie physique neuve exécutée et relue indépendamment.
Gel de 249 sources, 697 fichiers exacts, quatre liens partagés autorisés,
13 fichiers ingestion et export E04 de 243 fichiers conservés ; 971 références
du verrou d'exécution concordent. Aucun build rejoué ni état utilisateur copié.
Le pilote natif est en cours, session ROOT `53480`, après clearance fraîche
attestant zéro job et zéro question actifs sur l'hôte. Aucun PASS des 31 ni
nouveau rendu n'est acquis à ce relevé. Les gardes d'arrêt strict et les
postcontrôles de conservation restent requis avant la relecture terminale.
Le workflow historique des onze F04 contient encore deux empreintes sources
antérieures ; un delta de binding distinct est en préparation, sans modifier
les gels historiques ni leurs résultats. Voir les
[preuves de copie et conditions de lancement](journal/2026-10-03.md#copie-qa-neuve-et-démarrage-des-31-relevé-2104-utc).

**Terminal et diagnostic à 21:26 UTC :** session `53480` sortie 1,
fin réelle à 21:12:37 UTC. Les 31 résultats sont chacun passed/retry0,
sans skip/flaky/error, mais summary et composition demeurent FAILED.
Refus localisé à la comparaison d'exécutable du launcherdown pendant
son census, avant attente pidfd. Fin de vie, zombie ou changement physique
d'exécutable restent inconnus ; le même chemin est reproduit avec deux
scénarios synthétiques distincts. Delta QA ciblé en réalisation après
consultation officielle R15S44, pas de relance automatique. La peinture
à 300 % reste non qualifiée ; les réserves visuelles ne sont pas transformées
en bugs non démontrés. [Terminal et limites](journal/2026-10-03.md#terminal-des-31-et-diagnostic-du-refus-darrêt-relevé-2126-utc).

**Reprise à 21:52 UTC :** suivi publié dans `45e8482`, sans requalifier
l'échec. Nouvelle copie `PROGRAM-E04-native31-terminalA-qualification`
réalisée à 21:45:51 UTC puis contrôlée par ROOT et C : 249 sources,
13 fichiers ingestion, 697 fichiers physiques, quatre liens et 971 références
conformes ; état vierge, aucun build ou démarrage. Correctif privé du
contrôleur d'arrêt en validation finale : V1 refusée sur les retours non
entiers, V2 sur le chemin de verrou de la CLI ; aucune n'a été exécutée en
natif. Prochaine action : gel corrigé et revue indépendante, clearance
fraîche, puis nouvelle recette des 31 cas. La variante F04, vérifiée par
28 témoins purs, est préparée et relue, pas exécutée ; elle attend une
qualification admissible des 31 cas.
[Copie et réserves du contrôleur](journal/2026-10-03.md#nouvelle-copie-isolée-et-relecture-du-contrôleur-arrêt-relevé-2152-utc).

**Départ à 21:55 UTC, relevé à 21:57 :** gel A V3 contrôlé par ROOT et B,
39 tests purs PASS, verrou initial/final cohérent ; versions refusées
conservées. ROOT lance la recette des 31 cas, session `84419`, après une
clearance HOST à 21:54:25 UTC attestant 0 job/question actif et un verrou
lourd libre. La copie et le run sont ceux contrôlés ci-dessus ; nouvelle authentification
QA et imports synthétiques autorisés, aucun état de l'hôte repris. En cours,
sans verdict terminal. `EXIT0`, attestation terminale A, composition C, arrêt
strict, conservation et revue du rendu restent requis avant qualification
et miroir F04. Pas de clôture de F04, de la peinture à 300 % ou de la DoD globale.

**Terminal à 22:05:53, relevé à 22:19 UTC :** session `84419`, sortie 1
constatée à 22:06:28. Les 31 cas et l'arrêt ciblé passent, mais le contrôle
C de fin demande un champ `instance_id` absent du vrai reçu de démarrage.
Composition C et attestation A `FAILED` sur une `KeyError`, jamais requalifiées.
Bug du dispositif QA prouvé par le code émetteur et le schéma fermé,
référence [R15S45](SOURCES.md#r15s45--schéma-réel-du-reçu-de-démarrage-qa).
Delta V4 minimal en validation, sans code produit ou build modifié ;
nouvelle copie `strict-final` réalisée et contrôlée à 22:14/22:15, encore vierge.
Prochaine action : finir/revoir le delta de schéma, clearance fraîche puis
qualification intégrée des 31 cas. F04, peinture à 300 % et DoD globale restent ouverts.
[Terminal, conservation et nouvelle copie](journal/2026-10-03.md#recette31-terminale-et-défaillance-du-contrôle-de-schéma-relevé-2219-utc).

**Reprise à 22:36 UTC :** V4 scellée, 59 tests purs conformes ; ROOT et B
confirment les 42 pièces, 47 références et la liaison au schéma réel.
La preuve terminale B du run refusé est conservée : 119 absences strictes,
249 sources et export inchangés, sans requalification. ROOT a lancé
la nouvelle recette, session `81325`, après le contrôle de l'hôte à
22:30:35 UTC : aucune tâche ou question active, verrou lourd disponible.
Un seul traitement lourd ; ni nouveau build ni reprise des tâches en pause.
Le résultat natif reste en attente. Les validations indépendantes de
l'arrêt/conservation et du rendu précéderont tout miroir F04.
[Gel, preuve indépendante et départ](journal/2026-10-03.md#gel-v4-et-nouvelle-recette-native-relevé-2236-utc).

**Terminal et diagnostic à 22:49 UTC :** session `81325` sortie 1,
observée à 22:42:35 ; fin réelle à 22:41:13. Le contrôle final du schéma
fonctionne sur cette instance réelle, mais le census du lanceur de
géométrie échoue après ses sept tests. ROOT et A localisent ce callsite
dans une preuve fermée, sans déduire la valeur d'exécutable ou un zombie.
Troisième essai refusé conservé. Incrément QA V5 autorisé sur les seules
commandes collectées et sept groupes, sans changement produit ou build ;
préparation et contre-tests en cours. Nouvelle copie isolée autorisée,
aucun nouveau départ natif. B vérifie indépendamment arrêt et conservation.
[Résultats, diagnostic et portée](journal/2026-10-03.md#refus-du-lanceur-de-géométrie-relevé-2249-utc).

**Complément à 22:54 UTC :** B confirme les 97 absences et la conservation
dans une nouvelle preuve scellée, sans promouvoir l'échec. Copie
`owned-launcher` préparée par C et contrôlée par ROOT ; ses 971 références
sont exactes, état vierge. V5 reste en correction et test, aucun GO natif.
[Preuve et copie suivante](journal/2026-10-03.md#validation-indépendante-et-copie-suivante-relevé-2254-utc).

**Reprise à 23:10 UTC :** suivi publié dans `555382f`. V5 contrôlée par
ROOT et B : 105 tests purs, 57 pièces et 62 références conformes, garde
limitée aux commandes figées et aux mêmes identités. Recette native
`46805` en cours sur la copie contrôlée, après vérification de l'hôte à
23:08:02 UTC ; un seul traitement lourd, aucun build ni reprise des tâches
en pause. Qualification terminale et revues encore attendues avant F04.
[Gel V5 et départ](journal/2026-10-03.md#gel-v5-et-départ-de-la-recette-relevé-2310-utc).

**Terminal des 31 à 23:23 UTC :** sortie 0 observée, résultats stricts et
attestations C/A conformes. Vérifications indépendantes en cours ; miroir et
onze F04 toujours non exécutés. Les limites du rendu ne sont pas levées par
les assertions techniques. [Preuves terminales](journal/2026-10-03.md#terminal-des-31-cas-relevé-2323-utc).

**Miroir F04 à 23:37 UTC :** prérequis des 31 désormais
admissible ; copie créée, puis refus de la politique des parents Python,
avant tout chmod ou démarrage. La cause est prouvée sur les sources réelles,
pas déduite du plan. Correction QA privée en cours ; garde, refus et données
préservés. [Miroir et refus](journal/2026-10-03.md#admissibilité-des-31-et-refus-préparatoire-f04-relevé-2337-utc).

**Demande prioritaire, atelier GPU à 23:56 UTC :** instance de l'utilisateur
redémarrée sur demande explicite, frontend qualifié E04 installé et atelier
rouvert dans Chromium. Profil et racine des données conservés, nouveau runtime
`81cb1450…`, GPU déclaré et disponibilités vérifiées ; pas de génération de
qualification. Les recettes lourdes ne sont pas lancées pendant son essai.
Les anciennes clearances liées à `74acf854…` ne sont plus applicables ; toute
future porte F04 devra vérifier la nouvelle identité et la continuité des données,
sans assouplir ses contrôles. [Relance réelle](journal/2026-10-03.md#redémarrage-gpu-et-ouverture-dans-chromium-relevé-2356-utc).

**Arrêt demandé et reprise à 00:12 UTC, le 4 octobre :** instance utilisateur
arrêtée proprement à 00:03:21 UTC, sortie 0 ; quatre identités absentes,
contre-vérification indépendante A à 00:10:43 UTC. Données non réinitialisées
ni déplacées ; six documents, six versions, dix jobs et 92 requêtes enregistrées.
L'hôte reste arrêté. D et diagnostic modal sont des préparations privées,
pas des recettes natives ; nouvelle porte de conservation en diagnostic,
sans recyclage des attestations de l'ancien owner ni redémarrage implicite.
[Arrêt et reprise](journal/2026-10-04.md#arrêt-de-linstance-utilisateur-et-reprise-relevé-0012-utc).

**Préparations contrôlées à 00:18 UTC :** avis indépendant A favorable sur D,
préparateur réellement exécuté avec sortie 0 ; avis indépendant B favorable
sur le diagnostic modal, 38 tests purs relus et pins vérifiés par ROOT.
L'ancien collecteur ne pouvant attester l'hôte arrêté, E est une nouvelle
préparation privée, pas une modification du produit ou des reçus historiques.
[Contrôles et limites](journal/2026-10-04.md#préparateur-d-et-diagnostic-modal-relevé-0018-utc).

## R15-3 — reprise des contrôles QA, relevé du 3 octobre à 15:19 UTC

Le point de suivi documentaire `f331421` a été publié sur `origin/main` à 14:27 UTC.
Les sources produit du gel de 243 fichiers et des 13 fichiers du périmètre ingestion, ainsi que leurs tests, typage, lint et build, ne sont
pas modifiés par cette reprise. Les travaux suivants corrigent ou composent
les outils de qualification, sans anticiper leur réussite native.

| Axe existant | État réel et preuve | Prochaine action autorisée |
|---|---|---|
| Modale, complément F01/F02 et RB5 | C01-RB confirmé : l'ancien `execute` ignore un refus tardif pendant la fermeture. Sonde ROOT v3 distincte : 46 tests purs PASS ; lint de 10 fichiers MJS sans erreur ni avertissement ; revue C favorable limitée à cette sonde. Composition ROOT V2 : 68 tests purs PASS ; Ruff sur quatre fichiers Python et lint du script verts ; avis indépendant de composition en cours | Après cet avis : vérifier la cible historique et le dernier arrêt explicite, préparer la suite neuve, contrôler les ressources et l'autorisation de charge (`clearance`), exécuter les cinq cas stricts puis la modale, examiner le rendu et faire relire l'arrêt et la conservation |
| R15-3-Q05 | `run-20261003T1315` toujours FAILED. Instrumentation diagnostique : 83 tests purs PASS et revue C favorable préparatoire. Enveloppe B : 54 tests purs PASS, en revue C ; aucun nouveau navigateur lancé, phase réelle des trois erreurs historiques non établie | Relire l'enveloppe, contrôler le dernier arrêt applicable, puis ouvrir une fenêtre diagnostique isolée ; conserver les refus et les nouveaux échantillons, sans reconstruire ceux du run1315 |
| R15-3-F04 | Correction ROOT de l'oracle tardif déjà revue ; adaptateur de lecture des deux cartes en finition, non livré ni revu à ce relevé. Aucune nouvelle carte réelle qualifiée | Revue complète de l'adaptateur, liaison à l'exécution nominale `run-20261003T1050` et préconditions réelles ; recette GET/UI, deux captures, arrêt propre et conservation |

Les gels antérieurs restent immuables. Le premier assemblage ROOT conserve
son rouge de montage et ses diagnostics de lint ; V2 les corrige sans masquer
les contrôles. Un test pur ou un avis préparatoire ne valide pas D06. Le
descripteur ROOT de l'arrêt lié au run1315 est une entrée attendue à revalider, pas une observation
fraîche du runtime. Preuves, SHA complets et limites au
[journal](journal/2026-10-03.md#contrôles-qa-après-fermeture-et-compositions-relevé-1519-utc).
R23 reste inscrit et NOT_STARTED ; les autres critères globaux ouverts ne
sont pas clôturés par ces préparations.

## R23 — choix du modèle de génération et défaut Qwen 3.5 2B

**État réel au 4 octobre, 22:58 UTC :** choix au lancement confirmé par
l'utilisateur et implémenté. Tag exact `qwen3.5:2b` Q8_0 par défaut ; 4B
sélectionnable, profil antérieur conservé. Tokenizer et poids vérifiés hors
ligne, suite backend corrigée 1 510 PASS, 20 SKIP et deux exclusions natives
reprises séparément au vert. Web 309 PASS, lint/typage/build réussis.
Parcours GPU 2B et 4B : index conservé sans réimport/réindexation, SSE,
citations versionnées, annulation/replay, cinq E2E Chromium par modèle,
arrêt propriétaire et conservation. La consigne de citation est corrigée
sans modifier le parseur ni les budgets ; échecs antérieurs conservés.
Le pilote sans fabricant aboutit à une abstention, mais le 2B ajoute un
jugement de fiabilité contraire à la consigne. Cette limite reste ouverte ;
aucune qualité équivalente au 4B n'est annoncée. Pilotes GPU exécutés
à 22:43–22:49 UTC puis relus : mesures bornées, admission non recalibrée.
Comparaison DEV 100 questions, plateformes non exercées et D07 restent
à traiter. [Preuves](journal/2026-10-04.md#r23--choix-au-lancement-et-parcours-natifs-validés-relevé-2202-utc).

**Relevé historique au 4 octobre, 20:02 UTC :** choix implémenté dans le lanceur,
sans bascule à chaud ni téléchargement à `up`. `config/local16.yaml` désigne
le tag exact demandé `qwen3.5:2b` (Q8_0 officiel) ; `local16-4b.yaml` conserve
octet pour octet l'ancien profil 4B. Le verrou ajoute l'identité officielle
2B et six fichiers de tokenizer versionnés. Le frontend conserve l'état
matériel même si le nouveau champ informatif modèle est invalide. Tests
frontend 309/309, lint et typage réussis ; tokenizer provisionné, poids et
réponse native non validés. Sources [R23S02](SOURCES.md#r23s02--identité-du-tag-2b-et-tokenizer-versionné).
La nouvelle demande explicite du tag court est appliquée ; elle ne qualifie
pas le tag Q4_K_M initialement proposé, conservé ci-dessous comme historique.

**Demande reconfirmée dans l'itération, relevé du 4 octobre à 18:56 UTC :**
intégrer le choix du modèle avec `qwen3.5:2b` par défaut. Reconnaissance ciblée
du code et des sources officielles en parallèle du correctif Q05 ; aucune
installation, bascule ni fonctionnalité livrée à ce stade. L'intégration
suivra la vérification du lot Q05 déjà engagé. Le contrat actuel fixe le
modèle au démarrage ; un choix en cours d'utilisation reste à préciser.

**Demande actualisée le 4 octobre 2026, relevé à 16:12 UTC :** intégrer le
choix du modèle et utiliser `qwen3.5:2b` par défaut. L'utilisateur demande
ensuite de terminer le lot en cours avant cette intégration. R23 est donc
autorisé, mais différé ; aucune modification de profil, installation ou
bascule exécutée. Le 4B doit rester sélectionnable. Le tag court demandé
et la précédente exigence Q4_K_M devront être rapprochés des artefacts
officiels lors de la réalisation, avant de verrouiller leur identité ; ne
pas traiter deux quantifications comme équivalentes.

**Ajout demandé le 3 octobre 2026, relevé à 10:05 UTC.** Objectif :
permettre également le démarrage de la plateforme avec un modèle Qwen 2B
quantifié, sans remplacer le modèle 4B actuel. La formulation « 2b quantisé
4kk de qwen » est interprétée comme **Qwen 3.5 2B Q4_K_M**, dans la même famille
que le modèle livré ; cible officielle explicite `qwen3.5:2b-q4_K_M`.
Au relevé du 3 octobre, le tag court `qwen3.5:2b` désignait Q8_0 et ne
satisfaisait pas cette exigence initiale. Sources et limites :
[R23S01](SOURCES.md#r23s01--modèle-qwen-35-2b-et-quantification-explicite).

**État de référence vérifié lors de l'ajout du 3 octobre :** `config/local16.yaml` configure
`qwen3.5:4b-text`, sa source `qwen3.5:4b`, Q4_K_M et le tokenizer 4B ;
`config/models.lock.json` ne contient que ces deux modèles. Le lanceur contrôle
les modèles du profil contre ce verrou et la quantification observée ; changer
le seul nom du modèle ne constitue pas une intégration. Le support 2B est
**NOT_STARTED**, ni installé ni testé par cet ajout. La demande à cet instant
autorisait son inscription au plan ; elle ne déclenchait pas de téléchargement,
de bascule de profil, de redémarrage ou d'exécution du lot futur.

| ID | Couche, propriétaire et livrable attendu | Dépendances | Critère de validation | Statut et preuve |
|---|---|---|---|---|
| R23 | Runtime / génération — intégrateur, avec relecture indépendante : choix explicite 4B ou 2B, défaut 2B demandé, artefacts et profil distincts, procédures associées | W006/W007 (modèle texte et admission), W018 (plateformes), W024/W025 (mode de calcul), contrats de génération et sources R23S01/R23S02 ; conserver les qualifications R15 en cours | Tag et quantification rapprochés de la demande actualisée ; identité vérifiée ; préparation reproductible puis démarrage/redémarrage hors ligne sur cible isolée ; génération native avec SSE et citations ; admission et ressources mesurées ; non-régression du profil 4B ; limites de plateforme et de qualité déclarées | IN_PROGRESS — sélection et parcours natifs validés sur Linux aarch64 : 2B/4B, même index, SSE/citations/annulation/replay, cinq E2E par modèle ; 1 510 unités backend et deux contrôles natifs, web 309, lint/typage/build verts. Sous-lot publié sur `origin/main` (`a17819a`). Pilotes GPU exécutés et relus, sans réduction de seuil ni qualification D07. Admission froide CPU locale corrigée à 3584 Mio (W036), chaud 512 encore provisoire ; 83 unités de sélection/admission/documentation PASS. Restent comparaison DEV 100 et traitement du jugement injustifié du 2B ; autres plateformes et D07 non qualifiés. [Parcours](journal/2026-10-04.md#r23--choix-au-lancement-et-parcours-natifs-validés-relevé-2202-utc), [pilotes](journal/2026-10-04.md#r23--pilotes-gpu-et-préflight-dev-relevé-2258-utc), [admission froide](journal/2026-10-06.md#r23--mesure-cpu-2b-bornée-admission-du-6-octobre-à-0253-utc) |
| R23-OCR-01 | Ingestion / qualité — intégrateur avec diagnostic et validation non-auteurs : fiabiliser l'extraction des deux scans DEV sans modifier les sources gelées | R23, contrats d'ingestion et skill `pdf-ingestion-windows` ; QA propriétaire arrêtée, extractions partielles conservées | Reproduction ciblée ; correction prouvée avec même moteur et seuils ; publications complètes des sept documents, résolution des 100 scopes/annotations et 90 unités sans ambiguïté avant génération ; contrôles et relecture des cas touchés | IN_PROGRESS — P03 qualifié et publié (`d26a3a4`) : extraction complète native PASS, 236 unités sans exclusion, Ruff/mypy et documents verts, revue finale favorable. P02 bilingue puis fra seul refusés : ce dernier rétablit les signes, mais conserve quatre références erronées et dégrade les trois références du tableau ; 1/5 faits exacts, douze régions faibles. Diagnostic et refus relus, aucun correctif prouvé ni artefact adopté. Gate DEV, sept publications et scores non acquis. Admission froide R23 corrigée séparément (W036), sans résoudre l'OCR ; pas de nouvel apprentissage, volume accru ou répétition aveugle. [Comparaison courante](journal/2026-10-06.md#discriminant-de-langue-p02--préparation-distincte) ; [livraison P03](journal/2026-10-05.md#publication-du-sous-lot-p03-relevé-0037-utc) ; [rouge initial conservé](journal/2026-10-04.md#r23--gate-dev-refusé-et-qa-arrêtée-relevé-2316-utc) |
| R23-OCR-02 | Outillage / ingestion — construction séparée des outils d'extension Tesseract, intégrateur avec validateur non-auteur | R23-OCR-01, W034, skill `tesseract-lstm-extension` ; archive verrouillée, ICU/Leptonica ; protocole figé et relu | Configuration puis compilation réelles en QA neuve sous verrou et plafonds ; cibles, dépendances, versions et identités contrôlées, ressources et arrêts conservés ; pas de changement nominal ni apprentissage | VALIDATED_BOUNDED — outils Linux aarch64 seuls : construction réelle `PASS_TOOLS_ONLY` en 397,59 s, sept versions/dépendances et 707 mesures conformes ; revue finale non-auteur favorable, acceptée ROOT à 02:21 UTC. 625 identités observées absentes ; source/entrées/archive inchangées. Entraînement, adoption, P02 et autres plateformes non validés. [Décision](DECISIONS.md#w034-outils-séparés-avant-toute-extension-lstm) ; [preuves et avis final](journal/2026-10-05.md#construction-terminée-et-lecture-des-preuves-relevé-0212-utc) |
| R23-OCR-03 | Apprentissage OCR isolé — entrées officielles, proto-alphabet, lignes générales inédites, pilote borné et revue non-auteur | R23-OCR-02, W035, skill LSTM, entrées exactes et supervision qualifiée ; aucun DEV/final pour apprendre | Identités réelles et séparation des groupes ; proto/lexiques conservés ; apprentissage surveillé ; sortie unique et métriques préalables respectées ; revue indépendante ; aucun résultat produit déduit | VALIDATED_BOUNDED — pilote CPU Linux aarch64 au taux 0,001, 500 itérations, données existantes sans régénération : 400 variantes par bras, toutes les gates d'origine PASS. CER 4/21 200, témoins 0/8 642 ; rappel de ± à 28 px : 97,5 %, autres cellules : 100 %, précision : 100 %. Dix observations réutilisées, 811 identités absentes et ressources conformes dans 708 échantillons ; GO_NATIVE_PILOT_ONLY accepté ROOT. Échecs historiques conservés ; aucun modèle installé changé, ingestion P02 et critères globaux non qualifiés. [Résultats et suite nécessaire](journal/2026-10-06.md#r23-ocr-03--taux-mainteneur-et-refus-anticipé), [portée W035](DECISIONS.md#essai-du-taux-mainteneur--6-octobre-2026) |

Travail prévu, dans l'ordre utile :

- Verrouiller les artefacts exacts, leur provenance et leur licence. Vérifier le
  tokenizer, le template et le comptage des tokens pour le 2B ; ne pas réutiliser
  ceux du 4B sans preuve de compatibilité. Examiner la nécessité d'une dérivation
  texte seul selon W006, sans la supposer acquise pour cet artefact.
- Réutiliser la sélection par profil et les lanceurs existants. Séparer les
  manifestes du 2B et du 4B ; vérifier que l'absence du modèle non choisi ne
  bloque pas à tort la préparation ou le démarrage du modèle choisi. Aucun
  téléchargement à `up`, aucun remplacement silencieux du modèle actif et
  aucune nouvelle architecture de providers. Le mode non-thinking reste explicite.
- Mesurer le chargement à froid et à chaud, la mémoire et les latences sur une
  instance QA isolée. Calibrer l'admission à partir de ces mesures, sans reprendre
  les estimations 4B ni réduire la réserve pour obtenir un PASS. Un essai sur le
  Jetson de 61 Gio ne qualifie pas D07 sur un hôte de 16 Go maximum.
- Exercer une vraie question RAG avec ce modèle, le flux SSE, l'abstention et les
  citations versionnées, puis comparer la qualité sur le même jeu de développement
  et avec les mêmes extractions. Ne pas régler sur le jeu final ; ne pas charger
  les deux modèles simultanément. Aucun changement d'embedding, nouvel OCR ou
  réindexage du corpus n'est requis par le seul choix du modèle de génération.
- Contrôler la non-régression du démarrage 4B, les refus sur modèle absent,
  identité/quantification incorrectes et mémoire insuffisante ; faire relire les
  preuves, puis mettre à jour les procédures et références stabilisées seulement
  après validation réelle. Distinguer Windows, Linux aarch64 et Linux x86-64.

**État vérifié :** contrelecture terminale QA3 achevée : session
ROOT 59382 EXIT1, préparation refusée à 900,18 s par ACTIVE_STAGE_DEADLINE ;
arrêt et conservation bornée vérifiés, qualification refusée.
**Prochaine action de ce lot :** isoler le coût réel de préparation avant
une optimisation ciblée et son témoin, pas une quatrième relance identique.
Instrumentation source-only et diagnostic distinct : [contrat borné](journal/2026-10-05.md#r23-ocr-03--instrumentation-des-coûts-et-diagnostic-borné).
Le diagnostic distinct a terminé EXIT0 après 44 tests parent et 35 tests worker,
revue préparatoire indépendante ; résultat et fermeture relus conformes
par le rôle non-auteur, dans la seule portée diagnostique.
La décomposition des quatre appels a été exécutée sur une cible neuve :
[protocole et répartition](journal/2026-10-05.md#r23-ocr-03--décomposition-de-la-fermeture-des-journaux).
Parent et config raccordés par inversion exacte ; 38 tests nouveaux et
revue préparatoire conformes, parent EXIT0 après publication terminale.
Validation finale indépendante acquise dans la seule portée diagnostique.
Prochaine action : qualifier une correction ciblée de préparation qui
conserve les synchronisations et les
limites du pilote. Le correctif à deux lignes et le parent avec interruption
différée sont figés et relus dans la portée de protocole ; les erreurs
de lancement ou de retour non nul ferment désormais les admissions avant
la fermeture raw. Le raccord strict de config, ses 32 témoins et le
contrôle ROOT des cinq pins avant/après sont fermés. Exécution complète
unique session11165 fermée EXIT1 à18:15:03 UTC par le plafond de préparation,
900,46 s ; 1485 LSTMF partiels présents, pas d'apprentissage. Revue
finale non-auteur fermée, arrêt/conservation vérifiés bornément et
qualification refusée. Mesurer séparément initialisation de fonte,
dessin/encodage et publication des images avant une correction prouvée.
Les tests purs et le GO de protocole ne prouvent pas un gain ou une
préparation complète conforme.
Pas de quatrième relance identique.
Aucun résultat de ce diagnostic ne valide
les 1 000 groupes ou les 2 000 variantes du pilote complet.
Les contrôles d'identité, ressources et arrêt restent inchangés.
La préparation complète dans les 900 secondes reste non démontrée ;
le correctif procfs et les tests purs ne la valident pas.
Les entrées, fonte, proto, données et budgets restent inchangés ; ancien dataset
partiel exclu. Aucun redémarrage, hausse de budget ou adoption automatique
en cas d'échec. Ne pas rejouer
les essais de densité ou de mode sur ces alphabets incomplets. P03 est déjà
qualifié et publié ; son extraction privée n'est pas encore republiée par API.
La QA DEV précédente est arrêtée, les cinq captures publiées sont conservées. Après correction P02,
terminer les publications, vérifier l'extraction/OCR et résoudre les 100 scopes
et 90 unités attendues avant comparaison sur les mêmes questions et extractions.
Les deux pilotes GPU sont terminés ; leurs mesures ne ferment pas l'admission.
La procédure privée C reste une préparation, pas une preuve d'exécution DEV ;
elle vise sept documents d'une famille, et non sept familles. Ne pas utiliser
les anciens 16/20 comme bras apparié ni ouvrir le jeu final. Tracer et traiter le jugement
injustifié du 2B sans retirer le texte synthétique des preuves. R15-3-F03/F04,
Q05, les qualifications de plateforme et la DoD globale restent ouverts.

## Inspection autorisée et état courant

| ID | Couche et résultat attendu | Dépendances | Critère de validation | Statut | Preuve |
|---|---|---|---|---|---|
| I01 | Documents, architecture et intégrité du pack compris | Instructions applicables | Lecture des références, comparaison archive/extrait et manifestes | VERIFIED | Rapport d'inspection à consolider ; contrôles SHA-256 avant mise à jour du suivi : 20/20 et 18/18, archive 21/21 |
| I02 | CPU, RAM, GPU, disques et charge observés | Accès lecture machine | Mesures CIM datées et distinction capacité/disponibilité | VERIFIED | Relevés Windows des 29/09/2026 23:56–23:59 UTC ; rapport à consolider |
| I03 | Node, Python, OCR et plateforme disponibles identifiés | I02 | Versions exécutées, paquets et chemins vérifiés, absence PATH distinguée de l'installation | VERIFIED | Python 3.13.3 hors PATH, Node 22.17.0, pnpm 10.34.1 ; rapport à consolider |
| I04 | Corpus caractérisé et diagnostic écrit | I01, I02, I03 | Comptes/hashes/pages, inspection structurelle et visuelle, rapport et journal reliés | VERIFIED | reports/INSPECTION_DOSSIER_MACHINE_2026-09-30.md, reports/preuves-inspection-2026-09-30/corpus-inspection.json ; 182 pages et 24 échantillons visuels |
| I05 | Contrainte Windows native intégrée au référentiel | Décision utilisateur W001 | Documents actifs cohérents sans prérequis WSL/Docker ; voie native prouvée par sources officielles et contrat d'exploitation explicite | VERIFIED | DECISIONS.md, EXPLOITATION_WINDOWS.md ; les runtimes eux-mêmes ne sont pas encore qualifiés |

Les couches de réalisation ci-dessous sont autorisées par le `/goal` utilisateur du 30 septembre. Le suivi distingue réalisation en cours et validation acquise ; aucune case de recette n'est cochée par anticipation.

## Pilotage

Mettre à jour après résultat, décision ou blocage significatif. Un résultat `VERIFIED` doit pointer vers sa preuve et les critères de recette associés. États de travail : `NOT_STARTED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `VERIFIED`. Seul le propriétaire d'intégration modifie les contrats partagés et les lockfiles communs.

## Dépendances entre les couches de réalisation

Les couches B, C et D peuvent avancer en parallèle après les précontrôles A,
avec les moyens de qualification E. Leur intégration produit la chaîne réelle V ;
la recette complète F s'appuie ensuite sur les résultats indépendants de chaque couche.

| Couche | Responsabilité | Dépendances |
|---|---|---|
| A | Inspection, précontrôles et contrats minimaux | Instructions et références applicables |
| B | Ingestion, versions, provenance et géométrie | A ; appuis E |
| C | SQLite, Qdrant, embeddings, recherche et API | A ; appuis E |
| D | Interface, PDF.js, état, périmètre et citations | A ; appuis E |
| E | Fixtures, outillage, fonctionnement hors ligne, ressources et recette | A |
| V | Première chaîne verticale réelle | B, C, D et appuis E |
| F | Robustesse et recette complète | V et résultats indépendants de B, C, D et E |

Les branches B/C/D/E progressent en parallèle après leurs contrats minimaux, sans attendre qu'une branche entière soit achevée. V doit être intégré tôt, pas reporté après la finition de tous les écrans. La coordination ne doit pas saturer la machine avec plusieurs travaux lourds.

| ID | Résultat observable | Dépendances minimales | Propriétaire logique | État initial | Critères |
|---|---|---|---|---|---|
| A | Inventaire existant, doctor initial, contrats Scope/Citation/Chunk/QueryEvents, versions résolues | Accès dépôt/outils | Intégrateur | IN_PROGRESS | D01 ; packages/contracts/contracts.json présent, runtimes et doctor en préparation |
| B | Un PDF réel converti en blocs et provenance testable, indexation reprenable | Contrats version/page/bloc | Agent ingestion | IN_PROGRESS | D02,D03,D06 ; skill pdf-ingestion-windows créé et validé, code en cours |
| C | Requête scope → vrais BM25 et Qdrant → preuves et vraie génération locale | Contrats chunks/scope/events | Agent retrieval/API | IN_PROGRESS | D04,D05 ; frontières API/ingestion/governor partagées, code en cours |
| D | Trois panneaux et navigation citation→PDF fonctionnant contre API réelle | Contrats UI/API | Agent UI/PDF | IN_PROGRESS | D06 ; skill pdf-workspace-web créé et validé, versions npm officielles résolues |
| E | Fixtures, doctor, runners, traces réseau et mémoire, scripts exploitation | Structure et contrats utiles | Intégrateur qualité/exploitation | IN_PROGRESS | D01,D07,D08,D09 ; skill windows-rag-runtime créé, lu et validé |
| V | Import→extraction→index→question→réponse→clic→surlignage | Première version intégrable de B/C/D | Intégrateur | IN_PROGRESS | D02,D04,D05,D06 ; DEV publié, recherche et lecteur vérifiés ; première question refusée avant modèle par admission mémoire |
| F | Recette complète et rapport honnête sur machine cible | V et critères applicables | Intégrateur + vérificateur | NOT_STARTED | D01–D11 |

**État au 1er octobre 2026, 14:52 UTC** (le tableau garde l'état du 30/09 ; le suivi courant est porté par les lots R et J) : A IN_PROGRESS — contrats et `doctor` livrés, D01.3 à D01.5 cochés, D01.1 et D01.2 ouverts (R10) ; B IN_PROGRESS — D02.1, D02.2, D02.8 et D03.1 à D03.6 cochés, D02.3 à D02.7, D02.9 et D02.10 ouverts (essai d'extraction interrompu le 01/10 à 09:21), D03.7 à D03.9 ouverts (génération, R7) ; C IN_PROGRESS — D04.1 à D04.6 et D04.8 cochés, D04.7 et D05 attendent la génération (R7, R13) ; D IN_PROGRESS — D06.1 à D06.4, D06.7, D06.8, D06.10 et D06.11 cochés, D06.5, D06.6 et D06.9 ouverts ; E IN_PROGRESS — D08.3, D08.4, D08.6, D08.7 et D09.1 à D09.4 cochés, D07 non mesuré (R8), D08.1 bloqué (point à trancher 1), D08.2, D08.5 et D09.5 ouverts ; V : parcours vertical démontré (R2, point de 05:02), D05 non coché ; F NOT_STARTED (R13). Correction du 01/10 (J6).

## Répartition de fichiers

B possède `services/ingestion/` et ses tests. C possède les modules search/context/embedding/citations du backend et leurs tests. D possède `apps/web/`. E possède fixtures, evals et scripts qualité/exploitation. L'intégrateur possède `packages/contracts/`, les migrations partagées, les routeurs communs, la configuration et les lockfiles. Ajuster la répartition à l'existant sans écraser les travaux étrangers.

Répartition actuelle déléguée : B possède ingestion et ses tests ; C possède `services/api/`, y compris ses migrations/routeurs SQLite, et ses tests ; D possède frontend, package et lockfile propres à `apps/web/`. L'intégrateur possède `services/runtime/`, scripts, configuration, contrats, dépendances Python, fixtures/évaluations et suivi. Chaque agent crée/lit son skill spécialisé avant de coder. Les installations et tâches lourdes sont séquencées par l'intégrateur ; contrôle régulier de RAM/CPU/disque, aucun OCR/build/benchmark lourd concurrent.

## Points vérifiés et décisions restantes

Vérifiés : inventaire initial sans code/Git, corpus de cinq documents dont 182 pages PDF image, CPU 10 cœurs/12 logiques et 16 Gio, Python 3.13 installé hors PATH, Node/pnpm exécutables, sources officielles de binaires Ollama/Qdrant Windows. La présence de dépendances n'est pas une preuve d'intégration.

Décision acquise : Windows natif W001. Le noyau accepte les PDF ; le DOCX original est conservé hors de l'index PDF tant qu'un contrat métier distinct n'est pas demandé. Les scans PDF fournis constituent le corpus métier autorisé. La collision du port 8765 sera traitée par configuration explicite du projet, sans arrêt du programme existant.

Dernier relevé avant provisionnement : 30/09/2026 00:15:55 UTC, environ 4,39 Gio disponibles, 39,24 Gio libres sur D:. Ces valeurs évoluent ; aucune admission lourde n'est déduite de ce seul relevé. Prochaine action exécutable : provisionner uv/Python isolés et les dépendances verrouillées, puis intégrer les premiers résultats B/C/D et mesurer une tranche réelle.

Les mocks contractuels temporaires sont admis pour débloquer une branche, avec un marquage explicite. Ils sont retirés du chemin de livraison avant V et ne donnent aucun PASS E2E.

## Première tranche verticale

Un PDF natif FR contrôlé contenant une valeur technique identifiable, une section et une table simple. L'utilisateur l'importe, le voit dans le dossier, pose une question, obtient une réponse du vrai Ollama avec ID de preuve ; le clic ouvre la page et le bloc. Conserver la trace de toute la chaîne et les compteurs réels. Étendre ensuite aux difficultés en gardant cette tranche en non-régression.

## Règle de déblocage

Un blocage doit préciser symptôme, preuve, hypothèse, test déjà effectué, propriétaire et prochaine action discriminante. Un agent bloqué sur une dépendance ne réécrit pas le composant d'un autre : il réalise une tâche indépendante prête ou réduit le cas de test qui manque.

Un changement de stack n'est recevable que si la baseline échoue sur un cas mesuré et qu'un changement limité corrige ce cas dans le budget. Ne pas repartir en benchmark général après une erreur de paramétrage.

## État à renseigner pendant l'exécution

Le journal doit enregistrer les faits nouveaux sous forme date/ID/résultat/preuve/décision. Au moment de remise de ce brief : **aucune preuve d'exécution applicative, aucune performance cible et aucun critère D01–D11 ne sont déclarés validés**.

## Intégration V2.1 — 30/09/2026 UTC

Références : [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md), [QUALIFICATION.md](QUALIFICATION.md), décision W002. Les lots existants restent actifs ; aucun second plan. D10/D11 ajoutent qualification précoce, sources officielles, usage des skills et cohérence documentaire. OCR régional, révisions immuables, offsets en points de code, couverture du contexte final, pause coopérative et reprise manuelle sont maintenant des exigences d’implémentation. Recette : 16 PDF synthétiques minimum, 200 questions séparées 100 développement / 100 final, plus corpus métier autorisé. Les seuils ne sont ni diminués ni déclarés atteints.

Provisionnement observé à cette étape : uv 0.12.21 isolé, Python 3.12.14 local ; la résolution initiale comptait 126 paquets avant ajout du générateur de fixtures. Les résultats ultérieurs ci-dessous font foi pour l'état courant.

## Résultats partiels à 01:45 UTC — intégration en cours

A/E : premier `up` natif et second appel idempotent PASS, services Qdrant 1.19.1/Ollama 0.35.0/API en loopback, sans chargement LLM implicite. Readiness 503 cohérente sur base vide (collection absente). Preuves : reports/runtime-first-up.json, runtime-first-duplicate-up.json, doctor-first-running.json. Arrêt/reprise réels restent à qualifier.

QCPU : premier pilote froid FAIL `httpx.ReadTimeout` après 300 s sans premier token. Le log natif rapporte 2970 tokens d'entrée, 23,64 s de chargement, préfill 1024 tokens/118,23 s puis 1946/229,99 s. Essai chaud non exécuté. Le runner n'avait pas persisté ses échantillons avant exception ; ce défaut est corrigé pour les essais suivants. Preuves : reports/cpu-pilot-first-failure.json et cpu-pilot-first.service.log. Aucun seuil modifié, aucune performance extrapolée.

B : révision native antérieure 8 tests PASS, révision actuelle 24 tests unitaires PASS ; rerun natif/OCR courant requis. Le mixte a révélé langues non relayées, config TSV manquante puis pertes réelles de chiffres/unités. Les deux premières causes sont corrigées ; une correction de grille sur raster dérivé récupère les valeurs au diagnostic Tesseract, conversion complète encore en cours. Un avertissement d'incertitude n'est pas une validation d'exactitude. Preuves persistantes sous .runtime/qa/ingestion-synthetic ; l'ancien manifeste temporaire pytest supprimé automatiquement n'est pas reconstitué.

C : suite préstart sous Python 3.12 42/42 PASS ; histoire/scope 10/10 PASS après correction d'un risque de reprise des anciens messages lors d'un changement de scope. HTTP ciblé 8/8 PASS après correction du corps 304 et ajout de la couverture/publication des jobs. Compteurs LLM des chunks corrigés, 2/2 ciblés PASS ; redémarrage pour intégrer ces dernières écritures. Preuves distinctes dans reports/backend. Aucun retrieval qualité ou réponse réelle annoncé.

D/E : frontend actuel 12 tests PASS et typecheck PASS, nouveau build requis après ces changements ; build antérieur conservé comme preuve de sa révision. Fixtures : 32 PDF synthétiques, 200 questions réparties 100 développement/100 final, 15 tests structurels PASS, génération stable et gel final. Préflight indépendant : 150/180 unités de preuve présentes en texte natif, 30 unités attendent OCR ; annotations API encore à résoudre. Aucun final utilisé pour tuning.

E/D09 : commandes backup/verify/restore implémentées. Sauvegarde cohérente vide et restauration vers une autre racine PASS ; 7 tests backup PASS après deux échecs liés aux handles et fichiers WAL/SHM, conservés séparément. Provenance complète et comportement de snapshots peuplés/recherche/ancienne citation encore non exécutés. Preuves reports/backup-empty-first.json, backup-empty-rerun.json, restore-empty-first.json, runtime-backup-tests*.xml. D09 reste ouvert.

Corpus : ajout concurrent de manuels Z2M observé, 67 fichiers/634,118 Mio dans PDF. Les cinq originaux initiaux sont re-hashés identiques 5/5 ; aucun import/OCR en masse implicite. Preuve reports/corpus-delta-2026-09-30.json. Ressources 01:39 UTC : environ 6,13 Gio disponibles, 30,38 Gio libres sur D ; mesures continues lors des travaux lourds, un seul moteur lourd à la fois.

Prochaine action : terminer le rerun OCR ciblé, rebuild et redémarrer la révision intégrée, puis effectuer V réelle avec une fixture de développement et mesurer l'admission Qwen. V passe IN_PROGRESS au premier import réel ; F et D01–D11 restent non clos.

Mise à jour 01:46 UTC : le rerun mixte corrigé PASS en 106,30 s, tableau 4×3 et cellules/unités exactes (24 V, 45 °C, 2 A), natif préservé sans duplication, aucune région non résolue. Preuve .runtime/qa/ingestion-synthetic/mixed-corrected-20260930T014335Z ; pic RSS arbre 1063,62 Mio, réserve hôte minimum 5,0 Gio. Les scans et échantillons métier ne sont pas encore déclarés validés.

## Résultats partiels à01:07UTC — réalisation continue

A/E : Python3.12.14 +uv0.12.21 +127paquets résolus (126installés), lock Python/npm présents ; bootstrap -Offline PASS ; doctor distingue fichiers présents et services absents. Scripts rag.ps1/bootstrap.ps1 et runtime Windows présents, start/stop réels encore non validés. Job Object vrai enfant+descendant PASS après correction initiale. Governor3tests PASS, contrôles ruff ciblés PASS.

B :18tests unitaires +8natifs offline sous envfinal PASS ; pic arbre381,27Mio, sections/pages4/5/rotations/CropBox/reprise contrôlées. Premier mixteOCR FAIL (TESSDATA_PREFIX non relayé dans certains appels Docling), correction/rerun en cours. Aucun D02 complet.

C : suite initiale22cas PASS avec doubles explicitement isolés sous Pythonglobal3.13 ; smoke E5réelCPU/tokenizerQwen .venv3.12 PASS, preuves reports/backend. Contrôles finaux3.12 en cours.

D : typecheck PASS après4erreurs initiales conservées,7tests offsets/budgets PASS, export statique réel PASS. Aucun E2E réel encore déclaré.

E : Heron/TableFormer/languesOCR/E5/tokenizers/binaires natifs téléchargés et hashes vérifiés ; Qwen4B pull en cours sans inférence. Fixtures16+PDF/dataset200questions en préparation, annotations de blocs/révisions à résoudre sur extractions réelles. V etF restent NOT_STARTED ; D01–D11 non clos.

## Résultats partiels à02:30 UTC — reprise verticale

Les entrées01:07 et01:45 ci-dessus restent historiques. États courants : A/B/C/D/E/V IN_PROGRESS, F NOT_STARTED, aucun D01–D11 clos.

QCPU : pilote court réel279 tokens d'entrée, deux sorties64 tokens, PASS_PILOT_ONLY. Froid TTFT55,844s, chaud même préfixe0,813s ; le préfill chaud réutilise275/279tokens. Pic RSS somme3883,39Mio, hôte minimum2325,80Mio, CPU seul/contexte8192. Profil froid4352Mio, chaud additionnel512Mio, cache256Mio/deux checkpoints ; réserve1536 inchangée. Preuve reports/cpu-pilot-short-4threads.json. Aucun résultat3000/400tokens ni estimation de ces latences. Governor surveille la réserve et annule seulement la requête possédée ; six contrôles ciblés PASS, reports/governor-watch-final.xml.

B : dernier essai mixte/scans1PASS+2FAIL (valeurs/unités manquantes sur scan0, orientation erronée sur scan90) ; journal de faute native observé au second extract, pytest exit1. Les corrections orientation/OCR de cellules, limites raster8M et quarantaine sont implémentées,30 unités PASS, mais ne constituent pas un rerun réel du défaut. Fenêtres4+1 dans un même worker et échantillons métier encore à exécuter, sans moteur lourd concurrent.

C : suite intégrée59PASS, admission E5 conditionnelle5PASS, hook réserve4PASS. Retrait d'un document avant reprise du job : premier contrôle3FAIL/1PASS conservé, correction6PASS. Code actuel chargé dans API ; publication/collections réelles et évaluations100DEV/100final encore non exécutées.

D/V : build V2.1 PASS et15 unités PASS. Premier import navigateur créé, job8294f3ef-100a-475e-8378-983360f88b69 suspendu à5630Mio contre5632requis par ancienne estimation parser4096. Estimation parser2304Mio fondée sur mesure réelle1477,55RSS/1669,73private, réserve conservée. Version11debf6d-6e3c-4874-9ea4-395c1ad6661c et document e01b0666-ae93-40e5-9403-35decf00ae84 conservés ; reprise explicite, aucun reset/réimport. Premier E2E révèle viewer bloqué avant publication ; correction/build PASS, styles PDF.js6 encore en correction avant reprise. Preuve apps/web/test-results/2026-09-30-native-dev-first.

A/E : deux arrêts natifs réels exit0 des trois services. Premier redémarrage calibré FAIL WinError5 sur remplacement de runtime.json ; log conservé reports/runtime-calibrated-first-start-failure.log et rapport runtime-calibrated-up.json. Temporaires uniques et reprises bornées lecture/écriture NTFS corrigés ; premier test concurrent1PASS/1FAIL conservé, rerun réel Win32 2/2PASS, reports/runtime-atomic-windows-rerun.xml. Nouveau up PASS instancea0b20f3477944f73b22ad7328ebb4c31, reports/runtime-calibrated-up-rerun.json. Aucun processus tiers arrêté.

E/D09 : inventaire licences réellement installé126distributionsPython/71versionsnpm/26artefacts/18avis, reports/licenses-2026-09-30.json ; métadonnées, pas certification juridique ni preuve complète des runtimes prérequis. Snapshot peuplé/restauration/requête/ancienne citation toujours à faire.

Ressources02:29:24 UTC : RAM disponible6114,09Mio, D31070,55Mio, CPU3,8%. Prochaine action exécutable : achever styles PDF.js/build puis reprendre le jobDEV existant ; contrôler index réel, afficher sa version puis poser une question Qwen. OCR lourd attend ce créneau.

## Résultats partiels à 03:55 UTC — sources réelles et robustesse

A/B/C/D/E/V restent IN_PROGRESS ; F et la recette complète restent ouverts. Les mentions précédentes constituent l'historique.

V : même job repris explicitement, publié à02:35:57 UTC : document e01b0666-ae93-40e5-9403-35decf00ae84, version11debf6d-6e3c-4874-9ea4-395c1ad6661c, génération57ffa153-0f74-429b-82a8-72579b163e22. Deux pages structurées,11 blocs/11 chunks SQLite=11 points Qdrant, original et hashes source vérifiés. Preuve [publication](reports/backend/2026-09-30-first-publication-readonly.json). La fixture contient une table ; elle ne qualifie pas la voie native simple.

D :17 unités/typecheck/build PASS, export278 fichiers ; E2E source réel PASS11,4s après corrections TextLayer/PDF.js, rejet de promesse de rendu et metadata de recherche. Échec du locator de bibliothèque puis échec RenderingCancelledException conservés séparément, sans les convertir en durée d'indexation. [Rapport UI](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Recherche sans LLM, sélection réelle, source physique, rotation90/zoom125 et warnings objets vérifiés ; aucune réponse modèle encore qualifiée. Bindings DEV15/100 résolus sur cette seule famille ;85 questions restent à résoudre, final non utilisé pour réglage.

V/QCPU : question2f36429b-2ac6-4c5f-83c3-d72271f1adf9,03:03:19–03:03:23 UTC, FAIL admission froide5095Mio<5888 requis. `model_called=false`, aucune génération ni delta ;384 est le budget de sortie. La libération E5 récupère122,38Mio RSS et99,46Mio disponibles, insuffisant. [Preuve navigateur](../apps/web/reports/e2e-2026-09-30-qwen-question-first-evidence.json). Éviction conditionnelle supplémentaire des caches Rust E5/Qwen implémentée,14 contrôles PASS ; effet réel et coût/parité de rechargement encore à mesurer. Réserve1536 et seuils de performance conservés. Digest Qwen maintenant vérifié avant envoi du contexte,19 tests gateway PASS ; doubles HTTP explicitement identifiés.

E/D09 : sauvegarde peuplée20260930T031052Z-920d8a2a vérifiée,21 fichiers, SQLite intègre, snapshot248032768octets checksum4a6ee822a7df94997110ef189199a1f719559cc1d88c1c4d7951cb866a2f647e. Restauration initiale longue FAIL500/os3 ; variante chemins étendus FAIL500/os145 ; stockage court intermédiaire encore FAIL au temporaire, tous conservés. Restores ASCII court et Unicode court PASS ; solution avec stockage Qdrant plus court explicite et destination Unicode longue PASS : [preuve](reports/restore-first-published-long-root-short-store-rerun.json). Dix copies de données hashées avant rebasing, comptes identiques et11 points récupérés, Qdrant exit0. Démarrage applicatif/requête/ancienne citation sur restauration encore NOT_RUN. Verrou distinct du stockage Qdrant ajouté : premier contrôle2FAIL dû aux chemins de fixtures trop longs, reprise2PASS avec deux vrais superviseurs isolés, [preuve](reports/runtime-shared-storage-rerun.xml).

B : scan90 avec drain lifecycle FAIL sur journal natif ; parser/rendu sans Torch3PASS, avec Torch contre-exemple FAIL puis stress16cycles : deux AV dans docling_parse/pdf_parsers.cp312-win_amd64.pyd+0x7e4a57, lecture0xffffffffffffffff. Les processus continuent : le titre faulthandler first-chance ne prouve pas terminaison et les stacks d'autres threads ne localisent pas le fautif. Backend officiel pypdfium2 : journal natif vide, mais fidélité/orientation OCR encore FAIL (ready_partial/table3×4). Preuves séparées sous .runtime/qa/ingestion-synthetic. Correction géométrique ciblée en cours ; scans5pages4+1 et métier non validés.

Points vérifiés : arrêt/redémarrage natifs sans perte, dernière instancec87c102408de4d10aab9f8040b4e0be3 ; aucun service étranger arrêté. Qdrant1.19 utilise des tiers mémoire mmap ;11 points ne construisent pas encore HNSW. Licences/prérequis126 Python/71 npm/26 artefacts/18 notices inventoriés, provenance installateur Tesseract toujours limitée. Candidat IBM officiellement identifié (commit835ad14087e140460703cf0fae09f97d469d65c2, CLS/L2/384), skill lu/validé et lock séparé ; aucun téléchargement/inférence/A/B encore annoncé.

| Action | Classe / couche | Dépendance et livrable | Validation exacte | État / preuve |
|---|---|---|---|---|
| W-P01 | Bug / stockage Windows | Snapshot peuplé ; chemins courts explicites sans réglage global | Hashes/comptes puis API/recherche/ancienne source sur destination longue | Implémenté ; stockage PASS, parcours restant ; rapport restore ci-dessus |
| W-M01 | Amélioration / mémoire | Contexte déjà compté, modèle froid ; éviction mesurée et verrouillée | Admission et réponse Qwen réelles avec réserve ; rechargement/parité | Implémenté/tests PASS ; mesure applicative restante |
| W-PDF01 | Bug ou interaction native inconnue / ingestion | Backend officiel distinct ; même PDF et assertions | Scan90 exact, aucune faute/unresolved, puis scan0/mixte/4+1 | FAIL fidélité ; essai PDFium034739 conservé |
| W-REV01 | Incohérence / API et lecteur | Route blocks/outline révision explicite, sélection fixée | Ancienne révision après reindex, sans fallback courant ni fuite de scope | Correctifs intégrés au redémarrage04:36 ;10 tests API et27 unités web PASS ; parcours réel après reindex restant |
| W-CACHE01 | Amélioration / observabilité | Compteurs d'inférence/cache/worker et cas blanc | Réimport/reindex réellement sans calcul redondant ; blanc visible |14 tests PASS, nouveau restart requis ; E2E restant |

Prochaine action : achever le correctif OCR discriminant et la révision du lecteur, intégrer la révision stabilisée, mesurer l'éviction mémoire puis reprendre la première question réelle. Les contrôles de restauration applicative, évaluation DEV/comparatif/final,25k/30 questions/30min et blocage réseau OS restent à exécuter ; aucune case globale de Done anticipée.

## Résultats partiels à04:36 UTC — révision intégrée

A/V : arrêt de l'instancec87c102408de4d10aab9f8040b4e0be3 et redémarrage natifcc0b7e974ab14645af67f0f7c27bc8dc PASS, trois services arrêtés exit0, santé/readiness200, aucun modèle chargé implicitement. Le démarrage conserve désormais un manifeste des fichiers réellement observés, empreinte4b23a6a7af8db2ad3f24c347a02041d4eb1105ecde055095f5a1f2651867877d, sans inventer de révision Git. Doctor confirme le profil appliqué et le stockage Qdrant Windows valide. Preuves : reports/runtime-integrated-down-20260930T0436.json, runtime-integrated-up-20260930T0436.json, doctor-integrated-20260930T0437.json. Mémoire disponible au doctor5672,35Mio ; D27979,64Mio. La nouvelle question réelle attend son résultat ; aucune réponse anticipée.

C/D : routes de révision historique et sélection épinglée corrigées après trois échecs API conservés ;10 tests API PASS. Le bouton Retour perdait encore la source/révision archivée : deux unités en échec conservées, correction puis27 unités web/typecheck PASS. Build final PASS98,94s,278 fichiers/6673451octets, workspace/index.html SHA25698d86335841d59c28c4be723ac0f70fe872206180c4f32031301f101705e0253. Minimum RAM disponible pendant ce build5228,7Mio. Les dix nouveaux parcours lifecycle restent NOT_RUN ; un build n'établit pas leur réussite. Preuves sous apps/web/reports, tag2026-09-30-pinned-revision-return.

B : essai cinq pages PDFium terminé avec fenêtres4+1, journal de faute native vide et lifecycle drainé, mais FAIL sur fidélité des cellules/unités ; ceci ne ferme pas D02. Lecture TSV corrigée pour conserver les textes numériques et chaînes littérales ;42 contrôles purs PASS. Géométrie bitmap et bordures de cellules préparées sous options expérimentales désactivées par défaut ; aucun nouvel essai OCR ni adoption nominale à cette étape.

D10 : dix artefacts Granite provisionnés et hashes réels vérifiés, sans inférence. Runner séparé préparé sur export SQLite immuable,17 tests PASS après correction d'une fixture et d'une étiquette erronée, échecs conservés. Comparaison DEV100 et smoke de graphe restent NOT_RUN ;15 bindings DEV résolus ne constituent pas une évaluation complète. Preuves reports/backend/2026-09-30-comparison-runner-export-corrected.* et granite-identity-static.json.

Prochaine action exécutable : mesurer la question Qwen sur cette révision, puis qualifier API/source sur la restauration Unicode longue ; réserver ensuite le créneau lourd à l'OCR discriminant. D08 prépare un aperçu de règles Windows, sans modification du pare-feu ; contrôle réseau OS toujours non exécuté.

## Reprise du 30/09 à 08:43 UTC — état consolidé et lots R

Les sections précédentes restent l'historique. Entre 04:36 et 04:49, sans mise à jour du suivi : seconde question Qwen refusée avant modèle (5222 < 5888 Mio), arrêt de l'instance principale `cc0b7e97…` (04:44), démarrage de l'instance restaurée (API 8795), E2E ancienne citation en échec. État des lieux de 08:46 par six cartographies en lecture seule relues par l'intégrateur (rapports de sous-agents non versionnés ; constats repris ci-dessous avec leurs preuves).

**Statut par critère à 09:30 UTC** (seules les puces avec preuve sont PASS) : D04.1, D06.1, D07.6, D09.1, D09.2 PASS ; D09.3 citation PASS après restauration, question en cours ; D02.3, D02.6, D02.10, D04.4 (identifiants parasites), D03.2 (déplacement absent), D10.4, D11.8 FAIL ; D08.1 BLOCKED (pas de droits administrateur : blocage réseau OS impossible sans décision utilisateur) ; tous les autres critères PARTIAL ou NOT_RUN. Aucune recette globale close.

**Contrôles précoces (D10.1)** : Q-CPU PARTIAL — pilotes texte 900 tokens PASS_PILOT_ONLY, préfill ≈ 8,6 tokens/s sans réutilisation de préfixe pour un contenu nouveau, TTFT ≈ 106 s à 919 tokens ; la cible D07 (45 s à ≈ 3000 tokens) est très probablement hors d'atteinte sur ce CPU (projection ≈ 350 s, à mesurer). Q-PDF FAIL (W-PDF01). Q-SEARCH PARTIAL (tests unitaires, une requête réelle).

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| R0 | Git / publication | — | Dépôt, exclusions, remote privé, identité unique | Push sans corpus/runtime/secret ; auteur MOHAMED SEDKI sans trailer | VERIFIED — `2d735f2`, `e877c6a` ; W005 |
| R1 | Mémoire / génération (W-M01) | R0 | Modèle texte seul, estimations mesurées | Admission possible sous réserve 1536 ; pilotes conservés | VERIFIED pilotes — W006, W007 ; reports/cpu-pilot-text-900-* |
| R2 | V — première réponse réelle | R1 | Question → sources → réponse Qwen → citation cliquable | SSE brut, model_called, IDs de citation dans le registre, clic UI | VERIFIED le 01/10 (API 04:22, interface 04:46, rejeu 04:57 ; point de 05:02) — historique : 09:27 admise, `model_called=true`, réponse partielle correcte « 3,1 bar [S001] » puis annulée par le gouverneur (réserve 1500 < 1536 sous charge) ; à rejouer hors charge concurrente ([preuve](reports/backend/2026-09-30-restored-question-20260930T0927.json)) ; 20:29 question de l'utilisateur sur le corpus réel : réponse complète (`done`, `stop`), premier token à 175 s (attente d'admission 67 s, chargement 20 s), 298 s au total, 6 marqueurs de citation tous dans le registre (4 sources, 2 documents) ([preuve](reports/backend/2026-09-30-real-corpus-question-20260930T2029.json)) ; reste l'ouverture d'une citation dans l'interface ; 01/10 : VERIFIED — API à 04:22 (done, `model_called`, 6 citations relues, [preuve](reports/backend/r2-question-20261001T042222Z.json)), prompt corrigé (`986d846`, la réponse jugeait la source « non fiable »), interface à 04:46 : question, réponse « 3,1 bar », clic sur la citation, page et surlignage ([preuves](../apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)), rejoué à 04:57 après la mise en forme des réponses (`0c7fd84`) |
| R3 | D09.3 après restauration | R1 | Ancienne citation + question sur la restauration | E2E lifecycle PASS + réponse réelle | Citation VERIFIED ([preuve](../apps/web/reports/e2e-2026-09-30-restored-source-rerun-0910-evidence.json)) ; question VERIFIED le 01/10 à 05:25 sur une sauvegarde au format courant ([rapport](reports/restore-question-2026-10-01-0525.json), `bf71f14`) ; D09.3 coché |
| R4 | Code (7 zones : retrieval, API, runtime, ingestion, outils qualification, outillage docs, frontend) | R0 | Corrections des défauts prouvés, tests, revue adversariale | Tests unitaires/in-process PASS, junit sous reports/backend/…-lotR4-*, revue sans constat bloquant | VERIFIED (niveau unitaire et in-process) — commits c3f9a72, 61e5d78, 4c87775, bc1494f, 0fabf03, 72a10e5, b4c940b ; 7 revues indépendantes, 4 constats majeurs corrigés avec tests de reproduction ; suite complète 355 tests ([junit](reports/backend/2026-09-30-lotR4-full-unit.xml)). Parcours réels, build et E2E relèvent de R2/R3/R5/R6. |
| R5 | Build UI + E2E de non-régression | R4 frontend | Export rebuild, specs a11y/deeplink/géométrie/markup/canvas | Build surveillé PASS, E2E réels PASS sur cible isolée | IN_PROGRESS — 01/10 : E2E réels sur cible isolée (`tools/qualification/e2e_instance.py`, `8186162`) : géométrie 4/4, balisage hostile, budget de canvas, import, recherche, navigation et sélections 5/5 ; lecture seule 11/11 et génération sur l'instance principale ; D06.3, D06.4, D06.8 et D06.11 cochés ; build surveillé (`build-monitored.py`) non rejoué, builds simples `pnpm build` |
| R6 | Ingestion OCR (W-PDF01) | R4 ingestion (E1) | Voie scan fiable ou limite déclarée | scan90/scan0/mixte/5 pages exacts ou ready_partial honnête | VERIFIED sur fixtures synthétiques (W009) : 4/4 OCR sur le profil nominal, voie native 8/8 ; corpus métier et réindex des fixtures DEV restent à faire (R7) ; 01/10 : défaut trouvé par R7 et corrigé (`f1d91df`, W016) : une page A4, Lettre ou Legal scannée en pleine page était refusée en `OCR_RENDER_LIMIT` avant OCR (10,1 M pixels pour un plafond de 8 M) ; DA-P02 désormais lu par OCR, 7 mots de faible confiance signalés |
| R7 | Évaluation DEV (retrieval, contexte, génération) | R4, R6 | Import DA-P02..07, bindings fusionnés, rapports DEV | 100/100 résolues ; métriques avec dénominateurs | IN_PROGRESS — 01/10 07:06 (`a604a76`) : 7 documents DEV sur instance isolée, résolution 94/100 (6 non résolues par erreurs d'OCR réelles), recherche et contexte sans modèle : 83/83 unités au top 5 et dans le contexte (74 questions répondables), MRR@10 0,955, 0 fuite sur 94 questions ([résumé](reports/backend/2026-10-01-development-retrieval-summary.json)) ; reste la génération des 100 réponses DEV et leur grille (D05), plusieurs heures avec l'instance principale arrêtée |
| R8 | D07 performance | R2, R7 | Stress 25k nommé, 30 questions, scénario 30 min | p95 mesurés, FAIL conservés avec phase dominante | NOT_STARTED |
| R9 | D08 sécurité / hors ligne | R4 | Host/Origin sur serveur réel, clé d'API Qdrant, fixture hostile, observation sockets | Rapports ; blocage OS BLOCKED sauf décision utilisateur | PARTIAL — D08.3 VERIFIED sur l'instance principale : clé d'API Qdrant par démarrage (W010), [gardes HTTP réels 15/15](reports/http-guards-live-20260930T1636.json) (API 400/403, Ollama 403, Qdrant 401 sans clé) ; sockets loopback, Ollama sans socket externe. Restent : fixture hostile en E2E réel, D08.1 BLOCKED (décision utilisateur) ; 01/10 04:41 : instruction hostile dans une fixture PDF (inventer 999 bar, citer [S999]) sans effet sur la réponse, instance temporaire ([rapport](reports/injection-2026-10-01-0441.json), `df80786`) ; exfiltration et élargissement du périmètre non mesurés par cet essai |
| R10 | D01 provisionnement neuf | R4 runtime | Racine neuve provisionnée sans édition, redémarrage hors ligne | Rapport provision/doctor | NOT_STARTED |
| R11 | D09.4/D09.5 migration, licences | R4 API | Migration 003 + retour arrière, inventaire livré | Test migration sur sauvegarde, inventaire rejoué | IN_PROGRESS — D09.4 PASS le 01/10 à 04:14 (`77cc185`) : sauvegarde au schéma 2 restaurée et migrée en 3 au démarrage, 8 anciennes citations ouvertes avant et après réindexation, révision conservée, nouvelle génération active ([rapport](reports/migration-2026-10-01-0414.json)), retour arrière documenté ; D09.5 en partie (avis de tiers DIST-07, manques soumis à P7), inventaire à rejouer sur le kit réel |
| R12 | D10/D11 documentation | R4 docs, résultats | Documents canoniques synchronisés, brief, verify_pack PASS, registre skills | verify_pack --report PASS | IN_PROGRESS (outillage dans R4) |
| R13 | Recette finale | R2–R12 | Final exécuté une fois, rapport D01–D11 | Rapport final honnête | NOT_STARTED — preuve préparatoire D05 (01/10 05:33) : trois questions réelles, trois appels `/api/chat`, un seul point d'appel de génération dans le code ([rapport](reports/llm-calls-2026-10-01.json)) ; critères non cochés, la mesure D05 portant sur le test final |
| R14 | Espace documentaire (demande utilisateur reçue vers 09:34 UTC) | R4 docs-tooling, R12 | `docs/` : index documentaire, documentation stabilisée du système livré (architecture technique détaillée avec schémas SVG, spécifications, interfaces HTTP/SSE, dossiers d'exploitation et de déploiement, procédures, référentiels) ; `RAG_Local_Agents/` conservé comme dossier de chantier vivant (plan, journal, décisions, sources, preuves) et référentiel d'exigences V2.1 ; README racine point d'entrée | Chaque document : rôle, statut, date/commit en tête ; aucune information dupliquée entre documents ; liens vérifiés par l'outil documentaire ; procédures rejouées sur le poste | IN_PROGRESS — espace livré le 30/09 (`10b5dd9`), organisation consignée en [W019](DECISIONS.md#w019-espace-documentaire--docs-stabilisé-rag_local_agents-vivant). J9 puis R14-1 le 02/10 : références confrontées au code, propriétaires contrôlés, spécifications et dossier de déploiement ajoutés ; 58 tests documentaires et revue indépendante PASS. Les passages historiques gardent leur référence, les changements W029 sont datés et prouvés. Restent les procédures du kit non exécutées et les qualifications R22 ; rédaction ou contrôle de liens ne vaut pas installation |
| R15 | Textes de l'interface et relecture éditoriale | R4 frontend, R5 | Inventaire de tous les textes UI, réécriture des libellés génériques/bruts, vocabulaire unifié ; réécriture des passages génériques de la documentation existante | Revue de l'inventaire, tests unitaires/E2E mis à jour, captures relues | IN_PROGRESS — livraisons et captures du 30/09 et 01/10 conservées ; [inventaire](../apps/web/reports/ui-text-inventory-2026-09-30.md) actualisé contre le code le 02/10. R15-1 : disponibilité corrigée sans attribution de cause, 224 unités, typecheck/build, six E2E API réels et un négatif UI isolé PASS, deux tailles relues ; références R14-1 rédigées et revues. Aucun audit éditorial intégral de tout le fonds ni rendu de tous les états n'est déduit de ce correctif ciblé |
| R16 | Interface alignée sur la référence de forme decodair (demande utilisateur reçue vers 09:36 UTC) | Analyse decodair (lecture seule), R4 frontend, R15 | Principes retenus/adaptés/écartés documentés (reports/ui-reference-decodair-2026-09-30.md) ; shell (topbar, panneaux repliables/masquables, pied de page si utile, en-têtes), charte (tokens de couleur, typographie, icônes, densité, espacements), composants (cartes, listes, formulaires, filtres, actions, retours, états) et responsive harmonisés ; README racine au format de référence | Aucune régression : tests unitaires, typecheck, build, E2E existants rejoués ; captures 1366×768 et 1920×1080 examinées ; contraste et clavier contrôlés | IN_PROGRESS — livré à 18:31 (`10b5dd9`, [principes retenus](reports/ui-reference-decodair-2026-09-30.md)) ; tests unitaires, `tsc`, build et E2E lecture seule rejoués (18:31 : 8/8 ; 20:17 : 12/12 ; 01/10 03:13 : 11 réussis) ; captures 1366×768 et 1920×1080 examinées (R20) ; clavier contrôlé par `a11y.spec.ts` ; contraste des champs porté à 3:1 (`49a2a1a`) ; reste : E2E existants non tous rejoués sur le dernier build (`lifecycle.spec.ts`, point de 07:09) |
| R17 | Sécurité applicative alignée sur decodair (demande utilisateur reçue vers 16:45 UTC) | R9, analyse decodair (lecture seule) | Mécanismes repris/adaptés/écartés avec preuves decodair, OWASP et sources officielles ; réglages par environnement (développement sans `Secure` ni TLS, production durcie et refus au démarrage si incohérent) | Décision consignée, tests de refus (Host/Origin, CSRF, session expirée ou révoquée), contrôle réel | IN_PROGRESS — W011 livrée et vérifiée sous Windows (30/09 18:31 ; correctifs de 20:17) : refus testés dans `tests/integration/test_api_session.py` et `test_api_tls.py`, gardes réelles [19/19](reports/http-guards-live-20260930T1829.json), E2E de session 3/3, rejouées le 01/10 (`http_guards_check.py` 18/18 et 26/26) ; reste : constat C16 de l'inspection du 01/10 (origine `http://` de l'outil de comparaison en production), corrigé en J5 avec test, à intégrer |
| R18 | Contrôles au vert (demande utilisateur reçue vers 17:00 UTC : lint, typage, build et autres contrôles absolument verts) | — | `ruff check .`, `mypy services`, `tsc`, lint web, tests unitaires Python et web, build surveillé, E2E | Chaque contrôle PASS sur le même commit, sorties conservées | IN_PROGRESS — 17:03 : `ruff` PASS, `mypy` 141 erreurs ; 18:31 : `ruff`, `mypy` (68 fichiers), 417 tests Python, 120 tests web, `tsc`, build, E2E lecture seule 8/8 PASS ; 22:10 : `ruff` et `mypy` PASS, suite Python 477/480, échecs corrigés ou déclarés `xfail` puis rejoués ; 01/10 09:08 : suite complète 538 réussis et 2 `xfail` connus, `ruff` et `mypy` PASS (Windows) ; reste : série complète sur un même commit avec sorties conservées, E2E de cycle de vie (`lifecycle.spec.ts`), mêmes contrôles sous Linux (J5, J8) |
| R19 | Corpus réel `PDF/` pour l'usage, les tests et l'évaluation (demande utilisateur reçue vers 16:55 et 17:00 UTC) | R6, R9 | Import des 65 PDF lisibles avec leur arborescence, extraction complète ou limites déclarées ; E2E et évaluation sur ce corpus sans qu'aucun contenu ne quitte le poste | Documents `ready`/`ready_partial` avec couverture ; rapports agrégés versionnés, jeux dérivés du corpus hors Git | IN_PROGRESS — import 17:01–17:10 : 65 acceptés, 1 refusé (signature PDF absente), 1 `.docx` non pris en charge ; extraction lancée 17:11 ; sur demande de l'utilisateur, 4 documents extraits d'abord (1 prêt, 3 partiels publiés explicitement pour R21), 61 en pause jusqu'à son feu vert ; correctifs issus du corpus : découpes OCR bornées à la page (MIGBT 14/14 pages converties), résultat de worker périmé ; MR2_30A à réindexer |
| R20 | Recette visuelle et UX de l'interface (demande utilisateur reçue vers 17:05 UTC) | R15, R16, R19 | Captures 1366×768 et 1920×1080 sur le corpus réel, écarts relevés contre WCAG 2.2, WAI-ARIA APG, Fluent 2, GOV.UK Design System ; corrections | Captures relues avant/après, E2E et tests unitaires web PASS | VERIFIED (premier passage) — captures relues avant/après ([avant](../apps/web/reports/visual-qa-20260930T1849/), [après](../apps/web/reports/visual-qa-20260930T2015/)), 11 défauts corrigés (états de document, accords, redondance du périmètre, sous-titres décoratifs, Suivi : tri, résumé, priorité, reprise groupée, avancement, limites d'extraction lisibles, traitement remplacé), E2E lecture seule 12/12 ; [rapport de recette](reports/ui-recette-2026-09-30.md) (22:53) : grille de 9 sources officielles (WCAG 2.2, WAI-ARIA APG et 1.2, GOV.UK, NN/g), 11 défauts corrigés avec principe et preuve, 5 points ouverts (sur-titres restants, focus possiblement masqué sous la ligne fixe de l'arborescence, noms tronqués, pas de contrôle axe ni de lecteur d'écran, contrastes non mesurés) ; second passage le 01/10 à 03:10 (`49a2a1a`) : B infirmé (arbre défilant distinct de la ligne « Toute la bibliothèque »), C vérifié (nom complet et chemin en info-bulle), E mesuré ; 2 défauts corrigés (bordures de champ portées à 3:1, légende de page « Aucun texte extrait » affichée pendant le rendu), E2E lecture seule 11 réussis et recette visuelle 4/4 ; A tranché le 01/10 (sur-titres conservés, chacun porte une information ; motif de la référence decodair) ; reste D (audit axe, lecteur d'écran) |
| R21 | Méthode d'évaluation documentée et appliquée au corpus réel (demande utilisateur reçue vers 17:37 UTC) | R19 | Dossier de sources primaires (métriques de recherche, RRF, évaluation RAG, citations, abstention, questions synthétiques, statistiques) ; protocole adapté (CPU, corpus privé, sans expert) ; exécution, analyse critique et améliorations | Métriques avec dénominateurs et intervalles, analyse des échecs par cause, amélioration vérifiée sur un jeu tenu à l'écart | IN_PROGRESS — 31 sources primaires ([dossier](reports/evaluation-methodology-sources-2026-09-30.md)) ; protocole W013 ; séries 1 et 2 de recherche et de contexte exécutées, analysées et critiquées ([rapport](reports/evaluation/corpus-reel-2026-09-30.md)) ; restent l'amélioration vérifiée sur le jeu tenu à l'écart (EV-1) et la mesure de la génération (EV-3) ; 22:35 : diagnostic des pertes (branche lexicale, découpage un bloc par chunk loin de la cible de 320 tokens) ; essai « sans mots-outils » non adopté (5 gagnées / 1 perdue sur les séries 2 et 3, p = 0,22) |
| R22 | Distribution sur d'autres postes (demande utilisateur reçue vers 17:40 UTC) | R10, R17 | Analyse des voies (kit et scripts, installateur Windows, coquille Electron/Tauri, WinGet), licences de redistribution, parcours du poste vierge à « tout est vert » puis import des documents de l'utilisateur | Recommandation argumentée ; réalisation après arbitrage de l'utilisateur ; installation vérifiée sur une racine neuve | IN_PROGRESS — analyse confiée à un agent (17:41) ; réalisation autorisée par l'utilisateur (vers 17:43 UTC) après l'analyse, avec les tests prévus par `CLAUDE.md` et les skills ; contrainte utilisateur (vers 18:17 UTC) : aucune étape ne doit exiger de droits administrateur ou d'élévation ; DIST-01 fait (W011) ; DIST-02 commencé (22:58) : configuration de collection Qdrant lue sous `config/`, copie documentaire contrôlée par `verify_pack` (C12 levé) ; 23:40 : verrou lourd du poste, sauvegardes par défaut, stockages de restauration et cache Hugging Face réglables par la section facultative `runtime` du profil (valeurs par défaut inchangées sous le dépôt) ; 23:57 : `rag.ps1 init-profile` génère le profil par utilisateur (données, stockage Qdrant court, section `runtime`, ports vérifiés libres ; `e864293`) ; 00:11 : C13 corrigé, une base neuve sans collection est prête à importer (`dfb8dbd`, à déployer) ; C14 vérifié par le test existant (manifeste des sources sans dossiers de développement ni Git) ; DIST-04 `build_kit.py` et DIST-03 `install.ps1` écrits et testés unitairement (`c043bf9`, `050c962`), précompilation du bytecode à l'installation ; restent la fabrication d'un kit réel, son installation dans une racine d'essai, l'inventaire SHA-256 du dossier programme avant et après un cycle complet, DIST-05 à DIST-10 ; 02:45 (01/10) : DIST-07 en partie, `THIRD_PARTY_NOTICES.md` généré dans le kit depuis le verrou des artefacts (textes présents, mention de modification du modèle Qwen, manques soumis à P7) ; 03:34 : DIST-05 en partie (`0379d7f`) : verdict de `doctor` par rubrique (vert, orange, rouge) avec message et action, pannes provoquées testées (port occupé, modèle absent, fichier de modèle altéré, binaire altéré) ; `install.ps1` arrête l'installation sur une rubrique rouge, affiche le verdict final et relaie les messages Python sans altération (console UTF-8, défaut reproduit sous page OEM 850) ; reste `selftest` en racine temporaire ; 03:44 : DIST-06 écrit (`611124c`) : quatre raccourcis du menu Démarrer de l'utilisateur (ouvrir = `up` idempotent puis `open`, arrêter, diagnostic, sauvegarder) créés par `install.ps1`, testés hors navigateur ; 03:51 : DIST-08 écrit (`0885b26`) : `uninstall.ps1` (données conservées, jonctions non suivies, autre version préservée) et `install.ps1 -Update` (sauvegarde vérifiée de la version en place, profil repris, bascule des raccourcis) ; DIST-06 et DIST-08 restent à valider sur une installation réelle ; 04:08 : DIST-05 complété (`95fd824`) : `rag.ps1 selftest` (instance temporaire, verrou lourd partagé, import, extraction native, recherche, provenance, réponse citée si admise), exécuté en réel sur ce poste : orange, réponse non admise faute de mémoire ([rapport](reports/selftest-2026-10-01-0402.json)), appelé par `install.ps1` après `up` |

**Règles ajoutées le 30/09 (commits f8fbb1c 09:35 et d4924d9 09:37 UTC) :** référence de forme `D:\enhacements\decodair` (principes UI et format du README, sans métier ni branding) ; section « Documentation et textes de l'interface » dans `CLAUDE.md`/`AGENTS.md` racine, renvoi dans `RAG_Local_Agents/AGENTS.md`, section « Textes de l'interface » du skill `pdf-workspace-web`.

**Points à trancher (décisions utilisateur, non déductibles) :** (1) D08.1 — accepter une coupure réseau physique pendant la recette (mode avion/câble) ou obtenir une règle pare-feu de l'administrateur ; sinon D08.1 reste BLOCKED. (2) Corpus métier : jeu de questions métier annotées sur les PDF autorisés (expert métier) — sinon qualification métier BLOCKED. (3) D07 — si les seuils de latence échouent comme projeté, ils restent FAIL (aucune baisse de seuil sans décision explicite). (4) Index Qdrant de l'instance principale : migrer sa collection, créée avant W017, vers la forme `memory` (recréation par réindexation complète ou mise à jour des paramètres, opération sur l'index de l'utilisateur) ou la laisser sous l'ancienne forme, fonctionnelle en 1.19.1 et acceptée par le contrôle, jusqu'à une prochaine réindexation ou mise à jour de Qdrant (ajouté le 01/10 à 10:51 ; tranché le 01/10 à 12:15 : migrer maintenant, fait à 12:17).

**Ressources 09:27 UTC :** 5690 Mio disponibles, D: ≈ 24,8 Gio libres ; un seul moteur lourd à la fois ; les agents du lot R4 n'exécutent que des tests légers après contrôle mémoire.

Prochaine action : lire le résultat de la question restaurée, puis intégrer R4 (revue, tests, commit), rebuild UI et E2E question/citation sur l'instance principale.

## Point à 13:55 UTC — lot R4 intégré

R4 VERIFIED au niveau unitaire et in-process (voir le tableau). Aucun parcours réel n'est déduit de ces tests. Conséquences à traiter : réindexation nécessaire pour les nouvelles règles d'identifiants (table `identifiers`), empreinte d'extraction modifiée par les changements d'ingestion (le prochain réindex relancera le worker), nouvelle fixture hostile et document de 14 pages disponibles pour R5/R9.

Prochaine action exécutable : arrêter l'instance restaurée (ancien code), build surveillé de l'interface (R5), relancer l'instance restaurée sur le nouveau code pour la question D09.3 (R3), puis instance principale, réindex de DA-P01 et E2E réels (R2/R5). Un seul traitement lourd à la fois.

## Point à 14:10 UTC — génération bloquée par la mémoire hôte

Deux questions réelles sur l'instance restaurée (nouveau code, modèle texte) : 13:58 refus immédiat à 4723 < 4992 Mio ; 14:05 avec W008, état `waiting_for_resources` émis (4932 Mio), refus après 120 s à 4709 Mio ([preuve](reports/backend/2026-09-30-restored-question-w008-20260930T1405.json)). Nos services occupent ≈ 115 Mio après libération des caches ; la pression vient de processus étrangers (navigateur ≈ 1,5 Gio, antivirus, sessions Claude). Admettre la génération sans cette marge ferait tomber l'hôte sous la réserve de 1536 Mio (baisse mesurée 3327 Mio) : aucun seuil n'est abaissé.

**BLOCKED — décision utilisateur :** libérer ≈ 0,5 Gio pendant les créneaux de génération (fermer le navigateur Edge hors de la recette ou d'autres applications), ou laisser D05/D07 génération et la question D09.3 bloquées sur ce poste. Travaux indépendants poursuivis : E2E sans génération (R5), OCR réel (R6), interface decodair (R16), documentation (R14).

## Point à 16:40 UTC — D08.3 corrigé, arrêt console rétabli

- W009 publié (`4c172dd`). Workflow interface (R15/R16) et documentation (R14) toujours en cours, fichiers disjoints de ce lot.
- D08.3 : clé d'API Qdrant tirée à chaque démarrage (W010), transmise au seul enfant Qdrant, lue par l'API et les outils de l'instance ; restauration avec sa propre clé. Contrôle réel 15/15, test d'intégration sur le binaire verrouillé, sauvegarde puis restauration (11 points).
- Défaut trouvé pendant ces essais : un lanceur qui ignore CTRL+C (terminal d'outil) transmet cet attribut aux enfants (WIN09) ; Qdrant et Ollama étaient alors terminés par le Job après 30 s au lieu d'un arrêt console. [Avant](reports/runtime-down-before-ctrlc-fix-20260930T1636.json) : `forced_job_close_after_stop_timeout` ; [après correction](reports/runtime-down-after-ctrlc-fix-20260930T1637.json) : `console_sigint`, code 0. Test d'intégration qui échoue sans la correction.
- Restauration : un premier essai a échoué sur une erreur d'E/S Windows transitoire dans Qdrant (os error 145, répertoire temporaire encore tenu) ; le second a réussi. Reprise bornée (3 essais, collection absente seulement) ajoutée et testée ; échec et reprise manuelle conservés ([rapports](reports/runtime-restore-transient-20260930/)) ; la racine `.runtime/rt-qkey-20260930T162754Z` et le stockage `.runtime/q/feeaad73` de l'essai échoué restent en place.
- Dette relevée : `ruff check services/` signale 18 constats préexistants dans `services/api` (imports non triés, alias `datetime.UTC`, `B008` sur `File`) ; aucun nouveau constat dans les fichiers modifiés. À traiter dans un lot dédié.

Prochaine action exécutable : intégrer les livrables du workflow (tests unitaires web, typecheck, build surveillé, E2E en lecture seule, captures), puis R7 (import DA-P02..07 et réindex DA-P01) sur l'instance principale. Génération toujours BLOCKED (décision utilisateur du point 14:10).

## Point à 17:13 UTC — nouvelles demandes intégrées (R17–R20)

- Demandes reçues entre 16:38 et 17:05 UTC : règles de documentation renouvelées (déjà en place, précisées) ; sécurité applicative sur le modèle de decodair (R17) ; lancement de la plateforme (fait à 16:43, instance `0c0cd4d9…`) ; utilisation du corpus réel `PDF/` pour l'usage, les tests et l'évaluation (R19) ; contrôles absolument verts (R18) ; recette UX avec captures (R20).
- Contrainte retenue pour R19 : le corpus est privé ; aucun texte de document n'est affiché dans les sorties d'outils ni envoyé hors du poste. Les jeux d'évaluation dérivés du corpus restent sous `.runtime/` (hors Git) ; seuls les rapports agrégés sont versionnés. Les questions sans annotation d'un expert métier seront déclarées comme telles.
- Contrainte d'ordonnancement : l'empreinte d'extraction inclut les sources `services/ingestion/*.py` ; toute modification de ces fichiers pendant l'extraction du corpus change l'empreinte des documents suivants. Les corrections de typage de l'ingestion sont faites au début de l'extraction ; les documents déjà extraits seront réindexés.
- R18 : `ruff check .` PASS après correction des 79 constats (fixtures réexportées, instructions séparées, `Annotated` pour l'import, variable de boucle renommée) ; reproductibilité des fixtures PASS (37 fichiers identiques) ; 340 tests unitaires PASS (échec intermédiaire du registre des skills dû au hash périmé du skill modifié, corrigé puis rejoué 19/19).

Prochaine action exécutable : typage mypy au vert (services puis outils), backend de R17, intégration du workflow interface puis R20 ; extraction du corpus surveillée en continu.

## Point à 18:31 UTC — intégration R14–R18 vérifiée et déployée

- R14 : espace documentaire livré par le workflow, revue indépendante OK (`docs/`, `README.md`, `CHANGELOG.md`, `tools/docs/`, 36 tests). Mise à jour pour W011 (session, commande `open`) à faire.
- R15/R16 : charte, composants, coquille et textes livrés ; revue indépendante : 5 constats (dont le lecteur tombé dans une piste de 0 px), tous corrigés avec reproduction. Build surveillé PASS (269 s, mémoire disponible minimale 2 937 Mio), E2E lecture seule 8/8 sur le nouveau build. Recette visuelle avec captures (R20) à faire.
- R17 : session W011 déployée (instance `dce352e1…`) : refus sans session 401, lien à usage unique, `rag.ps1 open` ouvre l'atelier de l'utilisateur, gardes réels [19/19](reports/http-guards-live-20260930T1829.json), HTTPS de production vérifié sur un vrai serveur TLS (certificat de test), E2E de session 3/3.
- Défaut corrigé pendant le déploiement : un arrêt propre de l'API passait le job d'extraction actif à `cancelled` au lieu de le mettre en pause (`JobSupervisor.cancelled()` incluait la fermeture) ; reproduit par un test, corrigé, redéployé ; le job du corpus annulé à 18:25 a été relancé.
- R18 : `ruff check .` PASS, `mypy` PASS (68 fichiers), 417 tests Python PASS (unitaires et intégration, dont TLS réel), 120 tests web PASS, `tsc` PASS, build PASS, E2E lecture seule 8/8. Restent hors de cette série : les E2E d'import, de cycle de vie et de génération, qui exigent une instance isolée.
- R19 : 3 des 4 documents du corpus prêts (partiels), CPR-07A relancé ; anomalie OCR « essais MIGBT » pages 11–14 à reproduire.
- R21 : dossier de sources de la méthode d'évaluation livré (`reports/evaluation-methodology-sources-2026-09-30.md`, 31 sources lues) ; protocole à consigner puis à exécuter.
- R22 : analyse de distribution livrée (`reports/distribution-analysis-2026-09-30.md`) ; DIST-01 couvert par R17 ; contrainte sans droits administrateur inscrite dans les chartes.

Prochaine action exécutable : commit et push de cette intégration ; mise à jour de la documentation stabilisée pour W011 ; recette visuelle R20 sur le corpus réel ; puis R21 et R22 (étapes DIST-02 et suivantes).

## Point à 20:17 UTC — recette visuelle R20, W012 et écarts de la documentation

- R20 : trois séries de captures (18:49, 19:58, 20:15) ; corrections vérifiées au rendu et par les tests. Défauts de fond trouvés grâce au corpus réel : états de document non réalignés sur le job (pause, annulation, partiel à publier), traitement remplacé encore présenté comme décision, limites d'extraction affichées par code brut.
- W012 (arbitrage de l'utilisateur) : publication automatique quand seules des figures ne sont pas interprétées ; vérifiée en réel sur « Evaluation module4 » (réextrait 19:52, publié, prêt). Les 3 autres documents gardent une perte de texte réelle.
- Écarts relevés par l'agent de documentation, corrigés : jeton écrit avant validation de l'origine et clé TLS non vérifiée avant lancement, lien dans un rapport, refus sans en-têtes de sécurité, inactivité jamais atteinte (relectures périodiques, lecteur compris), motif d'expiration perdu, priorité affichée d'après le mode instantané, reprise groupée pouvant s'arrêter à mi-course. Restent documentés : outils de qualification en HTTP de développement, `app_url` = origine, `rag.ps1` sans `--no-browser`.
- Contrôles : 439 tests Python PASS (dont HTTPS réel), 130 tests web, `tsc`, `ruff`, `mypy` PASS, build PASS, E2E lecture seule 12/12, contrôles documentaires PASS, `verify_pack` PASS.
- R19 : constats d'extraction à traiter : pages non converties par Docling (MIGBT p. 11–14, MR2_30A 3 pages ; le résumé d'erreur Docling est désormais conservé pour les prochaines extractions), orientation OCR non déterminée (CPR-07A, 4 zones).

Prochaine action exécutable : commit et push ; puis R19 (reproduire les échecs de conversion avec le résumé d'erreur), R21 (protocole d'évaluation à consigner puis exécuter sur le corpus réel), R22 (DIST-02 et suivantes, sans droits administrateur).
## Point à 22:10 UTC — R19 correctifs d'extraction, R21 séries 1 et 2

- R19 : deux défauts trouvés sur le corpus réel et corrigés avec tests de reproduction : découpes OCR et de tableaux hors de la page (« Crop exceeds page dimensions » de pypdfium2, MIGBT p. 11–14 ; après correction 14/14 pages converties) ; résultat de worker d'une exécution précédente relisible après une pause (lien avec l'échec de 20:40 non prouvé). Le worker arrêté sans résultat donne son code de sortie ; les exceptions inattendues sont journalisées avec leur pile. MR2_30A garde 3 pages non converties de son ancienne extraction : réindexation à faire.
- R21 : protocole W013 appliqué (`tools/qualification/corpus_eval.py`) ; série 2 : Success@10 157/160 [0,946 ; 0,994], contexte 150/160 [0,889 ; 0,966], abstention de recherche 20/20, aucune fuite ; pertes : 3 échecs de recherche, 6 blocs classés 7e à 10e, 1 coupé par le budget de preuve ([rapport](reports/evaluation/corpus-reel-2026-09-30.md)). Porter la liste finale à 8 fragments est exclu par la spécification ; l'amélioration à vérifier porte sur le classement d'une branche pour les requêtes courtes (EV-1).
- Contrôles : `ruff` et `mypy` (69 fichiers) PASS ; suite Python entière 477/480, les 3 échecs analysés (un test dépendant de l'emplacement du dossier temporaire, corrigé ; deux diagnostics du défaut tiers W-PDF01, déclarés `xfail` non stricts) et rejoués ([junit de la reprise](reports/backend/2026-09-30-r19-r21-rerun.xml)). Interface non modifiée depuis `6935e13`.

Prochaine action exécutable : commit et push ; documentation stabilisée (worker, découpes bornées, outil d'évaluation) référencée sur ce commit ; puis EV-1 (rang par branche des 10 pertes, sans texte), réindexation de MR2_30A, R22 (DIST-02 et suivantes, sans droits administrateur).
## Point à 22:40 UTC — diagnostic R21 et écart de découpage

- Constat (incohérence, prouvée) : le découpage `codepoint-block-v1` produit un chunk par bloc (MR2_30A : 547 chunks pour 546 parents, 31 tokens E5 en moyenne ; MIGBT : 13) alors que la spécification demande une cible de 320 tokens aux frontières structurelles ([SPEC_ARCHITECTURE.md](SPEC_ARCHITECTURE.md), découpage ; code : `services/api/indexing.py:119-131`). Impact mesuré : la branche lexicale manque 9 des 10 blocs perdus de la série 2. Correction envisagée (EV-1) : regrouper les blocs consécutifs d'une même section jusqu'à 320 tokens, sources multiples par chunk, nouvelle révision de chunker, réindexation, puis séries 2 et 3 rejouées en apparié.
- Essai non adopté : retrait des mots-outils de la requête FTS5 (5 gagnées / 1 perdue, p = 0,22).
- Outil : `corpus_eval.py build --seed --exclude-dataset` pour des séries de confirmation indépendantes (test unitaire ajouté).

Prochaine action exécutable : commit et push ; puis EV-1 (regroupement des blocs par section) après lecture des contrats de citation et de périmètre concernés ; en parallèle possible : rapport de recette R20, R22 DIST-02.
## Point à 23:35 UTC — jeu de référence W014 et perte silencieuse de la voie structured

- W014 (demande utilisateur vers 22:44) : 85 questions établies par lecture intégrale des 4 documents (72 avec réponse), sous `.runtime/evals/annotated-v1/`, non validées par un expert ; outil `annotated_eval.py`. Mesure A (23:09) : page dans le contexte 59/72 sur le document, 47/72 sur toute la bibliothèque ; tableaux et pages images faibles ([rapport](reports/evaluation/corpus-reel-2026-09-30.md)).
- Bug prouvé (R19) : la voie `structured` perdait jusqu'à 99 % du texte de certaines pages sans rien déclarer (6 pages sur 79 dans CPR-07A et MR2_30A) ; corrigé : contrôle de couverture de la couche texte, reprise de la page en voie `native`, sinon perte déclarée ; tests unitaires, 12 tests d'intégration réels de l'ingestion PASS ([junit](reports/backend/2026-09-30-structured-fallback-ingestion.xml)). Réindexation des documents à faire pour l'effet réel.
- R20 : rapport de recette livré ; DIST-02 : première étape livrée (`050f2c2`).
- EV-1 (`section-pack-v1`) : implémenté et testé, non commité ; mesure prévue en deux temps pour séparer les effets : B = réextraction avec les correctifs d'extraction et l'ancien découpage (sans redémarrer l'API), puis C = nouveau découpage après redémarrage, sur le jeu W014 et les séries 2 et 3.

Prochaine action exécutable : build de l'interface (libellés des nouveaux codes), réindexation des 4 documents (B), mesure, puis redémarrage avec `section-pack-v1`, réindexation (C) et mesure.
## Point à 00:58 UTC (1er octobre) — mesures B et C, découpage W015 adopté

- B (réextraction des 4 documents avec les correctifs de découpe OCR et de la voie `structured`, 23:37–00:38) : plus aucune page non convertie sur MR2_30A ; reprise par la voie native sur CPR-07A p. 5, 8, 9 et MR2_30A p. 7, 8, 9 ; les 3 questions dont la preuve était sur les pages perdues sont retrouvées. Mémoire libre minimale pendant la réextraction : 2 127 Mio.
- C (redémarrage à 00:47 avec `section-pack-v1`, réindexation depuis l'extraction en cache en moins de 2 min) : bloc attendu dans le contexte 46 → 53 sur 68 (document) et 37 → 41 (bibliothèque) ; page sur la bibliothèque 51 → 48, perte concentrée sur le document italien. Décision W015 : découpage adopté, conforme à la cible de la spécification ; perte suivie.
- Le nouveau code de l'API est déployé (disponibilité sur base neuve, emplacements `runtime`, découpage) : instance `6346e31c…`, disponibilité `ready`, collection `present`.

Prochaine action exécutable : EV-3, génération réelle sur 22 questions du jeu W014 (16 avec réponse, 6 sans) dans le créneau de nuit, contrôles automatiques puis relecture de chaque réponse ; documentation stabilisée du découpage ; R22 suite (DIST-03).
## Point à 01:29 UTC (1er octobre) — EV-3 interrompu faute de mémoire

- EV-3 lancé à 00:58 sur 22 questions du jeu W014 : 2 réponses obtenues sur 9 tentatives, 3 générations annulées par le gouverneur (réserve hôte), 3 admissions refusées, puis arrêt du lanceur par Claude Code (mémoire du poste critique) à 01:24. Relecture : une réponse juste et complète, une abstention injustifiée ; les deux tronquées par la limite de sortie ([rapport](reports/evaluation/corpus-reel-2026-09-30.md)).
- Proposition EV-5 (non appliquée) : consigne système orientée « réponse d'abord, limites en une phrase », à mesurer sur le même échantillon.
- Blocage (décision utilisateur, déjà au point de 14:10) : la génération exige environ 5 Gio libres pendant toute la série ; avec le navigateur, trois sessions Claude et deux antivirus actifs, ce poste ne les garde pas. EV-3 n'est relancé qu'à la demande de l'utilisateur, après libération de mémoire.

Prochaine action exécutable sans génération : fabrication d'un kit réel et installation dans une racine d'essai (DIST-03 à DIST-05), à lancer quand la mémoire libre le permet (copies lourdes, pas de modèle chargé).
## Point de reprise à 02:34 UTC (1er octobre) — travaux lourds suspendus faute de mémoire

État réel : instance principale `6346e31c…` disponible sur le code `dad60f5` pour l'interface et le runtime (découpage `section-pack-v1`, reprise de la voie `structured`, disponibilité sur base neuve) ; 4 documents publiés, 61 en pause. Derniers contrôles : 428 tests unitaires Python, 12 tests d'intégration réels de l'ingestion, `test_api_http` 29/29, 131 tests web, `tsc`, `ruff`, `mypy`, `check_docs`, `verify_pack` PASS.

Suspendus par l'arrêt automatique de Claude Code (mémoire critique, dont 2,2 Gio pris par un autre projet du poste), à relancer seulement à la demande de l'utilisateur :
1. EV-3 : `annotated_eval.py answer` sur le jeu `.runtime/evals/annotated-v1/runs/20261001T004923Z/dataset.json` (reprise automatique des questions en erreur), avec au moins 5 Gio libres pendant toute la série.
2. Kit : `tools/dist/build_kit.py build --output <dossier neuf>` (environ 30 min sous antivirus) ; supprimer d'abord le kit partiel `%TEMP%\apdfk2`.
3. Installation d'essai : `tools\dist\install.ps1 -Destination %TEMP%\apdfp -DataRoot %TEMP%\apdft -Ports 18785,16333,21434 -NoStart`, puis inventaire du dossier programme (`program_inventory.py snapshot`), cycle `up` → import → recherche → `backup` → `down`, second inventaire et comparaison (validation DIST-02).

Décisions attendues de l'utilisateur : P1 à P10 de l'analyse de distribution (notamment P2 modèle source, P3 bibliothèques GPU, P5 noms des dossiers), D08.1 (coupure réseau pendant la recette), seuils D07, feu vert pour les 61 documents en pause, validation du jeu W014 par un expert.
## Point à 03:13 UTC (1er octobre) — recette de l'interface, second passage

Réalisé depuis le point de reprise : DIST-07 (avis de tiers générés dans le kit, `dc74b2a`, 02:45) ; R20, points ouverts B, C et E examinés, deux défauts corrigés et vérifiés (`49a2a1a`, 03:09) : bordure des champs à 3:1 (WCAG 2.2, 1.4.11) et légende de page « Lecture de la page… » tant que le texte n'est pas lu. Contrôles : 133 tests unitaires web, `tsc`, build, E2E en lecture seule 11 réussis et 20 non autorisés, recette visuelle 4/4, captures relues ([rapport](reports/ui-recette-2026-09-30.md#second-passage--1er-octobre-2026)).

Restent ouverts pour R20 : A (sur-titres, choix de présentation) et D (contrôle axe, passage au lecteur d'écran). Les travaux lourds suspendus (EV-3, kit, installation d'essai) restent soumis à l'accord de l'utilisateur, ainsi que les décisions listées au point de 02:34.

Prochaine action exécutable sans travail lourd : point D, partie automatique (contrôle d'accessibilité dans les E2E en lecture seule) si une bibliothèque d'audit est déjà disponible localement ; sinon, à proposer.
## Point à 03:36 UTC (1er octobre) — DIST-05, verdict de doctor

Réalisé : verdict par rubrique en tête de `doctor` (`0379d7f`, 03:34) : programme, modèle, profil, ports, services, mémoire ; base neuve démarrée annoncée « index vide, prêt à importer » (C13). `install.ps1` refuse de démarrer sur une rubrique rouge, joint le verdict avant et après `up` au rapport, et fixe `PYTHONUTF8` et la console en UTF-8 le temps de l'installation. Contrôles : 9 tests du verdict avec pannes provoquées, essai de bout en bout d'`install.ps1` sur un kit factice altéré (échec avec l'ancien script, succès avec le nouveau), 451 tests unitaires Python, `ruff`, `mypy`, `doctor` réel : verdict vert. Documentation d'exploitation, de dépannage et d'architecture référencée sur `0379d7f`.

Reste pour DIST-05 : `selftest` réel en racine et ports temporaires (import d'un PDF synthétique, extraction, recherche, citation, génération si admise) ; il démarre une seconde instance (Qdrant, Ollama, API) et relève donc des travaux lourds soumis à la mémoire disponible. R20 point D (audit automatique) : aucune bibliothèque d'audit n'est installée localement ; l'ajout de `@axe-core/playwright` (téléchargement depuis le registre npm) est proposé, non réalisé.
## Point à 03:52 UTC (1er octobre) — DIST-06 et DIST-08 écrits, validation réelle en attente

Réalisé : raccourcis du menu Démarrer (`611124c`), désinstallation et mise à jour côte à côte (`0885b26`), avec des essais sur faux programmes et kit factice (doublures de `rag.ps1` nommées comme telles) : 24 tests de distribution, `ruff`. Aucun de ces essais ne remplace le critère de validation : clic sur « Atelier documentaire » puis second clic sans second `up` sur une installation réelle (DIST-06) ; mise à jour sur données peuplées avec ouverture d'une ancienne citation, puis désinstallation avec inventaire des données inchangé (DIST-08).

Ces validations, comme l'installation d'essai, demandent un kit réel (environ 30 min de fabrication sous antivirus) puis une instance supplémentaire : travaux lourds suspendus depuis 02:32 et soumis à l'accord de l'utilisateur. Mémoire relevée à 03:40 : 5 411 Mio libres.
## Point à 04:09 UTC (1er octobre) — contrôle réel `selftest`

Réalisé : `rag.ps1 selftest` (`95fd824`). Deux exécutions réelles sur ce poste, l'instance principale restant disponible : 03:59, orange, 98 s, avec deux défauts (racine temporaire non supprimée, Qdrant tenant encore un fichier ; séparateur du message de mémoire) ; 04:02, après correction, orange, 71 s, toutes les étapes `PASS` sauf la réponse, non admise (4 821 Mio disponibles, 4 992 requis), racine supprimée. 460 tests unitaires Python, `ruff`, `mypy`. Documentation d'exploitation, de dépannage et d'architecture référencée sur `95fd824`.

Limites : la voie OCR n'est pas exercée par le contrôle ; la réponse citée ne l'a pas été faute de mémoire. Prochaine action sans travail lourd supplémentaire : aucune sur DIST-05 ; les validations DIST-02, 06 et 08 attendent le kit réel.
## Point à 04:18 UTC (1er octobre) — R11, migration qualifiée sur sauvegarde

Réalisé : `tools/qualification/migration_check.py` (`77cc185`) et essai réel sur la sauvegarde du 30/09 à 03:11 (schéma 2) : PASS en 162 s, instance principale non touchée, cible et stockage court retirés. Critère D09.4 coché dans `DEFINITION_OF_DONE.md` avec sa preuve ; retour arrière d'une migration documenté dans `SAUVEGARDE-RESTAURATION.md` §6. D09.3 reste ouvert (ancienne citation PASS, question après restauration non aboutie) ; D09.5 attend l'inventaire du kit réel.
## Point à 05:02 UTC (1er octobre) — R2 vérifié, prompt et affichage des réponses corrigés

Réalisé : première réponse réelle par l'API puis dans l'interface (R2), avec clic sur la citation enregistrée ; deux défauts relevés sur ces réponses et corrigés : la consigne « données non fiables » revenait à l'utilisateur comme jugement sur sa source (`986d846`), et le Markdown du modèle s'affichait brut (`0c7fd84`). Résistance à une instruction hostile remesurée après la reformulation : PASS (`df80786`). Contrôles : 462 tests unitaires Python, 136 tests web, `tsc`, build, E2E lecture seule et génération 12 réussis, captures relues. Le mode « Priorité aux questions » basculé par le scénario de génération est rétabli après chaque essai ; les 61 traitements en pause n'ont pas bougé.

Restent : D09.3 (question sur une instance restaurée), R3, R7, R8, R10, R13 ; validations DIST-02, 06 et 08 sur un kit réel ; EV-3 ; décisions utilisateur listées au point de 02:34.
## Point à 05:29 UTC (1er octobre) — D09.3 validé, défaut latent des chemins de restauration corrigé

Réalisé : D09.3 (question et ancienne citation après restauration) PASS sur une sauvegarde au format courant (`bf71f14`) ; critère coché. En chemin, défaut latent de la distribution trouvé et corrigé (`33e8cee`) : pour un profil généré, les stockages de restauration dépassaient la borne de Qdrant dès 39 caractères de racine des données ; ils sont désormais voisins du stockage court, et `init-profile` comme `install.ps1` refusent un chemin trop long avant toute copie. La sauvegarde du 30/09 à 03:11 reste non admissible à la génération sur ce poste (profil de l'époque, 5 888 Mio requis), ce qui est documenté. Pour chaque essai de génération en instance temporaire, l'instance principale a été arrêtée puis redémarrée (inactive, `readiness` 200 ensuite).

Contrôles : 464 tests unitaires Python, `ruff`, `mypy` ; essais réels conservés.
## Point à 05:52 UTC (1er octobre) — E2E d'import sur instance isolée

Réalisé : outil `tools/qualification/e2e_instance.py` (`8186162`) ; scénarios Playwright d'import joués pour la première fois sur une cible isolée réelle : géométrie 4/4, balisage hostile, budget de canvas, import, recherche, navigation et sélections 5/5 ; instance arrêtée et racine supprimée, instance principale intacte. Critères D06.3, D06.4, D06.8 et D06.11 cochés avec leurs preuves (`DEFINITION_OF_DONE.md`). Preuves E2E du jour corrigées : la cible était inscrite en dur (`87a8aef`).

Restent pour R5 : build surveillé et rejeu complet sur le build de livraison ; pour D06 : 2, 5, 6, 7, 9, 10.
## Point à 07:09 UTC (1er octobre) — qualification par instances isolées

Réalisé depuis 05:30 : D01.3, D01.4, D01.5, D02.1, D02.2, D02.8, D03.1 à D03.4, D06.3, D06.4, D06.8, D06.11 et D08.6 cochés avec leurs preuves (`DEFINITION_OF_DONE.md`) ; outils `e2e_instance.py`, `library_check.py`, diagnostic `index_consistency` (`e4c7caf`) ; défaut OCR des pages scannées corrigé (W016, `f1d91df`) ; R7 partie recherche : 94/100 questions DEV résolues, rappel et couverture du contexte 83/83, 0 fuite de périmètre (`a604a76`). Instance principale redémarrée à 06:50 sur le profil W016, `doctor` vert (7 rubriques).

Restent, par ordre de dépendance : génération des réponses DEV et grille D05 (R7, plusieurs heures, instance principale arrêtée pendant l'essai) ; D04 et D05 sur le jeu final (R13, une seule exécution) ; performance D07 (R8) ; cycle de vie E2E (`lifecycle.spec.ts`) ; fautes injectées D03.5 et D03.6 ; validations de distribution sur kit réel et EV-3, suspendues à l'accord de l'utilisateur ; décisions listées au point de 02:34.
## Point à 07:35 UTC (1er octobre) — fautes injectées

Réalisé : `tools/qualification/fault_check.py` (`f9c48da`) ; arrêts forcés pendant l'extraction et les embeddings, puis reprise sans doublon ni génération fantôme ; panne de Qdrant pendant un import sans document présenté comme prêt, puis reprise. D03.6 coché ; D03.5 reste ouvert (écriture des points et publication non visées par un arrêt forcé réel, l'étape étant trop brève pour le sondage). Chaque essai sur instance isolée, racines supprimées, instance principale intacte.
Complément (01/10, J6) : D03.5 a été coché à 07:40 (`389a3c0`) après l'essai de 07:35–07:40 : arrêt forcé pendant l'écriture des points sur un document de 200 pages (1 800 fragments, 1 800 points, une seule génération publiée) ; la publication, tenue en une seule transaction SQLite, n'a pas été visée par un arrêt réel ([DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md), D03 ; journal du 01/10, 07:35–07:40). « D03.5 reste ouvert » décrit l'état d'avant cet essai.
## Point à 09:08 UTC (1er octobre) — recherche et périmètre (D04)

Réalisé : D04.2 à D04.6 et D04.8 cochés avec leurs preuves (`DEFINITION_OF_DONE.md`). Test unitaire des filtres avant la coupe top-k sur quatre périmètres, essai réel `tools/qualification/scope_check.py` sur instance isolée (Qdrant et E5 réels, sélection courte mesurée par le compteur natif de Qdrant), contre-exemple RRF suivi jusqu'au contexte ; deux tests rendus discriminants après vérification par mutation. Deux erreurs `mypy` déjà committées (`fault_check.py`, `migration_check.py`) corrigées. Contrôles : suite Python complète 538 réussis et 2 `xfail` connus (W-PDF01), 906 s ; `ruff` et `mypy` au vert.

Restent pour D04 : D04.7 (réponses générées, R7 puis R13) et les objectifs de qualité sur le jeu final (R13). Prochaine action exécutable sans accord supplémentaire : critères D05, D06 et D08 démontrables par instances isolées, la génération DEV (R7) demandant l'arrêt de l'instance principale.
## Point à 09:25 UTC (1er octobre) — extraction D02 : essai interrompu

Réalisé : `tools/qualification/extraction_check.py` écrit (vérité terrain du générateur pour les sept documents DEV, le scan bilingue et la frontière pages 4/5 ; schéma raster sans texte produit sur place ; jeu final ni importé ni lu) ; reprise bornée d'un import refusé par l'admission mémoire mise en commun (`wait_admitted`, `fault_check.py`) ; test d'intégration de la publication partielle prolongé jusqu'aux événements d'une question (avertissement `partial_extraction` émis avant la fin de la réponse), PASS.

Blocage : premier essai lancé à 09:18 sur instance isolée, arrêté vers 09:21 par Claude Code faute de mémoire sur le poste (campagne Playwright d'un autre projet en cours, laissée intacte) ; aucun résultat. Instance isolée arrêtée à 09:22, racine supprimée, aucun processus survivant, instance principale intacte. L'essai n'est pas relancé sans l'accord de l'utilisateur. D02.3 à D02.7, D02.9 et D02.10 restent ouverts.

Prochaine action : sur accord, rejouer `extraction_check.py` sur instance isolée quand la mémoire libre le permet ; sinon, poursuivre les travaux sans traitement lourd.
## Point à 09:39 UTC (1er octobre) — D06.10

Réalisé : D06.10 coché (`DEFINITION_OF_DONE.md`) : deux gardes statiques ajoutées à `ui-guards.test.ts` (aucun bouton sans action, aucune donnée simulée ni adresse étrangère dans les sources livrées) ; 138 tests unitaires web et `tsc --noEmit` au vert. D03.7 examiné : purge signalée `source_removed` et message affiché tel quel ; l'ouverture d'une ancienne citation après une nouvelle version n'a de preuve qu'en test d'intégration (modèle simulé pour produire la citation) : reste ouvert jusqu'à un essai réel avec génération.

Toujours en attente de l'accord de l'utilisateur : rejeu de `extraction_check.py` (D02), puis essais avec génération (R7, D03.7, D05) qui demandent l'arrêt de l'instance principale. Mémoire libre du poste observée entre 2,6 et 5,4 Gio depuis 08:30 (campagne Playwright d'un autre projet).
## Point à 09:46 UTC (1er octobre) — D08.3

Réalisé : D08.3 coché (`DEFINITION_OF_DONE.md`) : `tools/qualification/http_guards_check.py` rend rejouable le contrôle des gardes HTTP du 30/09, qui n'avait pas d'outil versionné, et y ajoute le préflight CORS et le relevé des sockets en écoute ; 18/18 sur l'instance principale, écoute sur 127.0.0.1 seulement ([rapport](reports/http-guards-live-20261001T0943.json)). Correction : le point précédent portait « 09:55 », heure en avance sur l'horloge ; le commit `fcce2b0` date de 09:40.

Restent ouverts en D08 : D08.1 (blocage réseau du système, décision utilisateur), D08.2, D08.4, D08.5 (exfiltration et élargissement de périmètre), D08.7.
## Point à 09:52 UTC (1er octobre) — D08.7

Réalisé : D08.7 coché (`DEFINITION_OF_DONE.md`) : `tools/qualification/log_privacy_check.py` cherche dans les 120 journaux de l'instance principale le texte réellement extrait, les questions et les réponses enregistrées : aucune occurrence, détecteur validé par un témoin positif sur les checkpoints ; exclusions Git vérifiées ([rapport](reports/log-privacy-20261001T0949.json)). Le commit `6e1f9be` (D08.3) n'a pas pu être poussé (connexion TLS vers GitHub interrompue, deux essais à 09:46) : il reste local avec celui-ci jusqu'au retour du réseau.

Restent ouverts en D08 : D08.1 (décision utilisateur), D08.2, D08.4, D08.5.
## Point à 09:58 UTC (1er octobre) — skills relus, constat d'interface

Skills relus par chemin et travaux du jour confrontés à leurs invariants ([relevé](reports/skills-usage-2026-10-01.json)) : `rag-retrieval-evaluation`, `hybrid-rag-api`, `rag-qualification-fixtures`, `rag-pdf-provenance`, `pdf-ingestion-windows`, `pdf-workspace-web`. Aucun écart pour la recherche, les fixtures et l'ingestion.

Constat C-UI-01 (infirmé à 09:59, voir le point suivant ; texte d'origine conservé) : dans `apps/web/src/components/scope-control.tsx`, « Appliquer » est désactivé pour un périmètre page ou section tant que la citation ouverte n'est pas vérifiée, mais la raison (`binding.actions.reason`) n'est affichée que dans `apply`, inatteignable quand le bouton est désactivé : l'utilisateur ne voit pas pourquoi. Même invariant du skill `pdf-workspace-web` (« les contrôles désactivés indiquent pourquoi ») non tenu, sans défaut fonctionnel, pour : envoi de la question (`analysis-panel.tsx`), annulation en cours, retrait d'un document (`document-tools.tsx`), page précédente et suivante, limites de zoom 50 % et 300 % (`pdf-viewer.tsx`). Correction prévue : raison affichée sous le sélecteur et dans `title`/`aria-describedby` ; garde statique « tout `disabled` porte une explication » dans `ui-guards.test.ts`. Validation : tests unitaires, typecheck, build et E2E rejoués, rendu examiné. Non réalisée à ce stade : le build et les E2E attendent une mémoire libre suffisante (2,6 à 5,4 Gio observés).

Push : `6e1f9be` et `52801b3` toujours locaux (quatre essais entre 09:46 et 09:55, github.com injoignable ; api.github.com joignable).
## Point à 10:00 UTC (1er octobre) — C-UI-01 infirmé

Relecture complète de `scope-control.tsx` avant correction : la raison est déjà affichée dans la fenêtre du périmètre (`binding.actions.reason` rendu en `role="status"` sous le sélecteur) et les options page et section sont elles-mêmes désactivées ; le constat reposait sur la seule lecture de `apply`. Les autres contrôles désactivés montrent leur état à côté d'eux : compteur « N / total » des pages, pourcentage de zoom, « Retrait en cours… » dans la confirmation, avertissement de comparaison. C-UI-01 est classé infirmé ; reste une amélioration facultative (raison en info-bulle sur ces boutons), sans priorité, à reconsidérer avec la relecture des textes de l'interface (R15).
## Point à 10:04 UTC (1er octobre) — D06.2

Réalisé : D06.2 coché sur preuves existantes, après vérification que les sources de l'interface n'ont changé depuis les parcours que pour le rendu du texte des réponses (`0c7fd84`, 05:01, antérieur au parcours isolé de 05:42). Aucun nouvel essai lancé. Restent en D06 : 5, 6, 7, 9 (ancres de région sur le corpus contrôlé, sélection OCR, offsets, réponse progressive et reconnexion SSE), qui demandent extraction ou génération.
## Point à 10:20 UTC (1er octobre) — D06.7

Réalisé : D06.7 coché (`DEFINITION_OF_DONE.md`) : nouveau scénario Playwright `unicode-selection.spec.ts`, joué sur une instance isolée (aucun OCR ni génération) : aller-retour exact en points de code pour hors BMP, accent combinant, ligature et césure, refus explicite d'une sélection ambiguë ([rapport](../apps/web/reports/e2e-2026-10-01-unicode-selection-evidence.json)). Limite consignée : la ligature U+FB01 est développée en « fi » par l'extraction comme par PDF.js. Instance arrêtée, racine supprimée.

Restent en D06 : 5, 6 et 9 (ancres de région sur le corpus contrôlé, sélection sur régions OCR, réponse progressive et reconnexion SSE), qui demandent extraction OCR ou génération.
## Point à 10:32 UTC (1er octobre) — D08.4

Réalisé : D08.4 coché (`DEFINITION_OF_DONE.md`). Test d'intégration à jonction Windows réelle (`test_api_http.py`), vérifié par mutation (sans résolution du chemin, l'original extérieur est servi et le test échoue) ; `http_guards_check.py` étendu à huit traversées encodées, 26/26 sur l'instance principale ([rapport](reports/http-guards-live-20261001T1030.json)) ; tests HTTP et de stockage 57/57.

Restent ouverts en D08 : D08.1 (décision utilisateur), D08.2 (observation réseau pendant le scénario complet, génération comprise), D08.5 (exfiltration et élargissement de périmètre, génération).
## Point à 10:50 UTC (1er octobre) — D10.3, W017

Constat (incohérence, prouvé par le schéma officiel) : la collection Qdrant était créée avec `on_disk` et `on_disk_payload`, dépréciés en 1.19.1, contrairement à `CONFIGURATION.md` §6. Corrigé (W017) : placement par `memory`, contrôle effectif `placement_matches` acceptant les deux formes, test unitaire, collection de sondage et autocontrôle sur instance isolée ([rapport](reports/qdrant-memory-2026-10-01.json)). D10.3 coché. La collection existante de l'instance principale garde l'ancienne forme : sa migration est une décision à prendre (Points à trancher).

Push : toujours bloqué (github.com injoignable) ; commits locaux depuis `6e1f9be`.
## Point à 10:53 UTC (1er octobre) — D10.4

Réalisé : D10.4 coché : `verify_pack.py` 11/11 et `build_brief.py --check` PASS au commit `449504f`, rejoués après chaque modification de documentation canonique du jour. Le statut FAIL du 30/09 à 09:30 n'avait pas de motif consigné ; il est remplacé par cette preuve. D10.1, D10.2 et D10.5 restent ouverts (contrôles précoces Q-PDF et Q-CPU, essai d'embedding, rapport final).
## Point à 12:20 UTC (1er octobre) — décisions de l'utilisateur, migration Qdrant, instance principale arrêtée

Décisions de l'utilisateur reçues vers 12:15 : (a) relancer `extraction_check.py` sur instance isolée dès que la mémoire libre dépasse environ 5 Gio ; (b) arrêter l'instance principale pour les essais avec génération (R7, D03.7 à D03.9, D04.7, D05, D06.9, D07, D08.2, D08.5, D10.1, D10.2) ; (c) migrer maintenant la collection Qdrant principale (point à trancher 4).

Réalisé : (c) migration en place à 12:17, PASS ([rapport](reports/qdrant-memory-migration-main-2026-10-01.json)). Instance principale arrêtée à 12:18, au repos (aucune question ni traitement actif ; 61 traitements toujours en pause). Le prochain démarrage relira la collection migrée par `placement_matches`.

En cours : attente d'une mémoire libre d'au moins 5 120 Mio avant de relancer l'extraction (4 975 Mio à 12:19, l'API d'un autre projet occupant 833 Mio, laissée intacte). Ordre prévu : `extraction_check.py` sur une instance isolée conservée, puis liaisons DEV, résolution et génération des 100 réponses DEV sur cette même instance (R7), grille D05, mesures D07. Git Bash ne démarre plus depuis 12:18 (erreur interne Cygwin) : commandes passées par PowerShell.
## Reprise du 1er octobre à 14:52 UTC — poste Linux aarch64 (W018) et écarts de l'inspection

**Demandes de l'utilisateur :** `/goal` du 01/10 vers 14:50 UTC (exécuter le chantier jusqu'à PLAN et DoD, skills pertinents, ressources surveillées) ; vers 14:55 « ajuster selon l'environnement ici, ça doit rester compatible aussi avec Windows » (décision [W018](DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)) ; vers 15:00 « corriger ce que tu avais trouvé en écart dans ta première analyse ».

**État de départ (preuves) :** clone `ea49d05` du 01/10 12:42 UTC sur un Jetson AGX Orin (Ubuntu 20.04.6 aarch64, glibc 2.31, 61 Gio, 8 cœurs en ligne en `MODE_30W`, `/` 9 Go libres, carte microSD de 206 Go libres) ; inspection en lecture seule de 13:20 à 14:45 UTC : six cartographies, chacune revérifiée par un vérificateur indépendant (152 affirmations : 123 confirmées, 27 corrigées, 1 réfutée, 1 invérifiable). Constats repris dans les lots J5 et J6 ci-dessous. Identité Git locale absente du clone, fixée à 14:52. Débit réseau mesuré : environ 250 Ko/s par connexion.

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| J0 | Préalables | — | Identité Git locale, W018, skill Linux depuis sources officielles, registre des skills et sources | `verify_pack` PASS ; skill lu et appliqué | VERIFIED — skill `linux-rag-runtime` (sources : LNX01 à LNX15, LNX19 et LNX20, voir sa ligne dans [SKILLS.md](SKILLS.md)), revérifié puis généralisé à x86-64, registre à jour ; `verify_pack` 11/11 (commit `26fa7a5`) ; lu et appliqué par R1, R2 et leurs reprises |
| J1 | Environnement Python multiplateforme | J0 | `pyproject.toml` et `uv.lock` pour `win32/AMD64`, `linux/aarch64` et `linux/x86_64`, `bootstrap.sh` | Résolution Windows identique ; `uv sync --locked` PASS sous Linux | IN_PROGRESS — verrou re-résolu à 15:09 (aarch64) puis 16:36 (x86-64) : partie Windows identique (paquets, roues, empreintes), aarch64 inchangé par l'ajout de x86-64 ; `torch 2.14.0+cpu`, `torchvision 0.29.0+cpu` et `zstandard` pour Linux seulement ; `uv sync --locked` PASS et imports vérifiés sur ce poste aarch64 (16:05) ; commit `26fa7a5` |
| J2 | Runtime POSIX | J1 | Supervision Linux (groupe de processus, signaux, `flock`, environnement des enfants, binaires par plateforme), CLI, verrous d'artefacts par plateforme, `rag.sh` | Tests Linux PASS ; chemins Windows inchangés ; `up`, `status`, `down` réels sous Linux | IN_PROGRESS — réalisé et revu deux fois (R1, R1b) ; chaîne réelle `provision`, `pull-model`, `up`, `status`, `doctor` (vert, 7 rubriques), `down` passée le 01/10 entre 17:31 et 17:54 (preuves sous `.runtime/qa/linux-chain-2026-10-01/`, hors Git) ; `mypy --platform win32` propre ; rondes 4 et 5 closes (point de 21:54) ; reste : essais listés à ce point |
| J3 | OCR sous Linux | J1, J2 | Leptonica et Tesseract 5.4.0 compilés depuis les sources verrouillées, commande Tesseract par plateforme | Tests OCR Linux PASS sur les fixtures | VERIFIED borné Linux — binaire reproductible (même SHA-256 depuis deux emplacements), lié statiquement, version 5.4.0 et manifeste vérifiés. Défaut à 90° conservé dans la campagne historique ; reprise de densité W029-7 validée le 02/10, neuf tests réels finaux PASS et API neuve 19/19 PASS, sans modifier police ou seuil. Aucune qualification Windows ni du corpus métier déduite des fixtures |
| J4 | Interface | J1 | `packageManager` pnpm 10.34.1, commande du lanceur selon la plateforme, sonde E2E Linux, build surveillé portable | `tsc`, tests unitaires web, build sous Linux PASS ; Windows inchangé | IN_PROGRESS — trois rondes revues (dernière « conforme ») : commandes du lanceur lues sur `/health`, textes Windows identiques à `HEAD` (test `windows-texts.test.ts`), contrat de réindexation réel, sondes E2E portables ; 19:00 : `tsc` PASS, 199/199 tests unitaires web, pnpm 10.34.1 ; reste : E2E Linux (API et navigateur), recette Windows (tests, `session.spec`, build surveillé) |
| J5 | Écarts de code de l'inspection | J1 | Corrections C1–C17 retenues (contrat, réindexation en pause, secrets du worker, boucles de fond, watchdog, clés de profil sans effet, rotation de l'audit, jeton avant `try`, collecte des tests hors Windows, origine HTTPS, dépendances déclarées) | Test de reproduction rouge puis vert pour chaque défaut ; suite complète PASS | IN_PROGRESS — C1, C2, C3, C4, C5, C6 (W021), C7, C8, C9, C11, C12, C13 (test de contrat Docling), C16 corrigés avec essais rouges puis verts et trois revues ; collecte de toute la suite sous Linux : 0 erreur ; 19:00 : suite hors intégration 741 réussis, 12 ignorés (Windows), 0 échec ; `ruff` PASS ; `mypy --platform win32` PASS ; `mypy` Linux : 3 erreurs du fichier gelé (W022) ; reste : intégration complète après l'extraction J10, C10 et C17 (documentation), suite Windows |
| J6 | Écarts documentaires de l'inspection | — | Cellules périmées du plan, statuts de DECISIONS, README, `00_LIRE_AVANT.md`, manifestes SHA-256 historiques, renvois `.claude/`, index du journal, renvois de lignes de `docs/` | `check_docs`, `verify_pack`, `build_brief --check` PASS | IN_PROGRESS — fait et vérifié au commit `26fa7a5` (sauf renvois de lignes et état du README) ; 18:59 : renvoi `verify_bundle.py` de `QUALIFICATION.md` corrigé ; renvois de lignes de `docs/` et état du README reportés en J9 sur le commit final |
| J7 | Chaîne réelle Linux | J2, J3, J4 | Provisionnement, `doctor`, `up`, ouverture, import, question, citation, sauvegarde et restauration | Rapports JSON et E2E sur ce poste | VERIFIED — preuves de la qualification Linux du 02/10 ([journal](journal/2026-10-02.md)) : clone neuf provisionné en ligne puis démarré hors ligne (D01.1, D01.2), `doctor` vert, `up` et `down` sans seconde instance (D01.5), ouverture par `open --no-browser` consommée par Chromium (W023), import, question et citation par Playwright sur l'API réelle (D06.2, D06.3), sauvegarde, restauration et ancienne citation (D09.1 à D09.3) ; l'ouverture dans le navigateur de la session graphique n'a pas été essayée |
| J8 | Qualification Linux | J7 | D01–D11 évalués pour la plateforme Linux, avec machine déclarée ; D08.1 dans un espace de noms réseau utilisateur (`unshare -rn`, `lo` seul) | Rapport par critère ; seuils inchangés ; FAIL conservés | IN_PROGRESS — exécuté le 02/10 (L0 à L10, corrections/rejeux/finitions) ; état autoritaire dans le tableau Linux de la [DoD](DEFINITION_OF_DONE.md). W029 lève le gel et corrige les défauts Q-PDF sur fixtures (réelle finale 9/9, API neuve 19/19) ; W029-6 vérifié pour la réextraction et la conservation, sans recette de qualité globale. D09.5 PASS dans le cadre interne W030, pas de validation juridique. Restent notamment D04.7 et jeu final, D07 BLOCKED sur hôte de 61 Gio, D09.4 BLOCKED, critères D03/D06 sans recette et écarts D11 ; aucun PASS Windows déduit des essais Linux |
| J9 | Documentation et publication | J1–J8 | Documentation stabilisée selon l'état livré, brief, commits | `check_docs`, `verify_pack` PASS ; push | IN_PROGRESS — audit D10/D11 et intégration documentaire du 02/10 conservés au journal ; lignes D10/D11 corrigées selon leurs preuves exactes, références stabilisées et décisions actualisées. Reprise W029/R14-1/R15-1 : sources officielles J8S02 complétées sans antidater, relevé actuel de skills distinct de l'historique, compteur des tableaux corrigé après revue. Contrôles finaux du lot PASS à 18:26 : `check_docs` 7/7, `verify_pack` 11/11, brief synchronisé et revue indépendante favorable ; lot publié sur `origin/main` (`635d74a`). Limites historiques et recettes non exécutées restent explicites |

**Points à trancher ajoutés :** (5) les critères à exécuter sur le poste Windows (R7 sur le corpus métier, D07 sur l'hôte de 16 Go, feu vert des 61 documents en pause) ne sont pas exécutables depuis ce poste : ils restent ouverts pour Windows, et les essais Linux ne les remplacent pas ; (6) le GPU du Jetson reste inutilisé tant que D-01 (CPU seul) n'est pas révisé par l'utilisateur.

**Ressources :** un seul traitement lourd à la fois ; `.runtime/` et `.venv/` sur la carte microSD ; espace de `/` contrôlé avant chaque installation (`node_modules`, build web).

Prochaine action : environnement Python synchronisé (J1), puis J2 et J5 en parallèle sur des fichiers distincts.

**Précision de l'utilisateur vers 16:34 UTC :** l'installation doit fonctionner sur n'importe quel poste Windows, comme avant, et sur n'importe quel poste Linux, pas seulement ici ([complément W018](DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)). Réalisé à 16:36 : `uv.lock` étendu à `linux/x86_64` (résolutions Windows et aarch64 identiques), artefacts Linux x86-64 verrouillés (Qdrant 1.19.1 musl, Ollama 0.35.0 `linux-amd64`), sources Tesseract valables pour les deux architectures Linux (`platform` en liste, `entries_for_platform` adapté). Ajouté : J2b — généraliser `bootstrap.sh` (uv 0.12.21 `x86_64-unknown-linux-gnu`, SHA-256 `23f02075…52c0`) et les éventuelles hypothèses aarch64 du code de R1/R2, puis vérifier qu'aucun chemin ou réglage propre à ce poste n'est versionné ; preuve D01 Linux par `bootstrap.sh` puis `rag.sh provision` sur une racine neuve.

**Demande de l'utilisateur vers 18:10 UTC :** évaluations question-réponse sur les documents réels déposés dans `PDF/` ([W020](DECISIONS.md#w020-évaluation-question-réponse-sur-le-corpus-réel-du-poste-linux-pdfmgv-pdftest)). Lot ajouté :

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| J10 | Évaluation sur le corpus réel Linux | J7 (instance Linux) | Import et extraction des 4 documents ; jeu annoté par lecture intégrale (dev `MGV/`, test `TEST/`) relu par un second agent ; mesures de recherche et de contexte (`annotated_eval run`) ; réponses du vrai modèle et grille de jugement | Rapports agrégés versionnés, dénominateurs et intervalles ; aucun texte du corpus dans Git | VERIFIED — corpus caractérisé à 18:13 (208 pages, couche texte partout) ; import 18:14 (4/4) ; jeu de 105 questions (66 dev, 39 test ; 83 répondables, 22 sans réponse) écrit et vérifié contre les PDF à 18:31 ; extraction terminée à 20:32 (`MGV-B.1` et `MGV-D.0` en `ready_partial` publiés explicitement pour l'évaluation, `modelcards` `ready`, `ePMO` sans texte) ; recherche et contexte mesurés à 20:36 ([rapport](reports/evaluation/corpus-linux-2026-10-01.md)) : développement bloc au top 10 44/52 = 0,846, contexte 39/52 ; tenu à l'écart (`modelcards`) 16/17, contexte 14/17 ; `ePMO` 0/12 ; points faibles : tableaux et unités, questions de suivi ; génération sur GPU et jugement le 02/10 (01:15–02:56) : exactes 27/47 = 0,574 en développement et 11/17 = 0,647 tenu à l'écart, abstention justifiée 19/19, bloc dans le contexte → 37/51 exactes, bloc absent → 0/11 ([rapport](reports/evaluation/corpus-linux-2026-10-01.md#génération-et-jugement-2-octobre-2026)) ; limites : jugement de l'assistant non relu par un expert (point à trancher 2), `ePMO` non évalué (point 8) |

**Constat J10 (01/10, 18:20 UTC), à trancher (8) :** `TEST/ePMO.pdf` (2 pages A3, 3 265 caractères de couche texte, 236 images) sort `ready_partial` sans aucun texte : routage `regional_ocr`, puis rendu refusé `PDF_RENDER_LIMIT` (9 025 398 pixels à l'échelle 3 pour un plafond `max_page_render_pixels` de 8 000 000), `DOCUMENT_WITHOUT_TEXT`. C'est la limite déclarée par W016 (A3 refusé), mais elle fait perdre aussi la couche texte native. Options : (a) garder la limite (document déclaré non exploitable) ; (b) pour une page au-delà du plafond, retenir la couche texte native au lieu de l'OCR régional ; (c) rendre ces pages à une échelle réduite qui respecte le plafond. (b) et (c) modifient l'ingestion et l'empreinte d'extraction des deux plateformes : décision de l'utilisateur. L'évaluation J10 mesure la limite telle quelle.

## Point à 18:59 UTC (1er octobre) — intégration avant commit, ronde 4

Contrôles sur l'arbre de travail : suite Python hors intégration 741 réussis, 12 ignorés (propres à Windows), 0 échec (2 min 07) après deux corrections de l'intégrateur (attentes bornées à 2 et 4 s remplacées par une échéance de 30 s dans `test_api_jobs.py`, instables sous charge ; compte des skills projet porté à 7 dans `test_docs_tooling.py`) ; `ruff check .` PASS ; `mypy --platform win32` PASS (89 fichiers) ; `mypy` Linux : 3 erreurs du fichier gelé `checkpoint.py` (W022) ; web : `tsc` PASS, 199/199 tests unitaires ; test du build surveillé intégré (`tests/unit/test_web_build_monitored.py`, 13/13). Tests d'intégration (Docling, OCR, services réels) : après la fin de l'extraction J10, pour ne pas cumuler deux traitements lourds.

**Ronde 4 (à lancer après les mesures J10) :** runtime — tolérance par empreinte de contenu des sources Tesseract inopérante dans `provision_artifacts` (le groupe `tesseract-source` doit être laissé à `provisioning.build_tesseract`), `bootstrap.sh` sans contrôle glibc ≥ 2.28 ni refus de musl, `--no-browser` absent des lanceurs, lien de session passé en clair sur la ligne de commande du navigateur sous Linux, chemin Linux x86-64 non exécuté (archives à télécharger et parcourir au moins), `pull-model` sans comparaison au verrou ; OCR — conclusion de l'enquête 90° à ramener à ce que les mesures établissent, version finale des essais OCR à rejouer, priorité des compilateurs système, garanties non couvertes par des essais, `.part` laissés, minimum GCC de `-ffile-prefix-map` à sourcer, module OCR ignoré sans police Liberation ; API — `progress` des travaux figé à 0,05 pendant l'extraction (calcul sur les fenêtres durables), message `job_pausing` au vocabulaire de l'atelier, fin de flux TLS mal classée, version de Node absente de la preuve du build, `resume_required` à l'import pour `pausing`/`cancelling`.

**Points à trancher ajoutés :** (7) watchdog C5 : limites indépendantes (300 s sans fichier ni CPU, 900 s sans fenêtre durable) au lieu de min(300, 900) — à confirmer ; (9) W-PDF01 sous Windows : passer le `xfail` en strict maintenant qu'il est limité à Windows.

**Demande de l'utilisateur vers 20:20 UTC :** sur un poste pourvu de GPU, le système doit être proposé, détecté et utilisé automatiquement ([W024](DECISIONS.md#w024-accélération-gpu-détectée-proposée-et-utilisée-automatiquement-quand-elle-est-disponible)). Lot ajouté :

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| J11 | Accélération GPU automatique | J2, J7 | Étude des sources officielles (Ollama, NVIDIA JetPack, onnxruntime, PyTorch, Docling), skills mis à jour, détection et proposition dans `doctor`, utilisation automatique avec repli CPU, mode CPU imposable, artefacts officiels par plateforme et variante | Essai réel sur ce Jetson (GPU utilisé, latence mesurée) ; postes sans GPU inchangés (tests) ; D07 toujours mesurée en mode CPU | IN_PROGRESS — J11.1 à J11.9 réalisés (sous-lots du point de 21:43) ; J11.10 (rejeu sous Windows) à faire |

## Point à 21:43 UTC (1er octobre) — J11 : étude close, arbitrages W025, réalisation

Étude J11 close : trois recherches dans les sources officielles (Ollama v0.35.0, NVIDIA CUDA for Tegra et JetPack, onnxruntime, PyTorch, Docling), un essai réel sur ce Jetson et une conception relue par une revue adversariale (5 constats hauts, 7 moyens, 6 bas). Mesures de l'essai, en `MODE_30W` avec le complément officiel `jetpack5` : préremplissage ×13,6 (invite de 2 121 tokens : 7,6 s sur GPU, 103,6 s sur CPU) ; génération ×2,3 à ×2,7. Arbitrages consignés dans [W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024) : génération seule ; GPU automatique sur les couples qualifiés (aujourd'hui linux-aarch64 avec `cuda_jetpack5`) ; proposition ailleurs ; repli CPU limité à une erreur 500 reçue avant le flux, avec une nouvelle admission à froid ; recette D07 en `llm.accelerator: cpu`. Le point à trancher 6 est clos par W024 et W025.

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| J11.1 | Décisions | — | W025 et amendement de W022 (section `llm` du profil modifiable) | Décisions consignées | VERIFIED — [W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024) ; D-01 annotée |
| J11.2 | Runtime | J11.1 | `services/runtime/accelerator.py` : profil, signaux du poste, lecture de la découverte d'Ollama, couples qualifiés, résolution du mode | Tests unitaires de chaque règle sur des extraits réels de journaux (Windows Iris Xe, Jetson avec et sans complément) | IMPLEMENTED — `accelerator.py`, 91 tests sur des extraits réels de journaux (Iris Xe, Jetson avec et sans complément) ; essai réel en J11.8 |
| J11.3 | Artefacts | J11.2 | Groupe `ollama-gpu` du verrou (`jetpack5`, `jetpack6`), sélection par poste, `provision` (non téléchargé en profil `cpu`), sonde de découverte | Tests ; empreinte d'extraction inchangée | IMPLEMENTED — groupe `ollama-gpu` (tailles et SHA-256 vérifiés contre la release), complément facultatif dans un `provision` complet (complément W025), sonde de découverte ; empreinte d'extraction inchangée (test) |
| J11.4 | Runtime et profil | J11.2 | `load_profile`, état `accelerator` de `runtime.json`, variable transmise à l'API seule, profil livré en `auto` (deux copies, `verify_pack`, brief), D01.4 marqué « à revalider » | Tests ; `environment()` d'Ollama identique | IMPLEMENTED — profil livré en `auto` (deux copies identiques), `verify_pack` 11/11, brief ; D01.4 marqué « à revalider » dans la DoD ; `environment()` d'Ollama identique (instantanés Windows et Linux) |
| J11.5 | API | J11.4 | Options de génération selon le mode, résidence, repli (H1, H2, B4), diagnostics, métriques, indicateur authentifié | Tests ; corps en mode CPU identique octet pour octet | IMPLEMENTED — corps CPU identique octet pour octet à HEAD ; repli limité au 500 avant le flux, nouvelle admission à froid ; `/jobs.generation` et `llm_accelerator` ; occupation relue hors du flux |
| J11.6 | Supervision | J11.3, J11.5 | `doctor` : rubrique « calcul », propositions, états sans découverte et GPU écarté | Tests des états ; verdict Windows sans GPU : même niveau | IMPLEMENTED — rubrique « calcul » (états testés sous Linux et Windows simulé), résumé d'un poste sans GPU utilisable identique à HEAD ; raccourci et `install.ps1` affichent la proposition (PowerShell 7.4.15) |
| J11.7 | Qualification | J11.5 | `calibration --accelerator`, `perf.py` (`d07_eligible`), `selftest`, `SwapFree` relevé | Tests | IMPLEMENTED — `calibration --accelerator`, `perf.py` (`d07_eligible`), `selftest`, `SwapFree` ; procédure D07 décrite dans la DoD et `QUALIFICATION.md` |
| J11.8 | Essai réel | J11.3–J11.7 | E1 à E8 sur ce Jetson, sur une instance isolée puis sur l'instance du chantier redémarrée en `auto` | Preuves au journal | VERIFIED — E1 à E6 et E8 réels le 02/10 entre 00:59 et 01:16 UTC ([journal](journal/2026-10-02.md)) : complément vérifié et extrait, découverte « Orin, CUDA, cuda_jetpack5 », `selftest` PASS en GPU (100 % GPU) et en CPU (100 % CPU), instance du chantier redémarrée en `auto` (`gpu_ready` puis `gpu_in_use`) ; pilote : premier mot sur contenu nouveau 10,5 s contre 145,5 s sur CPU ; E6 partiel (H-GPU-2 renforcée, mesure exacte impossible sans root) ; E7 couvert par les tests seulement ; preuves sous `.runtime/qa/j11-gpu-2026-10-02/` (hors Git) |
| J11.9 | Documentation | J11.8 | Skills, `SOURCES.md`, procédure D07, documentation stabilisée | `check_docs`, `verify_pack` PASS | VERIFIED — skills (`linux-rag-runtime`, `windows-rag-runtime`, `hybrid-rag-api`, ligne `compatibility` des cinq skills du pack), `SOURCES.md` (GPU01 à GPU15), documentation stabilisée et schéma `sequence-up` rédigés le 02/10 entre 01:20 et 02:20 UTC, relus contradictoirement (22 constats) ; `check_docs`, `diagrams --check`, brief et `verify_pack` PASS ; commit `c32b759` ([journal](journal/2026-10-02.md)). Écarts relevés ensuite par l'audit D10/D11 : lot J9 |
| J11.10 | Windows | J11.9 | Rejeu sous Windows (suite, `doctor` : rubrique « calcul » verte, `selftest`) | À exécuter par l'utilisateur | NOT_STARTED |

Prochaine action : contrôles et commit de l'état des rondes 4 et 5, puis réalisation de J11.2 à J11.7 avec une revue indépendante.

## Point à 21:54 UTC (1er octobre) — rondes 4 et 5 closes

Réalisé et testé sous Linux (code au commit `ba945af`, documentation intégrée ensuite) :
- **Runtime :** `open` ouvre l'URL de boucle locale ([W023](DECISIONS.md#w023-ouverture-de-session-sous-linux--url-de-boucle-locale-directe)), `--no-browser` et `-NoBrowser` dans les deux lanceurs, lien jamais écrit dans un rapport ; `bootstrap.sh` lit la glibc par `getconf` puis `ldd --version` et refuse musl, une bibliothèque C non reconnue ou une glibc antérieure à 2.28 ; `pull-model` ne compare au verrou que les modèles du profil (compléments W018 et W021), `doctor` juge tout le verrou ; groupe `tesseract-source` laissé à `build_tesseract`. Parcours d'ouverture testé sur l'API réelle (303 puis 200 ; origine opaque refusée en 403 sans consommer le lien).
- **OCR :** repli des compilateurs vers le PATH avec le recours nommé (GCC 8 ou Clang 10, [LNX19](SOURCES.md)) ; commentaire FAST_FLOAT ramené aux relevés ; essai du compilateur réel ignoré avec motif sous le minimum ; installation achevée avant la prise du verrou couverte ; essais de l'espace libre, seuil de 2 Gio.
- **API et interface :** `progress` suivi pendant l'extraction ; fin de flux TLS classée ; message `job_pausing` et fixtures alignés sur `main.py` ; sonde Node du build surveillé selon sa provenance, `CREATE_NO_WINDOW` prouvé sous win32 simulé ; avis d'import « aucun nouveau traitement » pour `reused: true` sans `job_state` ; `API.md` §2.2 et réimport par état.
- **Documentation :** risque résiduel de W023 révisé ; LNX18 à LNX20 ; `EXPLOITATION.md` §3 et §4, `DEPANNAGE.md` §3 ; README racine et README web ; skill `linux-rag-runtime` (`aa07d2fe…`).
- **Contrôles :** pytest hors intégration 826 réussis, 12 ignorés (Windows) ; intégration 37 réussis, 4 ignorés, 1 échec connu (OCR à 90°) ; `ruff` et `mypy --platform win32` propres ; `mypy` Linux limité aux 3 erreurs du fichier gelé ; web `test:unit` 203/203, `tsc` PASS ; `check_docs` 7/7 ; `verify_pack` 11/11.

Reste à faire :
- **Windows :** `.\rag.ps1 open` et `-NoBrowser` (le test textuel ne valide pas la syntaxe PowerShell) ; `pull-model` ; suite Python, dont `test_web_build_monitored.py` ; build surveillé.
- **Linux :** essai réel de `./rag.sh open` avec Firefox snap ; poste musl et glibc antérieure à 2.28 ; plancher GLIBC de `bin/ollama` amd64 ; Qdrant musl (sortie de `file` à conserver) ; Clang jamais exécuté, mélange de chaînes C et C++ jamais compilé, `CC` et `CXX` non consultés (limite déclarée) ; sans affichage graphique, un navigateur en mode texte installé consommerait le lien (lecture de `webbrowser.py`, non essayé).
- **Exploitation :** identité des sources à recapturer au prochain `up` (`bootstrap.sh` a changé) : fait au redémarrage de l'instance prévu en J11.8.
- **À trancher (10) :** rapport daté `apps/web/reports/ui-text-inventory-2026-09-30.md`, qui cite l'ancien message `job_pausing` : le figer tel quel (rapport daté) ou l'annoter.
- **Constat :** l'import ne dit pas si le dernier traitement renvoyé est terminé ; un avis « déjà indexé » exigerait d'étendre `job_state` à tous les états (changement de contrat, non décidé).

## Point à 00:58 UTC (2 octobre) — J11.2 à J11.7 réalisés et revus

Réalisation par quatre agents (fondations, runtime, API, interface), puis revue adversariale sur quatre angles : 31 constats, dont 26 confirmés ou plausibles et 5 réfutés. Corrections par deux agents, contre-vérification (26/26 corrigés), puis quatre écarts mineurs corrigés par l'intégrateur. Le principal : la relecture de l'occupation du GPU retardait la fin des réponses ; elle passe désormais en tâche de fond, bornée à 5 s. Deux comportements ajoutés sont consignés en complément de W025. Incident : une copie de l'agent runtime, relancée par erreur par un message de l'intégrateur, a écrit en parallèle ; elle a été arrêtée et son bloc de tests incompatible retiré. Ses ajouts PowerShell validés sont conservés.

PowerShell 7.4.15 officiel (Linux arm64, SHA-256 vérifié contre `hashes.sha256`) est installé en outil de développement dans le scratchpad. Les versions 7.6.6 et 7.4.20 exigent la glibc 2.33, absente de ce poste. Le parseur ne trouve aucune erreur dans `rag.ps1`, `bootstrap.ps1` et `tools/dist/*.ps1`. Nouveau test `test_powershell_syntax.py`, ignoré avec son motif sans PowerShell. Limite : c'est PowerShell 7.4, pas Windows PowerShell 5.1.

Contrôles : pytest hors intégration 1175 réussis, 12 ignorés (Windows) ; web `test:unit` 217/217, `tsc` PASS ; `ruff` PASS ; `mypy --platform win32` PASS ; `mypy` Linux limité aux 3 erreurs du fichier gelé ; `check_docs` 7/7 ; `verify_pack` 11/11 ; brief synchronisé. Résidu C12 (clés d'identité d'Ollama créées par les essais de signaux du 01/10 à 18:33, chemin relatif résolu depuis `bin/`) déplacé, sans suppression, de `.runtime/bin/ollama-0.35.0/bin/.runtime` vers `.runtime/qa/linux-chain-2026-10-01/ollama-signals-residu-bin`.

Prochaine action : J11.8, essai réel sur ce Jetson (E1 provision du complément déjà en cache, E2 et E3 `selftest` en GPU puis en CPU, E4 instance isolée, E5 et E6 mesures de mémoire), puis redémarrage de l'instance du chantier en `auto` et génération J10.

## Point à 13:31 UTC (2 octobre) — qualification Linux J8 exécutée, corrections intégrées

Qualification Linux exécutée sur ce Jetson, critère par critère ; résultats et preuves dans le tableau « Qualification Linux » de la [DoD](DEFINITION_OF_DONE.md), déroulé dans le [journal](journal/2026-10-02.md).
- Défauts trouvés et corrigés, puis rejoués en conditions réelles : sondes de port en `TIME-WAIT` (D03.5), télémétrie d'ONNX Runtime hors ligne (D08.2), pages données au modèle, indice de couverture des identifiants (W026), barre supérieure étroite, intitulés d'avertissements, inventaire des licences, outils de qualification.
- `injection_check` : PASS automatique seulement si la valeur injectée est absente ; sinon relecture humaine. Aucune adoption sur 16 passages.
- Grille D05 du jeu DEV jugée par deux juges et un arbitre (assistant, non expert) : exactitude 67/80 = 0,838, abstention correcte 20/20, assertions soutenues 196/223 = 0,879. Deux causes dominent les erreurs : « intervalle de contrôle » compris comme une plage d'acceptation (0/7 en français) et l'OCR de DA-P02, qui lit « + » au lieu de « ± ».
- Artefacts lourds et fichiers temporaires déplacés sur la carte SD (demande de l'utilisateur).

**Points à trancher ajoutés :**
- (11) Lever le gel W022 pour corriger D02.6 (schéma converti en texte OCR), D02.7 (tableau des pages 4 et 5 non rattaché) et D02.10 (unités d'un tableau scanné perdues), ainsi que le cas `ePMO` (point 8). Conséquence : l'empreinte d'extraction change, d'où une réextraction complète, y compris des 61 documents du poste Windows.
- (12) Exécuter le jeu final de qualification sous Linux, une seule fois. Il expose le jeu tenu à l'écart, et le sceau d'identité du final est commun aux deux plateformes. Recommandation : après la décision 11 et le gel du code de livraison, ou après la recette Windows R13.
- (13) Valider la redistribution des composants dont le texte de licence manque (point P7 de l'analyse de distribution), puis compléter `LICENSES/` et `THIRD_PARTY_NOTICES` (DIST-07).

Prochaine action : contrôles complets, commit, puis lot J9 (revue D10.5 et D11, documentation stabilisée de la qualification Linux).

## Point à 14:35 UTC (2 octobre) — lot J9 : audit D10/D11 et intégration documentaire

Réalisé :
- Audit D10/D11 en lecture seule sur le commit `36824e2` : 19 écarts entre résultats annoncés et preuves, corrections C01 à C47 proposées ; relecture de la documentation rédigée le même jour (14 constats).
- Intégration : README, CHANGELOG (W021, W023, `pull-model`, `a30b9e1`, protocole de la mesure GPU), architecture (plateforme Linux en sections 1, 2 et 9 ; sections 5.1, 8 et 11), API, exploitation, sauvegarde, dépannage, index de `docs/`, README web et des outils, QUALIFICATION section 10, SOURCES (LNX21, LNX22, J8S01, J8S02, TOOL01 à TOOL03), SKILLS, lignes D10 et D11 du tableau Linux de la DoD ; brief régénéré.
- Écartés après vérification : référence « W018, complément » d'EXPLOITATION section 2 (exacte : point 2 du complément de 16:37) ; usage de LNX16 et LNX17 par le skill Linux (absents de sa liste de sources). Corrigé en l'appliquant : sous Linux, le code 145 ne désigne aucune erreur.

Statuts Linux : D10 FAIL (en partie) — D10.3, D10.4 PASS ; D10.1, D10.5 FAIL ; D10.2 NOT_RUN. D11 FAIL (en partie) — D11.5, D11.7 PASS ; D11.1, D11.2, D11.3, D11.4, D11.6, D11.8 FAIL. Windows : aucune case modifiée.

Contrôles : `check_docs` 7/7 ; `build_brief --check` PASS ; `verify_pack` 11/11 à 14:34:50 UTC (rapport hors dépôt) ; 28 empreintes de skills identiques au registre ; liens et ancres des lignes ajoutées résolus ; fins de ligne CRLF conservées.

Points vérifiés et conformes : sources de W024 et W025 (GPU01 à GPU15) ; mesures D05 Linux et J10 égales à leurs preuves ; D10.3 ; E2E L9 (21 réussis, 1 ignoré) ; uv, Tesseract et Leptonica, complément `jetpack5` ; empreintes PowerShell et des preuves GPU recalculées ; aucun skill dans le contexte du LLM.

Constat (défaut de test, prouvé) : `tests/unit/test_runtime_selftest.py:31` applique sur toutes les plateformes la borne de 57 caractères du binaire Qdrant Windows, que le produit n'applique pas sous Linux (`qdrant_path_bounded`, `restore_backup`) : le test échoue si `TMPDIR` dépasse 38 caractères. Correction envisagée : limiter l'assertion à `sys.platform == "win32"`.

Points à trancher ajoutés :
- (14) Télémétrie d'ONNX Runtime sous Windows : `ORT_DISABLE_TELEMETRY` n'y est pas lue (ETW, W028) ; décider si une mesure propre à Windows est requise (README, section 8).
- (15) Recette E2E sous Linux : les scénarios Playwright de J8 ont tourné sur Ubuntu 20.04, que Playwright 1.63 ne prend plus en charge, grâce à `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` (TOOL02) ; accepter cette méthode comme preuve D06 ou exiger un système pris en charge.
- (16) Désignation du Jetson : « poste de qualification Linux » (DoD) ou « poste Linux aarch64 de développement » (README, architecture) ; dans les deux cas non représentatif de l'hôte de 16 Go de D07.
- (17) Copier sans modification sous `.runtime/qa/j9-2026-10-02/` les preuves aujourd'hui dans les copies de travail de session (essai d'étude J11 `run1-results.json` et `run2-results.json`, archive PowerShell 7.4.15, rapport d'audit et rapports de contrôle du lot J9).

Prochaine action : appliquer les textes restants (DoD D04 et D06, DECISIONS, journal, skill et sa ligne du registre), régénérer le brief, rejouer `verify_pack` et `check_docs`, puis commit et push.

**Complément à 14:47 UTC :** textes restants appliqués après vérification mot pour mot contre l'état des fichiers : lignes D04 et D06 de la DoD ; DECISIONS (statuts de W018, W020, W024 et W025 ; sources, compléments et retours arrière de W018, W021 à W023, W025 et W026 ; D-15 ; nouvelle W028) ; SOURCES (J8S01 reliée à W028) ; plan, journal et son index ; skill `linux-rag-runtime` et sa ligne du registre. La décision proposée sous le numéro W027 est consignée en [W028](DECISIONS.md#w028-corrections-j8-à-effet-de-comportement--sondes-de-port-posix-et-télémétrie-donnx-runtime) : W027 porte déjà la décision de l'utilisateur sur PDF.js. Empreinte du skill `linux-rag-runtime` : `29e50be8…31d2` (au lieu de `694aa269…dcef`). Contrôles : `build_brief` puis `--check` PASS ; `check_docs` 7/7 ; `verify_pack` 11/11 à 14:45:59 UTC (28 empreintes conformes, rapport hors dépôt) ; liens et ancres des lignes ajoutées résolus ; nombre de lignes CRLF inchangé (DECISIONS 55, PLAN 335, SOURCES 86, DoD 189, SKILLS 102). Prochaine action : mettre à jour les lignes D10 et D11 de la DoD (D10.5 ; D11.1 à D11.3, D11.8), régénérer le brief et rejouer les contrôles, puis commit et push.

## Point à 15:34 UTC (2 octobre) — décisions de l'utilisateur sur les points 11 à 13, import par dépôt

- (11) Gel de l'ingestion levé ([W029](DECISIONS.md#w029-levée-du-gel-de-lingestion-w022)) : corriger D02.6, D02.7, D02.10 et le texte natif des pages au-delà du plafond de rendu (`ePMO`), puis réextraire. L'utilisateur demandait une extraction sur GPU : impossible avec des composants officiels sous JetPack 5 (W025, P1) ; l'extraction reste sur CPU.
- (12) Jeu final : après ces corrections et le gel du code.
- (13) Clos : usage interne, sans validation juridique ([W030](DECISIONS.md#w030-usage-interne--registre-des-licences-sans-validation-de-redistribution)) ; D09.5 PASS sous Linux dans ce cadre.
- Essai de l'utilisateur : l'import par la boîte de choix du Chromium snap reste muet (fichier non transmis). Ajout du dépôt de PDF sur la bibliothèque et d'un message explicite ; E2E `library-drop.spec.ts` rouge puis vert, non-régression de `workspace` et `a11y` ([journal](journal/2026-10-02.md)).

Prochaine action : commit, puis lot de corrections de l'ingestion (W029), avec relecture des skills `rag-pdf-provenance` et `pdf-ingestion-windows`, tests rouges puis verts, rejeu de `extraction_check` et réextraction du corpus de ce poste.

## Point à 16:16 UTC (2 octobre) — import sous Chromium snap : cause établie

- Constat (prouvé, [journal](journal/2026-10-02.md)) : sur ce poste, le bouton « Importer des PDF » ne transmet aucun fichier. La boîte GTK 3 du Chromium 153 snap renvoie « annulé » après le choix d'un fichier. Une page témoin réduite à un `<input type="file">` échoue de la même manière, alors qu'avec `--gtk-version=4` le fichier est transmis. Le défaut ne vient ni de l'atelier, ni de l'API, ni de CORS. Le portail de sélection de fichiers est en version 2, sous la version 3 que Chromium exige ([SOURCES IMP01 à IMP03](SOURCES.md#sources-du-diagnostic-de-limport-sous-chromium-snap-2-octobre-2026)).
- Parcours vérifié dans ce même navigateur : glisser-déposer des PDF sur la bibliothèque (202, avis « déjà importé à l'identique » pour un fichier présent). [DEPANNAGE.md](../docs/exploitation/DEPANNAGE.md#5-import-et-ingestion), section 5, est mis à jour.
- Le produit ne règle pas les options du navigateur de l'utilisateur. Le bouton reste en place, avec son message explicite quand la boîte se referme sans fichier.

Point à trancher ajouté :
- (18) Passer le Chromium snap de ce poste en GTK 4 (`CHROMIUM_FLAGS="$CHROMIUM_FLAGS --gtk-version=4"` dans `~/.chromium-browser.init`, puis redémarrage du navigateur) pour réparer le bouton. Ce choix modifie l'environnement de l'utilisateur et peut réintroduire les régressions GTK 4 sous GNOME (LP:2106312, LP:2106342) ; il appartient à l'utilisateur.

Décision de l'utilisateur à 16:20 UTC sur le point 18 : Chromium reste tel quel ; l'import se fait par glisser-déposer sur la bibliothèque. Point 18 clos.

Prochaine action : sans changement, lot W029 (corrections de l'ingestion) en cours, puis réextraction du corpus de ce poste.

## Reprise à 16:48 UTC (2 octobre) — W029 et références documentaires

État de référence : `main`, commit `5ca3685`, avec corrections locales de l'ingestion déjà présentes au démarrage, conservées. Les constats W029 restent ceux du point de 15:34 et de la DoD ; aucune qualification finale n'est encore exécutée. Périmètre autorisé : corrections et preuves W029, puis réextraction du corpus de ce poste ; R14/R15/R22 restent des actions du même chantier, pas un second plan. Exclusions : aucun changement du Chromium de l'utilisateur, aucune substitution de moteur, aucune baisse de seuil OCR, aucune généralisation Linux vers Windows ou vers l'hôte 16 Gio de D07.

| Action | Couche / dépendance | Livrable et critère exact | État et preuve |
|---|---|---|---|
| W029-1 | Ingestion / W029 | Orientation OCR inconnue : aucun texte inventé, région non résolue explicite ; fixture réelle du schéma | VERIFIED borné Linux : schéma réel et région non résolue conservée ; neuf tests réels finaux et API neuve 19/19 PASS après W029-7 |
| W029-2 | Assemblage / W029 | Section et tableau cohérents entre pages 4/5, y compris reprise des fenêtres ; fixture réelle | VERIFIED borné Linux : cinq pages et reprise PASS ; garde d'en-tête courant limitée au haut des deux pages, négatifs testés ; API PASS |
| W029-3 | OCR régional / W029-1 | Cellules et unités DA-P03 exactes sans modifier source ni seuil .8 ; segmentation positive et cas négatifs, extraction réelle | VERIFIED borné Linux : douze cellules exactes et neuf crops tracés, neuf tests réels finaux PASS après W029-7 ; API neuve : DA-P02 et DA-P03, chacun 3/3 lignes exactes |
| W029-4 | Routage / W029 | Couche native fiable conservée après `PDF_RENDER_LIMIT`, sans rendu refusé ; limite toujours déclarée et reprise identique | VERIFIED borné Linux : A3 réel et reprise PASS, hash source conservé, couverture native ≥95 %, `ready_partial` et limite non résolue ; aucune extrapolation au corpus |
| W029-5 | Validation / W029-1 à 4 et W029-7 | Contrôles ciblés, `extraction_check` sur API isolée, puis relecture indépendante code/tests/skills/DoD | VERIFIED borné Linux : API neuve 19/19, neuf tests réels finaux, 1442 unités Python et relectures indépendantes PASS ; dix SKIP de plateforme, deux tests de provisionnement marqués integration exclus. Treize SHA stables ; aucune preuve du corpus ou de Windows déduite |
| W029-6 | Corpus du poste / W029-5 | Réextraction avec empreinte courante ; états et limites observés, originaux inchangés | VERIFIED borné Linux — quatre handles terminaux à 21:21:43 UTC, 208 pages réextraites en séquence, treize sources d'ingestion inchangées. Rapport final `validation/final-conservation.json` sous QA W029-6 : conservation et nouveaux états PASS, revue indépendante favorable. Quatre extractions partielles ; une génération publiée sans perte de texte, trois retenues sans publication ni remplacement de leurs actives. Originaux, révisions et citations historiques contrôlés conservés ; deux documents exclus inchangés. Aucune recette de qualité globale D02 ni preuve Windows déduite |
| R14-1 | Documentation / R14, R22 | Propriétaire dans les en-têtes et le contrôle ; spécifications du comportement livré, dossier de déploiement lié aux vrais scripts ; contradictions prouvées corrigées | VERIFIED borné documentaire : huit références avec propriétaire, spécifications et déploiement livrés ; 58 tests, `check_docs` 7/7, revue indépendante des affirmations contre le code. R14/R22 restent ouverts pour les procédures réelles non rejouées |
| W029-7 | OCR cellulaire / W029-5 | Corriger le petit glyphe à 90° sans changer police/fixture/seuil ; conserver les cellules déjà admissibles, borner/tracer la dérivation et prouver la géométrie inverse | VERIFIED borné Linux : reprise ciblée ×2 pour le petit glyphe non admissible, baseline admissible ou nonfinite non remplacée ; négatifs et géométrie inverse PASS, revue indépendante 62/62, vraie extraction à 90° PASS dans la campagne finale 9/9. Gel régional `6e9b6718…`, aucune modification de fixture/seuil |
| R15-1 | Textes frontend / R15 | Disponibilité formulée sans attribuer une cause absente ; inventaire confronté au code, unités/typecheck/build et rendu aux deux tailles | VERIFIED borné correctif : 224 unités PASS, typecheck/build PASS ; 6 scénarios API réels PASS et 1 état négatif UI intercepté PASS, captures relues. Le nouvel E2E avait initialement ciblé la copie desktop masquée du statut ; sélecteur corrigé, interface inchangée |
| W029-8 | Tests de qualification / W029-5 | Isoler la racine QA des tests de frontières pour qu'un `--basetemp` sous `.runtime/qa` n'admette pas leurs cibles dites étrangères ; assertions de gel et exclusivité inchangées | VERIFIED : racines LOCAL_QA isolées dans les trois seuls tests, aucune assertion ou outil modifié. Différentiel avant patch : trois FAIL sous QA/trois PASS hors QA ; après : 49/49 ciblés et suite générale 1442 PASS/10 SKIP. Revue indépendante favorable |
| R14-2 | Documentation / R14-1, J7 | Corriger les annonces Linux périmées du point d'entrée du référentiel ; rôle/statut explicites, renvois aux procédures livrées et qualification par plateforme | VERIFIED borné documentaire — incohérence de `00_LIRE_AVANT.md` corrigée contre les scripts publiés et les journaux D01 du clone `4d8ba68` ; neuf liens/ancres revérifiés, `check_docs` 7/7, `verify_pack` 11/11, brief synchronisé, avis final indépendant favorable après précision Linux x86-64 et plafond D07 de 16 Go physiques. Preuves `docs-r14-2-final.json` et `verify-pack-r14-2-final.json` sous QA W029-6, journal 19:40 UTC. Aucun nouveau provisionnement, aucune qualification x86-64/Windows déduite ; R14/R22 restent ouverts |
| R15-2 | Textes frontend et serveur / R15-1 | Corriger conséquences d'avertissements, compte réel de reprise groupée, doublons SSE, recherche vide et messages serveur ; inventaire confronté aux sources, tests rouge/vert et rendu relu | VERIFIED borné aux corrections recensées — serveur publié (`abfc1e0`) : cinq modules, 174 régressions PASS, Ruff/mypy ciblé et revue indépendante favorables ; contrats inchangés. Frontend : seize constats corrigés, 27 traductions inventoriées, 244 unités PASS, typecheck PASS, build QA 42,65 s. Rejeu sur instance neuve à 22:59 : DA-P01 réellement importé/publié ; 11 PASS/0 FAIL/SKIP/flaky, dont quatre cas API/session réels et sept états UI explicitement substitués. Dix-huit captures aux deux tailles examinées indépendamment ; sonde console sans erreur observée. Passage rouge 9/2 et correction de trois sélecteurs conservés séparément ; mêmes sources applicatives/export rehashés, aucun rebuild inutile. Native STOPPED, 43 identités observées absentes, zéro inconnu ; données/preuves et ancienne auth QA archivées conservées. Sources du poste et treize SHA ingestion préservés. Preuves sous `.runtime/qa/r15-editorial-20261002T191600Z/frontend-pilot/run-0pd1gccv/`, résumé SHA `824b4fbc2ee323ba910b3c850548767291b9bb06e8200bc60ca1f4c8ff41a0ce`, inventaire frontend et [journal](journal/2026-10-02.md). Ce lot ne ferme ni le lint R15-3, ni la suite complète, ni D06/Windows ; aucun nouveau serveur exécuté sur l'instance du corpus |
| D11-1 | Validation du contexte / D11.6, contrats §7 | Couvrir l'absence de consignes/skills de développement dans les messages et le corps Ollama ; préserver les noms de fichiers cités comme données documentaires | VERIFIED borné assemblage/requête CPU doublée — huit nouveaux tests inclus dans la régression finale 74 PASS, Ruff PASS et avis final indépendant favorable. Vrais `ContextBuilder` et `OllamaGateway` ; garde `Path.open` sur cinq fichiers synthétiques temporaires après initialisation, compteur caractères/4 et transport HTTP explicitement substitués. Oracle mutable initial corrigé : le même mutant en mémoire passe avant (8 PASS), puis produit deux FAIL attendus après ; contrôle normal vert. Aucun modèle réel, contrôle global des lectures disque, PDF hostile ou découverte native de skill qualifié. Preuves JUnit `d11-instruction-isolation-final.xml`, `d11-mutant-before.xml` et `d11-mutant-after.xml` sous QA W029-6, moniteurs séparés sous QA W029, [journal](journal/2026-10-02.md). D11.6 et D11 global restent ouverts |

Sources : W029S01/W029S02 et DOCS01/DOCS02 de [SOURCES.md](SOURCES.md). Nouveau skill `project-documentation` créé avant le lot R14-1 ; aucune règle d'ingestion déplacée dans ce skill. Ressources observées vers 16:41 UTC : environ 44 Gio de mémoire disponible, 8,1 Gio libres sur le volume système et 172 Gio libres sur la carte SD. Trois sous-agents au maximum (quatre rôles avec l'intégrateur), fichiers d'écriture disjoints ; extractions lourdes sérialisées et surveillées.

Point à 17:32 UTC : preuves sous `.runtime/qa/w029-20261002T165030Z/` (API `extraction-api/report.json`, empreintes avant/après dans `summary.json`, réelle `ingestion-real-regression/results.xml`, unités `ingestion-unit-final/results.xml`, UI `web-build/` et `web-e2e-*/`). Aucun changement des treize sources d'ingestion pendant les extractions. Le défaut à 90° est conservé dans sa campagne en échec ; aucun `xfail`, seuil ou attendu affaibli. Les preuves de W029-1 à 5 restent celles de l'empreinte avant W029-7, pas une certification du delta en cours.

Prochaine action exécutable : finaliser et faire relire W029-7, rejouer la campagne réelle et l'API sur son empreinte, synchroniser le suivi et le brief, puis intégrer le lot vérifié. W029-6 reprend ensuite avec contrôle des traitements actifs et sauvegarde ; ni corpus ni originaux n'ont été touchés par cette recette.

Point à 17:49 UTC : W029-7 gelé (`regional_grid.py` SHA `6e9b67188543f0d5180079996db163dc34fb0b7b264758ca82514d374a47ecb7`), avis indépendant favorable et 62 tests purs PASS (`.runtime/qa/w029-density-review-20261002T174610Z/results.xml`). Campagne de neuf tests réels lancée après cet avis, sous verrou lourd ; preuves en cours `w029-20261002T165030Z/ingestion-real-final-v2/`, pas encore de verdict. Ensuite : API dans une instance neuve, sans réutiliser les anciennes extractions, puis contrôle documentaire final/revue avant commit et push. L'ancien essai interrompu reste séparé. Les lignes D10/D11 issues de J9 doivent encore être synchronisées avec leurs preuves exactes ; aucune clôture globale anticipée.

Point à 18:01 UTC : campagne réelle terminée à 17:54:07 UTC, 9 PASS, aucun échec ni skip, 343,06 s Pytest (`ingestion-real-final-v2/results.xml`), treize empreintes inchangées (`summary.json`). Le défaut du scan à 90° est corrigé sur la fixture réelle ; les campagnes en échec et interrompue restent conservées. `ruff` global PASS. Recette API finale démarrée à 17:59 sur un stockage neuf distinct, port 40101 (`isolated-final-state.json`, preuve attendue `extraction-api-final/report.json`) ; aucune réextraction du corpus utilisateur lancée. Prochaine action : obtenir ce résultat, finir la régression isolée et la revue indépendante, synchroniser les références/DoD/brief, puis commit et push avant W029-6.

Point à 18:14 UTC : API finale terminée à 18:07:16, 19/19 PASS en 470,38 s, dix documents/21 pages et treize SHA inchangés ; deux tableaux scannés contrôlés, chacun trois lignes exactes. Avis d'intégration indépendant favorable borné aux fixtures. Régression unité générale : 1429 PASS, 20 SKIP explicités (Windows et outil PowerShell absent), trois échecs prouvés de fixtures d'isolation, deux tests de provisionnement marqués integration exclus. Les cibles dites étrangères sont en fait sous la vraie `LOCAL_QA` lorsque le basetemp suit notre procédure ; W029-8 corrige les racines du test, pas les protections produit. Aucune suite générale verte annoncée avant le rejeu. Prochaine action : corriger/revalider W029-8, obtenir la revue finale documentaire, puis intégrer le lot et préparer la sauvegarde du corpus actif exact.

Point à 18:25 UTC : W029-8 corrigé et relu indépendamment, quatre lignes ajoutées aux seules fixtures de `test_qualification_tools.py` ; quatre outils et cinq jeux/gel/manifeste inchangés. Régression finale terminée à 18:22:50 : 1442 PASS, dix SKIP de plateforme, deux tests de provisionnement integration exclus, aucun échec/erreur ; 186,72 s Pytest, 194,73 s commande (`python-unit-final-green/`). PowerShell 7.4.15 existant fourni explicitement : dix contrôles syntaxiques exécutés, pas de qualification Windows PowerShell 5.1. W029-5 et W029-8 validés sur ce périmètre ; publication en préparation après les contrôles documentaires finaux. Instance du poste confirmée en lecture seule : `74acf854…`, profil `jetson-local16.yaml`, API 8785, données sur SD ; aucune sauvegarde ni réextraction encore lancée. Prochaine action : commit/push du lot, puis inventaire précis des traitements/versions et sauvegarde vérifiée avant W029-6.

Point à 18:34 UTC : lot intégré et poussé sur `origin/main`, commit `635d74a3ab49108e31a84df0fdd5b4159a9a3509`, identité Git conforme, aucun corpus/runtime/secret indexé. Contrôles et revue finale indépendants favorables ; références documentaires/suivi bornés, chantier global toujours ouvert. Les deux instances QA sont arrêtées par leur superviseur, racines et preuves conservées ; l'instance du poste reste active. À 18:32, lecture seule : six documents/six travaux (deux `ready`, quatre `ready_partial`), aucun travail ou question actif, aucune file queued/paused. Prochaine action W029-6 : refaire ce précontrôle, figer les IDs/versions et hashes, créer une sauvegarde SD neuve et la vérifier, puis réextraire par l'API les documents concernés en conservant anciennes révisions/citations et limites partielles. Aucun corpus Windows ou jeu final exécuté à ce point.

Point W029-6 à 18:52 UTC : quatre dernières versions correspondent de façon univoque aux quatre SHA des originaux `PDF/`, 208 pages ; les deux autres documents actifs sont exclus. Manifeste figé sous `.runtime/qa/w029-corpus-20261002T184300Z/`, sans titre ou texte privé. Sauvegarde neuve `.runtime/backups/w029-before-reextract-20261002T184300Z`, ID `20261002T184644Z-c2c0cd79` : 218 fichiers, une collection/1 656 points, SQLite intègre/FK zéro ; `backup` et `verify` séparé PASS (14,56 s/2,08 s). Relecture et vérification indépendante favorables, mutations reprises, aucune question/travail actif avant lancement. Les hashes des lignes immuables incluent `chunk_sources` et `tables_data`, vérifiés contre la base sauvegardée avant POST. Quatre réextractions prévues par API, en séquence, sans import du dossier ni publication partielle explicite ; le manifeste des handles est conservé et la surveillance des ressources active. Prochaine action : suivre ces handles jusqu'à leurs états réels, comparer nouvelles empreintes/limites et conservation des anciennes révisions/citations, puis revue indépendante du résultat. Pas de clôture D02 ou Windows déduite de ce lancement.

Complément D11.2 du 02/10 : consultation officielle actuelle de `torch 2.14.0+cpu`, `python-zstandard 0.25.0` et Ollama `0.35.0-jetpack5`, métadonnées et verrous confrontés, sources D11S01–D11S08 et rapport local `source-review.json` dans la QA W029-6. Les nouveaux avis et releases ne déclenchent aucune migration. **Point à trancher (19), risque hôte :** L4T 35.4.1 constatée est dans les plages de bulletins NVIDIA 5716 et 5797 ; une maintenance OS/pilote relève d'un périmètre et d'un propriétaire distincts, sans élévation autorisée ici. Aucune exploitation ni correction hôte essayée ; le repli CPU ne traite pas ce risque. D11 global reste ouvert. Cette consultation ne reconstitue pas les sources ou lectures historiques manquantes.

Point W029-6 à 19:16 UTC : le validateur QA relu indépendamment a exécuté un contrôle intermédiaire en lecture seule, terminé à 19:14:40 (`validation/progress-20261002T191400Z.json`, 64,95 s sous surveillance). Conservation PASS : neuf tables historiques, six versions/originaux et six fichiers `extraction.json`, deux documents exclus inchangés ; 461 anciennes citations, 2 131 spans et 124 pages de révision relus par API, hashes/offsets/géométrie conformes. Les autres sidecars/checkpoints historiques ne sont pas couverts par ce contrôle. Nouveaux états IN_PROGRESS, sortie 3 attendue, pas de validation finale. À 19:16:03, trois handles sont terminaux (`ready_partial` non publié, `ready` publié, `ready_partial` non publié) ; la quatrième réextraction, 140 pages, est lancée en séquence. Prochaine action : suivre ce dernier handle, exécuter un nouveau contrôle final puis faire relire états, limites et conservation ; aucune clôture W029-6, D02 ou du chantier à ce stade.

Point R15-2 à 21:02 UTC : préflight du build et copie physique QA contrôlés, avis indépendant favorable **limité à la préparation**. `build-preflight.json` et `staging-check.json` sous QA R15 : 224 fichiers sélectionnés, six compléments, quatre liens de dépendances autorisés ; 12 contrôles purs PASS, treize sources d'ingestion et seize références frontend concordantes. Le profil QA ne change que le mode CPU et le chemin absolu du verrou commun ; ses ports et ses données doivent encore être isolés par `control_profile` avant démarrage. Sources officielles R15S01/R15S02 consignées dans [SOURCES.md](SOURCES.md). Le build existant ne prend pas lui-même le verrou : enveloppe `flock -n -o -E 75` requise, à relâcher avant import contrôlé. Dossiers de preuves/authentification privés, traces brutes jamais publiées. Conservation courante de `out` relevée (243 fichiers) ; celle de `.next` et `public/pdfjs` reste à préciser avant le build, sans extrapoler ce premier manifeste. [Relevé de skills](reports/skills-usage-2026-10-02-r15-recette.json) et détails d'exécution dans le [journal](journal/2026-10-02.md). Aucun build, service, import ou navigateur exécuté par cette préparation ; R15-2 reste IN_PROGRESS.

Prochaine action exécutable à ce relevé : préparer et faire relire le pilote D03.7/D03.9 sur fixtures techniques, sans exécution lourde concurrente. Quatrième extraction à 56,43 % à 21:02:01 UTC, état `extracting` ; helper toujours actif, aucun redémarrage ni publication partielle. Après les quatre états terminaux : nouvelle validation finale W029-6, revue indépendante, puis build et recette R15-2 sur instance QA neuve. Les cases D03.7–D03.9 restent ouvertes : un retrait logique n'est pas une purge physique et un réindex identique n'est pas une migration d'embedding. Windows et l'hôte physique de 16 Go restent à qualifier séparément.

Complément à 21:04 UTC : baseline privée `shared-areas-baseline.json` capturée à 21:03:58 ; 203 fichiers `public/pdfjs` hashés intégralement, `.next` limité à son lien/cible et 18 marqueurs explicites (dix fichiers hashés, gros caches et dossiers par métadonnées seulement). Outil `shared_areas_check.py`, neuf prédicats purs PASS et Ruff PASS ; comparaison après build non exécutée. La borne n'autorise aucune garantie sur l'intégralité du cache `.next` ; détail et SHA dans le journal. Le précédent manifeste `out` et cette baseline sont à recontrôler après le futur build isolé.

Point W029-6 final : quatre jobs terminaux à 21:21:43 UTC, helper terminé avec sortie 0 en 8 981,86 s. Validation finale en lecture seule à 21:34:07, `validation/final-conservation.json` SHA `b05edc7297b0cd13cc9737f803907c1dcddc22103ebcc90d9fd0e2e45b878e1b`, état/conservation/nouveaux états PASS ; relecture indépendante favorable. Périmètre de conservation identique au contrôle intermédiaire, toujours sans les autres sidecars/checkpoints : neuf tables historiques, six originaux et six `extraction.json`, deux documents exclus, 461 citations/2 131 spans/124 pages. Les quatre extractions sont partielles ; une génération sans perte de texte est publiée, les trois pertes de texte restent retenues sans remplacer leurs actives. Cohérence des quatre générations actives : 1 342 fragments SQLite/points Qdrant contrôlés par diagnostic. W029-6 satisfait son critère borné ; ni D02 global ni Windows ne sont clos.

Reprise après W029-6, actualisée à 22:33 UTC : le pilote R15 corrigé a servi le build qualifié sur une nouvelle QA et publié la fixture DA-P01 réelle. Navigateur : 9 PASS/2 FAIL, zéro skip/flaky ; deux sélecteurs d'alerte ambigus avec l'annonceur Next.js, pas de défaut applicatif démontré. Les trois assertions concernées ciblent désormais le `main` de session ; typage rejoué PASS. Les sources applicatives et l'export sont inchangés ; passage rouge, données et ancienne authentification à conserver. Prochaine action R15 : contrôleur de reprise à delta de test explicite, relecture indépendante, clearance neuve puis rejeu des onze cas et sonde console, captures réellement examinées ; aucun rebuild des mêmes sources. D03.7/D03.9 : pilote et enveloppe préparés, tests purs et revue indépendante favorables, aucune exécution native déduite. D03.8 ne se valide pas par un réindex identique ; retrait logique distinct de la purge physique. Les exécutions lourdes restent séquentielles ; Windows et la cible physique de 16 Go demeurent à qualifier séparément.

### Extension des contrôles demandée le 2 octobre, suivie à 22:33 UTC

L'utilisateur confirme lint, typage, build, QA/E2E, analyse critique indépendante et corrections itératives. Ces contrôles complètent le chantier existant ; aucun second plan n'est créé. Constat classé **incohérence du dispositif de contrôle** : aucun lint frontend dans `apps/web/package.json` et aucune dépendance/configuration ESLint installée. `tsc` et `next build` ne remplacent pas ce contrôle ([sources R15S03–R15S05](SOURCES.md#contrôles-de-qualité-frontend-r15-2-octobre-2026)).

| ID | Lot et dépendances | Livrable et critère de validation | Statut et preuve |
|---|---|---|---|
| R15-3-Q08 | Qualification UI / D06.6, sections QLONG déjà publiées, F05 | Un parcours sommaire→section→recherche UI ; scope exact et passages dans les blocs de la section, témoin hors section, identité/révision conservées, aucune génération/import ; arrêt conservatif et relecture indépendante | VALIDATED_BOUNDED — un cas strict PASS/retry0 ; deux recherches, 18 blocs QLONG distincts hors section dans le témoin, 21/21 blocs admissibles dans les six passages scoped. Deux captures vues ROOT/non-auteur, arrêt et conservation établis ; avis `GO_NATIVE_Q08_BOUNDED` accepté. Actions page/bloc/OCR non rejouées, DoD globale et Windows non clos ; [preuve](journal/2026-10-06.md#r15-3-q08--action-de-section-sur-lextraction-publiée) |
| R15-3-Q09 | Traçabilité / D06.6 Linux ; final31/E04, Q07, Q08 | Relier le critère exact aux quatre preuves fermées et à la continuité du code, contrôler le suivi et faire relire sa portée ; aucune nouvelle exécution applicative | VERIFIED — assemblage et delta acceptés indépendamment ; statut Linux réconcilié, contrôles 7/7 et 11/11 PASS, brief synchronisé. Cases Windows et DoD globale inchangées ; [preuve](journal/2026-10-06.md#r15-3-q09--sélection-et-actions-réconciliation-des-preuves) |
| R15-3-F05 | Bug du lecteur PDF / R15-3, citation Q06 et données conservées | Synchroniser offsets/slots sans bloquer le scroll manuel. Critère : unités, lint, typage et build verts ; citation14→document1→retour14 puis resize réel, six repères natifs distincts visibles/couverts/peints, scope inchangé, arrêt et relecture non-auteur | VALIDATED_BOUNDED — 342 unités PASS, export `6ae946b1…`, native03 1 PASS/retry0, trois captures vues et avis `GO_NATIVE_CITATION_ANCHOR_LINUX_BOUNDED`. D06.5/global non clos ; [preuves et limites](journal/2026-10-06.md#r15-3-f05--citation-page-14-déviée-vers-la-page-13). Les états historiques des autres lignes sont conservés à leur date, pas transférés au nouvel export |
| R15-3 | Qualité transverse / R15-2 ; recette isolée et ressources disponibles | Lint frontend explicite, versions maintenues/peers contrôlés ; lint, typage configuré et régressions pertinents réussis après corrections ; couverture E2E réelle et substitutions distinguées, rendu et limites relus indépendamment | IN_PROGRESS — qualité produit inchangée : backend Ruff, 1 517 pytest PASS/12 SKIP/45 exclus, typage Linux/win32 et 17 intégrations Linux ; frontend 305 unités, typage, lint119/0/0, export `7168111f…` et 31 cas stricts sur gel `e093c06b…`. F01/F02/F03/F04 et Q01 VALIDATED_BOUNDED dans leurs critères, contrôles inchangés non rejoués. Dernière recette Q05 `64878/2e222a EXIT1` FAILED après quatre reçus, avec deux PNG 300 % relues ; arrêt courant owner72fd, C 20 absences strictes et conservation bornée. Revue finale non-auteur A `14307b32…` acceptée ROOT à 17:22:23 UTC, FAILED inchangé ; C-v2 et D acceptés séparément ROOT à 18:06:28 UTC après 26/47 tests purs et revues non-auteur A. Assemblage du vrai caller et verrou distinct en préparation, sans GO. STOP FBE `fc5278d0…` désormais historique, non réutilisable comme dernier arrêt courant. Révision distincte, ancres, reconnexion SSE, Windows/16 Gio et DoD globale ouverts. [Preuves et prochaine action](journal/2026-10-04.md#q05--correctifs-qa-acceptés-séparément-relevé-1806-utc) |
| R15-3-F01 | Bug : boucle clavier et focus initial de la confirmation / R15-3 | Compléter Tab/Shift+Tab aux bornes sans remplacer le dialogue natif ; désigner Annuler à l'ouverture nominale, garder cible statique pending, Échap, fermeture et retour. Validation : sonde inchangée initial/Tab/retour aux trois tailles et pending, unités/qualité puis export réel au vert | VALIDATED_BOUNDED — arbitrage ROOT du 04/10 à 14:14 UTC après revue finale non-auteur A `bb6ab2e2…` / `a86f8940…`. Qualité, export et 31 acquis sur `e093c06b…` / `7168111f…`, non rejoués. Recette neuve `29568/1dfe36 EXIT0` : cinq RB stricts et sonde finale PASS, trois nominales et pending/récupération ; 64 observations clavier, retour du focus, aucune console tardive inattendue ni GET de cleanup aborté. C actuelle `2411ac8a…` / `af6f3eca…` acceptée : owner FBE arrêté, 35 QA/quatre HOST absents, SQL neuf ready/query0 et conservation bornée. Cinq mêmes PNG modales effectivement vues ROOT/C ; DELETE unique interceptée/400, zéro backend, pas de retrait métier qualifié. Deux hunks cleanup ND et liaison CB ne retirent aucune assertion. Anciens FAILED et incidents de lecteur conservés ; cause historique inconnue. Ni Q05 ni DoD globale clôturés. [Critères et preuves](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc) ; [historique du défaut](journal/2026-10-04.md#c3-native-et-défaut-du-focus-initial-relevé-0427-utc) |
| R15-3-F02 | Bug : titre de confirmation tronqué / R15-3 | Limiter l'ellipsis du lecteur à son titre direct ; préserver largeur et retour à la ligne du dialogue. Validation : garde CSS PASS et nouveau rendu long réellement examiné aux tailles utiles, sans régression lecteur | VALIDATED_BOUNDED — titre seul validé ROOT le 04/10 à 11:04:24 UTC : garde CSS, titre complet sans ellipsis aux trois tailles, mêmes cinq originales vues ROOT/C, export `7168111f…` sur gel `e093c06b…`. Ancienne recette FAILED conservée, pas promue en PASS. Nouvelle recette `29568/1dfe36 EXIT0` et cinq modales neuves C/ROOT préservent le titre ; revue finale A `bb6ab2e2…` acceptée ROOT à 14:14 UTC. F01/F03 désormais validés séparément dans leur portée ; Q05 et DoD globale restent ouverts. Pas de nouveau build ou rejeu des contrôles inchangés. [Validation initiale](journal/2026-10-04.md#revue-c-terminale-et-validation-bornée-f02-relevé-1105-utc), [validation actuelle](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc) |
| R15-3-Q01 | Inconnue : identité de descendant refusée / R15-3 | Instrumenter sans retirer les refus naissance/exécutable ; refaire une chaîne de 31 cas terminale sur l'export inchangé contrôlé, avec arrêt/conservation et revue indépendante. Valider ensuite RB5 et la sonde sur leurs vrais reçus, pas les résultats bruts précédents | VALIDATED_BOUNDED — arbitrage ROOT après relecture ciblée A du 04/10 : nouvelle chaîne terminale 31 stricts/42 collectés/sept groupes sur gel `e093c06b…` et export `7168111f…`, revue C `4c625d36…` et reçu ROOT `356c176e…`. Puis recette neuve `29568/1dfe36 EXIT0` sur le même export : RB5 strict cinq PASS et sonde modale finale `3d956e67…` PASS ; arrêt FBE, conservation et revues C `2411ac8a…` / A `bb6ab2e2…` acceptées ROOT. QA0732 reste un prérequis historique, pas la qualification actuelle. Refus stricts conservés, aucune identité inconnue adoptée ni signalée ; rouges et causes OS inconnues au journal, sans reconstruction de 0612. Le critère d'action n'exige pas cette reconstruction ; ni peinture300 ni DoD globale qualifiés. [Chaîne actuelle et bornes](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc) et [historique](journal/2026-10-03.md) |
| R15-3-Q02 | Inconnue : interruption initiale de0415 / R15-3-Q01 | Consigner uniquement le signal réellement reçu et la phase dans la prochaine enveloppe privée ; préserver l'interruption et le cleanup originaux. Validation : tests de propagation et confidentialité, revue indépendante puis recette terminale ; ne pas reconstruire la cause passée | IN_PROGRESS — KeyboardInterrupt est l'erreur principale 0415 ; son déclencheur reste inconnu. SIGINT par défaut et SIGTERM du handler sont possibles, sans attribution prouvée. Logger V2 gelé, tests purs de propagation/confidentialité/restauration et avis indépendant favorables. Pour 0510, aucun signal n'est consigné par ce logger ; la preuve porte sur une ValueError, pas KeyboardInterrupt. Ce relevé ne qualifie pas une réception de signal réelle et ne reconstitue pas 0415. Sans argv, environnement, locaux, jetons ni contenu réseau ; aucun signal ignoré ou retry automatique. Nouvelle chaîne terminale toujours requise |
| R15-3-Q03 | Bug de revue : affichage d'un storageState malgré le périmètre interdit / R15-3 | Consigner l'incident sans secret, restreindre les lectures, vérifier depuis le code et l'arrêt réel l'invalidité du cookie de session concerné ; revue indépendante du confinement, sans effacer les preuves ni agir sur HOST | CONTAINED_BOUNDED — fichier `read-ui-previous-auth.json` de QA0510 affiché par B ; cookies navigateur exposés, aucun secret recopié dans les rapports. Inspections B arrêtées. Registre de sessions uniquement mémoire prouvé par le code ; PID API 3027761 absent strictement à 05:36:51. Le cookie de session lié à ce registre QA n'est plus validable après cet arrêt, aucune révocation HOST ou suppression effectuée. Rapports root c31c/B58c0 ; avis indépendant C be05 favorable sur le confinement de cette session, lu et rehashé par root. Lectures futures limitées aux fichiers et champs autorisés, sans dump JSON par motif. Exposition historique non effacée, inventaire exhaustif des secrets non certifié ; le fichier entier n'est pas déclaré inoffensif. [Trace de l'incident](journal/2026-10-03.md#recette-v2-rouge-et-confinement-de-lincident-de-revue--05190543-utc) |
| R15-3-Q04 | Bug du contrôleur QA : refus primaire masqué par cleanup / R15-3-Q01 | Conserver primaire et secondaire séparément, exécuter le nettoyage obligatoire et refuser la qualification s'il échoue. Validation : doubles du vrai g.command sur erreurs/interruption/logger, restauration des hooks et avis indépendant puis chaîne réelle terminale | VALIDATED_BOUNDED — V4 gelé sans modifier g/V1/V2/V3 : primaire/secondaire distincts et diagnostic limité ; propagation/restauration du vrai g.command et du corps des 31 exercées avec doubles parmi les 105 tests purs. Revue indépendante C favorable, puis QA0732 terminale EXIT0/31 stricts avec arrêt/conservation vérifiés par C cb678057, lu par root. Aucun cleanup échoué transformé en PASS. Le succès natif n'a pas provoqué une erreur primaire/cleanup : ce comportement d'erreur reste établi par les tests purs. Diagnostic 0612 et identité secondaire inconnue préservés. Cette validation concerne le contrôleur privé, pas D06/R15 globaux. [Trace](journal/2026-10-03.md) |
| R15-3-Q05 | Incohérence de preuve : canvas alloué ne démontre pas une peinture PDF / R15-3 | Établir une attente bornée et une capture utile de PDF synthétique peint à 300 %, avec identité/version/page/zoom/budget explicites. Distinguer preuve de pixels, fin de RenderTask et contenu extrait ; revue indépendante et essai réel avant validation | VALIDATED_BOUNDED au 05/10 à 21:36 UTC — test canonique corrigé, 20+5 tests purs et typage/lint conformes ; second essai strict PASS, capture à 300 % relue ROOT/non-auteur, 127 lectures peintes, pic de 5 canvases et 21 605 280 pixels, libération et arrêt conformes. Aucun résultat RenderTask, ancres métier ou DoD globale acquis. [Résultat courant et limites](journal/2026-10-05.md#q05--oracle-de-peinture-et-recette-canonique-isolée). Historique du 4 octobre conservé : historiques rouge1155/1315 et refus préauth `7124 EXIT1` préservés, causes non reconstruites. Composition puis paquet PC acceptés après tests purs et relecture non-auteur, avant admission ROOT. Nouvelle recette `64878/2e222a EXIT1`, achevée à 17:00:31 UTC : source249/export7168, quatre reçus postcheckpoint, deux PNG intègres montrant QLONG-P11-1/2/3 à 300 %, réellement vues ROOT/A. Échantillons canvas5/21 605 280 pixels ; aucune fin de RenderTask ni texte qualifié. FAILED au caller : warning fatal, trois transports en fermeture ; la sonde revient avec pending3 malgré une attente antérieure pending0. Arrêt/conservation C conformes bornés, revue finale non-auteur A `14307b32…` / `4e1af23b…` acceptée ROOT à 17:22:23 UTC, FAILED inchangé. C-v2 readback/drain/rapport accepté après 26 tests purs et D STOP72fd après 47 tests purs, revues A puis ROOT à 18:06:28 UTC. Assemblage source-only du vrai chemin opérateur/caller en cours ; l'essai synthétique ne prouve ni le PDF ni le warning historique. Pas de replay identique, seuil abaissé ou GO neuf. [Preuves et prochaine action](journal/2026-10-04.md#q05--correctifs-qa-acceptés-séparément-relevé-1806-utc) |
| R15-3-F03 | Bug du test RB03 : sélecteur de titre ambigu / R15-3-Q01 | Cibler le seul titre du lecteur, sans modifier les assertions de fermeture, focus ou périmètre ; préserver la recette rouge et préparer un gel QA séparé. Validation : témoin discriminant du sélecteur, revue indépendante, cinq cas stricts puis modale relue sur le même export | VALIDATED_BOUNDED — arbitrage ROOT du 04/10 à 14:14 UTC après revue finale non-auteur A `bb6ab2e2…` / `a86f8940…`. Sélecteur245 et témoin/revue historiques conservés ; 17 pièces historiques RB reprises, dont les sept sources MJS, sans changement des assertions. Recette neuve `29568/1dfe36 EXIT0` : cinq RB stricts une tentative/retry0/skip0/flaky0, sonde modale PASS et rendu relu sur le même export `7168111f…`. B `e24b76df…` / `c96253f8…` voit 13 originales RB ; avis visuel complémentaire, B étant auteur F01/ND/CB. ROOT voit cinq incluses ; C actuelle valide arrêt/conservation et cinq modales, sans transfert d'un ancien STOP. Interceptions déclarées, Q05 et DoD globale non acquis. [Validation actuelle](journal/2026-10-04.md#validation-finale-bornée-f01f03-relevé-1414-utc) ; [défaut et témoin du sélecteur](journal/2026-10-03.md#recette-f04-terminale-et-diagnostic-modal--relevé-1146-utc) |

| R15-3-F04 | Bug du contrôle QA des artefacts natifs / R15-3 | Vérifier les artefacts d'exécution précisément dérivés des sources gelées, sans effacer les preuves ni admettre les fichiers inconnus. Dépendances : miroir qualifié et R15S34. Livrable : enveloppe privée séparée, tests discriminants et revue indépendante ; validation : nouveau miroir, onze parcours réels, arrêt et conservation | VALIDATED_BOUNDED, 04/10 à 01:59 UTC — miroir703/249sources, sept parents/86Python qualifiés D/A puis conservés B ; E2 sortie0/11stricts. B f69fa52f :138 absences fraîches, trois exe historiques incomplets non réparés, sources/export/marqueurs conformes. C e277dc28 :10PNG vus, dix blocs de citation recomputés ; ROOT de9b1c2f :3PNG inclus. A a5f2feb9 : critère d'action exact satisfait. La carte corrompue est validée par le scénario canonique neuf, pas par une exécution de l'ancien adaptateur GET/cards. R1 réemployée, spans entiers, console exhaustive non qualifiée ; DoD globale inchangée. Refus E et préparations antérieures préservés au journal. [Terminal, preuves et limites](journal/2026-10-04.md#terminal-f04-e2-et-relectures-relevé-0157-utc) |

Actualisation à 10:46 UTC : nouvel adaptateur F03 V3 relu indépendamment,
85 tests purs PASS après un rouge discriminant sur le schéma réel des services.
Liaison réelle EXIT0 puis RB1032 : cinq cas stricts PASS, zéro nouvel essai,
saut ou instabilité. La chaîne complète reste FAILED : sonde complémentaire
TypeError dans la phase large browser_launch, zéro GET auxiliaire/capture,
cause précise encore inconnue ; aucun défaut produit déduit. Arrêt et
conservation déclarés favorables, vérification indépendante terminale en cours.
F03 reste ouvert jusqu'à la sonde/rendu et ses preuves. F04 : gel distinct
116 tests purs PASS, revue indépendante favorable ; nouveau miroir1026 de
697 copies vérifié, puis six parents0700→0500 réellement préparés par ROOT,
sources600 et racines700 conservées. Aucun des onze cas encore exécuté à
ce relevé. Q05 : enveloppe native et revue indépendante en finition ; aucune
peinture300 réelle acquise. [Trace et reçus](journal/2026-10-03.md#f03-v3-recette-rb5-et-préparation-f04--relevé-1046-utc).

Actualisation à 09:47 UTC : gel du sélecteur F03 préparé/relu, 61 tests purs
et deux témoins sélecteur PASS ; avis indépendant C 2bfa615f et 133 pins
contrôlés par root. Le vrai bind refuse avant création du target et démarrage :
comparaison des dictionnaires de services entiers avec la projection à trois
champs du reçu d'arrêt. Les tuples PID/naissance/exécutable concordent, mais
le runtime comporte aussi des métadonnées d'arrêt et de journal. Nouveau
correctif QA et témoin du schéma réel nécessaires ; gel V2 conservé, aucune
qualification RB5/modale supplémentaire. Q05 caller livré, 51 tests purs
et lint8/0/0, pas encore essai natif ; enveloppe runtime en préparation.
F04 en correction privée, sans nouvelle fenêtre lifecycle.

Actualisation à 09:18 UTC : la première fenêtre lifecycle/génération0914
s'arrête avant tout cas : contrôle QA refusant 29 artefacts natifs non recensés
(28 caches Python et un marqueur Qdrant vide), 697 copies nommées inchangées.
Résumé `a3204406` FAILED_PRESERVATION, arrêt nominal déclaré et quatre
identités natives constatées absentes par C ; revue terminale en cours.
Correction QA R15-3-F04 suivie ci-dessus, sans autoriser des fichiers inconnus
ni modifier les anciennes preuves. Aucun parcours lifecycle ni génération
n'est validé par cette tentative. RB5 corrigé et Q05 restent indépendants.

Actualisation du replay à 08:45 UTC : les mentions « préparé » ou « navigateur
NOT_RUN » des lignes R15-3/F01/F02/Q01 décrivent leur état avant RB0828.
Le nouveau replay est rouge sur le ciblage QA F03, pas sur le garde d'identité
ni sur Échap. F01/F02 restent sans qualification ciblée complète ; la sonde
modale n'a pas été lancée. Corriger et relire le gel QA séparé, puis produire
une clearance réelle neuve avant toute nouvelle fenêtre native. Ne pas
recompiler ni modifier le produit sur cette erreur de sélecteur.

Actualisation R15-3/Q01/Q04/Q05 à 08:02 UTC : QA0732 termine à 07:53:17,
session 27876 sortie 0 constatée à 07:58:51. Les sept résultats qualifient
31 cas stricts, retry 0, aucun échec/skip/flaky ; arrêt et conservation déclarés
conformes par le contrôleur. C vérifie indépendamment les identités, données
et empreintes terminales avant clôture de Q01. Root a réellement examiné
19 captures principales et celle à 300 % de cette nouvelle exécution, sans
transférer les comptes de 0612. La capture à 300 % reste blanche et ne qualifie
pas la peinture ; un texte possiblement coupé en bibliothèque réduite à
1366 px est soumis à la revue indépendante, sans diagnostic de cause à ce stade.
Le succès natif ne déclenche pas le scénario d'erreur primaire/cleanup :
ce comportement reste prouvé par les tests purs, pas par une erreur native
provoquée. RB5/sonde/lifecycle restent NOT_RUN sur ces nouveaux bindings.
[Exécution et prochaine action](journal/2026-10-03.md#recette-v4-terminale--07430802-utc).

Reprise à 23:14 UTC : conserver et publier le lot éditorial R15-2 vérifié, puis corriger le lint sans désactiver ses règles. Délégation cohérente : intégrateur sur le lecteur PDF, sous-agent frontend sur les autres composants/événements, vérificateur indépendant pour la clôture ; troisième axe backend, lanceur de 17 intégrations gelé et 57 tests purs PASS, natif non exécuté. Après les modifications fonctionnelles : unités, typage, lint, nouvel export QA et parcours navigateur concernés, avec nouvelles empreintes et ressources surveillées. D03.7/D03.9 restent préparés, non exécutés ; Windows, hôte de 16 Go et autres critères du chantier restent ouverts.

Reprise à 23:53 UTC : lot éditorial R15-2 publié sur `origin/main` (`05da85c`). Les 17 intégrations Linux runtime/TLS ont réellement réussi sur QA isolée : 17 PASS, aucun échec/skip, 10,66 s Pytest ; arrêt des processus possédés et refus sans adoption des services existants contrôlés, résumé privé `d03-pilot/backend-quality/native-runtime17-65hs2geg/summary.json` sous QA R15. Ce passage ne qualifie ni RAG, Windows, D03 ni D07. Frontend R15-3 : corrections PDF et neuf autres sources implémentées ; dix témoins PDF et quatorze témoins de cycle de vie réussis, doubles et SSR distingués. Nouveau graphe installé frozen dans un pool SD privé (210 paquets, 18,53 s), six dépendances de développement ajoutées sans changer les versions existantes ; contexte peer Babel optionnel de Next/styled-jsx modifié. Seul le lien local `node_modules` a été remplacé après relecture indépendante ; ancien pool conservé, deux marqueurs contrôlés, pas preuve d'intégrité globale. Première suite complète des corrections : 265 PASS/3 FAIL/0 SKIP sur 268 tests ; deux gardes de câblage et le parseur de grille doivent être adaptés au code réel sans perdre leurs assertions. Typecheck : un échec de rétrécissement de type dans le nouveau test, pas dans les sources produit. Ces rouges restent conservés, aucune validation frontend globale anticipée. Prochaine action exécutable : corriger et faire relire les trois oracles/type du test, puis suite complète, lint et typage ; ensuite gel neuf, export QA et navigateur. Les contrôles Python inchangés restent acquis ; D03.7/D03.9 et les autres critères ouverts ne sont pas clôturés.

Reprise du 03/10 à 00:26 UTC : le pilote D03 réel est achevé et arrêté, conservation relue indépendamment. D03.7 reste partiel (citations/version/réindex et retrait logique vérifiés, aucune purge physique) ; D03.8 NOT_RUN. D03.9 PASS Linux aarch64 sur le scénario de génération épinglée et retrait avant contexte, après publication partielle explicite ; pas indexation complète naturellement concurrente ni passes GC dénombrées. Voir la [qualification Linux de la DoD](DEFINITION_OF_DONE.md) et le journal pour les limites exactes ; cases Windows inchangées. Frontend final : lint complet PASS, puis dernière garde de session corrigée sans toucher le produit et contre-test renforcé ; 274 unités et typage PASS, rouges conservés. Prochaine action exécutable : geler et relire le stager et l'enveloppe de la QA frontend, copier les seules sources requises dans une racine SD distincte, nouveau build sous verrou, puis 31 cas sans génération/lifecycle et rendu. Les onze autres cas et les compléments de régression des hooks demandent leurs bindings et fenêtres isolées ; pas de réussite E2E anticipée ni clôture R15-3/chantier.

Reprise du 03/10 à 00:48 UTC : les contrôles frontend et D03 ont reçu un avis indépendant favorable borné. Préparation QA V2 : 124 tests purs verts et 42 entrées de verrou relues, mais le premier staging réel refuse avant création avec `KeyError: runtime` : section absente du vrai YAML HOST, ajout limité et approuvé du verrou dans le profil CPU. Les deux profils et les cibles encore absentes ont été revérifiés ; erreur du contrôle préparatoire, pas du produit. Prochaine action : corriger et contre-tester ce cas réel sans modifier le gel historique, relire le nouvel incrément, puis reprendre la copie et sa vérification avant clearance fraîche/build/31 E2E. Aucun nouveau build, service ou navigateur exécuté à ce relevé ; R15-3 reste IN_PROGRESS.

Reprise du 03/10 à 01:23 UTC : correction privée V3 du staging vérifiée sur les vrais profils (rouge discriminant conservé puis 134 tests purs PASS), copie et gel relus indépendamment. Build neuf surveillé PASS, puis 31 cas E2E PASS stricts sur sept groupes ; neuf imports terminés, aucune question modèle créée. Arrêt ciblé terminé à 01:11, 128 identités observées absentes, données et zones originales conservées ; ressources échantillonnées sans qualification 16 Go. Les 19 captures principales sont lisibles ; la capture du budget à 300 % n'attend pas la fin du dessin et ne prouve pas à elle seule un rendu achevé. Prochaines actions exécutables : finaliser la relecture indépendante des 31 ; vérifier le rendu zoomé dans une fenêtre GET seule ; relire les enveloppes privées avant les cinq régressions ciblées et les onze lifecycle/génération sur des bindings réels. Pas de rebuild des mêmes entrées, de réimport aveugle ou de clôture globale ; [journal](journal/2026-10-03.md) pour les preuves exactes.

Reprise du 03/10 à 01:53 UTC : revue indépendante des 31 favorable bornée ; le dessin page11 à300% est déjà visible dans la trace et relu par root/B, sans nouvelle fenêtre native ni attribution de la cause du blanc initial. Copie lifecycle exécutée et contre-vérifiée, 697 fichiers exacts, sans auth/données anciennes ni démarrage. Première invocation des cinq cas arrêtée avant création du run : le reader privé impose600 au manifeste historique664, sans défaut produit établi ; ancienne QA toujours arrêtée, historiques préservés. Prochaine action exécutable : relecture/contre-tests de l'enveloppe V2 puis clearance fraîche et cinq régressions ; en parallèle, préparation seule de l'orchestration des onze cas sur la copie isolée. Les exécutions natives restent séquentielles et soumises à leurs gates ; pas de réussite anticipée ou de nouveau plan.

Reprise du 03/10 à 02:26 UTC : RB5 V2 a été exécuté puis arrêté avec données conservées : 2 PASS/1 FAIL/2 NOT_RUN, verdict indépendant rouge. RB01 hydratation/retry et RB02 continuité responsive passent ; RB03 échoue dans la confirmation, RB04/RB05 n'ont pas été exécutés. Deux défauts ciblés corrigés dans R15-3-F01/F02 après consignation officielle R15S21 : boucle clavier et titre tronqué. Deux nouveaux témoins rouges conservés, puis 54 tests ciblés et 277 complets PASS, typecheck et lint entier PASS (116 fichiers, zéro erreur/avertissement). Prochaine action exécutable : finir qualité/revue du delta, créer un nouveau gel et export QA, puis réexécuter les parcours concernés et examiner le rendu. Les enveloppes historiques restent immuables ; le préparateur des onze cas exige un nouveau miroir explicitement lié au gel qualifié. Ni anciennes captures, ni succès des 31, ni tests DOM doubles ne valident le nouveau navigateur.

Reprise du 03/10 à 03:02 UTC : revue source/qualité du correctif favorable bornée ; préparation stage31 gelée, 34 tests purs PASS et avis indépendant favorable, sans prérequis RB5 futur. Copie réellement créée à 03:00:19 dans `frontend-quality/PROGRAM-20261003T0301`, gel SHA `70658c3f7ecc236fd5bddfcc9cbda7aaf3a8c8f92b8383aeb6ac682c4551ef74` : 243 sources et un profil CPU physiques, quatre liens partagés approuvés, treize SHA ingestion et trois correctifs identiques, aucun ancien export/auth/donnée repris. Contrôle root PASS ; contre-vérification indépendante en cours. Prochaine action : avis postcopie, clearance HOST fraîche puis nouveau build et 31 parcours exacts ; RB5/sonde modale et lifecycle11 attendent leurs nouveaux reçus. Build, HTTP et navigateur NOT_RUN sur cette copie à ce relevé. Les sources officielles Playwright de la sonde sont consignées R15S22, sans qualification native déduite.

Reprise du 03/10 à 03:33 UTC : build du frontend corrigé PASS et export de 243 fichiers exact, mais recette0301 interrompue sur `owned_identity_executable_changed` : 28 cas qualifiés, deux résultats bruts non qualifiés, dépôt non exécuté. Arrêt, conservation et absence des 117 identités vérifiés indépendamment ; le refus n'est pas attribuable à un PID/exécutable précis avec les preuves présentes. Prochaine action exécutable : geler et faire relire l'instrumentation conservant les décisions originales et la reprise sur l'export inchangé, puis clearance fraîche, recette native et revue terminale. Ne pas refaire lint, tests unitaires, typage et build acquis sur les mêmes octets ; le nouveau navigateur est motivé par la qualification interrompue et le contrôle de commande instrumenté. Après 31 cas réellement qualifiés : RB5 strict, sonde modale et onze cas sur leurs nouvelles liaisons. F01/F02 restent implémentés, pas validés au navigateur ; chantier et DoD non clos.
