# Préparation des cycles documentaires — 30 septembre 2026 UTC

Tous les scénarios de `lifecycle.spec.ts` sont **NOT_RUN**. Aucun navigateur,
POST, import, réindexation ou modèle n'est lancé par cette préparation. La
qualification du parcours DEV natif déjà exécuté reste documentée dans
`../../reports/QUALIFICATION_UI_NATIVE_2026-09-30.md`.

## Existant vérifié avant ajout

- `workspace.spec.ts` : shell réel, import DEV unique, source/géométrie,
  sélection page/bloc et première question refusée à l'admission.
- `tests/unit/test_api_storage.py` : réimport même version/job, cache séparé
  par identité d'embedding ; le cache utilise `FakeEmbedding`, sans preuve
  d'inférence réelle.
- `tests/unit/test_api_jobs.py` : cache d'extraction vérifié, corruption refusée.
- `tests/unit/test_api_gateways.py` et `test_api_cache_lifecycle.py` : lifecycle
  des sessions/tokenizers, transports ou runtimes explicitement substitués.
- `tests/unit/test_qualification_fixtures.py` : blank/chiffré/invalide au lecteur
  PDF, sans import API ni rendu UI de ces erreurs.

Les nouveaux cas complètent ces tests ; ils ne présentent pas les contrôles
isolés comme un parcours E2E. Ils ne contiennent ni `page.route`, réponse
interceptée, source/citation fabriquée, injection de store ou appel `/queries`.

## Cible et gardes

Un superviseur fournit un fichier de bindings concret à partir du template
`lifecycle-targets.example.json`, avec les IDs réellement lus. Les `null` du
template indiquent l'absence de binding ; ils ne sont jamais remplacés par un
UUID/hash imaginaire. Le fichier est conservé séparément par exécution et revu
avant d'activer un permis. Ne pas utiliser un chemin métier ni la racine corpus
PDF comme stockage.

Les gardes comparent : URL HTTP loopback exacte, `data_dir` réel sous `.runtime/`,
`control/runtime.json` en état running, instance exacte, URL du superviseur,
SHA du fichier profil et SHA du profil effectif fourni par `/diagnostics`.
La présence d'une instance différente ou d'une question active fait échouer
l'admission de la recette. La validation de l'isolation/absence de traitements
lourds appartient au superviseur avant la commande ; les tests ne démarrent,
n'arrêtent ni ne reconfigurent les services.

Chaque cas nécessite son propre `permits` dans le binding. Les mutations sont
ordonnancées une par une avec un `--grep` exact. Les imports emploient les PDFs
contrôlés du manifeste `evals/qualification-v2.1/manifest.json` après vérification
SHA/volume ; les originaux ne sont jamais écrits. Les cas encrypted/corrupt/
blank refusent un chemin documentaire déjà présent : la première preuve est
préservée, sans retry silencieux. Aucun reset, retrait, purge, arrêt forcé,
publication partielle ou reprise automatique n'est inclus.

Les jobs sont suivis par leur ID réel. Pause, erreur ou dépassement du délai
froid est conservé ; une pause fait échouer immédiatement la recette sans
resume. Le délai de 540 s n'est pas une performance déclarée.

## Cas préparés et limites

| Permis | Précondition exacte | Observation attendue | Limite de clôture |
| --- | --- | --- | --- |
| `http_original_cache` | Document/version/fixture SHA réels | Octets SHA exacts, ETag, 304 vide, range206 exact | Cache HTTP seulement |
| `read_old_citation` | Query/source/version/génération/révision/page et hashes de blocs réels | Registre exact, deep-link, GET blocs avec ancienne révision, texte/ancre, garde page actuelle/archivée et Retour avec bloc exact | Ne prouve pas restauration d'historique ni clic de citation dans le chat |
| `read_old_version` | V2 active et V1 réellement archivées | Menu V1, texte attendu 2.7, original SHA V1 | Ancienne révision après reindex du même fichier reste un cas séparé |
| `reimport_identical` | Document prêt au chemin racine égal au nom de fixture | Même document/version/job, aucune version/job ajouté, publication inchangée | Zéro calcul d'embedding non prouvé par ces IDs |
| `reindex_current` | Document/version/génération initiales exactes ; créneau moteur libre | Un seul POST UI, nouveau job/génération publié, mêmes versions de fichier | Cache parser/embedding non prouvé sans empreinte et trace de calcul |
| `import_version_2` | V1 QV-01 prête, V2 absente, même chemin `Procédure QV-01.pdf` | V2 non indexée409 et V1 active avant publication ; V2 prête4.9 puis lecture V1 2.7, deux SHA préservés | Pas de question/citation de modèle ; observation prépublication indispensable |
| `file_error:encrypted` | Fixture chiffrée absente de la cible | Import202 puis job `PDF_ENCRYPTED`, erreur UI visible | Refus mémoire intermédiaire bloque le cas au lieu de masquer l'erreur |
| `file_error:corrupt` | Structure invalide avec signature PDF, chemin absent | Import202 puis `PDF_INVALID`, erreur UI visible | Aucun prétendu refus au stade upload si le header est valide |
| `file_error:blank` | Page blanche absente | État réel ready, page `blank`, blocks[], UI « page blanche/aucun texte exploitable » | L'indexeur autorise réellement 0 chunk ; aucun code empty_extraction n'existe |
| `file_error:size-limit` | Service/stockage séparé, profil max65536 octets, fixture112085 octets | HTTP413 `file_too_large`, message UI, aucun document créé | Ne qualifie pas le plafond nominal200MiB |

