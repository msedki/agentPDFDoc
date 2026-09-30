---
name: rag-pdf-provenance
description: "Implémente et vérifie extraction PDF, OCR régional, provenance, géométrie et citations versionnées du RAG local ; utile pour pages mixtes, rotations et reprises."
compatibility: "Agents de développement avec lecture du dépôt ; réseau officiel pour les vérifications externes autorisées ; application locale CPU uniquement."
metadata:
  origin: "project-authored"
  version: "2.1"
  project: "RAG-LOCAL-16"
---

# Extraction PDF et preuves localisables

## Entrée et périmètre

PDF autorisés ou fixtures contrôlées ; original hashé ; version ; contrat de blocs/citations. Lire les sections parsing/provenance de [IMPLEMENTATION.md](../../IMPLEMENTATION.md) et le profil de [CONFIGURATION.md](../../CONFIGURATION.md).

## Exécution

1. Avant une API ou un chemin nouveau, vérifier les sources officielles du parseur, de l'OCR et du viewer selon [RECHERCHE_ET_SKILLS.md](../../RECHERCHE_ET_SKILLS.md), avec la version effectivement installée.
2. Inspecter une page représentative et sa couverture par régions. Choisir voie native qualifiée, structurée ou OCR régional ; ne pas OCRiser tout un document déjà textuel.
3. Préserver original, version et révision d'extraction. Produire blocs, tables, unités, ordre, pages et coordonnées dans le contrat canonique. Signaler toute région non interprétée.
4. Persister au checkpoint sans en faire une frontière sémantique. Reconstituer les liens entre pages seulement lorsqu'ils sont justifiés ; ne pas fusionner arbitrairement deux tableaux.
5. Vérifier sélection et citation sur texte source immuable/hashé ; transformer CropBox, rotation et viewport de façon testable. Replier explicitement à bloc/page si la localisation exacte n'est pas disponible.

## Preuves et cas obligatoires

Comparer visuellement et structurellement page native, page « texte natif + tableau scanné », table pages 4/5, rotation, recadrage et caractères complexes. Tester reprise après interruption et résolution d'une citation d'ancienne version. Utiliser la [DoD](../../DEFINITION_OF_DONE.md), D02/D03/D06.

Livrer adaptateur, fixtures, extraction réelle et preuves de localisation. Ne pas annoncer un schéma compris sans voie d'interprétation validée. Un test avec extraction mockée ne valide pas le parseur réel.
