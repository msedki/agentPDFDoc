# Recette visuelle et ergonomique de l'atelier — 30 septembre 2026

**Rôle :** rapport de recette du lot R20 (documentation vivante) : défauts relevés sur captures du corpus réel, principe enfreint, source officielle, correction et preuve. **Statut :** premier passage clos ; points ouverts en fin de document. **Date :** 30 septembre 2026, 22:53 UTC. **Base :** captures avant `apps/web/reports/visual-qa-20260930T1849/` (build du commit `10b5dd9`), après `apps/web/reports/visual-qa-20260930T2015/` (contenu du commit `6935e13`) ; E2E [lecture seule et recette visuelle 12/12](../../apps/web/reports/e2e-2026-09-30-r20-final-2015-evidence.json).

## Méthode

Parcours réels de l'atelier sur l'instance principale, avec les documents du corpus `PDF/` importés (65 documents, 4 extraits), capturés à 1366×768 et 1920×1080, puis à 900×700 pour la largeur réduite (scénario `tests/e2e/visual-qa.spec.ts`, activé par `RAG_E2E_VISUAL_QA=1`). Chaque capture a été relue à l'écran ; un défaut n'est retenu que s'il est visible sur la capture ou reproduit dans l'interface. La grille d'analyse vient des sources ci-dessous, consultées le 30/09/2026 ; la référence de forme reste [decodair](ui-reference-decodair-2026-09-30.md).

