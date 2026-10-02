---
name: project-documentation
description: Maintenir l'espace documentaire de ce dépôt, ses références stabilisées, ses procédures et sa traçabilité à partir du code et des preuves réelles. Ne couvre ni les changements fonctionnels ni la recette du frontend.
metadata:
  origin: project-authored
  version: "1.0"
---

# Documentation du système livré

## Entrée et sources

Lire les instructions applicables, les actions R14/R15/R22 de
`RAG_Local_Agents/PLAN.md` et l'index `docs/README.md`. Reprendre les documents
canoniques existants. Pour un changement de contrat, lire le code, ses tests et
la preuve d'exécution concernée ; une description ou un test avec doubles ne
prouve pas un fonctionnement réel.

Références de méthode consultées le 02/10/2026, consignées dans
`RAG_Local_Agents/SOURCES.md` (DOCS01 et DOCS02) :

- [Diátaxis](https://diataxis.fr/) : distinguer référence, explication et procédure
  selon le besoin du lecteur. Cette classification ne remplace pas la séparation
  vivant/stabilisé propre au dépôt.
- [Guide rédactionnel de Google](https://developers.google.com/style/highlights) :
  conditions avant instructions, liens descriptifs, formulations directes et
  dates non ambiguës. Adapter ces principes au français ; ne pas importer les
  conventions orthographiques anglaises.

## Maintien

- Le plan, les décisions, le journal et les preuves restent dans le dossier
  vivant `RAG_Local_Agents/`. Les références du système livré restent dans
  `docs/`. Un nouveau document n'est nécessaire que pour un rôle manquant.
- Chaque en-tête identifie rôle, propriétaire logique, statut, référence réelle,
  date UTC et source de vérité. Citer un commit ou le commit de base accompagné
  des modifications locales datées, jamais un commit futur supposé.
- Une exigence reste distincte d'un comportement constaté. Les spécifications
  associent règle métier, comportement, cas limite et critère d'acceptation aux
  contrats et à la DoD sans recopier leurs seuils ou états volatils.
- Une procédure précise prérequis, environnement et cible, commandes exactes
  tirées des scripts, effets persistants, vérifications et reprise/retour arrière.
  Signaler une voie écrite mais non exécutée ; ne pas exécuter une installation,
  migration ou suppression pour la seule rédaction.
- Référencer les plateformes et versions réellement vérifiées. Un essai Linux
  ne qualifie pas Windows, un test isolé ne qualifie pas un poste vierge.
- Rédiger pour l'action du lecteur : termes du domaine, limites précises,
  messages exploitables. Retirer promesses, emphase et remplissage. Une table ou
  un SVG n'est utile que s'il clarifie une relation ou une procédure.

## Validation et livraison

Relire les affirmations modifiées contre leurs sources, puis exécuter les
contrôles concernés : `test_docs_space.py`, `test_docs_tooling.py`,
`tools/docs/check_docs.py`, `tools/docs/diagrams.py --check`, génération et
contrôle du brief, `RAG_Local_Agents/tools/verify_pack.py` avec un rapport neuf
sous `.runtime/qa/`. Mettre à jour l'empreinte de ce skill dans le registre s'il
change. Ces contrôles de structure ne prouvent pas la justesse des procédures.

Faire relire indépendamment un nouveau contrat ou dossier d'exploitation.
Consigner résultats et limites dans le suivi existant, sans fermer R14/R22 si
leurs procédures réelles restent non exécutées. Les textes affichés par
`apps/web` suivent le skill `pdf-workspace-web` et sa validation de rendu.
