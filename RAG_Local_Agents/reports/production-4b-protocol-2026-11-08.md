# I4 — fiabilité documentaire et préparation à la diffusion

**Rôle :** protocole préalable et critères d'acceptation I4. **Propriétaire :** intégration RAG.
**Statut :** fixé avant modification produit, 8 novembre 2026 (UTC).
**Référence :** `fa3eabce5ab0c309b1ca8f01602fced2eb7f1dd8`, branche `enhanced_version`.
**Demande :** implémenter les pistes différées d'I3, même méthode, générateur 4B seul,
pour renforcer la confiance avant diffusion. Le [PLAN](../PLAN.md) reste canonique.

## 1. Périmètre et état de référence

Le worktree I4 de référence est immuable. Ses 75 fichiers de service sont identiques
octet pour octet au snapshot natif final I3. Les observations I3 restent historiques,
jamais présentées comme de nouvelles exécutions : 11/12 positifs stricts et 18/18
limites contrôlées ; PDF 0/2 réponses complètes, 1/4 relation demandée ; Office
primaire 5/8 stricts et trois erreurs d'admission, reprise distincte 2/3 stricts.
La suite portable I3 termine avec 3 801 réussites, cinq échecs CMake préexistants.

Les nouvelles comparaisons exécutent les deux révisions sur les mêmes entrées,
poids et paramètres. Les tests logiciels, rejeux d'adaptateur, extractions réelles,
requêtes natives et parcours HTTP sont identifiés séparément. Une trace `done`,
un document retrouvé ou une citation exacte ne suffisent pas à noter une réponse.

| Constat prouvé | Hypothèse d'amélioration et contrôle discriminant |
|---|---|
| INA226 : relation d'alimentation au rang 8 puis perdue au plafond de six résultats | Sélection selon les propriétés documentaires demandées, à budget constant, sans perdre les preuves déjà couvertes ni les identifiants obligatoires. |
| TMP117 : titre et deux lignes numériques présents dans l'extraction, sans groupe Docling ni lien entre chunks | Reconnaître seulement une liste écrite explicite par marqueurs, ponctuation, indentation/colonne et fermeture ; conserver ses dépendances jusqu'au catalogue. Aucune attribution au titre simplement le plus proche. |
| P01 : fait utile entièrement cité mais réserve globale inutile | Contrat extractif générique pour les questions simples, sujet/prédicat/condition littéralement ancrés. Les explications causales absentes, pronoms ambigus et réserves sources restent non établis. |
| Sept intégrations OCR ignorées faute des artefacts requis | Provisionner les artefacts existants verrouillés, exécuter les vraies voies native/structurée/OCR et contrôler nombres, signes, unités, conditions et localisateurs contre les images. |
| Cinq tests de construction dépendent d'un CMake absent malgré leur isolation partielle | Reproduire puis corriger le prérequis ou la frontière de fixture exacte, sans affaiblir les assertions, et vérifier la construction/provenance réelles séparément. |
| Erreurs d'admission et différence de pression mémoire entre les blocs I3 | Dossiers temporaires propres, inventaire avant chaque bloc, ressources/arrêts/annulations contrôlés ; erreurs conservées, aucune réduction de réserve. |

## 2. Invariants

- Qwen3-4B Q4_K_M reste le seul générateur ; aucun 8B, autre générateur, entraînement
  ou changement exploratoire de quantification. Les modèles d'extraction et
  d'embedding restent ceux du verrou existant.
- Aucun texte libre du modèle documentaire n'est admis dans la réponse. Catalogue,
  références, registre, calculs par code et validation avant publication demeurent.
- Originaux immuables ; texte, hashes, positions et versions disponibles conservés.
  Une relation de mise en page ne devient ni un fait ajouté ni une section inventée.
- Périmètre appliqué avant recherche et à chaque dépendance/expansion. Une dépendance
  hors portée ne peut servir à certifier une valeur, même si elle est proche.
- Plafonds de candidats, fragments, contexte et réserve mémoire inchangés. Une
  incapacité à tout conserver est tracée, pas masquée par une hausse silencieuse.
- Pas de correction lexicale OCR par attendu, de dictionnaire de réponses ou de
  règle contenant les valeurs/noms des composants du corpus comme solution.
