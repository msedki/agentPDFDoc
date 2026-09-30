# Changements intégrés — baseline documentaire 2.1

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md).

**Date :** 29 septembre 2026. **Remplace :** baseline documentaire 1.0.

Les corrections ci-dessous sont **appliquées aux fichiers de réalisation**, pas annoncées comme déjà implémentées dans le logiciel. Les anciennes archives restent inchangées. Cette archive V2.1 ne contient pas de copie concurrente de la V1 ou de l'audit à appliquer manuellement.

| Audit | Correction intégrée | Fichiers canoniques concernés | Preuve produit demandée |
|---|---|---|---|
| A01 | Couverture finale des identifiants après RRF et coupe de contexte | IMPLEMENTATION, SPEC_ARCHITECTURE, DoD, config | Cas adverse exact absent du top dense |
| A02 | Routage Docling natif/structuré/OCR régional ; page mixte couverte | SPEC_ARCHITECTURE, CONFIGURATION, QUALIFICATION | Table scannée avec paragraphe natif, sans double texte |
| A03 | Pause coopérative ; reprise manuelle initiale ; watchdog séparé | SPEC_ARCHITECTURE, IMPLEMENTATION, CONFIGURATION, config | Chat/import sans kill périodique ni rechargements inutiles |
| A04 | Qualification CPU précoce ; chargement/prompt/sortie/cache séparés | QUALIFICATION, DoD, PLAN | Mesures sur hôte cible complet |
| A05 | E5 baseline et un seul candidat comparatif vérifiable | DECISIONS, CONFIGURATION, IMPLEMENTATION, QUALIFICATION | Décision justifiée ; absence de candidat non transformée en benchmark |
| A06 | Budget de contexte par mode et contrats de suivi conversationnel | IMPLEMENTATION, SPEC_ARCHITECTURE, config | Preuve réellement envoyée et référent autorisé |
| A07 | Offsets Unicode sur texte source hashé ; budget global de pixels | IMPLEMENTATION, DoD, config | Sélection caractères complexes et contrôle raster |
| A08 | Dataset 200/100/100, dénominateurs et métriques de contexte final | QUALIFICATION, DoD, config | Résultats par catégorie et incertitude |
| A09 | Placement Qdrant qualifiable, graphe RAM initial ; mapping de schéma explicite | CONFIGURATION, config, QUALIFICATION | Configuration effective relue et RAM mesurée |
| A10 | Invariants fixes, paramètres qualifiés, vérifications indépendantes | AGENTS, PROMPT_IMPLEMENTATION, PLAN, DECISIONS | Intégration verticale sans waterfall général |
| A11 | Frontières de checkpoint distinctes des structures ; révisions d'extraction | SPEC_ARCHITECTURE, IMPLEMENTATION, DoD | Section/table pages 4/5 et anciennes citations |
| A12 | Sources séparées canoniques, génération et vérification du brief | 00_LIRE_AVANT, tools, brief complet | Synchronisation automatiquement contrôlée |

## Précisions supplémentaires

La fiche et la publication officielles du candidat Granite issues de l'audit n'ont pas pu être reconfirmées pendant cette révision. Elles restent des références à vérifier, pas une preuve actuelle de supériorité. Le candidat ne devient donc pas une dépendance obligatoire de démarrage.

Les nettoyages d'index attendent les requêtes qui épinglent encore une génération ; l'identité d'extraction est distincte de la version PDF. Un changement d'embedding garde un espace dense séparé. La recette mesure aussi l'exactitude sur questions répondables afin qu'une abstention systématique ne fasse pas artificiellement réussir le soutien des assertions.

## Statut des vérifications

`CONTROLES_DOSSIER.json` décrit uniquement les contrôles exécutés sur les fichiers et les exemples de référence. Aucun résultat de runtime, de LLM, de PDF réel, de GPU/CPU cible ou de parcours navigateur complet n'est attribué à ces contrôles.


## Ajout V2.1 — sources et bons skills

Consigne utilisateur intégrée dans `AGENTS.md` et `PROMPT_IMPLEMENTATION.md` : consulter systématiquement les sources officielles pour étudier, décider et mettre à jour ; rechercher les bonnes pratiques/SOTA utiles sans essais aveugles ; lire les compétences pertinentes avant usage.

Création de `RECHERCHE_ET_SKILLS.md`, `SKILLS.md`, `CLAUDE.md` et cinq `skills/*/SKILL.md` propres au projet. D11 ajouté à la recette ; registres, plan, architecture, implémentation, qualification et configuration mis en cohérence. Sources officielles consultées pour la spécification et la méthode, avec limites d'accès explicites.

Les nouvelles règles s'appliquent aux agents de développement et ne modifient pas le fonctionnement hors ligne du produit. Les compétences externes ne sont ni installées ni supposées exécutées ; les skills projet restent des fichiers à intégrer et à tester dans le client réel.
