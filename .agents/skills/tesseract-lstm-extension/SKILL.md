---
name: tesseract-lstm-extension
description: Construire les outils Tesseract 5.4 et qualifier une extension d'alphabet LSTM dans une cible isolée, avec données d'apprentissage distinctes de la recette RAG. Utiliser pour le proto-modèle, le remapping et le pilote ; pas pour l'ingestion ordinaire, les LLM ou les embeddings.
metadata:
  origin: project-authored
  version: "1.0"
---

# Extension d'alphabet OCR

## Entrée et portée

Lire les instructions applicables, l'action OCR du plan canonique, la
décision et les preuves qui motivent l'extension. Reprendre
`pdf-ingestion-windows` pour le contrat d'extraction et
`linux-rag-runtime` pour la construction et la supervision locales.
Le présent skill décrit une méthode ; il n'autorise ni adoption d'un modèle,
lecture du corpus privé, ni utilisation des jeux DEV/final pour apprendre.
Une preuve d'alphabet incomplet ne prouve pas l'absence de tous les modèles.

Avant mutation, préciser la phase autorisée : outils, provisionnement des
entrées, données synthétiques, pilote ou intégration. Nommer la cible neuve,
les fichiers modifiables, les plafonds et la règle de sélection du candidat.
Conserver binaires, poids, configuration et seuils nominaux jusqu'à une
qualification distincte. Un simple changement de charset n'apprend aucun signe.

## Outils séparés

Utiliser Tesseract 5.4.0, révision `1be261dc226d49bdcad0ab2fcb10f8395edc1225`,
et le verrou d'artefacts du projet. Vérifier archive/contenu, compilateur,
Leptonica et ICU avant une construction hors du préfixe nominal. Relever
les sources et paramètres utilisés, puis les hashes des exécutables.

Le [CMake training épinglé](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/CMakeLists.txt)
conditionne les outils LSTM à ICU et réclame Pango lorsque PkgConfig est
trouvé. Pour des images de lignes préparées sans `text2image`, un cache
neuf peut désactiver cette découverte optionnelle avec la
[variable officielle CMake 3.16](https://cmake.org/cmake/help/v3.16/variable/CMAKE_DISABLE_FIND_PACKAGE_PackageName.html).
FindICU n'est pas appelé avec `REQUIRED` : CMake peut réussir et omettre
les outils conditionnés à `ICU_FOUND`. Exiger ICU trouvé, sa version et ses
bibliothèques résolues, puis la liste effective des cibles nécessaires.
Ne pas présenter cette branche comme un build acquis, modifier les sources CMake ou ignorer
une dépendance obligatoire. Pas de cache nominal réutilisé, installation
système, téléchargement implicite ou modification globale du PATH.

Construire les seules cibles utiles : `lstmtraining`, `lstmeval`,
`combine_tessdata`, `combine_lang_model`, `unicharset_extractor`,
`merge_unicharsets` ; ajouter les outils de propriétés ou de lexiques si
la préparation les requiert. Les versions, retours, composants et sorties
attendus sont vérifiés, pas seulement l'existence d'un exécutable.

## Entrées et séparation des données

Épingler modèle flottant officiel, ressources langdata, scripts et fontes ;
vérifier taille, identité complète et licence de chaque entrée. Le modèle
integer/fast n'est pas un point de continuation entraînable. Conserver son
identité si nécessaire comme baseline d'inférence, pas comme poids float.

Préparer des lignes générales inédites et leurs transcriptions UTF-8 ;
aucun PDF, ID, phrase ou annotation des jeux de recette n'alimente le
générateur, le train ou le choix des paramètres. Figer le manifeste, les
graines et le partage train/évaluation avant le pilote ; répartir les
variantes d'une même ligne dans un seul groupe, contrôler les doublons.
Inclure témoins de caractères existants et signes nouveaux pour mesurer
oubli et confusion, sans réparation lexicale ni translittération.

Le [workflow tesstrain épinglé](https://raw.githubusercontent.com/tesseract-ocr/tesstrain/405346a3a67d8e4e049341d1da6a4b752e0b8351/Makefile)
prépare images TIFF/PNG, transcriptions `.gt.txt`, boîtes de lignes et
`.lstmf`. Inspecter les commandes effectivement utilisées : ses cibles
de téléchargement et de nettoyage ne sont pas une autorisation. Pas de
`make training` aveugle ; une pipeline avec `tee` doit préserver le statut
du moteur et vérifier les fichiers de sortie.

## Alphabet, recoder et lexiques

Extraire les composants du modèle de départ. Fusionner l'ancien alphabet
en premier, puis les nouveaux tokens avec
[`merge_unicharsets`](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/merge_unicharsets.cpp).
Contrôler ordre/IDs des entrées existantes, propriétés Unicode, tokens des
signes requis et recoder du proto-modèle. Un commentaire ou une forme
normalisée ne vaut pas entrée reconnaissable.

Conserver les ressources lexicales nominales compatibles ; ne pas les
remplacer par les phrases d'apprentissage. Si les lexiques sont reconstruits,
vérifier leur aller-retour et les composants DAWG effectivement exportés.
[`combine_lang_model`](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/combine_lang_model.cpp)
peut continuer après une liste illisible : contrôler stderr, charset21,
recoder22 et lexiques attendus, pas seulement EXIT0.

## Pilote borné et export

La [procédure mainteneur](https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html)
permet `--continue_from` d'un réseau non integer et exige
`--old_traineddata` correspondant lorsqu'on change l'alphabet. Vérifier le
remapping effectif dans
[`TryLoadingCheckpoint` 5.4](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtrainer.cpp).
Fournir train et évaluation disjoints. Figer les critères, le nombre
d'itérations, le plafond des caches et une deadline externe ; les
[`training_iteration`](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmtraining.cpp)
ne bornent ni les échantillons refusés ni le temps écoulé.

Exécuter sous le verrou lourd du projet, dans une QA privée, sans recette
native, OCR ou LLM concurrents. Mesurer CPU, mémoire disponible/RSS des
descendants et disques ; arrêter la seule cohorte possédée sur dépassement.
Le cache `max_image_MB` ne borne pas toute la RSS, et train/évaluateur en
possèdent chacun un. Cette voie ne fournit pas de support GPU : ne pas
substituer un autre moteur pour obtenir une accélération.

Sélectionner selon la règle préalable sur l'évaluation d'apprentissage,
jamais selon DEV/final. Préserver échecs, skips, checkpoints et reprises.
Exporter avec `--stop_training`, puis qualifier séparément l'éventuelle
conversion integer. Vérifier présence réelle du réseau17, alphabet21,
recoder22, lexiques/configuration et lecture effective de toutes les langues.
Une commande réussie, un faible CER train ou un nouveau token ne suffit pas.

## Admission produit

Faire relire indépendamment procédure, identités, séparation des données,
mesures et métriques d'évaluation. Un pilote réussi ne ferme ni l'action
OCR ni la DoD. Avant adoption : extraction réelle avec les mêmes seuils,
fidélité UTF-8, cellules/unités/références, confiance, provenance,
native/scan/rotations et régression de l'ingestion selon le skill associé.
Identifier le candidat dans le verrou et le fingerprint, prévoir retour au
modèle antérieur et qualifier chaque plateforme ; un build Linux ne prouve
pas Windows. Actualiser uniquement les références du système réellement
validé, et les preuves/limites dans le plan et le journal existants.
