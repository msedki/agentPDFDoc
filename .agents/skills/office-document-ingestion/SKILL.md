---
name: office-document-ingestion
description: Étudier, implémenter et vérifier l'ingestion DOCX et XLSX locale de ce dépôt, ses structures, valeurs, formules et citations sources. Utiliser pour les adaptateurs Office et leurs contrats ; compléter avec hybrid-rag-api et pdf-workspace-web pour leurs couches. Ne couvre ni les PDF ni le recalcul d'un classeur.
metadata:
  origin: project-authored
  version: "1.0"
  project: RAG-LOCAL-16
---

# Documents Office dans le RAG local

## Entrée et portée

Lire les instructions applicables, le lot Office du PLAN canonique, ses
décisions et preuves. Vérifier les versions réellement installées et leurs
backends avant de choisir un adaptateur. Distinguer étude, prototype de QA
et code produit ; un format reconnu par Docling n'est pas encore intégré
à ce projet. Les originaux restent immuables, privés et hors Git.

Références confrontées le 9 octobre 2026 : Docling2.131.0/Core2.99.0,
python-docx1.2.0 et openpyxl3.1.5 installés. Les backends Docling du tag
v2.131.0 ont les mêmes octets que l'installation. La documentation openpyxl
stable affiche3.1.3 : consulter également le code3.1.5, sans transposer
aveuglément les signatures. La connaissance est réutilisable ; le suivi
des choix et exécutions reste dans PLAN, SOURCES et les rapports.

## Source, structure et provenance

- Conserver format, SHA-256 original, version, identité du parseur/options,
  couverture, avertissements et dérivés distincts. Les IDs et localisateurs
  sont déterministes pour cette identité ; une nouvelle version ne réécrit
  aucune ancienne citation. Ne pas inventer des pages ou coordonnées PDF.
- DOCX : parcourir paragraphes, tableaux et objets dans l'ordre XML réel ;
  préserver titres/styles hérités, hiérarchie, listes/numérotation, fusions,
  images/légendes, métadonnées, liens, notes et autres parties utiles. Ancrer
  au package/partie/élément source et au hash exact du texte ; un texte répété
  ne suffit pas à identifier un paragraphe. Signaler les éléments non couverts.
  Vérifier namespaces et relations Strict/Transitional : l'API Document de
  python-docx ne charge pas le DOCX Strict sondé. Une normalisation éventuelle
  reste un dérivé ; les ancrages se rapportent aux parties originales.
- XLSX : conserver feuille/partie, adresse A1 et plages, ordre et visibilité,
  tables/en-têtes/fusions, types, valeur XML et format numérique, formules et
  valeurs mises en cache séparément, noms définis, commentaires et relations.
  Une valeur cachée n'est pas une preuve de recalcul récent. Un cache absent
  reste absent ; jamais zéro ou valeur calculée inventés.
- Le parseur n'exécute aucune macro, formule, liaison externe ou objet embarqué.
  Les références entre feuilles sont des relations sources ; leur extraction
  ne prouve pas une évaluation complète de la grammaire Excel.
- Garder les structures de tableau/cellule à côté du texte d'indexation.
  Sérialiser pour la recherche des unités bornées avec leurs en-têtes, types,
  unités et localisateurs. Ne pas traiter un classeur entier comme un texte
  unique ni transformer une matrice clairsemée en un rectangle immense.

## Réutilisation et limites réelles

Réutiliser versions, générations, gouverneur, checkpoints, déduplication,
publication atomique, FTS5/E5/Qdrant et citations immuables là où leurs
contrats l'autorisent. Examiner les hypothèses PDF des blocs/pages/scopes,
routes et lecteur avant de brancher les formats. Garder la voie PDF existante
et ses preuves ; les contrats Office portent des localisations typées.