| Id | Source | Version ou date | Ce qui est retenu |
|---|---|---|---|
| UX01 | [WCAG 2.2](https://www.w3.org/TR/WCAG22/) (W3C) | Recommandation du 12/12/2024 | 1.3.1 Info et relations, 1.4.11 contraste non textuel (3:1), 2.4.6 titres et étiquettes, 2.4.7 focus visible, 2.4.11 focus non masqué |
| UX02 | [Understanding 4.1.3 Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | WCAG 2.2 | Un message d'état (attente, progression, résultat) doit être restitué sans prendre le focus |
| UX03 | [Understanding 3.2.4 Consistent Identification](https://www.w3.org/WAI/WCAG22/Understanding/consistent-identification.html) | WCAG 2.2 | Une même fonction porte la même identification d'une vue à l'autre |
| UX04 | [Understanding 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | WCAG 2.2 | Cibles d'au moins 24 × 24 px CSS |
| UX05 | [WAI-ARIA APG, motif Button](https://www.w3.org/WAI/ARIA/apg/patterns/button/) | Non datée sur la page | Bouton bascule : `aria-pressed`, étiquette inchangée quand l'état change |
| UX06 | [WAI-ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/), rôles `progressbar` et `status` | Recommandation du 06/06/2023 | Une barre d'avancement décrit un travail long en cours ; un statut est un message indicatif |
| UX07 | [GOV.UK Design System, Tag](https://design-system.service.gov.uk/components/tag/) | Non datée sur la page | Statuts par adjectifs, jamais par la couleur seule ; un tag n'a pas l'air cliquable |
| UX08 | [GOV.UK Design System, Error message](https://design-system.service.gov.uk/components/error-message/) | Non datée sur la page | Dire ce qui s'est passé et comment corriger, sans jargon ni code |
| UX09 | [Nielsen Norman Group, 10 heuristiques](https://www.nngroup.com/articles/ten-usability-heuristics/) | J. Nielsen, mise à jour du 30/01/2024 | 1 visibilité de l'état, 2 langage de l'utilisateur, 8 design minimaliste, 9 erreurs en langage clair sans code |

## Défauts corrigés

| # | Constat sur les captures d'avant | Principe (source) | Correction | Preuve |
|---|---|---|---|---|
| 1 | Bandeau de contexte : « 65 exclus : 61 indexation en pause, 4 extraction partielle à publier » (accords faux) | Texte exact dans la langue de l'utilisateur (UX09 n° 2) | Accords singulier et pluriel par libellé | Capture après 01 et 05 ; `tests/unit/panel-state.test.ts` |
| 2 | Périmètre répété trois fois sous deux libellés (puce « Bibliothèque entière », sélecteur « Toute la bibliothèque », ligne cochée de l'arborescence) | Une même notion, un même nom (UX03) ; information redondante (UX09 n° 8) | Puce masquée pour toute la bibliothèque | Captures 01 à 05 après |
| 3 | Sous-titre décoratif « Réponses avec sources » dans l'en-tête du panneau d'analyse | Titres qui décrivent leur contenu (UX01 2.4.6), design minimaliste (UX09 n° 8) | Sous-titre retiré ; les autres sur-titres restent (point ouvert A) | Captures 02 avant et après |
| 4 | Documents dont le traitement est en pause affichés « En attente », partiels bloqués « Indexation en cours » ; indicateur global « Index en retard » alors que rien ne progressait | Visibilité de l'état réel (UX09 n° 1) | États du document réalignés sur le dernier traitement (correctif serveur) ; libellés « Extraction partielle à publier », « Traitement annulé » ; indicateur « Index incomplet » | Captures 02 et 05 avant et après ; `test_api_jobs.py`, `status.test.ts` |
| 5 | Suivi : 61 traitements en pause listés avant ce qui attend une décision, sans résumé | Visibilité de l'état et priorité à l'action attendue (UX09 n° 1) | Tri par besoin d'attention (décisions, échecs, en cours, pauses, annulés, terminés) et résumé des groupes | Capture 05 après ; `jobs-view.test.ts` |
| 6 | Suivi : aucune action groupée pour 61 pauses (61 boutons « Reprendre ») | Efficacité, minimalisme (UX09 n° 8) | « Reprendre les 61 indexations en pause », tout ou rien côté serveur | Capture 05 après ; `test_api_resume_paused` |
| 7 | Modes « Priorité aux questions / aux imports » sans état sélectionné visible ni exposé | Bouton bascule avec `aria-pressed`, étiquette fixe (UX05) ; information non portée par la seule présentation (UX01 1.3.1) | `aria-pressed` et mise en évidence du mode actif, étiquettes inchangées | Capture 05 après ; `jobs-panel` |
| 8 | Barres d'avancement grises pleines pour des traitements en pause, lues comme « terminé » | Une barre d'avancement décrit un travail en cours (UX06) ; état visible et juste (UX09 n° 1) | Avancement affiché seulement pendant un calcul | Captures 05 avant et après |
| 9 | Limites d'extraction affichées par code brut, répétées (« Le service signale une limite sans la décrire (code GRAPHIC_INTERPRETATION_UNAVAILABLE) ») | Pas de code, dire ce qui se passe et quoi faire (UX08, UX09 n° 9) | Intitulé, conséquence et pages pour chaque code d'extraction, regroupés par code | Capture 05 après ; `warnings-grouped.test.ts` |
| 10 | Traitement remplacé par un plus récent présenté comme une décision à prendre | Visibilité de l'état réel (UX09 n° 1) | Étape « remplacé par un traitement plus récent », exclu des décisions | `jobs-view.test.ts` |
| 11 | Écran « Session requise » : « Vérifier de nouveau » sans apparence de bouton | Composant identifiable et contrasté (UX01 1.4.11) | Bouton secondaire bordé (`session-gate.tsx:86`) | Capture 11 après |

Contrôles associés : 130 tests unitaires web, `tsc`, build, E2E en lecture seule 12/12, dont l'ordre de tabulation, le focus visible à chaque arrêt clavier, les onglets à tabulation mobile et les séparateurs redimensionnables au clavier (`tests/e2e/a11y.spec.ts`), et 3 scénarios de session.

## Points ouverts (non corrigés)

| Id | Observation sur les captures d'après | Classement | Suite proposée |
|---|---|---|---|
| A | Sur-titres encore présents : « Lecture de l'original » au-dessus du nom du document, « Périmètre actif » dans l'analyse, « Poste documentaire local » dans l'en-tête | Amélioration : « Lecture de l'original » distingue l'original du texte extrait, mais le libellé du bas (« Texte extrait & provenance ») porte déjà cette distinction | Trancher par panneau ; garder seulement les sur-titres qui portent une information |
| B | Arborescence défilée : la ligne fixe « Toute la bibliothèque » recouvre en partie l'élément suivant | Hypothèse à vérifier : un élément de l'arbre qui prend le focus au clavier pourrait être entièrement masqué par la ligne fixe (UX01 2.4.11) | Test clavier sur une arborescence longue ; `scroll-padding-top` si le masquage est reproduit |
| C | Noms de documents tronqués dans l'arborescence | Inconnue : nom complet non vérifié au survol ni au lecteur d'écran | Vérifier le nom accessible et l'info-bulle |
| D | Aucun contrôle automatique d'accessibilité (axe ou équivalent) ni essai avec un lecteur d'écran | Limite de la recette | Ajouter un contrôle automatique aux E2E ; un passage NVDA sur les parcours principaux |
| E | Contrastes non mesurés par outil (lecture visuelle seulement) | Limite de la recette | Mesurer les jetons de couleur contre 4,5:1 (texte) et 3:1 (composants) |

## Limites

Captures sur un seul poste (Windows 11, Chromium de Playwright, zoom 100 %) ; aucun test utilisateur ; le corpus ne comptait que 4 documents extraits sur 65, et les états à 61 pauses sont ceux d'une situation de chantier.