- Aucun déploiement production, release binaire ou qualification Windows n'est
  déduit du travail dans ce conteneur. La publication de code sur la branche est
  autorisée dans la continuité ; la décision de diffusion reste fondée sur les gates.

## 3. Matrice préenregistrée

| Bloc | Volume et frontières |
|---|---|
| I3 régression | 30 cas et oracles conservés ; relecture stricte, dont P01 comme défaut connu à corriger. |
| I4 sélection | Au moins huit cas discriminants : propriété minoritaire, plusieurs documents, rôle erroné, condition différente, contradiction, doublons, identifiant obligatoire et capacité insuffisante. |
| I4 structure | Huit cas : liste native explicite indépendante, colonnes intercalées, faux titre sans parent écrit, parent ambigu, scope tronqué, OCR mixte résolu, OCR ambigu et liste longue au plafond. |
| I4 qualitatif | Au moins huit cas FR/EN : condition et exception explicites, sujet/predicat différent, négation, cause absente, condition inconnue, pronom ambigu et information manquante. Les entrées exactes précèdent les modifications correspondantes. |
| I4 exploitation | Huit frontières : refus mémoire, admission après libération, annulation avant modèle, annulation en génération, timeout, plan tronqué, absence de delta non vérifié et libération permettant la requête suivante. Réutiliser les tests existants quand ils exercent ces frontières. |
| Transfert tenu à l'écart | Huit questions, six répondables et deux limites, sur trois PDF Analog Devices distincts des familles TI utilisées : AD22103, AD22105 et LTC1540. Originaux, questions et oracles figés avant produit ; seuls hashes/compteurs sont partagés jusqu'au gel final du code. |
| OCR réel | Sept intégrations existantes, puis deux scans déterministes de pages du transfert, avec mêmes questions/oracles que leur original natif, provenance OCR effective et contrôle sur l'image originale. |

La séparation du transfert est une discipline de travail dans un espace partagé,
pas une barrière d'accès prétendue. Le développeur du produit ne consulte pas les
huit oracles avant gel ; l'agent de validation les prépare et les relit. La revue
reste non aveugle au bras lors de l'analyse finale et ne vaut pas audit humain externe.
Les documents de transfert restent de l'électronique : aucun résultat interdomaines
ne sera revendiqué. Aucun ajustement produit sur les sorties du transfert final.

## 4. Definition of Done I4 — critères fixés avant essais

| ID | Acceptation |
|---|---|
| I4-D01 — fidélité/portée | Zéro fait, relation, chiffre, condition, citation ou localisateur inventé dans les contrôles ; zéro fuite de scope ; tous les segments publics rattachables à des preuves exactes ou à une opération autorisée traçable. |
| I4-D02 — sélection | Les huit cas de sélection satisfont leur oracle au plafond existant, aucune propriété/condition auparavant couverte perdue ; les obligations impossibles restent explicitement incomplètes. INA226 doit conserver bus et alimentation jusqu'à la réponse. |
| I4-D03 — structure | Les huit contrôles structurels passent ; aucun lien dans les négatifs ambigus/hors colonne/hors scope ; les deux relations TMP117 et leurs conditions restent justifiées par les dépendances exactes jusqu'au rendu. |
| I4-D04 — réponse simple | P01 et les positifs qualitatifs restent complets sans réserve injustifiée ; tous les négatifs gardent leurs limites. I3 doit atteindre 12/12 positifs et conserver 18/18 limites après relecture stricte. |
| I4-D05 — OCR | Sept intégrations réelles exécutées sans échec/ignorance liée au provisionnement ; deux scans de transfert exécutés avec chiffres, signes, unités et conditions demandés exacts, provenance OCR et géométrie vérifiables. Une confiance OCR élevée seule n'est pas une réussite. |
| I4-D06 — non-régression | Suite portable sans les cinq anciens échecs ni nouvel échec ; intégrations pertinentes, Ruff/Mypy, contrats HTTP, brief/pack vérifiés. Les plateformes indisponibles restent NOT_RUN, pas PASS. |
| I4-D07 — natif/transfert | Office8 et PDF2 I3 rejoués avant/après, sans remplacement des échecs ; candidat sans erreur et utile sur les positifs. Transfert final : 6/6 positifs complets et 2/2 limites correctes. Aucune hausse de refus créditée comme gain. |
| I4-D08 — ressources/exploitation | Plafonds et réserve de 1 536 Mio conservés ; pas de travail lourd concurrent. Les transitions injectées respectent le délai configuré + 2 s dans les contrôles déterministes, libèrent ticket/worker et permettent une requête suivante. Parcours HTTP/SSE avec services locaux réels et arrêt vérifié. Mesures natives RAM/latence par phase/route, erreurs au dénominateur ; critères D07 du projet/cible non remplacés par ce lot. |
| I4-D09 — reproductibilité | Révisions réellement séparées, entrées/oracles/versions/poids et code hashés ; séparation diagnostic/transfert, effets des principaux mécanismes contrôlés par ablations locales à entrées identiques. Une mesure primaire par cas et bras ; toute reprise motivée est annoncée avant, bornée et publiée séparément. |
| I4-D10 — livraison | Bilan PASS/FAIL/BLOCKED/NOT_RUN par critère, pistes réalisées/non acquises et raisons, commandes, documentation canonique et journal ; commit/push sans force sur enhanced_version et contrôle du SHA/arbre distant. |

