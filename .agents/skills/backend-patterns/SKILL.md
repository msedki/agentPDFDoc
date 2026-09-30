---
name: backend-patterns
description: Architecture backend de Decodair en Python, FastAPI, SQLAlchemy 2 et PostgreSQL. À charger pour créer ou revoir une route, un service applicatif, une transaction, un import, un worker, une requête paginée ou une destination mémoire/SQL.
---

# Backend Decodair

Ce dépôt n'est pas un backend Node/Supabase. Partir du code et des versions
réelles : FastAPI, sessions SQLAlchemy synchrones, Psycopg 2 et PostgreSQL 16.
Ne pas introduire un second modèle async ou une nouvelle file de travaux sans
gain mesuré et sans plan de migration.

## 1. Lire avant de concevoir

1. Lire `CLAUDE.md`, le plan du chantier et les autres skills applicables.
2. Suivre la route jusqu'au service, au modèle, à la migration et aux tests.
3. Vérifier la configuration et le chemin de production ; une colonne ou un
   adaptateur inutilisé ne constitue pas une capacité.
4. Relever le grain, l'identité, la provenance, les volumes et les requêtes
   réellement servies.

Pour un import volumineux ou une question d'empreinte, charger aussi
`postgresql-data-pipelines`.

## 2. Frontières de responsabilité

- **Route FastAPI** : authentification, autorisation, contrat HTTP, validation,
  traduction d'erreur et appel d'un cas d'usage. Pas de règle métier répétée
  dans plusieurs endpoints.
- **Service applicatif** : transaction métier, idempotence, orchestration et
  état du travail.
- **Domaine / parseur** : fonctions déterministes, sans session SQL ni effet de
  bord ; mêmes octets et même version donnent le même résultat.
- **Infrastructure** : SQLAlchemy, SQL, stockage objet et adaptateurs externes.
  Elle ne renomme pas une hypothèse en fait métier.

Une abstraction n'est justifiée que si au moins deux implémentations réelles
existent ou si elle isole une frontière qui change déjà, par exemple la
destination SQL/mémoire. Conserver les règles communes au-dessus des
implémentations.

## 3. Transactions et sessions

- Une `Session` représente une transaction mutable et ne se partage pas entre
  threads ou tâches concurrentes.
- La route ou le worker ouvre et ferme la portée ; les helpers ne font pas de
  `commit()` caché.
- Utiliser une transaction par cas d'usage. Une revendication de job peut être
  committée séparément uniquement si sa trace doit survivre à l'échec du
  traitement.
- Après une erreur SQL, rollback avant toute réutilisation de la session.
- Pour plusieurs workers, réclamer le travail atomiquement, avec bail,
  heartbeat, nombre maximal d'essais et `FOR UPDATE SKIP LOCKED` lorsque le
  modèle le requiert.

## 4. Contrats HTTP et travaux longs

- Les listes sont filtrées, triées et paginées là où vit toute la population.
  Tri et colonnes sont en liste blanche ; ordre stable avec clé de départage.
- Un endpoint `202 Accepted` n'est honnête que si la source et l'état du job
  sont durables avant la réponse et repris après redémarrage.
- `BackgroundTasks` convient à une petite action après réponse. Un pipeline
  lourd ou critique exige un worker supervisé ou reste synchrone si la mesure
  prouve que le coût est court.
- Les bornes portent sur la taille annoncée **et** réellement lue. Pour une
  archive, borner aussi membres, volume décompressé et ratio.
- Les réponses volumineuses sont streamées ou exportées ; une liste ne renvoie
  pas des vecteurs complets pour chaque ligne.

## 5. Écritures et idempotence

- Distinguer l'identité métier d'un objet de l'occurrence qui dit où, quand et
  par quel run il a été observé.
- Une contrainte unique et un `ON CONFLICT` rendent l'idempotence atomique. Une
  lecture préalable seule ne protège pas contre deux workers.
- Pour un volume modéré, préférer l'API bulk SQLAlchemy
  `Session.execute(insert(Table), rows)`.
- Une liste passée à `Insert.values()` n'active pas le bulk ORM général ; elle
  reste pertinente pour un upsert avec expressions par ligne, mais doit être
  mesurée.
- Pour un import massif, utiliser `COPY FROM STDIN` vers une staging, valider,
  puis promouvoir avec `INSERT ... SELECT ... ON CONFLICT` dans la même
  transaction. Ne pas désactiver contraintes ou index en production sans
  procédure explicite et réversible.

## 6. Lectures et performance

- Sélectionner uniquement les colonnes nécessaires à la vue.
- Éviter N+1 et lazy loads implicites ; charger explicitement les relations
  utilisées hors de la portée de session.
- Indexer une requête observée, pas un nom de colonne. Vérifier avec
  `EXPLAIN (ANALYZE, BUFFERS)` sur une population représentative.
- Un BRIN vise une grande table dont la colonne est corrélée à l'ordre
  physique. Une petite table ne le justifie pas par principe.
- Ne pas partitionner par réflexe : la rétention, le pruning et la taille
  mesurée doivent payer le coût opérationnel des partitions.

## 7. Cache et destination éphémère

- Un cache ne devient jamais implicitement la source de vérité.
- Un mode mémoire bascule **lectures et écritures** derrière un résolveur de
  destination unique.
- Toute population en mémoire a un budget en octets, une durée de vie, une
  éviction explicite, un propriétaire et un signal visible à l'écran.
