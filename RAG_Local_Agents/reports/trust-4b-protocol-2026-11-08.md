# I5 — preuves documentaires et complétude avant diffusion

**Rôle :** protocole préalable, matrice et critères d'acceptation de la nouvelle
itération demandée. **Propriétaire :** intégration RAG. **Statut :** fixé avant
modification produit, 8 novembre 2026 (UTC).
**Référence :** `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, branche
`enhanced_version`, worktree séparé `../agentPDFDoc-i5-baseline`.

## 1. Référence, défauts et hypothèses

La demande poursuit les besoins prioritaires restant après I4 : faire porter les
contrôles sur les faits effectivement publiés, préserver les besoins de la
question et améliorer la récupération de sources difficiles. Le générateur
reste exclusivement Qwen3-4B Q4_K_M. Cette itération est numérotée I5 pour
conserver les identifiants et preuves historiques du dépôt.

Les 88 fichiers produit/configuration et les 46 fichiers de qualification du
gel I4 sont identiques à la référence. Le reçu privé
`baseline-source-identity.json`, SHA-256
`f2608e6ac868f8d70ec3876db13a42219af415467576f2fb2e73a64ac7c5559c`,
permet de réutiliser les observations I4 en les nommant historiques. Le transfert
I4 est désormais un jeu de développement et de régression, pas un test réservé.
Le Tesseract corrigé livré en I4 est utilisé dans les **deux** bras I5.

| ID / type | Constat vérifié et impact | Hypothèse à éprouver |
|---|---|---|
| F01 — bug | H01 : colonnes Min/Typ/Max fusionnées ; H03 : 0,25 V attribué à Min au lieu de Typ ; H07 : conditions et valeurs de deux sous-lignes fusionnées. `table_coverage` ne vérifie pas les rôles contre la géométrie. | Reconstruire seulement les liaisons univoques à partir des en-têtes et positions natives/OCR réellement observées, avec colonnes vides et sous-lignes conservées. Une ambiguïté interdit la relation concernée. |
| F02 — bug | H02 : page classée native sur 694 caractères de pied de page, corps absent ; sonde PDFium : 195 paths, 3 forms, 14 objets texte. Aucun bitmap n'oblige à l'OCR. | Détecter des objets visibles hors de la couche texte, borner une reprise OCR régionale et conserver une limite explicite si le corps ne peut être récupéré. |
| F03 — bug | H04 : alimentation présente dans le contexte et perdue dans le plan/rendu ; contrat désactivé par voltage + température. INA : propriété postposée et rôle voisin entraînent une réserve injustifiée. | Décomposer les obligations avant génération, ancrer sujet/propriété/rôle/condition à leur clause et compléter ensuite le plan depuis les seules preuves admissibles. |
| F04 — bug / amélioration | SCAN1 : 230 HW publié pour 230 µW dans un paragraphe supplémentaire ; SCAN2 : unités/signaux et sous-lignes altérés. Une égalité au texte OCR et une confiance élevée ne prouvent pas l'original. | Vérifier les lectures sensibles par géométrie et reprise OCR bornée ; ne pas substituer une valeur attendue. Publier des segments utiles avec leurs dépendances et écarter les ajouts libres non justifiés. |
| F05 — bug / amélioration | H05 : faits présents mais réserve globale inutile ; H06 : génération de plan dépassant le délai malgré des preuves disponibles. | Contrats qualitatifs bornés pour conditions/actions/fonctions explicites, état « analyse non couverte » distinct de « source absente », route déterministe lorsque toutes les obligations sont prouvées. |

Référence documentaire I4 : contrôlé 12/12 positives et 18/18 limites ; Office
natif 8/8 stricts ; PDF TI 1/2 strict ; transfert 1/8 strict (0/6 positives,
1/2 limites), complétude positive 1/6 ; scans 0/2 stricts, une réponse contenant
un nombre/unité faux. Ces dénominateurs ne sont pas sommés : les jeux se recoupent.
La suite portable I4 est 4 105 PASS, 25 SKIP, 45 désélectionnés ; elle ne prouve
pas les futurs octets I5. L'Office de référence I4 a un chevauchement Mypy : ses
latences ne seront pas utilisées pour une attribution causale I5.

## 2. Invariants et limites de l'architecture

- Un seul générateur 4B ; mêmes poids, quantification, tokenizer et modèles E5,
  extraction et OCR. Aucun modèle de jugement sémantique supplémentaire.
- Le générateur ne fournit que des identifiants de preuves et une organisation
  autorisée. Aucun fait libre, calcul implicite ou connaissance interne ne devient
  une réponse. Les calculs autorisés restent du code avec entrées et méthode.
- Chaque fait admis possède document, version disponible, page/section disponible,
  passage et dépendances. Pas de page, titre, bbox, rôle ni référence reconstitué
  lorsqu'il manque. Les originaux et citations historiques restent immuables.
- Les relations d'un tableau sont distinctes de la seule fidélité de ses mots.
  Géométrie, indices et rôles doivent s'accorder. La confiance OCR n'est pas une
  certification sémantique ; toute limite de méthode reste exposée au bilan.
- Un excerpt minimal garde les conditions, négations, exceptions et notes qui
  bornent son sens. Écarter un hors-sujet ne doit jamais supprimer une réserve.
- Scope avant recherche et à chaque dépendance ; plafonds candidats/fragments,
  contexte, pixels et réserve mémoire inchangés. Saturation et pertes sont tracées.
- Aucune règle contenant une valeur attendue du corpus ; aucune correction OCR
  fondée sur un oracle. Un désaccord de lectures ne devient pas un vote de vérité.
- Une seule tâche lourde à la fois ; services/stores QA distincts, arrêts vérifiés.
  Aucun déploiement de production ni qualification Windows/D07 supposés ici.

## 3. Matrice et séparation développement / transfert

| Bloc | Cas et frontières prévus |
|---|---|
| Géométrie de tableau | Au moins 10 contrôles : ordre et permutation de colonnes, case vide, fusion horizontale, sous-lignes, unité distincte, portée des conditions générales, géométrie absente/ambiguë, rotation, scope tronqué. Témoins H01/H03/H07 avec sources réelles, plus fixtures génériques. |
| Couverture de page | Au moins 6 contrôles : texte natif complet, pied de page seul/corps vectoriel, graphique seul, page mixte, rendu hors cap, reprise conservant le texte et les versions. H02 doit récupérer son paragraphe utile. |
| Obligations et rendu | Au moins 12 contrôles : question composite, fait omis du plan, propriété postposée, rôle voisin, sujet concurrent/pronom, condition/action/fonction, négation, exception, besoin inconnu, ajout hors besoin, budget insuffisant, contradiction. |
| OCR | Au moins 8 contrôles purs et les intégrations réelles pertinentes : signes, préfixes/unités, confiance élevée erronée, lecture manquante, lectures discordantes, crop hors cap, géométrie inverse, provenance exacte. Deux scans I4 sont du développement réel. |
| Régression | Contrôlé I3 : 12 positives + 18 limites ; Office natif : 8 cas ; PDF TI : 2 cas ; ancien transfert : 6 positives + 2 limites ; anciens scans : 2 positives. Les anciennes assertions et échecs restent conservés. |
| Nouveau transfert réservé | 10 questions (8 positives, 2 limites) sur 3–4 PDF primaires distincts des sources I4 ; 2 dérivés scan/mixte de pages positives, total 12 requêtes par bras. Questions/oracles/sources figés par le validateur avant mise au point ; il ne modifie aucun code produit. |
| Exploitation | Annulation, mémoire, timeout, plan tronqué, blocage avant delta, libération puis requête suivante ; HTTP/SSE réel, session/CSRF, version/citation après mise à jour. Réutilisation des tests valides, rejeu pour les frontières modifiées. |

La séparation des oracles est une discipline de travail dans l'espace partagé,
pas une barrière d'accès. Les auteurs produit reçoivent uniquement hashes et
comptages du transfert avant le gel final. Les documents demeurent techniques ;
aucun résultat interdomaines ni audit humain indépendant n'est revendiqué.

## 4. Definition of Done I5 — critères avant essais

| ID | Acceptation fixée |
|---|---|
| I5-D01 — fidélité | Zéro fait, chiffre, unité, rôle, condition, référence ou localisateur non soutenu dans **tous** les segments publics, y compris réserves et ajouts. Zéro fuite de scope. Les relations de tableau sont justifiées par la page originale, pas seulement par le texte extrait. |
| I5-D02 — ingestion | Contrôles de géométrie/couverture conformes ; H01/H03/H07 correctement liés, H02 corps utile récupéré ; originaux et dérivations traçables. Une sortie `ready_partial` seule ne satisfait pas la récupération. |
| I5-D03 — complétude | Obligations explicites avant génération, complétion/contrôle après plan ; toutes les positives de développement récupérables complètes sans réserve d'absence injustifiée, dont INA/TMP et H01/H02/H04/H05/H06/H07. Aucun ajout libre du modèle. |
| I5-D04 — OCR | Intégrations OCR réelles pertinentes sans échec/ignorance liée au provisionnement ; les deux scans I4 et les deux dérivés réservés donnent des réponses complètes avec chiffres, signes, unités, rôles et conditions exacts. Une abstention sûre sur une positive échoue au critère d'utilité. |
| I5-D05 — non-régression | Contrôlé : 12/12 positives +18/18 limites ; Office 8/8 stricts ; limites H03/H08 correctes ; suite portable, intégrations pertinentes, Ruff/Mypy et contrôles documentaires sans nouvelle régression. Les plateformes indisponibles restent NOT_RUN. |
| I5-D06 — transfert | Nouveau transfert : 8/8 positives complètes et 2/2 limites pertinentes, deux dérivés positifs stricts, zéro erreur d'exécution candidate. Tous les échecs au dénominateur ; aucune hausse des refus créditée comme amélioration. |
| I5-D07 — exploitation/coûts | Caps et réserve 1 536 Mio inchangés ; identité 4B vérifiée, services arrêtés, ressources libérées. Contrôles déterministes dans délai configuré +2 s ; HTTP/SSE réel sans delta avant validation. Latence/RAM mesurées par route et phase, régressions explicites ; aucune performance cible D07 déduite de cet hôte. |
| I5-D08 — reproductibilité | Référence/candidat séparés, entrées/oracles/versions/code hashés ; baselines et reprises identifiées ; ablations locales des principaux mécanismes à entrées constantes. Une mesure primaire par cas/bras, reprises motivées bornées et publiées séparément ; pas d'ajustement produit après ouverture du transfert final. |
| I5-D09 — livraison | Documentation canonique, matrice et bilan PASS/FAIL/PARTIAL/BLOCKED/NOT_RUN, commandes de reproduction, limites et risques ; commit/push sans force sur `enhanced_version`, identité/arbre/SHA distants vérifiés. |

Un critère non atteint ne sera pas abaissé. L'implémentation d'un mécanisme, une
réussite logicielle et une qualification de production sont des états distincts.
Le bilan reliera chaque besoin réalisé, différé ou non acquis à ses preuves.

## 5. Configuration, mesures et ordre d'exécution

Référence à maintenir : Qwen3 4.0B Q4_K_M, GGUF SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`,
Ollama 0.35.0, contexte 8192, CPU quatre threads, seed 0, température 0,2,
top_p 0,9, think=false, KV q8_0, keep_alive 10 min. Sortie générale 1536
tokens, factuelle 768 ; trace QA full 8 Mio, profil ordinaire inchangé.
Réserve 1536 Mio et estimation modèle froid 4352 Mio. E5-small INT8 et Qdrant
1.19.1 inchangés. Docling 2.131.0 / core 2.99.0 / PDFium 5.13.0.
Tesseract 5.4.0 corrigé I4, binaire SHA-256
`61461b50cb385288c9c1a0382c5836202bdb7ded69b899b04f83122399959c97`.
L'inventaire avant essai conserve versions effectives, manifeste de poids,
profil, architecture, CPU/RAM/swap et empreintes de skills réellement lus.

