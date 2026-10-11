---
name: local-llm-qualification
description: Comparer et qualifier les modèles de génération locaux et les profils de mémoire de ce RAG avant leur sélection ou leur livraison. Utiliser pour une nouvelle famille, taille, quantification, tokenizer ou règle de choix selon la RAM ; compléter avec les skills runtime et kit de la plateforme.
metadata:
  origin: project-authored
  version: "1.0"
---

# Modèles locaux et profils de mémoire

Lire les décisions W045, W059 et W060, le lot R28-LLM-01 du
`RAG_Local_Agents/PLAN.md`, les profils existants, `config/models.lock.json`
et les contraintes de la DoD. La RAM supplémentaire permet une candidature,
pas une qualification. Cette procédure complète
`RAG_Local_Agents/skills/local-cpu-qualification/SKILL.md` ; elle ne remplace
pas la recette CPU sur un hôte physique de 16 Go maximum.

## Identifier puis qualifier

- Comparer les fiches officielles de familles pertinentes : langue française,
  fidélité documentaire, sortie structurée, licence, architecture et disponibilité
  dans la version d'Ollama effectivement livrée. Un benchmark d'éditeur reste
  distinct du résultat sur les questions et documents de ce projet.
- Identifier un artefact exact : référence, révision/digest, quantification,
  manifeste et couches, licence, tokenizer et template. Les tags courants sont
  mutables ; la taille téléchargée et le nombre de paramètres actifs d'un MoE
  ne donnent pas le pic RAM ni le débit. Ne pas appliquer la dérivation GGUF
  texte seul de Qwen à une autre architecture sans vérifier son contrat.
- Vérifier le comptage des messages réellement sérialisés : template,
  BOS/EOS, mode de raisonnement, schéma de sortie et enveloppe applicative.
  Confronter ce comptage aux compteurs natifs ; une différence reste un écart
  à résoudre, pas une raison de relever silencieusement le contexte.
- Comparer au modèle existant sur les mêmes entrées autorisées et critères :
  PDF/DOCX/XLSX, scopes, cache de formule absent, recherche, question, analyse,
  comparaison et citations. Une sortie JSON valide n'établit ni pertinence,
  complétude ni exactitude des faits. Conserver les sorties intégrales et échecs.
- Mesurer séparément CPU et GPU, chargement froid, prompt, premier token,
  débit, temps total, mémoire disponible et RSS/VRAM réellement observés.
  Inclure les services et la réserve système. Un seul essai lourd à la fois ;
  garder les ports, données et processus isolés du fonctionnement courant.

## Sélection et livraison

Déduire les seuils des mesures du profil complet, avec marge explicite.
Sélectionner selon la RAM physique lors de l'installation ; l'admission runtime
contrôle aussi la mémoire disponible. Le choix manuel reste explicite et les
profils admissibles doivent être qualifiés, présents et vérifiés dans le kit.
Une sélection automatique ne télécharge rien hors ligne. Conserver une voie
CPU de base et expliquer un refus ou un repli dans le diagnostic.

Après récolte des résultats, retirer les copies de fabrication, transports,
caches de tests et candidats devenus inutiles. Vérifier leurs références et
processus avant suppression ; conserver sources, données, preuves nécessaires
et retour arrière. Mettre à jour le suivi existant avec les résultats réels.

## Références officielles

Consultées le 11/10/2026 ; versions et limites tracées dans
`RAG_Local_Agents/SOURCES.md` :

- [Ollama : sortie structurée](https://docs.ollama.com/capabilities/structured-outputs)
  et [chat et comptage v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go).
- [Ministral 3, fiche du mainteneur](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512).
- [Gemma 4, fiche du mainteneur](https://huggingface.co/google/gemma-4-26B-A4B-it).
- [Qwen3.5, fiche du mainteneur](https://huggingface.co/Qwen/Qwen3.5-27B).

Ces références orientent la présélection ; aucune ne qualifie un profil local.
