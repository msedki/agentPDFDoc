---
name: pdf-workspace-web
description: Construire ou vérifier le poste documentaire local Next.js/PDF.js de ce projet, avec périmètres versionnés, API FastAPI, citations et lecture hors ligne. À utiliser pour apps/web, pas pour l'extraction ou le provisionnement des modèles.
---

# Poste documentaire web local

Lire les contrats utiles dans `RAG_Local_Agents/SPEC_ARCHITECTURE.md` §3–5,
`IMPLEMENTATION.md` §2–3 et `DEFINITION_OF_DONE.md` D06/D08, puis
`packages/contracts/contracts.json` lorsqu'il existe. Ces documents définissent
le produit ; les références officielles ci-dessous définissent les APIs externes.

## Invariants de mise en œuvre

- Export Next.js statique, route `/workspace/`, IDs dans la query string. Aucun
  serveur Next, Server Action, endpoint API Next ou proxy requis à l'exploitation.
  Les requêtes REST/SSE et les originaux viennent de la même origine `/api/v1`.
- Distinguer état UI Zustand et état serveur TanStack Query. Recharger les états
  après import/indexation ; ne pas inventer progression, corpus ni réponse.
- Un scope est une action explicite. Le défilement, l'ouverture d'un PDF et le clic
  d'une citation ne changent jamais le périmètre. Une réponse garde son snapshot.
- Charger PDF.js dans le navigateur. Copier worker, cmaps, wasm et polices
  standard depuis la même version verrouillée de `pdfjs-dist` vers les assets
  locaux au build. Annuler/détruire chargements, renders et text layers remplacés.
  Les styles TextLayer viennent de la version installée : total scale/UserUnit,
  rotations et positions absolues doivent rester cohérents avec le canvas.
  Attacher immédiatement les handlers de `RenderTask.promise` pendant les awaits
  texte/fontes, pour que l'annulation du render ne devienne pas un rejet non géré.
- Borner à cinq canvases haute résolution et 24 millions de pixels RGBA au total
  (miniatures comprises) ; charger pages/blocs au voisinage du
  viewport. Transformer bboxes PDF canoniques avec le viewport PDF.js complet,
  rotation et CropBox compris. Ne pas fabriquer une bbox à partir d'un extrait.
- Pour sélectionner une preuve, envoyer des IDs de blocs, révision d'extraction,
  hash du texte immuable et offsets en points de code Unicode reconnus par
  le backend. Si la sélection native ne se réconcilie pas, montrer la limite et
  proposer l'analyse de page/bloc disponible ; aucun texte client autoritaire.
- Les citations sont cliquables seulement lorsqu'enregistrées dans les sources
  de la query. Afficher version, page et précision réelle (span/bloc/table/page),
  garder un retour à la position précédente. Les réponses ne rendent ni HTML
  actif, ni images distantes. Une référence inconnue reste signalée.
- Pour une citation enregistrée, charger blocs et sommaire avec sa révision
  d'extraction exacte ; isoler aussi les clés de cache par révision. Vérifier
  version, page et révision retournées, sans substitution par la plus récente.
  Le retour conserve la source précédente et son identité. Un deep-link de
  citation résout query/source dans le vrai registre avant ouverture : IDs
  invalides, source inconnue ou révision absente restent une erreur visible.
- Vérifier la révision publiée courante avant d'interdire les périmètres page/
  section sur une citation archivée : leur contrat ne fixe pas la révision.
  Une citation courante garde ces actions ; une ancienne révision garde
  l'analyse de sélection/bloc exact. L'ouverture seule ne modifie aucun scope.
- Les hits de recherche peuvent exposer version/blocs sans ID de citation.
  Afficher nom/page réels et « Passage », sans fabriquer de `Sxxx` ni interroger
  le registre. Les warnings peuvent être des objets : afficher message/code
  sûr, jamais l'objet React ni des détails arbitraires.
- Un flux SSE se reconnecte au query ID avec le dernier event ID, sans renvoyer
  POST `/queries`. Les annulations et fins interrompues gardent leur statut.
- Trois panneaux lisibles, repliables et redimensionnables, focus clavier visible,
  états vides/erreurs exploitables. Les contrôles désactivés indiquent pourquoi.

## Textes de l'interface

