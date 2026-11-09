# I5 — reprise du harnais après la phase de développement 5

**Rôle :** preuve et portée du correctif de précontrôle, préparation du suivi.
**Propriétaire :** qualification. **Date :** 9 novembre 2026 UTC.
**Statut :** harnais corrigé et contrôlé ; phase 6 démarrée par root à
01:25:34 UTC, sans résultat final revendiqué dans ce rapport. Le réservé reste
fermé et aucun verdict de production n'est prononcé.

## Incident conservé et cause non établie

Le bras de référence de la phase 5 comporte vingt mesures terminales dans cinq
blocs. Le reçu `development-baseline-phase5-completion.json`, SHA-256
`42528e5313fdb362b6d2dce039945e0e9c335f2516c6db134ccc19dc0c2b97da`,
confirme les cinq contrôles de stabilité des sources et les groupes possédés
vides, avec leaders réapés. Cela ne juge pas la qualité documentaire des réponses.

Le candidat de l'instantané 5 a terminé ses quatre questions du bloc A. Son
bloc B a ensuite échoué en environ 0,55 seconde dans `available_port()` avec
`OSError: [Errno 98] Address already in use`, avant la création de son dossier
de sortie et avant tout démarrage de service ou de requête. Le log est conservé,
SHA-256 `457d1a993ae881fbe15405f8aea2b3da140938e62a2338d260b88d6c127d291a`.
Aucun nouvel essai B n'a remplacé cet échec.

Le contrôle ultérieur de root n'a trouvé aucun moteur natif actif et a réussi
les trois binds ordinaires sur les ports 11439, 6339 et 6340. Le reçu du bloc A
prouve l'arrêt et la réapation des trois groupes. Le log de B n'identifie pas
le port en cause et aucun état de socket n'a été capturé au moment exact de
l'échec : **sa cause historique reste inconnue**. Un état `TIME_WAIT` est une
explication possible, pas une cause démontrée de cet incident précis.

Les seules extractions scans et TI restantes de l'instantané 5 ont ensuite
été exécutées sans question supplémentaire. Le reçu de continuation
`candidate-phase5-extractions-continuation.json`, SHA-256
`660ee1233e169e81b1d9729de79e9da4d9a5bcbfd79856e097a9b8ad78e53c00`,
confirme quatre workers terminés, groupes vides, leaders réapés et sources
inchangées. Les scans finissent à 00:56:18 UTC, TI à 01:08:04 UTC. Leur
réutilisation sur un autre instantané exige une preuve d'identité des sources
d'extraction ; leur réussite technique ne valide pas leurs tables ou réponses.

## Contre-exemple reproductible et raccord minimal

