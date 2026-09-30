---
name: local-cpu-qualification
description: "Mesure et qualifie RAM, CPU, latences, chargements, concurrence et fonctionnement hors ligne du RAG sur hôte 16 Go sans GPU, notamment après mise à jour."
compatibility: "Agents de développement avec lecture du dépôt ; réseau officiel pour les vérifications externes autorisées ; application locale CPU uniquement."
metadata:
  origin: "project-authored"
  version: "2.1"
  project: "RAG-LOCAL-16"
---

# Qualification locale CPU et maintien

## Entrée et périmètre

Machine inventoriée, corpus/profil identifiés, runtimes réels et changement précis à qualifier. Lire [QUALIFICATION.md](../../QUALIFICATION.md), [CONFIGURATION.md](../../CONFIGURATION.md) et les critères D07–D10 de la [DoD](../../DEFINITION_OF_DONE.md).

## Exécution

1. Consulter sources officielles, compatibilité et migrations des composants modifiés selon [RECHERCHE_ET_SKILLS.md](../../RECHERCHE_ET_SKILLS.md). Préserver un état restaurable ; verrouiller l'artefact après essai, pas avant preuve.
2. Inventorier CPU, OS, RAM hôte, swap, SSD, navigateur et versions. Inclure les services et le navigateur Windows natifs. Ne pas remplacer un test cible par une mesure sur un serveur plus puissant.
3. Mesurer séparément chargement, recherche, traitement du prompt, premier token et débit de sortie. Distinguer modèle froid, modèle résident, préfixe réutilisé et latence de la chaîne entière.
4. Tester pause coopérative, libération de mémoire, reprise et coût des chargements. Pas de mesures lourdes concurrentes, ni de kill périodique présenté comme une optimisation.
5. Vérifier l'application après blocage des sorties réseau non-loopback, sur un périmètre de test explicitement contrôlé. Ne pas désactiver globalement les protections ou la connectivité de l'utilisateur sans autorisation.
6. Tester une seule optimisation motivée ; comparer qualité ET ressources, puis arrêter la variante ou revenir à la baseline. Une mise à jour n'invalide que les caches concernés.

## Sortie et limites

Rapport avec machine, versions, corpus, commandes, unités, distributions et statut PASS/FAIL/BLOCKED/NOT_RUN. Aucun chiffre inventé ni qualité masquée par une sortie secrètement raccourcie. La taille du fichier modèle ne vaut pas pic RAM. Les contrôles documentaires ne sont pas des mesures du runtime.
