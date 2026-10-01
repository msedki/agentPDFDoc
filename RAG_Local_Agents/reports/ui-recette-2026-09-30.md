# Recette visuelle et ergonomique de l'atelier — 30 septembre 2026

**Rôle :** rapport de recette du lot R20 (documentation vivante) : défauts relevés sur captures du corpus réel, principe enfreint, source officielle, correction et preuve. **Statut :** premier passage clos ; second passage du 1er octobre (03:10 UTC, commit `49a2a1a`) : points B, C et E examinés, deux défauts corrigés ; A tranché (sur-titres conservés) ; reste ouvert D. **Date :** 30 septembre 2026, 22:53 UTC. **Base :** captures avant `apps/web/reports/visual-qa-20260930T1849/` (build du commit `10b5dd9`), après `apps/web/reports/visual-qa-20260930T2015/` (contenu du commit `6935e13`) ; E2E [lecture seule et recette visuelle 12/12](../../apps/web/reports/e2e-2026-09-30-r20-final-2015-evidence.json).

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
| UX10 | [Understanding 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | WCAG 2.2, consulté le 01/10/2026 | « Where a text-input has a visual indicator to show it is an input, such as a bottom border […], that indicator must meet 3:1 contrast ratio » ; un contrôle porteur d'un texte ou d'une icône assez contrastée n'a pas besoin de bordure ; l'indicateur de focus reste exigé |

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

## Points ouverts au premier passage

| Id | Observation sur les captures d'après | Classement | Suite proposée |
|---|---|---|---|
| A | Sur-titres encore présents : « Lecture de l'original » au-dessus du nom du document, « Périmètre actif » dans l'analyse, « Poste documentaire local » dans l'en-tête | Amélioration : « Lecture de l'original » distingue l'original du texte extrait, mais le libellé du bas (« Texte extrait & provenance ») porte déjà cette distinction | Clos le 01/10 : sur-titres conservés, voir le second passage |
| B | Arborescence défilée : la ligne fixe « Toute la bibliothèque » recouvre en partie l'élément suivant | Hypothèse à vérifier : un élément de l'arbre qui prend le focus au clavier pourrait être entièrement masqué par la ligne fixe (UX01 2.4.11) | Clos le 01/10 : hypothèse infirmée, voir le second passage |
| C | Noms de documents tronqués dans l'arborescence | Inconnue : nom complet non vérifié au survol ni au lecteur d'écran | Clos le 01/10 : nom complet vérifié, voir le second passage |
| D | Aucun contrôle automatique d'accessibilité (axe ou équivalent) ni essai avec un lecteur d'écran | Limite de la recette | Ajouter un contrôle automatique aux E2E ; un passage NVDA sur les parcours principaux |
| E | Contrastes non mesurés par outil (lecture visuelle seulement) | Limite de la recette | Clos le 01/10 : contrastes mesurés, bordures de champ corrigées (défaut 12) |

## Second passage — 1er octobre 2026

Examen des points B, C et E, de 02:46 à 03:10 UTC, sur l'instance principale. Contrôles : 133 tests unitaires web, `tsc`, build ([journal](../../apps/web/reports/build-2026-10-01-contrastes-legende.log)), E2E en lecture seule 11 réussis et 20 non autorisés (import, génération, cycle de vie, sonde mémoire ; [preuve](../../apps/web/reports/e2e-2026-10-01-contrastes-legende-0304-evidence.json)), recette visuelle 4/4 après correction de son attente ([preuve](../../apps/web/reports/e2e-2026-10-01-recette-visuelle-0307-evidence.json), [captures](../../apps/web/reports/visual-qa-20261001T0307/)). Captures intermédiaires conservées : [visual-qa-20261001T0258](../../apps/web/reports/visual-qa-20261001T0258/) (bordures corrigées, défaut 13 visible sur `02-document-ouvert-1920x1080.png`).

**Point B, infirmé par le code et les captures.** La ligne « Toute la bibliothèque » n'est pas superposée à l'arbre : elle est un élément de flux (`.library-all`, `flex: none`, [globals.css:166](../../apps/web/src/app/globals.css#L166)) placé au-dessus du conteneur défilant de l'arbre (`.tree`, `flex: 1; min-height: 0; overflow: auto`, [globals.css:169](../../apps/web/src/app/globals.css#L169) ; structure [library-panel.tsx:129-130](../../apps/web/src/components/library-panel.tsx#L129-L130)). La ligne coupée sur les captures est rognée par le bord haut du conteneur défilant, pas recouverte ; un élément qui prend le focus est ramené dans la zone visible de ce conteneur par le navigateur. Le parcours clavier de `a11y.spec.ts` (focus visible à chaque arrêt) reste vert.

**Point C, vérifié.** Le bouton d'un document porte le nom complet en texte, l'info-bulle donne le chemin relatif (`title={document.relative_path}`) et la case porte « Sélectionner <nom> » ([library-panel.tsx:104-106](../../apps/web/src/components/library-panel.tsx#L104-L106)) : la troncature est seulement visuelle. Essai au lecteur d'écran non fait (point D).

**Point E, mesuré.** Les contrastes sont calculés à partir des jetons de [theme.css](../../apps/web/src/app/theme.css) par `tests/unit/accessibility.test.ts` et `ui-guards.test.ts` : textes, placeholders, badges, boutons au repos et au survol, pastilles d'état et indicateur de focus étaient déjà couverts. Valeurs relevées : encre 11,8 à 14,6:1 et texte secondaire 4,75 à 5,9:1 sur toutes les surfaces ; anneau de focus 4,8 à 5,9:1. Seules les bordures de champ n'étaient pas mesurées, et elles échouaient (défaut 12).

| # | Constat | Principe (source) | Correction | Preuve |
|---|---|---|---|---|
| 12 | Bordure des champs (`--input` #C9CFC9) à 1,27–1,57:1 ; le filtre de bibliothèque et le numéro de page utilisaient même le filet décoratif `--border` (1,17–1,41:1). Pour la zone de question, les listes de portée et le numéro de page, cette bordure est le seul repère de l'emplacement du champ | Indicateur d'un champ de saisie à 3:1 (UX10, UX01 1.4.11) | `--input` porté à #788778 ; filtre et numéro de page passés sur `--input` ; mesure : 3,45:1 sur le fond, 3,76:1 sur les cartes et popovers, 3,57:1 sur la bibliothèque, au moins 3,05:1 sur toutes les surfaces | Test « field borders keep 3:1… » (`accessibility.test.ts`), rouge avant correction (1,57:1) ; captures 01 et 03 de [0307](../../apps/web/reports/visual-qa-20261001T0307/) |
| 13 | Pendant le rendu d'une page, la légende affichait « Aucun texte extrait » sur une page à texte natif (capture 02 à 1920×1080 de [0258](../../apps/web/reports/visual-qa-20261001T0258/)) : l'état initial « pas de texte » était affiché comme un résultat | Visibilité de l'état réel (UX09 n° 1) | Légende « Lecture de la page… » tant que la couche texte de PDF.js ou les blocs sont en lecture (`pageTextCaption`, [ocr-overlay.ts](../../apps/web/src/lib/ocr-overlay.ts)) ; la recette visuelle attend la légende finale au lieu d'une attente fixe de 1,5 s | Test « the page caption states no text only once… » (`ocr-overlay.test.ts`) ; capture 02 de [0307](../../apps/web/reports/visual-qa-20261001T0307/) avec « Texte natif ». L'état intermédiaire n'a pas été capturé : le rendu a été plus rapide lors de la seconde exécution |

**Point A, tranché : sur-titres conservés.** Chacun porte une information que le titre seul ne donne pas : « Lecture de l'original » distingue la page PDF du texte extrait affiché en dessous ; « Périmètre actif » est le libellé de la valeur affichée sous lui ; « Poste documentaire local » situe l'atelier sur le poste, sans service distant. Le motif suit la référence de forme decodair, qui l'emploie dans plus de quinze écrans ([analyse](ui-reference-decodair-2026-09-30.md)). Le sous-titre décoratif de l'analyse avait déjà été retiré (défaut 3).

La recherche dans le lecteur (`.viewer-search`) n'a pas de bordure : son icône de loupe (5,9:1) et son texte l'identifient, ce que UX10 admet ; elle n'est pas modifiée.

## Limites

Captures sur un seul poste (Windows 11, Chromium de Playwright, zoom 100 %) ; aucun test utilisateur ; le corpus ne comptait que 4 documents extraits sur 65, et les états à 61 pauses sont ceux d'une situation de chantier.
