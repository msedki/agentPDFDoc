---
name: pdf-ingestion-windows
description: Implémenter et vérifier l’ingestion PDF locale Windows avec Docling, Tesseract CLI sélectif, pypdfium2, provenance et reprise par fenêtres. À utiliser pour le pipeline documentaire de ce projet, sans substituer le moteur ni étendre l’autorisation au corpus privé ou aux installations.
---

# Ingestion PDF Windows

Appliquer les contrats actifs RAG-LOCAL-16 et la décision Windows native. Produire des extractions réellement exécutées ; les mocks unitaires ne prouvent ni OCR ni parsing.

## Frontières et exécution

- Le parent transmet au worker uniquement des chemins/identifiants/configuration sérialisables. Créer le worker par `spawn` ; ouvrir les documents, modèles et handles dans l’enfant. Ne pas importer Docling/PyTorch dans le processus API.
- Acquérir le créneau de travail lourd auprès du superviseur avant Docling/OCR. Un checkpoint validé par fenêtre de quatre pages survit à l’arrêt ; ne pas lancer ce travail pendant une génération LLM.
- Lire l’original sans réécriture. Valider signature, taille, pages, hash et limites ; persister l’extraction ailleurs. Les textes et messages d’erreur du parseur ne doivent pas apparaître dans les logs normaux.

## Pipeline et provenance

Précontrôler avec pypdfium2 : compte de pages, MediaBox, CropBox, rotation, couche texte, présence d’images et contenu rendu si nécessaire. Fermer explicitement textpage/page/document. Une faible quantité de texte ne prouve pas un scan : conserver une classification incertaine pour une page graphique ; ne pas OCRiser automatiquement une page blanche.

Borner les allocations raster avant le chargement des modèles : dimensions effectives, arrondi des pixels et échelle réellement utilisée par la voie structurée ou OCR. Contrôler aussi chaque région avant son rendu. La taille du fichier ne borne pas les dimensions d'une page. Une recette avec plafond réduit ne prouve pas la frontière du plafond de production.

Le référentiel V2.1 actif dans `RAG_Local_Agents/` exige la voie native sans modèles (`NativePdfPipeline`/`NativePdfFormatOption`) pour les pages simples fiables, la voie structurée CPU pour les mises en page et tables, puis l’OCR PDF-aware régional pour les zones imprimées non couvertes. Configurer artefacts locaux et services distants désactivés, sans descriptions de figures. Vérifier les signatures de la version installée avant de coder. Tesseract CLI charge `fra` et `eng` réellement présents avec chemins explicites. Conserver les cellules du parseur nécessaires à mesurer l’OCR réellement exécuté ; un routage OCR ne prouve pas une reconnaissance. Un remplacement de couche dégradée ne concatène pas deux versions du texte. Ne pas instancier plusieurs ensembles de modèles lourds en même temps.

Sur Docling 2.131, l’inventaire des langues et OSD de Tesseract CLI omettent `options.path`. Fournir aussi `TESSDATA_PREFIX` dans le processus worker pendant la conversion, puis restaurer son environnement ; ne pas modifier les langues installées globalement. Vérifier `osd` en plus de `fra`/`eng`. Cette limite est attestée par le code officiel installé `docling/models/stages/ocr/tesseract_ocr_cli_model.py` ; la réexaminer après un changement de version.

