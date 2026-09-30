---
name: official-source-review
description: "Vérifie les sources officielles et les contrats de version avant une étude, une décision technique, une mise à jour ou une affirmation SOTA concernant le RAG local."
compatibility: "Agents de développement avec lecture du dépôt ; réseau officiel pour les vérifications externes autorisées ; application locale CPU uniquement."
metadata:
  origin: "project-authored"
  version: "2.1"
  project: "RAG-LOCAL-16"
---

# Décider à partir de sources primaires

## Entrée et périmètre

Une question technique précise, le composant et sa version constatée, la décision à prendre et les contraintes CPU/16 Go/offline. Ne pas activer pour une correction purement typographique sans fait nouveau.

## Exécution

1. Lire la [politique de recherche](../../RECHERCHE_ET_SKILLS.md) et les décisions applicables dans [DECISIONS.md](../../DECISIONS.md). Réutiliser une vérification versionnée encore pertinente.
2. Consulter la documentation officielle actuelle pour l'évolution du sujet et la documentation/code de la version installée pour son contrat. Ouvrir les sources ; relever éditeur, URL, section, version et dates. Les liens initiaux sont dans [SOURCES.md](../../SOURCES.md).
3. Pour un résultat « SOTA », identifier le producteur, protocole, corpus, langues, configuration et limites. Distinguer une publication expérimentale d'une fonctionnalité stable ; ne pas extrapoler au CPU local.
4. Établir un test minimal de l'hypothèse ou de l'API. Réutiliser les extractions/caches ; ne pas installer une grille de modèles. Les recherches indépendantes peuvent être parallèles ; partager le résultat utile.
5. Enregistrer fait, incertitude, résultat réel, décision et fichiers affectés. Mettre à jour le registre et les contrats ; une simple liste de liens ne constitue pas une étude.

## Sortie et validation

Une décision traçable : source primaire + contrat de version + motif + test/mesure ou blocage + effet sur le dépôt. Vérifier un cas de changement d'API et un cas de source inaccessible. Une impossibilité de vérification n'autorise ni l'invention ni un téléchargement à l'exécution.

Ne pas transmettre de documents privés dans la recherche. Ne pas installer de skill externe sans lecture, contrôle de provenance et respect des permissions. Ce skill ne donne aucun outil au LLM du produit.
