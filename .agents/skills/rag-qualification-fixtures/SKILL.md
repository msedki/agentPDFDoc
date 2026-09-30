---
name: rag-qualification-fixtures
description: Générer et contrôler les PDF synthétiques et annotations de qualification V2.1 du RAG local, avec séparation développement/final, preuves attendues et résolution des IDs après extraction réelle. Ne réalise ni benchmark métier ni import/indexation.
---

# Fixtures et questions contrôlées

Lire `RAG_Local_Agents/QUALIFICATION.md` §3, §6–7 et la DoD pour le quota courant,
puis les skills projet `rag-retrieval-evaluation` et `local-cpu-qualification`.
Les données synthétiques valident l'ingénierie ; elles ne prouvent pas la qualité
sur des livrets industriels. Ne pas envoyer de corpus privé à un service externe.

## Contrat de génération

- Utiliser ReportLab de version verrouillée et les APIs vérifiées dans cette
  version. Produire texte natif, schémas/tables, scans, page mixte natif + table
  scannée, colonnes, Unicode, rotation/CropBox, labels, versions et frontière 4/5.
  Les entrées corrompues/chiffrées/blanches et hostiles sont identifiées séparément.
- Écrire seulement dans la cible dédiée autorisée. Calculer les SHA-256 des octets
  réellement générés ; enregistrer licence synthétique, version de générateur,
  pages, objectif de chaque cas et conditions de refus configurables.
- Séparer développement et final par familles documentaires. Respecter les quotas
  V2.1 par split : 35 factuelles FR/EN, 15 identifiants, 12 tableaux/unités,
  10 comparaisons, 8 suivis conversationnels et 20 sans réponse.
- Annoter réponse/absence, valeurs et unités, scope explicite et unités requises
  par document/page/texte source, alternatives et complétude. Pour une comparaison,
  exiger une preuve de chaque document. Pour un suivi, garder la question utilisateur
  antérieure et le référent ; une réponse modèle n'est pas une preuve.
- Les UUID de versions, révisions, générations et blocs restent `null` avant la
  véritable extraction. Une résolution lit l'artefact réel, exige le SHA de
  l'original, texte exact et révision/hash sources ; elle ne remplace pas une unité
  introuvable par le seul nom du document. Conserver les échecs non résolus.
- Le jeu final est gelé avec son manifeste. Ne pas l'utiliser pour ajuster le
  ranking ni déplacer après coup une question échouée vers le développement.

## Validation

Contrôler compte/quotas/unicité, familles disjointes, scans sans couche texte,
présence du texte natif sur le mixte, boîtes/rotation/labels et empreintes.
Inspecter visuellement quelques cas. Une mesure de ces fichiers n'est ni Recall
ni performance du RAG ; garder les résultats d'extraction et de recette séparés.

## Références officielles

- [ReportLab, guide utilisateur](https://docs.reportlab.com/reportlab/userguide/ch2_graphics/)
  et [fonctions PDF](https://docs.reportlab.com/reportlab/userguide/ch4_pdffeatures/).
  Si le site est inaccessible au navigateur de recherche, lire les signatures et
  docstrings du paquet éditeur installé ; noter cette limite.
- [ReportLab sur PyPI](https://pypi.org/project/reportlab/) : version, licence et
  provenance du paquet. Pas d'installation implicite dans un Python utilisateur.
- `tools/qualification/generate.py` et les manifests livrés constituent la méthode
  reproductible locale, pas une exigence universelle de génération de PDF.
