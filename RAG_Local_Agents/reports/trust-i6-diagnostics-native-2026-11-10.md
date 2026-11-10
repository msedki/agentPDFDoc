# Bilan technique natif I6R-06 — R4

**Rôle :** bilan technique des vingt positions et de leurs ressources.
**Propriétaire :** qualification native RAG.
**Statut :** exécuté, revue documentaire distincte.
**Date :** 10 novembre 2026 UTC.

Référence `0574f4e21ccaf95b25a48c6e226369376681ac18` ; candidat `522d86839d5c803c57daec0e799bfa48ee5aa8e7`.

Huit blocs séquentiels, vingt positions, une répétition. Les vingt positions passent le protocole technique gelé ; six échanges 4B ont un `received_done` réel. Les dix registres rendus du candidat ont été recalculés et vérifiés. La référence conserve son absence historique de ce registre. La relecture documentaire indépendante reste un verdict séparé.

| Bloc | Positions | Appels 4B terminés | Latence requêtes (s) | Pic RSS / PSS bloc (MiB) | Disponible min (MiB) | Technique | HTTP historique |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 01-baseline-original6 | 6 | 0 | 0.105–0.174 | 716.7 / 709.7 | 5920.2 | PASS | sans objet |
| 02-candidate-original6 | 6 | 0 | 0.106–0.177 | 718.2 / 710.8 | 6121.0 | PASS | sans objet |
| 03-baseline-selection2 | 2 | 2 | 25.402–45.074 | 4047.6 / 4038.8 | 2877.5 | PASS | sans objet |
| 04-candidate-selection2 | 2 | 2 | 44.968–79.239 | 3955.2 / 3946.8 | 2326.4 | PASS | sans objet |
| 05-baseline-http_conflict | 1 | 0 | 0.187–0.187 | 724.1 / 716.7 | 6122.0 | PASS | FAIL conservé |
| 06-candidate-http_conflict | 1 | 0 | 0.196–0.196 | 724.6 / 717.3 | 6021.9 | PASS | FAIL conservé |
| 07-baseline-http_selection | 1 | 1 | 58.452–58.452 | 3918.3 / 3910.3 | 2856.4 | PASS | PASS |
| 08-candidate-http_selection | 1 | 1 | 56.571–56.571 | 3967.1 / 3958.7 | 2956.3 | PASS | PASS |

Les deux FAIL HTTP historiques restent inchangés : le harnais exigeait un appel modèle, alors que le conflit doit suivre la route déterministe. Le diagnostic distinct exige zéro échange sur conflit et un échange 4B réel sur sélection. Les autres exigences HTTP (texte exact, ordre sources/deltas, terminal unique, reprise, versions, ingestion native et arrêt) sont conservées.

Les 24 reçus d’arrêt de groupes possédés, répartis dans les huit blocs, indiquent des groupes vides et des leaders récupérés ; les quatre listeners API sont fermés. Aucun timeout, aucune répétition favorable, aucune modification des sources mesurées ou du GGUF. L’état Git propre des deux bras a été capturé avant la reprise des travaux de documentation dans `campaign-source-end-state.json`.

## Contexte des mesures

Hôte Linux, 9 processeurs logiques visibles, 10 451 427 328 octets de mémoire physique rapportés ; CPU seul, Qwen3-4B Q4_K_M verrouillé, Ollama 0.35.0, Qdrant 1.19.1. Cette exécution ne qualifie ni Windows ni une machine physique de 16 Go. RSS/PSS sont des sommes de processus échantillonnées ; les requêtes déterministes très brèves ont seulement un ou deux échantillons.

Les sélections directes RX742/KX563 prennent 45,07/25,40 s en référence et 44,97/79,24 s sur candidat. Après RX742 candidat, la politique adaptative a confirmé le déchargement du modèle : mémoire disponible 2326 MiB, sous le seuil 2560 MiB. KX563 a donc rechargé le modèle. Le contexte mémoire et une seule répétition empêchent d’attribuer la différence à une évolution générale des performances.

## Preuves

`technical-aggregate.json` donne chaque position, route, requête/réponse modèle, mesure et empreinte. `rendered-evidence.json` reprend les textes exacts, citations, diagnostics et événements de registre avec les liens vers leurs preuves brutes. `evidence-allowlist.json` fournit les seuls chemins et empreintes à exporter. Les bases, HOME, caches, modèles, configurations privées et logs de service sont exclus. Aucun export récursif n’est nécessaire.