- La source brute, son empreinte et sa provenance doivent être durables avant
  de rendre une projection recalculable éphémère.
- Deux destinations implémentant les mêmes lectures ont une garde de parité sur
  la même population réelle.
- Une destination dans la mémoire du processus n'est activable qu'avec une
  seule réplique et un seul worker. Plusieurs workers Uvicorn sont plusieurs
  processus : ils ne partagent ni objets Python ni politique LRU. Si le
  routage ne garantit pas cette unicité, utiliser un magasin partagé ou le
  mode durable.
- Une lecture transverse en mode mémoire part des populations encore détenues,
  puis rejoint les records canoniques **par leurs occurrences source**. Le
  `source_file_id` propriétaire du record ne suffit pas après déduplication.
- Une ressource nommée dont la projection a été volontairement libérée rend un
  contrat 410 stable avec motif et action de reconstruction ; elle ne devient
  ni un 404 ambigu, ni une liste vide.

## 8. Erreurs, logs et sécurité

- Réponses publiques : codes stables et message actionnable, sans stack trace,
  SQL, chemin interne, secret ou contenu sensible.
- Logs structurés : identifiant de requête/job, objet, étape, durée et code
  d'erreur. Ne jamais journaliser token, mot de passe, URL pré-signée ni payload
  brut.
- Authentification et autorisation passent par les dépendances communes du
  dépôt ; ne pas réimplémenter un validateur JWT dans une route.
- Charger `security-best-practices` pour une revue de sécurité explicite.

## 9. Complétude d'une projection critique

Lorsqu'une liste sert à détecter ou suivre un état potentiellement dangereux,
définir sa **population de contrôle** avant toute jointure de référentiel ou de
projection. Un enrichissement optionnel (`criticité`, classification, dossier,
épisode) se joint en `LEFT JOIN` : son absence devient un état explicite et une
facette, jamais une disparition de la ligne source.

Le contrat de réponse expose au minimum :

- `source_total`, `represented_total` et `excluded_by_reason` avec l'invariant
  vérifiable `source_total = represented_total + somme(excluded_by_reason)` ;
- `completeness_state`, version et fraîcheur des référentiels/projections ;
- des catégories stables pour les valeurs absentes, invalides, non barémées ou
  non projetées, sans les confondre avec une population vide.

Une projection incomplète conserve les observations sources avec un statut
dégradé, ou fait échouer explicitement l'endpoint entier si le contrat de sûreté
l'exige. Elle ne renvoie jamais silencieusement une liste partielle comme si
elle était complète. Un état de cycle de vie ou de dossier est rattaché à
l'occurrence source couverte ; une jointure sur la seule identité courante ne
doit pas appliquer le traitement d'une ancienne occurrence à sa réapparition.

Les erreurs d'incomplétude utilisent un type stable et des champs lisibles par
machine, selon le modèle Problem Details, pour que le front distingue panne,
données incomplètes et résultat vide.

Cette discipline reprend des pratiques d'assurance transférables de la
NASA-STD-8739.8 (intégrité des entrées/sorties et traçabilité bidirectionnelle).
Elle ne constitue ni une déclaration d'applicabilité ni une revendication de
conformité à cette norme ou à l'IEC 62279.

## 10. Gate minimal

- [ ] Grain, identité, occurrence et provenance sont distingués.
- [ ] Transaction et responsabilité du `commit` sont visibles.
- [ ] Rejeu, concurrence, rollback et reprise sont testés.
- [ ] Filtres, tri, pagination et total portent sur la population complète.
- [ ] La population de contrôle et l'équation de réconciliation sont testées.
- [ ] Une absence d'enrichissement reste visible ou provoque une erreur typée,
      selon un contrat de sûreté explicite.
- [ ] Cycle de vie, dossier et épisode sont résolus pour l'occurrence couverte,
      y compris après réapparition de la même identité.
- [ ] Débit, mémoire et disque sont mesurés séparément si le volume décide.
- [ ] Tests ciblés puis gates du `CLAUDE.md` sont exécutés dans l'environnement
      requis ; les gates indisponibles restent ouverts.

## Sources officielles

- [FastAPI — Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI — Query Parameters and String Validations](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/)
- [FastAPI — Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [FastAPI — Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI — Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/)
  — `--workers` démarre plusieurs processus indépendants ; une mémoire locale
  n'est donc pas un magasin partagé.
- [SQLAlchemy 2 — Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [SQLAlchemy 2 — ORM-Enabled INSERT, UPDATE, and DELETE](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html)
- [PostgreSQL 16 — Table Expressions et jointures externes](https://www.postgresql.org/docs/16/queries-table-expressions.html)
- [PostgreSQL 16 — Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)
- [PostgreSQL 16 — Populating a Database](https://www.postgresql.org/docs/16/populate.html)
- [Psycopg 2 — Using COPY TO and COPY FROM](https://www.psycopg.org/docs/usage.html#using-copy-to-and-copy-from)
- [RFC 9457 — Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [RFC 9110 §15.5.11 — 410 Gone](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.11)
  — une représentation intentionnellement retirée est distinguée d'un 404
  lorsque le serveur connaît cet état.
- [NASA-STD-8739.8B — Software Assurance and Software Safety Standard](https://standards.nasa.gov/standard/nasa/nasa-std-87398)
- [IEC 62279:2015 — Railway software](https://webstore.iec.ch/en/publication/22781)