Un critère non atteint ne sera pas abaissé après observation. La qualification
de diffusion globale ne sera déclarée acquise que si ses critères applicables
sont tous démontrés ; sinon le bilan identifiera précisément les réserves.

## 5. Mesures, configuration et ordre

Générateur/verrou I3 inchangés : Qwen3-4B Q4_K_M, GGUF SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`,
Ollama 0.35.0, contexte 8192, température 0,2, top_p 0,9, seed 0,
`think=false`, KV q8_0, CPU au maximum quatre threads. Qdrant 1.19.1 et
multilingual-E5-small INT8 inchangés. Docling 2.131.0, docling-core 2.99.0 et
pypdfium2 5.13.0 ; le provisionnement OCR valide les artefacts du verrou avant usage.
Python 3.12.14, Linux x86-64, 10 451 423 232 octets RAM, neuf CPU visibles, sans
swap. L'inventaire exact et toute évolution de l'environnement seront conservés.

Mesurer les relations document × propriété × rôle × condition à quatre frontières :
extraction, top-k, sélection, catalogue/réponse. Rapporter rappel, faits utiles,
citations structurelles et justificatives, abstentions pertinentes, sur-refus,
erreurs, latences et pics RSS/PSS/USS disponibles. Ne pas sommer tests logiciels,
cas synthétiques, moteurs natifs et reprises dans un taux unique.

1. Figer protocole, sources, cas et oracles ; établir le worktree de référence.
2. Préparer les artefacts verrouillés, reproduire les défauts ciblés et enregistrer
   les nouvelles bases nécessaires avant chaque correction.
3. Implémenter les trois mécanismes indépendants, avec contrats minimaux de données,
   puis intégrer les contrôles de preuve et les erreurs d'exploitation.
4. Tester les unités, sondes et I3 ; corriger les défauts de développement, conserver
   échecs et reprises. Ne pas charger simultanément OCR et génération native.
5. Geler le candidat ; exécuter les deux bras natifs et le transfert réservé, puis
   relire chaque réponse contre les sources. Un problème découvert au transfert
   reste un échec de ce gel ; aucune sélection favorable de nouvelles sorties.
6. Vérifier HTTP, ressources, documentation, publier et distinguer préparation à
   la diffusion, qualification sur cet hôte et validation sur la cible réelle.

Les bases/index/temporaire de chaque exécution sont séparés. Les temporaires
reproductibles de nos propres essais peuvent être nettoyés avant les mesures
natives, avec reçu, en conservant sources, rapports, sorties et artefacts d'échec.

## Sources de méthode

- Code et rapports I3 du commit de référence ; source primaire des défauts reproduits.
- [Docling, options de pipeline](https://docling-project.github.io/docling/reference/pipeline_options/),
  consulté le 08/11/2026 ; contrats vérifiés contre le code 2.131.0 installé, pas
  déduits uniquement de cette documentation mouvante.
- [Tesseract, qualité et tableaux](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html),
  consulté le 08/11/2026 ; transformations et segmentation doivent être tracées,
  aucune confiance ou reprise OCR ne remplace la vérification des symboles.
- [Ollama, Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs),
  consulté le 08/11/2026 ; schéma et validation côté application, sans garantie de vérité.
- Méthodes ALCE et Sufficient Context déjà référencées dans I3 : séparer citation,
  pertinence de preuve et réponse complète, sans transférer leurs scores publiés.