Le précontrôle du harnais créait sa propre socket sans option de réutilisation.
Le runtime disposait déjà de `services.runtime.supervisor.port_probe()`, avec
`SO_REUSEADDR` sur POSIX et un chemin distinct sous Windows. La documentation
officielle Python explique le rôle de cette option pour une socket précédente
en `TIME_WAIT` ; les différences Windows sont déjà consignées dans SOURCES,
entrée J8S02 : [documentation socket Python 3.12](https://docs.python.org/3.12/library/socket.html).

Un contre-exemple utilise uniquement des sockets loopback éphémères possédées,
sans processus de service, OCR ou modèle. Après fermeture active d'un serveur
réutilisable, les états du noyau montrent `TIME_WAIT`. Le probe historique
échoue avec errno 98, le helper existant réussit et un nouveau listener avec
réutilisation peut réellement démarrer. Deux listeners étrangers encore actifs,
avec et sans réutilisation, restent refusés et continuent d'accepter leur propre
connexion. Reçu : `native-port-probe-counterexample-before.json`, SHA-256
`6d724dc00acfdf679ec8376b5e4d4aac0cbb1e6ae479852094f852d0b932b0c4`.

Le correctif remplace seulement le probe local de
`tools/qualification/run_grounded_native.py` par ce helper existant. Une erreur
conserve son errno et identifie désormais le port concerné. Aucun service tiers
n'est arrêté, aucun délai ni plafond n'est changé et aucun réglage du produit
n'est modifié. Le dispatcher réservé v3 utilise le même helper.

La suite ciblée donne **22 PASS, 0 FAIL, 0 erreur, 0 skip en 1,61 s**. Elle réunit
les six nouveaux cas de sockets et les gardes de deadline/lanceur I4 existantes.
Elle couvre notamment le serveur précédent sans réutilisation, les listeners
actifs sur loopback et toutes interfaces, et le redémarrage réellement possible.
Ruff passe sur les fichiers modifiés ; Mypy passe sur le lanceur. Ces contrôles
ne sont pas des appels de modèle et ne remplacent pas la campagne native.

| Preuve | SHA-256 |
|---|---|
| Lanceur corrigé | `b6a443645962a030d699905d6e6b4b623cbbfc06166dc5f991a115ba9f07c397` |
| JUnit des 22 cas | `f1894e8796102dab2184b39feb2e644d8ecbb04be9eb0ce5ecbcf627db167623` |
| Log des 22 cas | `92697f7176694d4ee0c8d03382d754a2d60610865a637efaf28e36f2f661bd51` |
| Reçu de préparation et contrôles | `2db53da3cbaf6bc4966d77d1f9cf5c47fe813fe7be1eacc7e8905bdd14c655a5` |

## Suivi de développement 6

Les corrections de H03 et du regroupement géométrique SCAN2 ont été stabilisées
et revues avant la copie de l'instantané 6. Le constructeur conserve la même base
`41857e17a438fe43123e4ef8274d9d2d446bfbc2` et la portée `services/`, `config/`,
`tools/`, `packages/`, `pyproject.toml`, `uv.lock`. Il vérifie les hashes avant,
après et dans la copie ; un dossier déjà présent n'est jamais remplacé. La copie
de 169 fichiers est cohérente, reçu `diagnostic-snapshot-6.json`, SHA-256
`f6c39760709a5bdb1cd454f9a99ba850d472583e6000f396e7c9b9ee8b293690`.

Le préparateur offre deux politiques explicites. Sans option supplémentaire,
il exige l'identité de tous les fichiers d'ingestion, runtime, configuration,
verrous de dépendances et préparateurs avec l'instantané 5, puis vérifie les
manifestes, PDF, extractions complètes, reçus de sources et arrêts des trois
lots. Avec `--fresh-extractions`, il prépare trois nouveaux lots complets sur
l'instantané 6. Il ne réattribue jamais à ce nouvel instantané une extraction
faite avec d'autres octets. La comparaison réelle trouve une modification de
`services/ingestion/table_geometry.py` : root a donc choisi trois extractions
complètes neuves, avec sept PDF. Le plan `development-candidate-plan-6.json`,
SHA-256 `a737527139241f525646ac4c463d6f40530858906590352777d4ebe56bde23fb`,
contient huit actions et a démarré à 01:25:34 UTC. Aucun ancien résultat n'est
réétiqueté comme produit par ces nouvelles sources.

Dans les deux modes, les mêmes vingt cas sont prévus en cinq blocs. La référence
phase 5 est réutilisée avec ses propres sources et mesures ; le harnais de
mesure doit être identique. La phase 6 est un suivi de développement après
corrections, sans aveugle et sans remplacement des primaires phase 5. Le pilote
enchaîne les actions séquentiellement, avec seuil mémoire, verrou de créneau,
identités avant/après, transmission des interruptions, reçus d'arrêt et refus
de toute sortie déjà présente. Un échec ou un arrêt non prouvé bloque la suite.

Douze tests synthétiques du préparateur et du pilote passent en 0,044 s, ainsi
que Ruff. Ils vérifient les deux politiques, les vingt identifiants uniques,
les chemins neufs, les liaisons d'entrée, la dérive d'entrée, l'arrêt après échec,
l'échec de lancement, l'intégrité et le signal transmis. Aucun moteur n'est
lancé par ces tests.

Les préparations réservées historiques restent conservées. La
[préparation courante v3](trust-4b-final-blocks-addendum-2026-11-09.md) et le
parcours HTTP v4 emploient le lanceur corrigé, avec leurs propres noms et
hashes. Leur préparation ne vaut ni gel final, ni ouverture du réservé, ni
réussite native ou documentaire.