Chaque libellé, aide, info-bulle, état vide et message d'erreur dit ce qui se passe
et ce que l'utilisateur peut faire, avec le vocabulaire du poste documentaire
(document, version, page, bloc, périmètre, source, extraction, indexation). Pas de
formule générique ni de texte d'ambiance ; un code technique brut n'est jamais
affiché seul (le traduire, garder le code en info-bulle ou en diagnostic). Les
mêmes termes désignent les mêmes objets dans toutes les vues ; relire les textes
modifiés avec la section « Documentation et textes de l'interface » du `CLAUDE.md`
racine.

Pour le shell, la charte et les composants, partir de la référence de forme
`D:\enhacements\decodair` décrite dans `RAG_Local_Agents/reports/ui-reference-decodair-2026-09-30.md`
(principes adaptés, pas de copie du branding ni du métier).

## Contrôle proportionné

Avant changement, vérifier les instructions de la zone. Verrouiller les versions
compatibles avec Node présent, puis type-check/build sous le créneau convenu.
Pour D06, utiliser Playwright sur l'API réelle : import → lecture → recherche/question
→ citation → retour, et changement de scope, rotation/zoom, arrêt/reconnexion.
Un test à réponses interceptées est un test UI isolé ; il ne valide pas la chaîne.
Examiner le rendu à 1366×768 et 1920×1080 et relever requêtes non-loopback,
erreurs console, compte de canvases et précision des overlays.
Les locators d'un document ciblent l'arborescence ; son nom figure également
dans le bouton de périmètre et ne distingue donc pas un bouton globalement.
Un statut terminal d'erreur fait échouer la recette immédiatement : ne pas
attendre une réponse absente, modifier l'admission ou renvoyer la question.
Conserver le SSE brut, query ID, scope et le fait qu'un moteur a été appelé ou
non. Les budgets de sortie ne sont pas des tokens réellement produits.
Sur Windows, la sonde navigateur part du PID vivant de son propre worker Node
et de `psutil.Process(pid).children(recursive=True)` ; relever RSS, private et
USS séparément, sans visiter les processus utilisateur ni sommer la RAM partagée.
Un nouveau relevé ne reconstitue pas une mesure historique manquante. Garder le
headless shell et les options Playwright par défaut tant qu'une source officielle
et un essai autorisé ne justifient pas un changement précis.

## Sources officielles

Consultées le 30 septembre 2026 ; vérifier les signatures dans les dépendances
installées avant de se fier aux guides de la version courante.

- [Next.js, export statique](https://nextjs.org/docs/app/guides/static-exports) :
  `output: 'export'`, limites serveur et accès navigateur après montage.
- [PDF.js, exemples](https://mozilla.github.io/pdf.js/examples/) et
  [API du mainteneur](https://github.com/mozilla/pdf.js/blob/master/src/display/api.js) :
  `getDocument`, viewport, RenderTask et assets. Si le site des exemples est
  inaccessible, lire les sources/types de la version installée, pas un tutoriel tiers.
- [React, useEffect](https://react.dev/reference/react/useEffect) : nettoyage des
  ressources externes et double montage de développement.
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview) :
  données serveur, cache et invalidation.
- [Zustand create](https://zustand.docs.pmnd.rs/reference/apis/create) et
  [persist](https://zustand.docs.pmnd.rs/reference/middlewares/persist) : hydratation
  navigateur et validation des valeurs persistées.
- [shadcn/ui, installation manuelle](https://ui.shadcn.com/docs/installation/manual) :
  composants locaux et utilitaire de classes ; éviter le CLI `latest` au runtime.
- [Tailwind, PostCSS](https://tailwindcss.com/docs/installation/using-postcss) :
  plugin local et CSS compilé, sans CDN.
- [Playwright, assertions](https://playwright.dev/docs/test-assertions) : assertions
  de comportements observables, traces et captures.
- [Playwright, navigateurs](https://playwright.dev/docs/browsers) et
  [BrowserType](https://playwright.dev/docs/api/class-browsertype) : headless shell
  par défaut sans `channel`, précautions sur les arguments personnalisés.
- [psutil, Process](https://psutil.readthedocs.io/stable/#psutil.Process) :
  descendants récursifs et distinction RSS/private Windows/USS.
- [Registre npm](https://registry.npmjs.org/) : métadonnées de versions et engines ;
  le tag `latest` sert seulement à résoudre une fois, jamais à identifier la livraison.