Le tessdata local doit aussi contenir `configs/tsv` officiel. Sinon Tesseract peut rendre un texte brut avec retour zéro malgré la demande `tsv`, ce qui casse le parseur Docling. Valider ce fichier avant le chargement des modèles. Source Tesseract 5.4.0 : [configuration TSV](https://github.com/tesseract-ocr/tesseract/blob/5.4.0/tessdata/configs/tsv), SHA-256 `59d079bb75d8b3d7c839a3564580cb559e362c93a9d70f234e421c0c3e767e04` ; le verrou de provisionnement du projet fait foi.

Lire la colonne TSV `text` comme chaîne littérale, sans inférence numérique ni conversion des labels `NA` en valeurs manquantes. Une sortie OCR `24` ne devient pas `24.0` ; les zéros initiaux, unités, accents et points de code restent tels que reconnus. Une équivalence numérique ne remplace pas la preuve du texte brut.

Une grille imprimée peut conduire Tesseract à ignorer ses chiffres malgré un retour zéro. Contrôler les cellules et unités, pas seulement les libellés. Le dérivé OCR régional `crossing-rules-v2` retire uniquement les longues règles horizontales et verticales d'une grille croisée détectée, sans redimensionner. Si la grille est rectangulaire continue, reconnaître ses cellules imprimées séparément et remplacer les sorties internes de la grille, sans concaténation ni doublon. Conserver les hashes du raster avant/après, cadres et paramètres ; une cellule imprimée sans reconnaissance reste non résolue. Le PDF original reste intact. Voir la [limite officielle de reconnaissance de tableaux et segmentation Tesseract](https://github.com/tesseract-ocr/tessdoc/blob/main/ImproveQuality.md#tables-recognition).

Les fragments de layout d'une image tournée peuvent être trop courts pour OSD. Les étendre seulement au bitmap réel qui ne recouvre aucun texte natif fiable. Tracer l'orientation et refuser un succès complet lorsque cette orientation reste inconnue. Pour une table OCR tournée, normaliser le crop et ses tokens, exécuter le même TableFormer déjà chargé puis inverser les coordonnées de toutes ses cellules. L'extension par `PdfFormatOption.pipeline_cls` et les hooks du pipeline/Tesseract/table sont adaptés à Docling 2.131 verrouillé : revérifier leur signature après mise à jour. Un run sur deux PDFs séparés ne prouve pas le lifecycle du worker multi-fenêtres ; vérifier une fixture OCR de cinq pages et la libération des threads/handles entre conversions. Une limite de couverture visible ne remplace pas la réussite du tableau contrôlé.

Un bitmap étiré dans le PDF peut rendre ses glyphes trop déformés pour OSD/OCR. Un dérivé utilisant les dimensions intrinsèques `PdfImage.get_px_size()` et la matrice en lecture seule doit refuser les images imbriquées, skew/reflection, chevauchements ou ROI incomplet. Composer image-matrice, rotation de page, réduction anisotrope, rotation OSD et crop ; inverser les dimensions réellement arrondies et les quatre coins vers le raster original avant la conversion PDF. Ne jamais modifier la matrice de l'original. La [documentation Tesseract sur les bordures](https://github.com/tesseract-ocr/tessdoc/blob/main/ImproveQuality.md#borders) indique qu'un caractère isolé sur une grande zone vide peut échouer ; un crop d'encre avec petite bordure exige son offset inverse explicite.

Le backend officiel [PyPdfiumDocumentBackend de Docling](https://github.com/docling-project/docling/blob/main/docling/backend/pypdfium2_backend.py) peut être qualifié comme alternative Windows. Conserver les mêmes modèles, OCR et assertions, distinguer le profil expérimental d'une décision nominale. Dans Docling 2.131, `get_page_image` rend à `scale * 1.5` puis réduit : inclure cette allocation dans les limites de page/région avant modèles. Conserver les journaux natifs et leurs guards pendant la comparaison, sans patch de DLL ni changement des options globales OpenMP.

Découper tous les rectangles OCR autour des cellules PDF natives fiables, y compris les rectangles renvoyés par la logique PDF-aware du moteur : un cluster de layout peut contenir simultanément bitmap et paragraphe natif. Une région qui ne peut pas être isolée dans les limites prévues reste explicitement non résolue.

Conserver le JSON Docling et sa géométrie originale. Transformer les coordonnées vers des points PDF non tournés en tenant compte de l’origine, de la CropBox et de la rotation. Tester l’adaptateur sur rotation et recadrage ; un simple retournement de l’axe Y est insuffisant. Ne pas fabriquer de bbox : indiquer précision `page` lorsqu’aucune région fiable n’est disponible.

Les pages API sont zéro-based ; contrôler le `page_range` Docling installé et conserver les indices absolus. Les IDs de bloc doivent rester déterministes pour une version/révision d’extraction/pipeline identique. Garder le texte exact, son hash et les offsets en points de code Unicode ; la normalisation est séparée. Les cellules de table, en-têtes, unités et liens source sont préservés. Reconstituer sections et relations entre fenêtres ; une continuation de table nécessite une preuve (en-têtes, voisinage, position et structure), pas seulement des noms semblables.

Écrire chaque fenêtre atomiquement avec identité original/pipeline, hash du JSON et couverture. Réutiliser seulement un checkpoint dont identité et hash correspondent. Une interruption avant publication laisse la fenêtre à refaire ; une extraction partielle doit rester visible et ne vaut pas succès complet.

Conserver un journal local des fautes natives hors logs normaux. Un journal ancien non vide met le dossier d'extraction en quarantaine avant toute reprise, même si le processus mort n'a pas pu écrire son marqueur. Conserver ce journal et les checkpoints ; la nouvelle tentative utilise un nouveau dossier. Vérifier le refus de reprise avec un sous-processus fatal isolé. Cette protection ne prouve pas la résolution de la cause native.

## Vérification utile

Tester d’abord les fonctions déterministes et un PDF synthétique français natif, puis les fixtures rotation/CropBox/scan/mixte et les reprises. Séparer preuves synthétiques et corpus métier autorisé. Enregistrer versions, paramètres et compteurs sans recopier le texte privé. Aucune réindexation/OCR coûteux d’un corpus inchangé sans hypothèse nouvelle.

Exécuter les recettes avec un `--basetemp` daté propre à chaque essai sous `.runtime/qa/` : les répertoires temporaires Pytest partagés et tournants ne conservent pas les artefacts d’échec. Garder les runs échoués et corrigés distincts. Si une preuve a disparu, déclarer cette limite et produire un nouveau run ; ne pas reconstituer un résultat de parseur.

## Sources primaires

Consulter la version verrouillée ou le code installé ; les liens mouvants suivants sont des points de découverte, pas des verrous.

- [Docling : conversion et options](https://github.com/docling-project/docling/blob/main/docling/document_converter.py) — contrat `convert`/`page_range`.
- [Docling : pipeline et OCR](https://docling-project.github.io/docling/reference/pipeline_options/) — options CPU, tables et Tesseract CLI.
- [Docling Core : géométrie](https://github.com/docling-project/docling-core/blob/main/docling_core/types/doc/base.py) — BoundingBox et origine.
- [pypdfium2 : pages](https://github.com/pypdfium2-team/pypdfium2/blob/main/src/pypdfium2/_helpers/page.py) et [texte](https://github.com/pypdfium2-team/pypdfium2/blob/main/src/pypdfium2/_helpers/textpage.py) — boxes, rotation et couche texte.
- [Tesseract : installation Windows](https://tesseract-ocr.github.io/tessdoc/Installation.html#windows) et [ligne de commande](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) — provenance des binaires, langues et OCR local.
