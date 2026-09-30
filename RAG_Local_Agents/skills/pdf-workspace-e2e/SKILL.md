---
name: pdf-workspace-e2e
description: "Développe et teste le poste documentaire arborescence-PDF-chat : navigation de citations, sélection Unicode, périmètre explicite, streaming et budget de rendu."
compatibility: "Agents de développement avec lecture du dépôt ; réseau officiel pour les vérifications externes autorisées ; application locale CPU uniquement."
metadata:
  origin: "project-authored"
  version: "2.1"
  project: "RAG-LOCAL-16"
---

# Interface documentaire et chaîne bout en bout

## Entrée et périmètre

Contrats API, backend accessible, fixtures contrôlées et parcours attendu. Lire les parcours de [SPEC_ARCHITECTURE.md](../../SPEC_ARCHITECTURE.md) et les contrats de sélection/SSE de [IMPLEMENTATION.md](../../IMPLEMENTATION.md).

## Exécution

1. Utiliser le skill UI/Playwright pertinent réellement disponible après lecture et contrôle, ou appliquer cette procédure. Vérifier les sources officielles de Next.js/PDF.js/tests pour toute API ou modification selon [RECHERCHE_ET_SKILLS.md](../../RECHERCHE_ET_SKILLS.md).
2. Construire les trois panneaux avec état partagé explicite. Un clic de source ou un scroll ne change pas le scope. Les états attente/annulation/partiel/erreur sont visibles.
3. Réconcilier sélection navigateur et texte source backend hashé ; convertir explicitement UTF-16/points de code. Tester ligatures, césures, caractères hors BMP et accents combinants.
4. Ouvrir la version/page/zone depuis l'ID de citation résolu par le backend ; préserver le retour à la position antérieure. Ne pas demander au LLM de produire une bbox.
5. Contrôler à la fois nombre de canvases et pixels alloués, miniatures comprises ; libérer les rendus obsolètes. Assets locaux uniquement, sans CDN.
6. Exécuter tôt import→index→question→réponse→citation→surlignage avec vrais backend, stores et runtime. Les mocks servent aux tests isolés et ne donnent pas de PASS E2E.

## Sortie et cas obligatoires

Tests, traces/captures, tailles d'écran, commandes et résultat réel. Couvrir zoom/rotation/CropBox, clavier/focus, reconnexion SSE sans seconde génération, annulation et scope changé. Appliquer D06/D08 de la [DoD](../../DEFINITION_OF_DONE.md). Pas d'écran factice présenté comme une fonctionnalité terminée.