Docling DOCX apporte une structure riche mais pas de provenance de page.
Docling XLSX utilise data_only et convertit les valeurs en chaînes : vérifier
ses pertes et compléter les faits natifs si nécessaire. Comparer à une
lecture structurelle python-docx/openpyxl sur le même corpus annoté, plutôt
que supposer une fidélité suffisante à partir d'un export Markdown.

Pour les gros XLSX, étudier openpyxl read_only, fermeture explicite et
dimensions déclarées parfois erronées. Une lecture des formules et une
lecture des valeurs cachées doivent se rapporter aux mêmes octets d'origine.
Les checkpoints réutilisés incluent les dépendances nécessaires : styles,
chaînes partagées, relations et noms peuvent invalider des unités inchangées.
Une recherche répétée par ReadOnlyWorksheet.cell peut rescanner les lignes ;
ne pas reproduire cette sonde de QA dans un gros classeur. Prévoir une
jointure streaming des faits OOXML formule/cache par adresse et mesurer le
coût réel des chaînes partagées et styles, même en read_only.

Un scope cellule/plage s'applique avant le classement et le top-k : projeter
le texte autorisé, ses bindings et les parents avant recherche/contexte.
Un simple filtrage après retrieval laisse les cellules exclues influencer
les scores. Si le contrat exige leur indépendance, borner également les
statistiques lexicales au contenu autorisé ; tester deux versions dont seuls
les contenus hors scope diffèrent, avec oracle d'adresses et de rangs.

Une prévisualisation PDF/HTML est un dérivé identifié. Elle ne remplace ni
les structures sources ni leurs adresses ; LibreOffice/Pandoc restent des
options à évaluer, pas des dépendances implicites du programme.

## Sécurité, ressources et vérification

Contrôler ZIP/OPC avant la bibliothèque : signature/parties attendues,
nombre et tailles décompressées des membres, total, compression, chemins,
doublons et corruption. Ne pas se limiter à la taille compressée. Parser XML
sans DTD/entités externes ni réseau ; utiliser les protections réellement
activées et tester leurs limites, y compris les liaisons externes.

CPU local sans GPU, cible 16 Go : mesurer temps, RSS et sorties en sous-processus
isolés, une tâche lourde à la fois, temporaires sous stockage utilisateur.
Pas de téléchargement de modèle pour ces formats natifs. Prévoir pause,
annulation, reprise par unités et erreur/limite visibles sans publication
partielle mensongère. Un plafond logiciel sur un hôte de 61 Gio n'est pas une
qualification native 16 Go. Conserver la compatibilité Windows et Linux
aarch64/x86-64 ; ne pas introduire une dépendance Jetson/Ubuntu dans l'adaptateur.

Employer de vrais conteneurs DOCX/XLSX annotés : structure riche, répétitions,
types, formules/cache absent ou périmé, feuilles multiples, gros classeur,
corruption et cas adverses. Distinguer fichiers synthétiques, exemples
officiels et documents métier. Mesurer les faits correctement localisés,
pertes/avertissements, stabilité des IDs, coût et reprises. Vérifier import,
recherche/scopes, questions/comparaisons et ouverture des citations, puis les
parcours PDF inchangés. Les benchmarks de parseurs ne prouvent pas le RAG
ni le lecteur ; l'étude finalisée précède toute implémentation autorisée.

## Sources primaires

- [ECMA-376, OOXML et OPC](https://ecma-international.org/publications-and-standards/standards/ecma-376/).
- [Microsoft, structure WordprocessingML](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document).
- [Microsoft, formules et valeurs cachées](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-formulas).
- [Docling v2.131.0, Word](https://github.com/docling-project/docling/blob/v2.131.0/docling/backend/msword_backend.py) et [Excel](https://github.com/docling-project/docling/blob/v2.131.0/docling/backend/msexcel_backend.py).
- [python-docx1.2.0, Document](https://python-docx.readthedocs.io/en/latest/api/document.html).
- [openpyxl, modes optimisés](https://openpyxl.readthedocs.io/en/stable/optimized.html).
- [LibreOffice, paramètres et profil utilisateur](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html).