Les deux versions QV-01 sont des fixtures techniques hors des 200 questions.
Leurs SHAs sont dans le manifeste ; V1 contient2.7bar et V2 4.9bar. La seed V1
et les bindings issus d'un éventuel vrai query/citation doivent être produits
dans un créneau séparé explicitement autorisé. Ce document n'autorise pas cette
seed ni une génération. Si aucune citation réelle n'existe, le cas citation
reste NOT_RUN ; ne pas fabriquer `S001` ni injecter une source dans l'UI.

## Cache : ce que les preuves peuvent établir

Lors de la préparation initiale, `GET /diagnostics` exposait uniquement les
chargements/libérations/reloads. La révision API exécutée lors de la deuxième
question expose aussi `embedding_session.inference` : `run_calls`, terminés/
échoués et entrées query/passage, limités au processus courant. Cette question
mesure 0→1 appel terminé, une entrée query et aucune entrée passage ; elle ne
qualifie pas un réimport ou réindex. Il faut leurs deltas réels, une identité de
processus stable et l'absence de calcul concurrent. Les hash/IDs inchangés et
un cache présent ne suffisent toujours pas. Ces cas préparés restent
explicitement `NOT_PROVEN` dans leurs attachments.

Une collecte backend en lecture seule peut ajouter : clé du cache
`(model_identity,text_hash)`, dimensions/SHA des vecteurs, générations/chunks,
jobs/stages/attempts, SHA des `extraction.json`/`window*.json` et identité du
pipeline. Cette collecte ne remplace toujours pas une trace exhaustive ou un
compteur de calcul lorsqu'il manque. Elle relève de C/root ; le frontend ne
reçoit ni handle SQLite ni détail de vecteur dans son produit.

B a changé le code/fingerprint depuis l'extraction DA-P01 du premier parcours.
Réindexer actuellement DA-P01 doit retraiter : cette cible ne peut pas prouver
la réutilisation du parsing actuel. Pour ce cas, préparer une extraction avec
le fingerprint courant, conserver cette identité et geler les fichiers concernés
entre baseline et reindex. Un changement du seul embedding sera une autre
cible/config, pas un changement de profil implicite dans ce script.

Le défaut initial est conservé : le viewer chargeait les blocs par version,
donc la dernière extraction publiée pouvait remplacer celle d'une ancienne
citation. Le correctif D03 transmet maintenant `extraction_revision_id` aux
routes blocks/outline, vérifie l'identité retournée et isole les caches. Le
deep-link relit le vrai registre ; « Retour » restaure aussi la source exacte.
Les tests unitaires passent, y compris deux FAIL initiaux du retour conservés.
Le parcours navigateur d'une ancienne révision après reindex du même fichier
reste **NOT_RUN** jusqu'à un binding réel et une cible isolée autorisée. Les
actions page/section sont bloquées seulement si la révision citée est réellement
archivée ; sélection/bloc exact restent disponibles. Le clic dans une réponse
réelle conservée puis réimport V2 sera aussi une recette distincte, sans
injecter un historique simulé.

## Commande à utiliser seulement après créneau et bindings concrets

Depuis `apps/web`, avec Node/pnpm déjà installés et services isolés déjà démarrés :

```powershell
$env:COREPACK_ENABLE_NETWORK='0'
$env:RAG_E2E_BASE_URL='http://127.0.0.1:<port de l'instance isolée>'
$env:RAG_E2E_CONTROL_TOKEN_FILE='<racine de données isolée>\control\admin-token'
$env:RAG_E2E_LIFECYCLE_ALLOWED='1'
$env:RAG_E2E_LIFECYCLE_TARGET='<binding concret revu>'
$env:RAG_E2E_GENERATION_ALLOWED='0'
$env:RAG_E2E_OUTPUT_DIR='test-results/<nouvelle-execution-unique>'
pnpm exec playwright test tests/e2e/lifecycle.spec.ts --grep '<cas exact autorisé>'
```

`RAG_E2E_BASE_URL` et `RAG_E2E_CONTROL_TOKEN_FILE` sont obligatoires ; le port 8785 et le jeton
`.runtime/data/control/admin-token` de l'instance principale sont refusés par `tests/e2e/target.ts`, sauf
`RAG_E2E_MAIN_INSTANCE_ALLOWED=1` posé délibérément pour une recette autorisée sur cette instance.

Ne pas reprendre un dossier de sortie existant : la trace initiale et son FAIL
restent séparés d'une reprise corrigée. Les tests utilisent les mêmes sondes
psutil propres au worker ; aucun processus navigateur utilisateur n'est lu
ou fermé. Les captures et réponses réelles restent dans l'output choisi.

`pnpm typecheck` et `pnpm exec playwright test --list` sont des contrôles de
préparation ; ils ne lancent aucun de ces scénarios et ne clôturent pas E2E.
