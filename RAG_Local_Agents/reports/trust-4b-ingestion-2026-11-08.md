# I5 — ingestion, preuves de lecture et conditions des tableaux

**Rôle :** bilan technique du lot ingestion et de ses frontières avec le catalogue de preuves.
**Propriétaire logique :** ingestion / intégration RAG.
**Statut :** bilan intermédiaire de développement, 8 novembre 2026 UTC ; qualification finale non acquise dans ce rapport.
**Référence publiée avant travaux :** `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, branche `enhanced_version`.
**Critères préalables :** [protocole et Definition of Done I5](trust-4b-protocol-2026-11-08.md). Le [PLAN](../PLAN.md) reste le suivi canonique.

## 1. Résultat établi et portée

Les essais de développement montrent une récupération du corps vectoriel auparavant perdu sur D01 et une reconstruction vérifiable des colonnes et sous-lignes des tableaux D01/D03. Les conditions générales sont conservées comme dépendances exactes. Les observations OCR disposent désormais d'un témoin de lecture revalidé avant publication ; une confiance élevée ou une citation littéralement identique au texte OCR ne suffit plus à autoriser une affirmation.

Ces résultats ne constituent pas une qualification de production. Les deux premiers pilotes portent sur des fenêtres de pages du corpus I4, devenu corpus de développement. Le troisième diagnostic traite les sept documents complets de développement, soit 125 pages ; ses résultats sont séparés ci-dessous. Les scans conservent des lectures incertaines et une erreur de signe concordante a été relevée dans SCAN1 : **`corroborated` désigne l'accord de lectures selon le contrôle exécuté, jamais une certification de l'information**. L'amélioration de leur localisation ne démontre pas encore une réponse finale complète et exacte. Aucun oracle du nouveau transfert réservé I5 n'a été utilisé pour ce lot. La qualification finale, le rendu de toutes les réponses et les performances de la chaîne complète doivent être consignés séparément.

Sous diagnostic 4, les huit intégrations OCR historiques ont ensuite réussi. Une nouvelle extraction complète des trois documents D01/D02/D03, soit 32 pages, conserve les relations et passages ciblés ; elle reste distincte des tests contrôlés et de l'évaluation des réponses finales.

Trois niveaux de preuve sont distingués dans la suite :

1. **Tests synthétiques** : glyphes, boîtes et textes contrôlés, puis fonctions réelles de projection et, pour les tests d'intégration, vraie base SQLite. Ils ne qualifient pas PDFium ou Tesseract.
2. **Rejeux purs** : application d'une fonction modifiée aux mêmes observations réelles déjà enregistrées. Ils isolent une modification de logique sans nouvelle reconnaissance.
3. **Nouvelles extractions de développement** : vrais workers, PDFium, Docling et OCR lorsque le routeur le demande, exécutés dans des copies de code figées. Ils ne couvrent pas nécessairement le document entier, ni la réponse HTTP finale.

## 2. Configuration et identité des essais

Le générateur reste exclusivement Qwen3-4B Q4_K_M ; il n'intervient pas dans les mécanismes décrits ici. Son identité et ses paramètres, ainsi que les invariants E5/Qdrant, restent définis par le [protocole I5](trust-4b-protocol-2026-11-08.md#5-configuration-mesures-et-ordre-dexécution). Aucun modèle de correction ou de jugement sémantique supplémentaire n'a été ajouté.

Les versions relevées dans l'environnement de développement sont Python 3.12.14, Linux x86_64, Docling 2.131.0, docling-core 2.99.0, pypdfium2 5.13.0, Pillow 12.3.0, NumPy 2.5.3 et SciPy 1.18.1. Le Tesseract 5.4.0 corrigé en I4 reste celui des deux bras, avec l'identité binaire du protocole. La lecture de métadonnées de paquets confirme leurs versions ; elle n'est pas un essai de moteur.

Les copies de code employées pour les diagnostics natifs sont identifiées par leurs reçus :

| Copie | Création UTC | SHA-256 du reçu `diagnostic-snapshot-*.json` | Portée |
|---|---|---|---|
| Diagnostic 1 | 20:38:31 | `91120153f16adfa4185e39106f992d2960acad126863d61f09b7b564b9411474` | Premier lot géométrie/OCR, avant les conditions générales et les corrections ultérieures |
| Diagnostic 2 | 20:56:23 | `3799f5136528281431c709f094f8cbc2f0365a5cc6532d477835f6e2afd8b6b6` | Conditions générales, projection native de leur texte, en-têtes supplémentaires |
| Diagnostic 3 | 21:48:38 | `4290ab689c3843b3923e7e13360c0535e125433188a4a5b707da985612bcedc1` | Sept documents complets ; tables codes→durée, frontières composites et localisation ordonnée de l'OCR incluses |
| Diagnostic 4 | 22:52:27 | `c393b906bf5bed33afb7be9ba9337c6b002928910930f99202f653275d0f4822` | Repère local, valeur simple, autorités DB et recontrôle OCR non agrandi ; identités vérifiées avant la campagne native OCR 3 |

Les reçus détaillés sont conservés dans `.runtime/qa/production-i5-20261108/`, hors Git conformément aux instructions du dépôt. Chaque préparation conserve les requêtes, les hashes du code, les résultats bruts du worker et l'enveloppe diagnostique. Les six reçus de préparation des deux premiers pilotes, puis les trois reçus de diagnostic 3, déclarent `changed_source_files: []`.

Les évolutions des tables codes→durée, des frontières des en-têtes composites et de l'alignement des occurrences OCR sont **postérieures** à diagnostic 2. Les hashes suivants sont ceux de diagnostic 3, également présents dans l'arbre de travail lors de sa revue en lecture seule :

| Module | SHA-256 |
|---|---|
| `table_geometry.py` | `234eb170e4797d1876f01ff36127ea7383b6cf208d17b4ec804e8b262aab06d9` |
| `source_quality.py` | `bd4adb7a4f50375db67d08f35b7de9fc42d0ddf604e63ae327fe5522ecba1464` |
| `docling_adapter.py` | `49455b1ae293658d199cb351263bb8180ef9991f2e187ca116fcf5d1c1cca7fa` |

Ces hashes situent les observations de ce rapport ; ils ne remplacent pas le gel final du candidat. Une extraction antérieure dont la projection ne se reconstruit plus doit être refaite, et non déclarée compatible par son seul nom de version.

## 3. Corrections et contrats de preuve

### 3.1 Corps vectoriel absent de la couche texte

La sonde initiale autorisée de D01 p0 a trouvé 694 glyphes natifs, 195 chemins vectoriels et trois formes. Le texte natif utile au classement était concentré dans le pied de page, tandis que le corps visible était représenté par des chemins. Un nombre global de caractères suffisait auparavant à classer cette page native.

[`preflight.py`](../../services/ingestion/preflight.py) compare désormais les groupes de chemins de forme compatible avec du texte aux rectangles réellement observés dans la couche native. Les lignes fines et les grandes formes isolées ne suffisent pas à créer une région de texte. La mesure `text_layer_overlap` est l'aire de l'intersection avec l'union des rectangles natifs observés, rapportée à l'aire de la région ; elle n'est pas une constante ni une preuve portant sur des rectangles non inspectés.

Le résultat fournit des **candidats OCR**, pas une lecture des chemins. Le routeur porte la raison `uncovered_vector_body`. Si la région ne peut être traitée, notamment à cause du budget de rendu, l'adapter conserve le texte disponible et une région non résolue explicite. Cette voie n'autorise pas l'interprétation d'un graphique.

### 3.2 Colonnes, cellules vides et sous-lignes

[`table_geometry.py`](../../services/ingestion/table_geometry.py) conserve le tableau initial dans `parser_table_data` et produit, lorsque les observations le permettent, un `table_data` reconstruit. Les indices de colonnes du parseur ne suffisent pas à prouver un rôle MIN/TYP/MAX. Les ancrages d'en-tête, leurs libellés complets et les positions des valeurs déterminent les liaisons.

Les règles appliquées sont les suivantes :

- Une case vide reste vide ; aucune valeur typique n'est transférée dans une colonne minimale absente.
- Une formule traversant plusieurs colonnes reste fusionnée, sans recevoir le rôle de la colonne située sous son centre.
- Plusieurs valeurs d'une cellule fusionnée sont séparées seulement si leurs sous-lignes se correspondent géométriquement. Une condition ou une unité décalée n'est pas associée à une valeur par simple ordre de liste.
- Une condition commune est conservée comme dépendance vers son occurrence source exacte, avec ligne, colonne, offsets et identifiants d'observations. L'aval contrôle aussi la qualité de sa cellule d'origine.
- Un qualificatif ou une marque dans un en-tête n'est ni effacé ni assimilé à un trait de grille. Un rattachement unique à une cellule géométrique permet de conserver, par exemple, le libellé OCR `| PARAMETER`. Une marque incertaine rend ses liaisons incertaines.
- La frontière utilise tout le libellé vérifié. Le seul mot CONDITIONS décalait auparavant le début de `TEST CONDITIONS` et détachait une partie de la condition. Le même défaut pouvait placer le début d'une durée dans la colonne précédant `CONVERSION TIME`.

La grammaire des codes indexés exige une famille explicite de préfixe commun et d'indices contigus, ainsi qu'un en-tête de temps/durée. Les suffixes de registre restent des mots sources. Aucune valeur attendue du corpus ne sélectionne une colonne, un code ou une conversion.

`table_quality` conserve le hash source, la page, le cadre, les observations, les liaisons, les dépendances et les hashes de projection. `validate_table_quality` reconstruit l'ensemble depuis les métadonnées rechargées par l'API et vérifie le texte sérialisé. Une propriété `supported` transmise par le retrieval ne fait pas autorité. Une preuve absente, altérée, trop volumineuse ou non reconstructible reste indisponible.

### 3.3 Glyphes natifs et conditions générales

La collecte native utilise les vrais indices PDFium avec le code Unicode, la boîte de caractère, les indicateurs de caractère généré et d'erreur de mapping, ainsi que le mode de rendu. Les indices PDFium ne sont jamais assimilés à des offsets Python. Les handles natifs sont fermés explicitement et la collecte est faite sous le verrou PDFium existant.

La projection des bandes de conditions peut corriger une duplication du parseur seulement en réassemblant les glyphes effectivement acquis. Le texte du parseur reste dans `parser_original_text`, avec la preuve et les hashes d'entrée/sortie. Une observation incertaine conserve le texte initial avec une preuve indisponible ; il n'existe pas de règle de remplacement d'un signe ou d'une valeur attendue.

`table_general_conditions` établit une liaison géométrique bornée entre le tableau et des fragments de la même page. Le bandeau doit présenter un titre explicite de caractéristiques/conditions, une affectation et une réserve telle que « unless otherwise… ». Une simple proximité ne suffit pas ; un tableau interposé empêche l'héritage. Les fragments conservent leur texte entier, leur boîte, leurs offsets, leur hash et leur révision.

L'état `supported` de ce contrat signifie **liaison géométrique établie** ; la qualité de lecture des fragments et leur scope restent des contrôles distincts. Un état `absent` signifie qu'aucun bandeau explicite n'a été établi par cette méthode, pas que le document ne contient aucune condition. Un témoin déclaré dont une pièce manque ne devient pas `absent`.

[`table_conditions.py`](../../services/api/table_conditions.py) recharge les blocs autorisés, la génération, la version et la géométrie depuis SQLite. La version propre à l'extraction reste distincte de la version DB créée lors d'un réimport ; les citations publiques utilisent l'identité DB effectivement autorisée. Les dépendances doivent entrer entièrement dans le budget de contexte.

Pour un bandeau parent placé dans un tableau, la portée vient des en-têtes inclus dans son rectangle source, jamais du seul `colspan`. Les tests aval vérifient qu'un bandeau limité à PARAMETER ne qualifie pas des valeurs situées hors de cette portée.

### 3.4 OCR : accord borné et localisation des incertitudes

[`ocr_verification.py`](../../services/ingestion/ocr_verification.py) conserve la lecture principale et une lecture complémentaire réelle, avec les hashes des rasters, les crops, les boîtes, les paramètres et le budget utilisé. La segmentation complémentaire est PSM 6 ; le facteur est 1 ou 2 selon la taille observée. Aucun désaccord n'entraîne une substitution du texte.

[`source_quality.py`](../../services/ingestion/source_quality.py) reconstruit l'accord par identité littérale, recouvrement géométrique réciproque et confiance minimale. L'appariement doit être bijectif : un mot supplémentaire dans la deuxième lecture, pouvant être une négation ou une réserve, maintient l'incertitude. Deux lectures qui donnent la même erreur restent une limite de méthode, pas une garantie sémantique.

Le contrôle raster des nombres commençant par `+` recherche une croix isolée ou une barre inférieure supplémentaire. Il peut refuser une lecture ; il ne produit jamais `±` à la place de `+` et ne prétend pas reconnaître toutes les formes typographiques.

Pour le texte courant, l'alignement ordonné des occurrences répétées exige une égalité de la **séquence complète** des mots avec le texte enregistré. Les boîtes PDF sont ramenées au repère d'affichage par l'inverse commun de [`geometry.py`](../../services/ingestion/geometry.py). Une ambiguïté de ligne, un chevauchement relatif ou une rupture horizontale compatible avec des colonnes interdit cette voie ; le comptage conservateur des occurrences reste alors utilisé. Les tableaux gardent leur traitement distinct.

L'adapter passe `page=page` à `block_quality`. Le témoin garde `page_frame` ; la revalidation aval compare ce cadre à celui rechargé depuis la DB. Une relecture documentaire a confirmé la cohérence CropBox/effective_box, rotation et dimensions affichées. Les deux défauts relevés pendant la revue — colonnes répétant les mêmes mots et petites boîtes dupliquées tolérées par un seuil absolu — sont traités dans le code courant. Cette inspection ne remplace pas les tests de moteur ou la qualification finale.

### 3.5 Valeur simple et repère local d'un tableau tourné

Les intégrations OCR historiques ont révélé une famille de tableaux légitimes que la première grammaire I5 refusait : un libellé, une valeur et une unité, avec trois en-têtes explicites en français ou en anglais. La nouvelle branche reconnaît cette bande géométrique seulement si chacun des trois rôles est unique et observé sur la même ligne. Des colonnes permutées restent liées par leurs positions ; deux colonnes de valeur, un rôle absent, un chevauchement ou un autre rôle statistique rendent cette branche indisponible. `Value` et `Valeur` conservent leur sens littéral : ils n'établissent ni minimum, ni maximum, ni valeur typique ou nominale. Les 26 nouveaux tests de cette famille ont été exécutés avec les régressions de géométrie ; leur résultat figure au §5.5.

Une seconde cause, distincte, concerne un tableau localement tourné de 90° dans une page dont la rotation PDF vaut zéro. Le parseur avait déjà ramené ses cellules au repère physique ; reconstruire ensuite les lignes dans le seul repère de page mélangeait les lignes et les colonnes. Le correctif sépare le repère de lecture du tableau et le repère physique de citation. Le témoin `table-reading-orientation-v1` doit relier une région OSD unique et résolue, les dimensions et hashes du prétraitement, la correction TableFormer réellement exécutée et les lectures OCR provenant du même raster. Le seul nombre `90` ne suffit pas. Les cellules reconstruites reviennent au repère physique avant leur exposition ; leur incertitude OCR est indépendante de cette transformation. Les 49 nouveaux cas purs couvrent les quatre rotations locales combinées aux quatre rotations de page, les métadonnées absentes ou contradictoires, les altérations de provenance et les autorités DB ; ils sont passés dans le lot de 112 tests décrit au §5.5. La qualification native du tableau tourné reste distincte.

La revue statique croisée a relevé une liaison manquante dans cette première implémentation : le hash OSD était seulement contrôlé comme une chaîne hexadécimale valide. Le producteur copie désormais ce hash réel dans le prétraitement et le validateur exige leur égalité. Les témoins tournés anciens qui n'ont pas cette liaison restent indisponibles ; la nouvelle exigence ne leur est pas ajoutée rétroactivement comme une preuve acquise. Les tests d'absence du lien et d'altération isolée du hash font partie du ciblé exécuté.

Le catalogue passe également au validateur le cadre de page et la boîte du bloc rechargés depuis SQLite. Une absence, une divergence géométrique ou un conflit de hash source bloque le témoin, même si celui-ci est cohérent avec lui-même. Une CropBox PDF non déclarée reste `None` ; la boîte effective réellement observée suffit au calcul du repère. Cette absence n'est pas remplacée par une CropBox inventée.

## 4. Budgets et comportement aux limites

Les plafonds globaux de pixels et la réserve mémoire du protocole ne sont pas augmentés. Les limites propres aux nouveaux témoins empêchent aussi une inspection ou une revalidation non bornée.

| Frontière | Limite constatée dans le code/configuration | Conséquence d'un dépassement |
|---|---|---|
| PDF | 200 Mio ; 2 000 pages | Refus explicite du document hors limite |
| Rendu | 8 000 000 pixels/page ; 13 000 000 pixels/région OCR | Route refusée ou repli conservant les régions non résolues |
| Préflight vectoriel | 4 096 observations ; 64 régions ; inspection des 256 premiers rectangles natifs | Limites tracées ; absence de certification d'une couverture non inspectée |
| Glyphes / table | 20 000 glyphes/page ; 6 000 glyphes/table ; 4 096 observations ou cellules | Tableau original conservé ; preuve indisponible |
| Témoin de table | 1 500 000 octets | Preuve indisponible, sans suppression silencieuse de dépendances |
| Conditions générales | 256 blocs inspectés ; 8 fragments ; 4 096 caractères | `general_condition_band_limit` ou autre indisponibilité explicite |
| Témoin OCR | 200 000 caractères ; 4 096 observations ; 256 lectures ; 256 tokens par lecture évaluée | Mots non vérifiés ou témoin indisponible |
| Reprises OCR | Pour chaque région, budget partagé de 32 appels entre reprise de ligne et vérification ; allocations cumulées imputées au plafond de région | `shared_retry_call_limit` / `shared_retry_pixel_limit` ; aucune reprise illimitée |
| Crop de vérification OCR | 4 096 × 256 pixels maximum après dérivation | Lecture complémentaire indisponible |
| Ressources application | Réserve hôte de 1 536 Mio ; une tâche lourde à la fois | Admission et libération contrôlées par le runtime existant |

Les lignes numériques sont examinées en priorité dans le budget de vérification OCR. Une ligne omise ne devient pas fiable par défaut. Les raisons de saturation font partie des preuves à analyser ; elles ne doivent pas être comptées comme amélioration de la qualité d'une réponse positive.

## 5. Résultats effectivement observés

### 5.1 Tests logiciels et régressions

| Étape | Résultat conservé | Nature de la preuve |
|---|---|---|
| Rouge générique initial | 9 FAIL, 0,29 s — `ingestion-generic-red.log` | Reproduction des défauts de géométrie/couverture avant correction |
| Première intégration | 57 PASS — `ingestion-targeted-1.log` | Tests purs et régressions ciblées |
| Mesure d'intersection et bornage | 61 PASS — `ingestion-targeted-2.log` | Tests ciblés, sans nouveau moteur |
| Conditions générales et glyphes | 70 PASS, 0,79 s — `ingestion-targeted-conditions-3.log` | Témoins synthétiques et intégration de l'adapter |
| En-têtes supplémentaires | 73 PASS, 0,63 s — `ingestion-targeted-conditions-4.log` | Inclut conservation et incertitude des marques |
| Codes/durées et frontières | 84 PASS / 1 FAIL, 2,23 s — `ingestion-targeted-mapping-1.log` | 82 tests ingestion réussis, deux régressions de contrat réussies ; conversion encore partielle à cette étape |
| Intégration aval suivante | 401 PASS, 11,78 s — `grounding-candidate-fifth.log` | Positifs historiques et contrôles catalogue/contrat, dont conversion, portée et condition commune |
| Correction du signe après diagnostic 3 | 124 PASS, 4,39 s — `sign-correction-1.log` | Signe, qualité source et contexte OCR ; sept nouveaux cas synthétiques de signe ; aucune nouvelle reconnaissance dans cette suite |
| Famille libellé/valeur/unité | 63 PASS, 29,17 s — `single-value-candidate-1.log` | 26 nouveaux cas génériques avec les régressions de géométrie |
| Repère local et autorités externes | 112 PASS, 0,84 s — `orientation-candidate-2.log` | 49 nouveaux cas purs, aucune reconnaissance ; reprise après correction de la garde CropBox absente |
| Autorités SQLite et valeur simple aval | 41 PASS, 3,24 s — `orientation-api-1.log` | Rechargement DB, refus des altérations de cadre/bbox et absence de rôle statistique inventé |
| Intégrations OCR historiques, campagne 3 | 8 PASS, 0 FAIL, 0 SKIP, 216,38 s — `ocr-candidate-3.log` | Vrais workers PDFium/Docling/Tesseract, assertions historiques intactes ; quatre avertissements de format JUnit, détaillés au §5.6 |

L'échec de conversion du passage précédent a été conservé : la table contenait déjà 16 liaisons géométriques soutenues. Le correctif aval empêche les en-têtes de bits de devenir des identifiants de composants ; les assertions positives historiques restent conservées. Les totaux des suites se recoupent et ne doivent pas être additionnés.

Ruff et Mypy ont réussi sur les trois modules du lot ingestion (`ingestion-ruff-mapping-1.log`, `ingestion-mypy-mapping-1.log`). L'intégration aval suivante dispose également de ses résultats Ruff/Mypy (`grounding-ruff-2.log`, `grounding-mypy-2.log`). Cela ne constitue pas encore le passage de toute la suite portable sur le candidat final.

Deux tentatives intermédiaires n'ont exécuté aucun test : mauvais noms de fichiers historiques, puis appel direct à pytest sans import du répertoire projet. Les journaux `ingestion-targeted-conditions-1.log` et `-2.log` restent conservés. La reprise valide utilise `python -m pytest` ; ces tentatives ne sont ni des PASS ni des régressions produit.

### 5.2 Nouvelles extractions réelles de développement

La sonde initiale, sans rendu, a duré 0,124 s pour D01 p0/p1 et D03 p2. Son reçu `native-geometry-probe-receipt.json` a pour SHA-256 `9635ef2588070afd598c2bdf43ff9a16efc52ac88e3afa455ade40acdfe89c18`. Elle ne recueillait pas encore les indicateurs generated/map-error ; les premières projections sur cette sonde demeurent donc partielles, sans certification rétroactive.

| Témoin de développement | Constat avant correction | Observation sur les pilotes natifs |
|---|---|---|
| D01 p0 / H02 | Le pied natif masque l'absence du corps vectoriel | 41 blocs récupérés dans le premier pilote ; le passage utile sur les fonctions de conditionnement est présent. Dans le second pilote, son témoin OCR est corroboré après correction de la correspondance des mots. |
| D01 p1 / H01–H03 | Fusion de colonnes et attribution d'une valeur typique à Min | 57 liaisons `supported` ; Min vide préservé. Le second pilote conserve le bandeau général, avec son texte natif reconstruit et ses réserves. |
| D03 p2 / H07 | Valeurs, unités et conditions de deux sous-lignes fusionnées | 119 liaisons `supported` ; deux sous-lignes distinctes et dépendance commune `COUT = 100pF` avec occurrence source. Le second pilote rattache quatre fragments du bandeau général. |
| SCAN1 | Des mots et unités supplémentaires peuvent être erronés malgré une confiance élevée | Le bloc complet reste incertain. La localisation ultérieure d'un passage utile est évaluée par rejeu pur ci-dessous, sans nouvelle OCR ni succès final revendiqué. |
| SCAN2 | En-tête contenant une barre supplémentaire, sous-lignes fusionnées, unités/conditions altérées | Première projection indisponible ; deuxième pilote partiel avec 114 liaisons. Certaines unités et conditions demeurent incertaines ; le bandeau général dépasse la limite de fragments. |

Les documents, révisions et hashes du corpus de développement sont ceux du [manifeste I4](production-i4-corpus/sources.json). Les deux scans ont les dérivations enregistrées dans [scan-transformations.json](production-i4-corpus/scan-transformations.json). Les indices ci-dessus sont des indices physiques à partir de zéro.

### 5.3 Rejeux purs et ablation

Le rejeu `ingestion-development-snapshot2-witness-replay-1.json`, en 0,624 s, revalide exactement D01 p1 et D03 p2 avec le code alors courant : tables et conditions générales soutenues. Il refuse l'ancien témoin SCAN2 après modification de la frontière complète d'en-tête (`table_quality_replay_mismatch`). La nouvelle projection pure sépare trois libellés auparavant fusionnés avec leur symbole, conserve les barres littérales et contient 117 liaisons, toujours partielles. Ce résultat exige une réextraction ; il ne constitue pas une mise à jour autoritaire des anciennes citations.

L'ablation `quality-order-ablation.json` compare les mêmes observations réelles avec `source_quality.py` avant/après alignement ordonné :

- Module avant : `0c896bc194db6a9482150a0754102d2c53c33d60f18488f87d6aa11d4196ec83` ; module après : `bd4adb7a4f50375db67d08f35b7de9fc42d0ddf604e63ae327fe5522ecba1464`.
- 55 blocs examinés ; 51 permettent une séquence géométrique intégrale exacte.
- 33 blocs restent corroborés et 22 restent incertains : aucun bloc entier n'est rendu artificiellement fiable.
- Le passage utile de D01, offsets `[0, 175)`, reste corroboré.
- Dans SCAN1, le passage d'alimentation, offsets `[0, 73)`, passe d'incertain à corroboré ; le bloc demeure incertain. L'incertitude d'une autre occurrence du même mot n'est plus imputée à cette occurrence lorsqu'une séquence géométrique intégrale la localise.

Cette ablation ne change ni les pixels, ni les lectures, ni les valeurs du texte. Elle mesure une localisation de preuve, pas une nouvelle reconnaissance, une citation finale validée ou une hausse du taux de réponses correctes.

### 5.4 Diagnostic 3 : documents complets et comparaison aux pilotes

Les extractions complètes sont conservées dans `development-transfer-candidate-3`, `development-ocr-candidate-3` et `development-ti-candidate-3`, sous le répertoire QA I5. La présente revue lit leurs enveloppes, témoins et reçus, puis compare les JSON correspondants de diagnostic 2. Elle n'exécute ni nouvelle reconnaissance, ni nouvelle revalidation produit, ni réponse RAG. Le fingerprint d'extraction enregistré est `0049a9f7eaff24e964778a1332ef4baa11eac01ece7db729896c28f0f29a71eb`.

| Cas de développement | Comparaison des observations 2→3 | Portée et limite |
|---|---|---|
| H01, D01 p1 | Texte et `table_data` identiques ; 57/57 liaisons `supported` ; même fragment général avec `TA`, plage `VS` et réserve explicite | La géométrie retrouvée dans la fenêtre reste présente dans l'extraction complète ; passage au catalogue et rendu final non exécutés par cette revue |
| H02, D01 p0 | 41 blocs ; route `uncovered_vector_body` ; passage de conditionnement de 175 caractères inchangé, avec 24 intervalles corroborés | Hash du passage `3638470f466547dc7510836254cfc9ebdc30bceddec629363659617532b46566` ; `page_frame` désormais conservé ; la correspondance locale ne certifie pas tous les blocs de la page |
| H03, D01 p1 | Ligne `Nonlinearity` conservée : colonne Typ `0.1`, Max `0.5`, unité `% FS1`, aucune cellule Min ; mêmes conditions de température dans le libellé | La projection ne décale pas une valeur vers la colonne vide. L'usage de l'unité et de ses renvois doit encore être vérifié dans la réponse |
| H07, D03 p2 | Texte et `table_data` identiques ; 119/119 liaisons `supported` ; deux sous-lignes distinctes ; dépendance `COUT = 100pF` de la ligne 15 vers la ligne 16, occurrence `[0,12)` en colonne 2 ; quatre fragments généraux inchangés | Les marqueurs encodés `l` restent littéraux ; la liaison et la lecture ne prouvent pas leur apparence visuelle |
| SCAN1, alimentation | Même texte de 289 caractères, hash `2bcbd32f4a2710c59ef53b0aef41046130a44b30cc6a302698b6dba17cef9073` ; la plage `[0,73)` passe de 14 intervalles corroborés et 1 incertain à 15 corroborés | La localisation obtenue par le rejeu pur est retrouvée lors d'une nouvelle extraction. Le bloc entier reste incertain ; la puissance transcrite `230 HW` demeure hors de cette plage et ne doit pas être ajoutée |
| SCAN2, tableau | 114→117 liaisons après séparation de libellés ; 9 soutenues dans les deux extractions, 105→108 ambiguës ; dépendance littérale `Cour = 100pF` conservée ; conditions générales toujours indisponibles (`general_condition_band_limit`) | Plus de cellules distinctes ne signifie pas plus de faits utilisables. Les unités `us`/`ys`, le symbole de condition et les signes incertains ne sont pas corrigés par une valeur attendue |

Les indices de pages, lignes et colonnes de ce tableau partent de zéro. Les états `supported` sont les états enregistrés des liaisons géométriques, pas un score de justesse de réponses finales.

#### Couverture complète du traitement, exploitation encore partielle

Les sept workers ont traité leurs 125 pages et déclarent `parser_complete: true`. Les sept documents terminent néanmoins `ready_partial` : 113 pages contiennent au moins une région non résolue, pour 3 284 entrées de régions non résolues. Ces entrées peuvent se recouvrir ; elles ne constituent pas un décompte de faits distincts perdus.

| Document | Pages traitées / total | Pages avec région non résolue | Entrées de régions non résolues | Tables `supported` / `partial` / `unavailable` |
|---|---:|---:|---:|---:|
| D01 | 7 / 7 | 6 | 131 | 1 / 0 / 5 |
| D02 | 11 / 11 | 8 | 249 | 0 / 0 / 5 |
| D03 | 14 / 14 | 12 | 610 | 2 / 0 / 2 |
| SCAN1 | 1 / 1 | 1 | 4 | 0 / 0 / 0 |
| SCAN2 | 1 / 1 | 1 | 3 | 0 / 1 / 0 |
| INA226 | 41 / 41 | 38 | 1 041 | 1 / 0 / 36 |
| TMP117 | 50 / 50 | 47 | 1 246 | 2 / 0 / 37 |

Sur 92 blocs de table, 6 sont soutenus, 1 partiel et 85 indisponibles. Les raisons enregistrées des 85 indisponibilités sont `explicit_numeric_headers_missing` (81), `table_observations_outside_row_geometry` (3) et `header_extra_text_ambiguous` (1). Ce comptage couvre aussi des familles hors grammaire actuelle : il ne mesure ni un taux de refus aux questions, ni un taux d'erreur. Les nombreux avertissements `OCR_ORIENTATION_UNRESOLVED`, les régions graphiques non interprétées et les limites d'isolation demeurent visibles ; un retour worker 0 ne les efface pas.

#### Budgets et contre-exemple de signe dans SCAN1

Chaque scan constitue une région OCR unique. Les traces de vérification enregistrent :

| Scan | Appels complémentaires / plafond | Pixels cumulés / plafond de région | Lectures corroborées / incertaines / indisponibles |
|---|---:|---:|---:|
| SCAN1 | 32 / 32 | 5 754 040 / 13 000 000 | 27 / 5 / 11 |
| SCAN2 | 32 / 32 | 10 343 118 / 13 000 000 | 7 / 25 / 2 |

Les 11 lectures indisponibles de SCAN1 et les 2 de SCAN2 portent `shared_retry_call_limit`. Aucun relèvement des plafonds n'est effectué pour cette revue. Le plafond de 32 vaut par région : sur D01 p0, cinq régions vérifiées consomment respectivement 8, 21, 16, 10 et 1 appels, soit 56 au total. Confondre plafond régional et plafond par page sous-estimerait ce coût.

Un contre-exemple concret interdit d'assimiler l'accord OCR à une certification : dans diagnostic 3, le bloc SCAN1 `8667c17a-fc1e-5f3f-8b70-ac405bf8b3d9` contient `+2.0°C maximum ambient setpoint accuracy`, avec `state: corroborated` et aucune raison d'incertitude. La lecture `region-0-line-0` donne `+2.0°C` dans les deux segmentations, avec des confiances de 0,90590012 et 0,92010864 ; l'ancien contrôle du signe renvoie `cross_only`. L'extraction native de D02 p0, parent de SCAN1 selon la dérivation I4 enregistrée, conserve `±2.0 ° C` à cet emplacement. La revue visuelle du PNG I4, puis celle du crop reconstruit décrit ci-dessous, confirment que la barre inférieure est présente. C'est un défaut réel d'admission de la qualité source, signalé avant gel final. Les observations de diagnostic 3 restent intactes. Le rapport ne prétend pas qu'une réponse finale fautive a été publiée : cette caractéristique n'est pas la plage d'alimentation demandée dans le cas SCAN1 courant.

La trace localise le mot en coordonnées PDF `[54.333333333333336, 620, 80, 626.3333333333334]`. Le raster de vérification mesure 1 836 × 2 376 pixels, hash des pixels `83eccb5e54f2e80ba26a9558f95b4f18be5d75306d9bcb0a336c665775e4d99e`. Le crop de ligne `[160,493,692,524]`, avec bord 10 et facteur 2 LANCZOS, produit 1 104 × 102 pixels, hash `052e7c650bbf5e9908ea4bdab7942b71947d04f612b05310d80c25710d263953`. Le crop propre au signe représente 999 pixels. Les fichiers temporaires de reconnaissance sont supprimés par le runtime ; leurs images ne sont pas présentées comme conservées. Le PNG original de la dérivation I4 reste disponible dans `production-i4-20261108/heldout-materialized-offline/scans/SCAN1.png`, hash fichier `c75628dc8b72219d9290b707112758e103f13d4171649c8ed57c45c811205538`, à une résolution distincte de 1 700 × 2 200. Il permet une revue sans nouvelle extraction du corpus réservé.

#### Correction générique et ablation sur le raster exact

Le plan du contre-exemple, `sign-counterexample-plan.json`, est enregistré à 22:16:29 UTC, avant la correction : barre séparée, épaisse ou connectée refusée, plus simple conservé si le glyphe et sa marge inférieure sont entièrement visibles, crop tronqué refusé, ancienne attestation de signe non promue, effet réel à mesurer séparément sur les occurrences utiles.

Le correctif recherche des bandes horizontales disjointes dans les colonnes de la croix. Il peut ainsi voir une barre inférieure rattachée à la même composante de pixels, cas que l'ancien parcours des seules composantes distinctes pouvait manquer. Le texte reconnu reste littéral. La revalidation exige maintenant `visual_sign_policy: leading-plus-raster-v2` et `visual_sign_check: cross_only` pour un token commençant par `+` ; une ancienne attestation sans cette politique reçoit `leading_plus_shape_unverified`. Elle n'est pas rendue compatible en modifiant rétrospectivement son témoin.

L'ablation `sign-shape-native-ablation.json` reconstruit le raster depuis le PDF dérivé avec PDFium 5.13, échelle 4,5, crop `(0, .01, .01, 0)`, puis redimensionnement Pillow à 1 836 × 2 376. Le hash des pixels obtenu est **identique** au `source_raster_sha256` conservé par l'extraction 3. Les deux versions du contrôle sont ensuite appliquées aux mêmes pixels et aux mêmes coordonnées de tokens déjà observées :

| Texte OCR conservé | Boîte du token dans le raster, valeurs arrondies pour lecture | Ancien contrôle | Nouveau contrôle |
|---|---|---|---|
| `+2.0°C` | `[163,497,240,516]` | `cross_only` | `additional_lower_bar` |
| `+150°C`, première occurrence | `[578,605,662,624]` | `cross_only` | `cross_only` |
| `+150°C`, seconde occurrence | `[802,1096,886,1115]` | `cross_only` | `cross_only` |

Le reçu conserve les coordonnées flottantes exactes, `new_ocr_calls: 0` et `text_replaced: false`. Son SHA-256 est `3c9e669813280d503e6b75e310dff126e8259e9fdf301ffcd8ed78ba8569fc2b`. L'image d'inspection privée `scan1-sign-native-exact.png`, SHA fichier `040d6ca8f28c844941a472c66c0809a45628877d536ecb8593d2a42a47e5dd28`, montre la barre inférieure. Les modules après correction sont `ocr_verification.py` (`b053ee9d0f7230086689da4c552ad29885eb218204edda9fd8dd9af93176b670`) et `source_quality.py` (`b22bccee88bf060fcdc21700ffb8e662832ffd6ee00a4f4daa36ea6d9ba3326f`), donc postérieurs à la copie 3.

Cette ablation démontre la discrimination du contrôle sur ces trois occurrences réelles, dont les deux plus simples conservés. Elle ne constitue pas une nouvelle OCR, une réextraction complète, un score général de reconnaissance des signes ou une vérification du rendu final. Le cas incorrect doit devenir inutilisable pour une affirmation ; il n'est jamais remplacé par `±2.0°C` dans le texte produit. Les 124 tests ciblés passent en 4,39 s, dont sept nouveaux cas synthétiques, mais une extraction fraîche sous diagnostic 4 et les réponses de développement restent à examiner séparément.

### 5.5 Régressions natives historiques : valeur simple et rotation locale

La première exécution des huit tests de `tests/integration/test_ingestion_ocr.py` sur le candidat a produit **5 FAIL / 3 PASS en 196,68 s**, reçus `ocr-candidate.log` et `ocr-candidate.xml`. Les assertions historiques n'ont pas été modifiées : elles exigent notamment un état `ready`, les cellules exactes et la conservation des rectangles de provenance. Les échecs portent sur le tableau mixte, les deux orientations du scan français, la continuation d'un tableau entre les pages 4 et 5, et le document scanné de cinq pages. Les refus `TABLE_RELATION_QUALITY_UNCERTAIN` révèlent une régression d'utilité ; ils ne sont pas crédités comme réussite de fidélité.

La grammaire de valeur simple a ensuite été vérifiée avec les régressions pertinentes : **63 PASS en 29,17 s**, dont 26 nouveaux cas, dans `single-value-candidate-1.log` et son JUnit. Ruff est passé dans `single-value-ruff-1.log`. La première commande Mypy, conservée dans `single-value-mypy-1.log`, a signalé une annotation manquante dans le module OCR importé ; elle ne constitue pas un passage vert de Mypy sur le lot final.

Le premier rejeu pur, `single-value-recorded-ocr-replay-1.json`, a relu les observations des mêmes extractions sans PDF ni OCR. Il a notamment reconstruit les cinq tables du document scanné et celle du cas mixte avec leur texte exact. Son enveloppe avait deux défauts : elle parcourait aussi les liens `current` de pytest, comptant deux fois certains fichiers, et exigeait abusivement `supported` pour un cas historique qui vérifie seulement les douze textes et leur provenance. Ce cas contient de vrais désaccords OCR entre `0` et `O` ; il doit rester partiel. Le reçu est conservé comme tentative, sans attribuer ses doublons au nombre de documents ni transformer ce refus en régression produit.

Le scan localement tourné conserve un défaut géométrique distinct et une unité concordante dont la confiance complémentaire est insuffisante. Le premier est traité par le témoin de repère local décrit au §3.5. Pour la seconde, une ablation séparée a exécuté quatre conditions fixées sur le raster exact déjà observé, sans changer les valeurs attendues : facteur 2/PSM 6, facteur 1/PSM 6, puis les mêmes facteurs avec PSM 7. Le hash du raster source est `e2fccdd395fd43a4fb3747d5012cadfb0e46a5396563d42599ae7bed48cb8edb`. La lecture `°C` reste identique ; la confiance est 0,75387695 avec le facteur 2 et 0,94908302 avec le facteur 1, sans effet supplémentaire de PSM 7. Le reçu `degree-confidence-ablation.json` conserve les quatre sorties et leurs hashes. Cette mesure motive une reprise bornée à évaluer ; elle n'autorise pas à baisser le seuil de 0,8, à ignorer un désaccord textuel ou à déclarer les huit intégrations réussies avant leur nouvelle exécution.

Le ciblé du repère local a d'abord produit 110 PASS en 1,70 s (`orientation-candidate-1.log`). Le rejeu dédupliqué suivant a exposé une garde trop stricte : elle refusait les pages sans CropBox explicite malgré leur boîte effective valide. Cette tentative rouge est conservée dans `single-value-recorded-ocr-replay-2.json`. Après correction et deux tests discriminants supplémentaires, le ciblé passe à **112 PASS en 0,84 s**, Ruff et Mypy passent sur les trois modules concernés (`orientation-ruff-2.log`, `orientation-mypy-2.log`). Le raccord DB passe ses **41 tests en 3,24 s** ; les anciennes assertions positives ne sont pas assouplies.

Le troisième rejeu pur, `single-value-recorded-ocr-replay-3.json`, porte sur **sept résultats de workers distincts et onze tableaux**, après résolution des liens pytest : sept tableaux sont `supported` et revalidés, le tableau aux identifiants `0`/`O` discordants reste `partial`, le tableau tourné ancien reste indisponible faute de liaison OSD enregistrée, et les deux tableaux natifs ne sont pas rejoués faute de glyphes conservés dans leur ancien témoin indisponible. Les huit projections exécutables conservent exactement le texte du tableau. Il n'y a aucun nouvel appel PDF/OCR et aucun fichier source modifié. Le verdict du helper est conforme à cette portée ; il ne vaut pas nouvelle extraction.

La nouvelle campagne native `ocr-candidate-2` a démarré le 8 novembre à **22:49:33 UTC**, après gel de 21 fichiers d'entrée/code, dans un nouveau dossier temporaire et avec le recontrôle OCR non agrandi développé séparément. Elle a été **interrompue par perte de session d'exécution** : le 22:56:07 UTC, le handle de processus n'est plus disponible ; le journal ne contient qu'un point, aucun résultat de worker ni JUnit n'existe, et le dernier événement est `page_load`. Aucun défaut produit, verdict OCR ou coût complet ne peut être attribué à cette tentative. Les reçus `ocr-candidate-2-inputs.json` et `ocr-candidate-2-session-loss.json` la conservent séparément de la première campagne.

À **22:57:03 UTC**, une sonde non destructive acquiert immédiatement le verrou existant `.ingestion.lock` avec `flock(LOCK_EX|LOCK_NB)`, puis le relâche ; son contenu et les 21 fichiers gelés sont inchangés (`ocr-candidate-2-lock-probe.json`). Ce constat autorise la restitution du créneau de ressources, avec une réserve explicite : **aucun reçu terminal d'arrêt de processus n'a pu être récolté**. Aucun essai identique n'a été relancé par le lot ingestion. Cette tentative ne démontre pas la non-régression native ; l'intégration a ensuite mené et récolté la campagne distincte ci-dessous.

### 5.6 Huit intégrations OCR historiques : nouvelle campagne complète

La campagne `ocr-candidate-3`, démarrée par l'intégration à **22:57:13 UTC**, réussit **8 PASS, 0 FAIL, 0 ERROR, 0 SKIP en 216,38 s** selon la sortie pytest. Le JUnit enregistre 216,369 s. Les quatre avertissements concernent l'utilisation de `record_property` avec le format `xunit2` ; ils ne sont ni des tests ignorés ni des erreurs OCR. Les assertions historiques d'état, de cellules exactes, de provenance physique, de continuation et de réutilisation du pipeline sont inchangées.

| Campagne sur le candidat | Résultat observé | Interprétation |
|---|---|---|
| OCR 1 | 5 FAIL / 3 PASS, 196,68 s | Régressions de géométrie et de famille de tableau démontrées ; reçu conservé |
| OCR 2 | Interrompue, sans résultat terminal | Perte du handle d'exécution ; aucun verdict produit ni coût OCR complet |
| OCR 3 | 8 PASS, 216,38 s ; quatre avertissements JUnit | Non-régression native acquise pour ces huit tests, après correction et nouvelle extraction |

La revue en lecture seule des résultats ne lance aucun moteur supplémentaire. Les sept workers ont produit **16 pages et onze tableaux** : dix tableaux `supported`, et un tableau `partial` conservant les désaccords d'identifiants `0`/`O`. Cinq documents sont `ready` ; les deux cas qui admettent explicitement une limite restent `ready_partial` : le tableau à identifiants discordants et le schéma sans orientation résolue. Le test de police constitue le huitième test, sans worker documentaire.

Le scan tourné de 90° est désormais `ready`, avec **douze liaisons sur douze soutenues**. La page garde sa rotation PDF à zéro, sa CropBox absente et sa boîte effective `[0, 0, 600, 800]`. Le témoin local porte la rotation 90° et le même hash OSD `e72f720c81ba3f6cee3fb24c792c131184c92322e40874d47d79de041699cc6e` dans l'orientation et le prétraitement. Les assertions historiques contrôlent les boîtes de chaque cellule dans la région physique attendue.

La relecture non agrandie de `°C` est effectivement exécutée et conservée dans le résultat : confiance principale **0,9462899**, premier candidat facteur 2 **0,75387695**, candidat facteur 1 **0,94908302**, seuil inchangé **0,8**. Les trois lectures gardent le même texte ; le candidat initial, ses coordonnées et son hash ne sont pas effacés. Les boîtes du candidat retenu concordent avec celles de la lecture principale. Le témoin `literal-agreement-unscaled-recheck-v1` indique `completed`. Pour cette région, le budget enregistre **sept appels de vérification, dont un recontrôle**, **1 133 868 pixels** cumulés, six lectures corroborées et aucune lecture omise ou incertaine ; les caps restent **32 appels / 13 000 000 pixels**. Ce résultat ne transforme pas l'accord du même moteur en certification sémantique générale.

Les SHA-256 conservés sont `60afbfa173be1245b087eb838c9a6c1175f6c742a4f62677a2c72b7002a67b0a` pour le JUnit, `979b7cde669451eb5b6b28a757791206f4cfcc1a5adf43fbbdae888f19eefca0` pour le journal et `38df80f970410c10fbaad0d2885b2d9bea36a6061b51fef8ec91197ee596f9eb` pour le reçu d'entrée. La revue détaillée `ocr-candidate-3-ingestion-review.json`, SHA-256 `79a1b5cd89468609c91ab4cd8a2afff4d2e062d604f8fe82bc6e4632d583c9cb`, relie chaque résultat de worker à son hash et conserve les observations du recontrôle.

La durée totale observée de la suite augmente de 19,70 s par rapport à la campagne 1. Une exécution par version, sans isolation des caches ni mesure mémoire spécifique à cette suite, ne permet pas d'attribuer cet écart à une modification particulière. Ces huit tests ne qualifient pas les futures réponses sur le corpus de développement ou de transfert, ni les performances sur les postes de production.

### 5.7 Diagnostic 4 : nouvelles extractions complètes D01/D02/D03

Les trois fichiers de `development-transfer-candidate-4` sont de **nouvelles extractions**, produites par les workers sous les identités de diagnostic 4. La revue compare leurs JSON achevés à ceux de diagnostic 3 ; elle n'exécute ni PDFium, ni OCR, ni rendu, ni nouveau rejeu des fonctions de preuve. Les trois hashes source sont identiques. Les 32 pages contiennent **2 244 blocs** dont les signatures complètes page/type/référence parseur/boîte/texte sont identiques aux extractions précédentes. Les identifiants de blocs et de révisions changent avec la nouvelle extraction ; ils ne sont pas assimilés aux anciennes références publiques.

| Cible de développement | Résultat de la comparaison 3 → 4 |
|---|---|
| D01 p0 / H02 | 41 blocs ; passage sur les fonctions de conditionnement conservé, 175 caractères, 24 observations, état `corroborated`, hash `3638470f466547dc7510836254cfc9ebdc30bceddec629363659617532b46566` |
| D01 p1 / H01–H03 | Tableau, 57 liaisons et bandeau général exacts ; la cellule `0.25` est `(row=9, column=2)` sous `Typ`, sans valeur inventée dans `Min` |
| D02 | 721 blocs aux mêmes textes/boîtes ; cinq tableaux toujours indisponibles, aucun gain de couverture de tableau revendiqué |
| D03 p2 / H07 | Tableau, 119 liaisons, une dépendance de condition commune et quatre fragments généraux identiques ; sous-lignes et conditions locales conservées |

Pour préciser la portée de H07, les indices suivants sont les indices canoniques, base zéro. La cellule `(15,2)` contient littéralement `COUT = 100pF Overdrive = 10mV` ; la valeur `(15,4)` sous `TYP` est `60`, avec `µs` en `(15,6)`. La cellule `(16,2)` contient seulement `Overdrive = 100mV` ; `(16,4)` vaut `50`, avec `µs` en `(16,6)`. Une unique dépendance `shared_condition` de `row_index=16` référence le fragment `[0,12)` de `(source_row=15, source_column=2)`, texte exact `COUT = 100pF`, depuis `source_parser_row=11`. Ses identifiants d'observation sont `n:g1010,g1011,g1012,g1013`, `n:g1015` et `n:g1017,g1018,g1019,g1020,g1021`. La condition commune reste donc directement présente pour la première valeur et explicitement référencée pour la seconde ; le texte source de la seconde cellule n'est pas enrichi artificiellement.

Le support géométrique enregistré conserve la structure déjà examinée sur l'original : la cellule CONDITIONS initiale de la ligne parseur 11 couvre les deux bandes, avec une boîte TOPLEFT `[226,85 ; 324,01 ; 354,36 ; 341,05]`. Le préfixe `COUT = 100pF` occupe `x=226,85–272,23` ; les deux affectations locales `Overdrive` commencent respectivement à `x=289,90686` et `x=289,90195`, sur deux bandes séparées de 10 points. Les valeurs et unités s'alignent sur leurs bandes ; les libellés reconstruits `tPD` et `Propagation Delay` ont une portée de deux lignes, 15–16. La dépendance résulte de cette structure commune et des affectations locales alignées de même clé, pas de la seule proximité d'une ligne. Cette comparaison ne constitue pas une nouvelle inspection visuelle de la page.

Les trois documents conservent leurs états `ready_partial`, avec trois tableaux `supported` et douze `unavailable` au total. Aucun état ou motif de qualité OCR de bloc ne change et aucun recontrôle non agrandi n'est déclenché. Les cinq observations commençant par `+` dans trois lectures de D01 restent `cross_only`, désormais avec la politique enregistrée `leading-plus-raster-v2`. Aucun texte, signe ou nombre n'est remplacé. Ces constats ne démontrent pas encore la réponse finale aux questions H01/H02/H03/H07.

Le reçu `preparation-receipt.json` du groupe a pour SHA-256 `36d655c1f4a1ffbe77dd6ea278cf4ffb671841cd0a068b17d4663546f3a7fec7`. Les trois workers terminent sans timeout, avec code 0, leader récupéré et groupe possédé vide ; `changed_source_files` est vide. La synthèse privée `development-transfer-4-ingestion-review.json`, SHA-256 `8019543104e0163c30fb5f872b1601eb7981a25171bc0821988d87e024b03fda`, conserve les hashes des six extractions comparées, les relations ciblées, les observations de signe et les coûts. Aucun document du transfert réservé I5 n'a été ouvert pour cette revue.

## 6. Coûts des extractions natives

### 6.1 Fenêtres de diagnostic 2

Les mesures suivantes viennent des trois `preparation-receipt.json` de diagnostic 2. RSS/PSS sont les pics de sommes échantillonnées du groupe de processus, exprimés en Mio (2²⁰ octets). Elles couvrent la préparation/extraction du worker, pas l'indexation, la recherche ou une génération 4B.

| Document | Fenêtre physique, base zéro | Temps (s) | RSS pic (Mio) | PSS pic (Mio) | Mémoire hôte disponible minimale (Mio) |
|---|---|---:|---:|---:|---:|
| D01 | 0–1 | 48,27 | 1 489,2 | 1 376,1 | 5 314,8 |
| D02 | 0 | 21,20 | 1 100,6 | 1 093,1 | 5 541,6 |
| D03 | 0–2 | 46,20 | 1 653,2 | 1 483,6 | 5 264,5 |
| SCAN1 | 0 | 36,90 | 1 274,5 | 1 266,9 | 5 479,7 |
| SCAN2 | 0 | 50,32 | 1 221,9 | 1 216,1 | 5 481,3 |
| INA226 | 0 | 24,56 | 1 088,5 | 1 082,6 | 5 535,7 |
| TMP117 | 0 | 35,53 | 1 080,1 | 1 074,2 | 5 494,4 |

Les sept reçus indiquent absence de timeout, retour 0, leader récupéré et groupe de processus possédé vide. Ces sorties ne prouvent pas une réponse correcte : les états d'incertitude de SCAN2 restent présents.

Les hashes des reçus de préparation de diagnostic 2 sont `b1ed84eb0042598728a6c9cb40953d58293625b4c97b55595da0a66f0bd41b16` pour D01/D02/D03, `8fe8f39b3c655a8c59b57bc7b145ed4259f426a2971cab6eeebefa3a67c8a530` pour les scans, et `9c5f0a6cefe07850e2cd738f90f48d91dfba1cc8432f519945c0fb7408b00f1e` pour TI.

Une observation par fenêtre, sans séparation complète des caches chauds/froids, ne permet ni percentile ni attribution causale de vitesse entre les deux pilotes. Aucune performance sur le PC D07 ou sur Windows n'est déduite de ces mesures. L'enveloppe diagnostique signale les pages omises avec `omitted_by_diagnostic_scope` ; ces omissions ne doivent être masquées ni interprétées comme un traitement complet du document.

### 6.2 Documents complets de diagnostic 3

Les coûts suivants proviennent directement des sept entrées des trois nouveaux `preparation-receipt.json`. Les temps sont affichés à la microseconde, sans leur attribuer une précision expérimentale supérieure à celle d'une mesure unique. Les pics RSS/PSS et le minimum de mémoire hôte disponible sont des valeurs échantillonnées, converties d'octets en Mio ; les nombres d'échantillons sont respectivement 148, 136, 210, 70, 87, 573 et 713 dans l'ordre du tableau.

| Document | Pages complètes | Temps (s) | RSS pic (Mio) | PSS pic (Mio) | Mémoire hôte disponible minimale (Mio) |
|---|---:|---:|---:|---:|---:|
| D01 | 7 | 76,139725 | 1 595,922 | 1 463,648 | 4 348,562 |
| D02 | 11 | 70,295422 | 1 876,348 | 1 723,176 | 3 995,562 |
| D03 | 14 | 109,659622 | 2 047,578 | 1 876,417 | 3 781,320 |
| SCAN1 | 1 | 36,193330 | 1 273,402 | 1 265,832 | 4 533,957 |
| SCAN2 | 1 | 44,766635 | 1 226,426 | 1 220,543 | 4 523,809 |
| INA226 | 41 | 301,536160 | 2 193,961 | 2 024,523 | 3 732,875 |
| TMP117 | 50 | 375,649824 | 2 135,215 | 1 890,949 | 3 903,332 |

La somme des sept durées enregistrées vaut 1 014,240719 s ; elle ne comprend pas les étapes ultérieures d'indexation, de recherche ou de génération. Les sept entrées indiquent `timeout: false`, `returncode: 0`, `leader_reaped: true`, `owned_group_empty: true` et aucun membre de groupe restant. Le plus grand pic RSS échantillonné est 2 300 534 784 octets et le plus grand pic PSS 2 122 866 688 octets, tous deux sur INA226. Il s'agit de mesures d'extraction sur cet hôte, sans extrapolation aux plateformes cibles ni qualification de latence d'une réponse.

Les SHA-256 des reçus de préparation sont :

- Transfert de développement : `04e7b15e80a9ebffc46ab0636a5d7ad76cc4c9d5ba8b6b6fc7371653233d6a7b`.
- Scans de développement : `d29c5f91a6398e380e2196668ef84c544d274832d0d297866d5f73efa38c9266`.
- Documents TI de développement : `1647ae26bbe69453ba55ea3be0167dc603827a194dd5507e8ec016775763fda4`.

Les deux scans gardent une portée d'une page dans les deux diagnostics ; les autres mesures portent désormais sur les documents entiers. Aucune accélération ou régression de vitesse n'est déduite d'une comparaison entre ces portées différentes. Une seule exécution, avec état des caches non isolé, ne fournit pas de percentile de performance.

### 6.3 Trois documents complets de diagnostic 4

La portée est cette fois identique à celle des trois documents correspondants de diagnostic 3. Les valeurs viennent des reçus de préparation ; les conversions en Mio et les écarts sont calculés depuis leurs octets et secondes enregistrés dans la synthèse privée du §5.7.

| Document | Pages | Temps 3 (s) | Temps 4 (s) | Écart observé (s) | RSS 4 pic (Mio) | PSS 4 pic (Mio) | Mémoire hôte disponible minimale (Mio) |
|---|---:|---:|---:|---:|---:|---:|---:|
| D01 | 7 | 76,139725 | 77,389095 | +1,249370 | 1 510,867 | 1 383,591 | 2 612,824 |
| D02 | 11 | 70,295422 | 79,348742 | +9,053321 | 1 805,645 | 1 705,248 | 2 242,625 |
| D03 | 14 | 109,659622 | 128,331101 | +18,671478 | 2 015,719 | 1 844,504 | 2 130,180 |

Les trois extractions totalisent 285,068938 s. Les pics et minima proviennent respectivement de 150, 153 et 244 échantillons. Les durées sont plus élevées lors de cette exécution ; l'état de l'hôte et des caches n'étant pas isolé, cet écart ne constitue pas une attribution causale à un changement particulier. La mémoire disponible minimale reste supérieure à la réserve de 1 536 Mio, mais ces mesures ne qualifient ni le poste D07 ni les plateformes de production. Aucun coût de recherche ou de génération n'est inclus.

### 6.4 Correctif de portée des en-têtes groupés : critères avant essai

La lecture des sorties de développement 4 révèle une limite distincte des valeurs : sur D01 page 1, le parseur fusionne le titre de groupe et `Typ` dans une cellule étroite. La projection littérale conserve bien les deux textes, mais le titre reste limité à la colonne `Typ`. Les lignes dont seules les bornes Min/Max sont renseignées perdent donc le sujet de ce groupe. L'ancienne image de contrôle I4 et la sonde PDFium sans rendu déjà enregistrée montrent un cadre commun aux trois sous-colonnes. La sonde ne contient toutefois que les types et boîtes d'objets : elle ne suffit pas à certifier les segments, leur matrice et leur peinture. Elle ne sera pas transformée rétroactivement en témoin complet.

Avant toute exécution du correctif, les critères sont les suivants. Un titre ne gagne une portée de groupe que si ses observations natives sont soutenues, qu'un rectangle fermé unique est reconstruit à partir de chemins PDF natifs enregistrés, et qu'il contient le titre ainsi qu'au moins deux sous-en-têtes explicites contigus. Le cadre doit exclure les lignes de données, les titres concurrents et toute séparation intérieure contradictoire. La position centrale, la typographie, un `col_span` du parseur ou une valeur voisine ne constituent pas cette preuve. Les coordonnées publiques restent celles du PDF physique ; la transformation vers le repère de lecture ne sert qu'à vérifier l'association.

La portée prouvée est structurelle : les deux sous-en-têtes peuvent inclure une unité, sans devenir deux rôles numériques. Le choix initial d'un cas Min/Typ/Max ne limite pas le test de cadre à cette famille. Ainsi deux cadres `Min/Typ` et `Max/Units` restent deux groupes distincts ; leur présence ne justifie pas de combiner la borne du premier avec celle du second sous un même composant. Les rôles et la satisfaction de chaque question demeurent contrôlés séparément dans le catalogue et le rendu. Cette précision est arrêtée avant les premiers essais de ce lot.

La capture prévue réutilise le handle PDFium déjà ouvert pour les glyphes. Elle borne préalablement le nombre d'objets à 4 096, les segments à 64 par chemin et 4 096 par page, puis la projection à 256 traits et 256 obstructions. Les segments, matrices, états d'activation, couleurs RGBA, épaisseurs, modes de dessin et informations de clipping disponibles sont conservés une seule fois par tableau, après restriction à sa région. Les bindings ne dupliquent pas ces observations : ils référencent les IDs des côtés et des textes. Une limite atteinte, un objet non résolu recouvrant le cadre, une transparence ou un clipping non démontré empêchent l'extension. Les seuls traits admissibles sont des segments rectilignes axiaux après matrice, peints de façon opaque et sombre, d'épaisseur positive au plus 2 points ; un rectangle plein étroit peut représenter un trait si ses quatre segments le prouvent. Les tolérances sont de 0,05 point pour l'axe et de 1 point pour la jonction de côtés. Cette preuve structurelle n'est pas une attestation générale de visibilité de tous les pixels du document.

Les tests prévus discriminent : cadre fermé, côté manquant, autre cadre adjacent, séparateur intérieur, titres concurrents, deux groupes distincts, portée verticale englobant une ligne de données, matrice/rotation, peinture/clipping inconnu, limites de capture et altération du témoin après catalogue. Un test aval doit conserver le sujet sur Min/Max lorsque Typ est vide, sans hériter du sujet d'un groupe voisin. Les assertions antérieures restent inchangées. Les anciens témoins dépourvus de traits ne reçoivent aucune extension ; une nouvelle extraction et un nouveau gel de code sont nécessaires. À la rédaction de cette section, il s'agit de critères fixés avant le correctif et ses essais, pas de résultats exécutés.

Les contrats consultés sont les headers officiels PDFium `fpdf_edit.h` et `fpdf_transformpage.h`, confrontés aux bindings installés pypdfium2 5.13.0, ainsi que les implémentations officielles `fpdf_editpath.cpp` (points locaux et matrice séparée) et `fpdf_transformpage.cpp` (handle de clipping emprunté). Une référence de clipping absente est distinguée d'un appel échoué ; aucun handle d'objet appartenant à la page n'est détruit par la capture.

Le correctif est maintenant écrit dans `services/ingestion/table_rules.py` et raccordé à la capture/projection de `table_geometry.py`. Il ne modifie pas l'OCR, son seuil de confiance ou son repère local. Les glyphes et sous-en-têtes du groupe doivent tous être natifs et soutenus. Une page sans caractère natif n'effectue pas cette capture ; une page mixte peut conserver des observations de chemins, sans élargir un en-tête OCR. Les chemins en pointillés, les références de clipping présentes et les courbes restent non admis. L'implémentation utilise le cas `CountPaths=-1` uniquement avec un handle de clipping non nul issu de l'objet connu : le code officiel consulté rattache ce cas à l'absence de référence interne. `CountPaths=0` n'est pas assimilé à une absence de clipping de texte. La peinture enregistrée et les obstructions sont des preuves structurelles bornées, sans garantie générale de visibilité raster.

Le runtime installé déclare PDFium `153.0.7999.0` avec pypdfium2 `5.13.0`. La consultation web de la branche `chromium/7999` n'a pas abouti ; le contrat des bindings installés a été confronté aux sources officielles courantes. Le petit test d'intégration ajouté dans `tests/integration/test_i5_native_rules.py` vérifie donc directement, sur un PDF synthétique neuf, la matrice et les coordonnées capturées, la peinture, le clipping et les pointillés. Il n'exécute ni rendu ni OCR. Les autres tests du lot sont des replays de doubles géométriques déclarés, pas des extractions natives. **À ce stade aucun de ces nouveaux tests n'a encore été exécuté**, et aucune nouvelle extraction de D01 n'est déduite de leur présence.

### 6.5 Reprise du lot cadres natifs : contrôles exécutés

La reprise a vérifié le correctif du §6.4 sans nouvelle extraction du corpus,
sans OCR et sans modèle. Les trois fichiers de tests nouveaux exécutent
**52 cas**, dont **trois intégrations PDFium réelles** sur de petits PDF
synthétiques. Le premier passage donne **52 PASS en 3,48 s**. Le lot élargi
de géométrie, qualité des sources, repères locaux, conditions et contexte OCR
donne ensuite **330 PASS en 9,11 s**. Ces ensembles se recouvrent ; leurs
effectifs ne s'additionnent pas.

Mypy relève d'abord que l'identifiant d'une arête peut être un entier ou une
chaîne pour le segment de fermeture, puis que le nom `index` réutilisé a été
inféré comme entier dans une boucle précédente. La correction déclare le type
de la liste d'arêtes et renomme cette variable locale `edge_index`. Elle ne
change ni les segments acceptés, ni la portée de l'en-tête, ni les seuils.
Le contrôle final donne **Mypy PASS sur deux modules**, **Ruff PASS** et
**52 PASS en 2,04 s** sur les octets corrigés. Les 330 cas précèdent ce dernier
delta de typage ; ils ne sont pas présentés comme un second passage final.

Les tests PDFium vérifient directement la matrice non identitaire, les
coordonnées physiques, la peinture, le clipping et les pointillés. Les tests
de catalogue relient les mêmes observations synthétiques à SQLite, à la
portée documentaire et au rendu des bornes Min/Max lorsque Typ est vide.
Un cadre manquant, un autre sujet explicite, une extension forgée et les
groupes voisins restent refusés. Ces preuves ne démontrent pas encore que
le cadre du PDF D01 réel est admis : une nouvelle extraction avec capture
des chemins reste nécessaire avant d'évaluer sa réponse.

Les journaux et JUnit de cette reprise sont conservés dans
`/workspace/scratch/ad56692d3810/qa/`, avec le reçu
`ingestion-rules-resumption-receipt.json`, SHA-256
`878d0f8e3f1ac44b3856878440047f5d8317a3b24ae5bbec2e46f6aa3f79c76f`.
Il contient les empreintes des treize fichiers source/test et des dix
fichiers de preuve. Le corpus de transfert réservé I5 n'a pas été consulté.

| Module prêt pour une nouvelle extraction de développement | SHA-256 courant à la clôture du lot |
|---|---|
| `table_rules.py` | `ad1ec6d82dd30cb518ef29bf867dedacc29514ec9837ed8be5018b9d562e59da` |
| `table_geometry.py` | `2f271e7effababa33314fd8d4a9bcbb7407a30d2b8872f22a4c2479d5cb2ed81` |
| `source_quality.py` | `d7d9868c814f6b459161f9139768adc9ce1ba144305224be66a89ae03b32de4e` |
| `ocr_verification.py` | `579dc44801ee959b9291481e3489ef3b74c90e1d64aac098f0daf8def27aad3b` |
| `docling_adapter.py` | `4c42ab343bfff282b22f1a461981249f82c99a308fa5e94950c9329635cbb826` |

Les rapports du diagnostic 4 et des huit intégrations OCR historiques restent
antérieurs à ce correctif de cadres. Ils conservent leur portée initiale.

### 6.6 Phase 5 des scans : sonde négative et regroupement géométrique du bandeau

La revue du 9 novembre conserve les extractions phase 5 et leurs défauts dans
`development-ocr-5-ingestion-review-r01.json` (SHA-256
`dc55dfb19afdfbe9e9b2034719071b127a4e515ac9bae7726daf258bd85ba87c`).
SCAN1 garde des preuves locales corroborées pour les deux plages demandées ;
le faux `+2.0°C` est maintenant bloqué par le contrôle de barre inférieure et
`230 HW` reste incertain. SCAN2 garde huit bindings ambigus pour les deux
sous-lignes de délai. Les 13 fragments de son bandeau provoquent séparément
`general_condition_band_limit`.

Une seule sonde native est exécutée après arrêt et récolte des workers TI.
Le plan privé `scan2-segmentation-probe-plan-r01.json`, SHA-256
`0d5d4040a1f376e6610e711c1d84fd18c54a7a315d72bb8fe774cf7dd5dfa7a2`,
fixe huit régions observées et trois conditions : facteur 2/PSM 6, facteur
1/PSM 6, facteur 1/PSM 7. Le rendu PDFium/Pillow retrouve exactement le hash
du raster OCR enregistré `ac0db1497450dd08822b78f9437f8c682327bd296b4ec0a35dce7e1b456485cf`.
Les **24 appels terminent en 6,522 s**, avec 1 383 450 pixels cumulés de crops,
aucun timeout et tous les sous-processus réapés, groupes vides. La reconstruction
de page est une allocation distincte des crops ; aucun plafond produit n'est
relevé. Les sorties TSV, confidences, rectangles inverses, configurations et
hashes de chaque tentative restent conservés.

La segmentation locale retire les pipes parasites, mais ne récupère pas les
symboles : `Cour` persiste, les unités sont encore `us`/`Us`, le bandeau conserve
`V*` et `OV`. Les contrôles numériques simples restent stables. Le reçu complet
`scan2-segmentation-probe-r01/receipt.json` porte le SHA-256
`40ffb621be1dbdcd270dc10217148fc85789d6387fb8a3abb62e5c73b4862425`.
**Aucun de ces réglages n'est adopté comme réparation OCR ; aucun symbole n'est
substitué et aucun accord du même moteur n'est transformé en vérité.**

Le changement retenu concerne exclusivement la liaison du bandeau. Au-delà de
huit fragments, `build_table_general_conditions` peut constituer des pièces de
ligne : une bande verticale commune, un ordre horizontal sans recouvrement et
des espacements bornés par les hauteurs observées sont nécessaires. Un fragment
haut compatible avec deux lignes, un rectangle d'aire nulle ou trop de pièces
restent refusés. Chaque fragment conserve sa propre référence exacte ; le groupe
n'invente ni parent concaténé, ni hash de source composite. Les cas tenant déjà
dans huit pièces conservent leur annotation antérieure sans changement.

Sur le rejeu pur des observations extraites de SCAN2, **13 fragments deviennent 2 pièces** ;
les plafonds restent **8 pièces / 256 blocs / 4 096 caractères**. Les quinze
annotations des tableaux D01–D03 restent identiques. Les huit bindings de délai
et les lectures du bandeau restent incertains. Le reçu
`general-condition-lines-development-replay-r01.json`, SHA-256
`5de044b82762e776eb631fa14ab67ef25bb1115fa8efcbc6c67af10ad0462f87`,
atteste ce rejeu sans OCR ni modification des extractions conservées.

Les contrôles ciblés de géométrie, conditions, en-têtes et repères passent :
**184 PASS en 1,45 s**, JUnit
`/workspace/scratch/ad56692d3810/qa/i5-general-lines-3.xml`. Ruff et Mypy passent
sur `table_geometry.py` et Ruff sur le nouveau fichier de tests. Une première
exécution a exposé trois fixtures de rotation utilisant le mauvais sens de
l'axe vertical ; ce défaut de test a été corrigé dans la fixture, sans modifier
le calcul produit pour obtenir le vert. Son JUnit rouge reste conservé.
Sources de cette vérification :

| Fichier | SHA-256 |
| --- | --- |
| `services/ingestion/table_geometry.py` | `38fc377bb490cb63ae18b6e64b31ca6d25303b2193be890fdaef157f25ad8610` |
| `tests/unit/test_i5_general_condition_lines.py` | `b3ca4540beae46064a620774bbf9cb175e389db2cfb6d2ae7e149e70d378e069` |

Le raccord API conserve la revalidation avant aplatissement et la barrière de
qualité pour **chaque fragment**. Ses sept nouveaux tests SQLite passent après
un premier résultat rouge de 3 échecs ; le groupe adjacent passe **111 tests**,
Ruff et Mypy sont verts. La revue indépendante du raccord, sans réexécution,
est conservée dans `ingestion-independent-api-line-review-r01.json`, SHA-256
`097310e79ca89cb9786f056fc318bad4633c5f0dca47cd7f70ae312c18252529`.
La géométrie a également été relue indépendamment, sans constat bloquant
(`general-condition-lines-independent-review-1.json`, SHA-256
`1558527f497d6e32b1bf7c10b8438cf49c0d04620d0127f605a881073addfd24`).
La grammaire n'est pas étendue : un point numérique dont les mots sont répartis
dans plusieurs parents reste insuffisant, même lorsque la ligne est liée.

Les nouvelles extractions après gel sont décrites au §6.7. **Ce regroupement
n'acquiert ni les unités/conditions de SCAN2, ni I5-D04.** La revue des réponses
conserve ses verdicts séparés dans le
[rapport de développement](trust-4b-development-review-2026-11-09.md).

### 6.7 Réextractions complètes et réponses de développement phase 6

L'instantané 6 réextrait les **sept documents complets, 125 pages et 6 066 blocs**
en trois groupes successifs. Tous les workers terminent avec code 0, sans
timeout, chefs réapés et groupes vides. Le fingerprint d'ingestion est
`df7d4c9bc6e7b819c039d5976ebdf4731e0b97e6cd0037bcf28907876f2804de` ;
les sources de géométrie et leurs hashes du §6.6 sont ceux de cet instantané.
Les sept documents restent `ready_partial` : une fin de parseur ne transforme
pas les régions non résolues en couverture complète.

| Groupe réextrait | Pages / blocs | Constat séparé du verdict de réponse |
| --- | --- | --- |
| D01–D03 | 32 / 2 244 | Textes, types, références de parseur et rectangles identiques à la phase 5 ; quinze qualités de tableau inchangées, nouvelles identités de bandeau revalidées |
| SCAN1–SCAN2 | 2 / 41 | Lectures OCR et témoins de qualité inchangés ; SCAN2 obtient deux pièces géométriques pour treize parents, mais les huit bindings de délai restent ambigus |
| INA226–TMP117 | 91 / 3 781 | Signatures de blocs identiques à la phase 5 ; les plages de première page et leurs conditions sont présentes dans les nouvelles extractions |

La relecture des **12 réponses PDF phase 6** conclut à **6/10 positifs stricts
et complets, 1/2 limites strictes et 3 erreurs**. SCAN1 répond aux deux plages
sans publier l'unité OCR erronée de son paragraphe parent. SCAN2 s'abstient sans
publier ses lectures corrompues et reste FAIL positif. H07 conserve ses délais
et conditions vérifiés mais perd leur association au sujet imprimé distinct ;
H06, H08 et TMP117 échouent au traçage avant de livrer une réponse. Ces résultats
distinguent la fidélité de l'ingestion, le contrat de publication et l'exécution.
Ils ne qualifient pas une diffusion en production.

| Reçu privé phase 6 | SHA-256 |
| --- | --- |
| `development-transfer-6-ingestion-review-r02.json` | `019216a6568f2a3315843b22c2f9ae0f42abf55d4a8c448f3341cfc5985c75cb` |
| `development-ocr-6-ingestion-review-r01.json` | `2f3091f55a73ff6d0b33ccd63cfcfba076a3be7be6b938f785435b44d9a97fbe` |
| `development-ti-6-ingestion-review-r01.json` | `373fda351fe950063d91ad897f43ed7de8992801c17e387272e13a4bea7b0829` |
| `development-phase6-independent-review-r03.json` | `630d2dc64bfb1e62e7242e9a09b3975c91d64d6d309136c4e745673fe93706e0` |

Cette relecture réutilise les vues originales déjà conservées et les JSON
terminaux fermés ; elle n'ajoute aucun rendu ou appel de moteur. Les résultats
phase 5 et les révisions intermédiaires de revue restent intacts.

## 7. Limites restantes et état des critères

| Point | État à la rédaction | Ce qui reste à établir |
|---|---|---|
| I5-D02, géométrie et corps utile | PARTIAL au niveau du critère global ; témoins D01/D03 et corps utile conservés dans les extractions complètes phase 6 | Association explicite du sujet au tableau H07, dépendances du candidat final et familles de tableaux encore indisponibles |
| I5-D04, scans positifs | Non acquis ; SCAN1 PASS et SCAN2 FAIL dans les réponses phase 6 | Lectures sensibles et conditions de SCAN2 toujours incertaines ; une abstention sûre ne valide pas l'utilité d'une positive |
| I5-D01, absence de faits publics non soutenus | Non démontré par ce seul lot | Contrôle de toutes les sorties finales, y compris réserves, ajouts et localisateurs |
| I5-D05, non-régression | Suites ciblées PASS ; huit intégrations OCR historiques PASS dans la campagne 3 ; suite portable finale non établie ici | Rapport final des contrôles sur les mêmes octets candidats |
| I5-D06, transfert réservé | NOT_RUN dans ce rapport | Deux bras, nouvelles extractions lorsque nécessaires, dénominateurs et erreurs conservés |
| I5-D07, exploitation/coûts | Sept documents complets, 125 pages traitées, coûts d'extraction et arrêts de workers constatés ; sept documents `ready_partial` | Latences/mémoire de bout en bout, HTTP/SSE, plateformes cibles et libération des ressources au niveau applicatif |

Deux limites de méthode restent déterminantes. D'une part, un code Unicode visible, sans erreur de mapping signalée par PDFium, ne prouve pas l'apparence exacte du glyphe imprimé : le marqueur encodé `l` de D03 n'est pas réécrit en puce et n'est pas présenté comme visuellement certifié. D'autre part, deux segmentations du même moteur OCR peuvent répéter une erreur. Les tests de formes et les contrôles de correspondance réduisent des risques identifiés ; ils ne couvrent pas tous les signes, polices ou mises en page.

Les grammaires supportées restent bornées. Un tableau sans ancrages explicites reconnus, une portée de condition non démontrée, une géométrie ambiguë ou une preuve dépassant les caps peut rester indisponible. Leur coût en utilité doit rester visible dans les résultats, sans créditer les refus comme des réponses correctes.

## 8. Reproduction et références

Depuis la racine du dépôt, avec le runtime local provisionné et sans autre tâche lourde :

```sh
.venv/bin/python -m pytest -q tests/unit/test_i5_table_geometry.py tests/unit/test_i5_vector_coverage.py tests/unit/test_i5_table_conditions.py tests/unit/test_ingestion_provenance.py tests/unit/test_ingestion_geometry.py tests/unit/test_ingestion_render_budget.py tests/unit/test_ingestion_limits.py
.venv/bin/python -m pytest -q tests/unit/test_i5_single_value_tables.py tests/unit/test_i5_table_reading_frame.py tests/unit/test_i5_table_authority.py tests/unit/test_i5_explicit_value_table.py tests/unit/test_i5_catalogue_quality.py
.venv/bin/ruff check services/ingestion/preflight.py services/ingestion/table_geometry.py services/ingestion/docling_adapter.py tests/unit/test_i5_table_geometry.py tests/unit/test_i5_vector_coverage.py tests/unit/test_i5_table_conditions.py
.venv/bin/mypy services/ingestion/preflight.py services/ingestion/table_geometry.py services/ingestion/docling_adapter.py
```

Les huit intégrations OCR historiques nécessitent les moteurs et la police de fixture provisionnés. Elles utilisent leurs paramètres d'extraction historiques, sans lancement d'un générateur :

```sh
RAG_TEST_PDF_BACKEND=pypdfium2 RAG_TEST_OCR_DERIVATIVES= .venv/bin/python -m pytest -q tests/integration/test_ingestion_ocr.py
```

Conserver une sortie et un JUnit distincts pour chaque exécution, ainsi que la récolte terminale du processus. Le démarrage d'un worker ou un journal partiel ne remplace pas ce résultat.

Pour une nouvelle extraction de développement, le préparateur réel accepte `--kind development-window`, `--inputs`, `--application-root`, `--runtime-root`, `--output` et `--execute`. Les entrées doivent être celles d'un corpus déjà consommé, avec fichiers et hashes vérifiés ; le dossier de sortie doit être distinct des reçus conservés. Par exemple, lorsque les artefacts de ce diagnostic sont présents :

```sh
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-window --inputs .runtime/qa/production-i5-20261108/development-i4-targeted-candidate-2/inputs.json --application-root . --runtime-root . --output .runtime/qa/production-i5-20261108/reproduction-ingestion --execute
```

Cette commande produit de nouvelles mesures sur le code exécuté. Elle ne doit pas être présentée comme une reproduction bit à bit de diagnostic 2 sans réutiliser sa copie de code et les identités de son reçu. Le transfert réservé suit le protocole distinct et n'est jamais remplacé par ces fenêtres de développement.

Pour les sept documents complets déjà consommés de diagnostic 3, les trois groupes sont exécutés séquentiellement avec `--kind development-pdf`, dans des sorties neuves :

```sh
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i5-20261108/development-transfer-candidate-3/inputs.json --application-root . --runtime-root . --output .runtime/qa/production-i5-20261108/reproduction-full-transfer --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i5-20261108/development-ocr-candidate-3/inputs.json --application-root . --runtime-root . --output .runtime/qa/production-i5-20261108/reproduction-full-ocr --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i5-20261108/development-ti-candidate-3/inputs.json --application-root . --runtime-root . --output .runtime/qa/production-i5-20261108/reproduction-full-ti --execute
```

Ces commandes sont documentées, **non relancées lors de la revue**. Elles utilisent l'arbre courant ; reproduire les mêmes octets de code exige la copie figée de diagnostic 3 identifiée au §2. Les reçus d'extraction seuls n'exécutent pas les questions, ne qualifient pas leur rendu et ne remplacent pas les comparaisons complètes du protocole.

Références officielles et preuves de contrat consultées :

- [PDFium, `fpdf_text.h`](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_text.h), blob consulté `fe96ccd5b2a5355868957df738a8ca01ddc5ee0a` : indices de caractères, Unicode, boîtes et indicateurs de mapping/génération ; ces indicateurs ne sont pas une validation visuelle.
- [PDFium, `fpdf_edit.h`](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_edit.h), blob consulté `77fa19c81e3837ddf03fea1469ec406b653f6afb`, et [implémentation des chemins](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/fpdfsdk/fpdf_editpath.cpp), blob `97ef64788f8ca79e793dc4cc06907863a6f4fb44` : segments locaux, matrice, modes de dessin et états disponibles. [Implémentation du clipping](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/fpdfsdk/fpdf_transformpage.cpp), blob `1dfdb950590ca1ec012354db1fcbe42abbde397e` : handle emprunté et distinction entre référence absente et chemins enregistrés. L'applicabilité native au build installé doit être établie par le test synthétique, pas par la documentation seule.
- [API Python pypdfium2](https://pypdfium2.readthedocs.io/en/stable/python_api.html) : documentation 5.15.1 confrontée au helper et aux bindings installés 5.13.0 avant leur utilisation ; indices texte/caractères distincts et fermeture explicite des objets.
- [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) et code installé du backend PDFium/OCR : modèle de provenance, géométrie et sérialisation, confrontés aux versions indiquées plus haut.
- [Tesseract — amélioration de la qualité](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) et [CLI/TSV](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) : segmentation, crops et observations ; aucun score publié n'est transféré à cette application.
