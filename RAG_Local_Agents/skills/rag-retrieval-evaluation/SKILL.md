---
name: rag-retrieval-evaluation
description: "Implémente et évalue recherche hybride, embeddings, identifiants exacts, scopes et conservation des preuves dans le contexte final avant réponse du RAG."
compatibility: "Agents de développement avec lecture du dépôt ; réseau officiel pour les vérifications externes autorisées ; application locale CPU uniquement."
metadata:
  origin: "project-authored"
  version: "2.1"
  project: "RAG-LOCAL-16"
---

# Recherche et contexte sous contrôle

## Entrée et périmètre

Corpus extrait autorisé, annotations de preuves, profils d'embedding identifiés et question/scope. Lire [IMPLEMENTATION.md](../../IMPLEMENTATION.md) et [QUALIFICATION.md](../../QUALIFICATION.md) aux sections recherche/mesure.

## Exécution

1. Vérifier la fiche officielle et l'API des composants modifiés conformément à [RECHERCHE_ET_SKILLS.md](../../RECHERCHE_ET_SKILLS.md). Une dimension égale n'autorise jamais à mélanger deux espaces d'embedding.
2. Appliquer les filtres de scope avant top-k dense et lexical ; comparer les ensembles autorisés puis assembler les preuves sans expansion hors périmètre.
3. Vérifier l'ordre BM25, la fusion RRF et la déduplication. Ajouter la couverture d'un identifiant explicitement visé après toutes les transformations, sans confondre simple occurrence et preuve pertinente.
4. Compter le contexte sérialisé avec le tokenizer réel. Mesurer ce que le LLM reçoit, pas seulement le top-10 initial. Suivre la couverture par identifiant/document et les coupes.
5. Évaluer sur le jeu de développement ; une seule alternative ciblée et vérifiable selon [DECISIONS.md](../../DECISIONS.md). Réutiliser l'extraction, protéger le jeu tenu à l'écart et éviter une réindexation inutile.

## Preuves et cas obligatoires

Contre-exemple RRF avec référence exacte absente du dense ; codes voisins ; page/section restreinte ; comparaison équilibrée ; question sans réponse ; relance pronominale et changement de scope. Ancienne réponse du LLM jamais utilisée comme preuve.

Publier Recall@k, couverture du contexte, exactitude, citations, abstention et coûts avec dénominateurs. Les calculs de référence du dossier ne remplacent pas un test du véritable sélecteur. Critères D04/D05/D10 de la [DoD](../../DEFINITION_OF_DONE.md).