Mesurer par document × propriété × rôle × condition : extraction, recherche
top-k, contexte effectivement envoyé, registre de preuves, plan effectif et
réponse. Séparer rappel littéral/proxy et rappel des relations ; complétude,
affirmations fausses, réserves injustifiées, refus partiels/totaux, citations
littérales et citations justificatives. Rapporter erreurs, RSS/PSS/USS quand
disponibles, extraction/indexation, chargement, préremplissage, premier token,
génération et latence complète. Changement de route déterministe/modèle explicite.
Une observation par cas ne prouve pas une distribution de latence.

1. Geler ce protocole, référence et corpus réservé ; documenter les constats.
2. Reproduire les témoins de développement avant correction, implémenter les
   mécanismes indépendants et leurs contrats minimaux, intégrer tôt la chaîne.
3. Exécuter les tests ciblés, extractions réelles de développement et ablations
   discriminantes ; corriger et conserver les essais initiaux en échec.
4. Geler le candidat puis ouvrir le transfert réservé. Réaliser les deux bras
   sur les mêmes sources/runtime, nouvelles extractions/index lorsque concernés.
   Une extraction ancienne n'est réutilisée que si son identité reste valable.
5. Régressions finales, parcours HTTP, relecture de toutes les sorties natives,
   bilan par critère, commandes, documentation et publication vérifiée.

## Sources de méthode

- Rapports, traces et sources I4 au commit de référence ; source primaire des
  défauts observés. Sonde PDFium sans rendu du 08/11/2026 conservée en QA I5.
- [PDFium Python API](https://pypdfium2.readthedocs.io/en/stable/python_api.html),
  consulté le 08/11/2026 ; indices texte et caractères peuvent différer,
  rectangles dans le repère PDF, fermeture explicite et absence de thread safety.
  Le contrat 5.13.0 installé est vérifié avant usage des glyphes.
- [Tesseract — qualité](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
  et [CLI/TSV](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html),
  consultés le 08/11/2026 : segmentation, résolution et format observables,
  aucun score de confiance assimilé à une vérité documentaire.
- Sources ALCE/Sufficient Context et Docling déjà enregistrées I3/I4, toujours
  applicables à la distinction preuve/citation/complétude ; aucun score publié
  transféré à cette application. Aucune nouvelle dépendance décidée ici.
