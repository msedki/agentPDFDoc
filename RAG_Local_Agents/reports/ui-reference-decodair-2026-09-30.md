# Référence de forme decodair — principes retenus pour l'interface et le README

**Rôle :** analyse de référence qui fixe ce que l'on reprend de `D:\enhacements\decodair` et comment · **Statut :** Vivant (sert le lot R16, sera condensé en convention stabilisée après implémentation et validation) · **Référence :** decodair commit `afbf8e305`, agentragpdf commit `e6f7606` · **Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** ce fichier pour les choix ; `apps/web/src` pour l'état livré.

Analyse en lecture seule, faite par trois lecteurs indépendants (shell et charte, composants et états, README et documentation) puis relue par l'intégrateur. Aucune commande de build, de test ni de serveur n'a été lancée sur decodair ; les valeurs viennent du code (`frontend/src/…`) et de sa documentation. Les couleurs hexadécimales de decodair sont converties à la main depuis ses triplets HSL ; les ratios de contraste cités sont des calculs, pas des mesures outillées.

## Ce que l'on reprend, adapte ou écarte

La règle générale : les principes de structure, de hiérarchie, de densité et de réutilisation sont repris ; l'identité visuelle (orange brûlé, barre latérale chocolat, logo, polices chargées depuis Google Fonts) et tout le métier ferroviaire, multi-utilisateur ou Docker restent chez decodair.

### Shell applicatif

| Sujet | Decodair (preuve) | Décision pour agentragpdf |
|---|---|---|
| Structure | `h-dvh`, topbar pleine largeur puis rangée navigation / contenu, un seul conteneur qui défile par zone (`app-shell.tsx:130-193`) | **Repris.** Déjà en place (`.workspace-shell` 100dvh) ; chaque panneau garde son propre défilement. |
| Topbar | 56 px, trois zones : marque et bascule, recherche, actions icône 32-36 px nommées (`header-bar.tsx:111-336`) | **Adapté.** Passer de 66 px à 56 px : bascule bibliothèque + marque à gauche ; périmètre au centre ; état des services, Suivi avec compteur annoncé, Aide, bascule analyse à droite. Pas de compte, workspace ni PWA. |
| Barre latérale | Trois états étendue 240 px / réduite 64 px / masquée, bouton cyclique dont le libellé annonce l'action suivante, Ctrl/⌘+B (`app-shell.tsx:28-128`) | **Adapté.** Bibliothèque en trois états (largeur actuelle redimensionnable / rail de 64 px portant Importer, Filtrer, Sélection / masquée) avec Ctrl/⌘+B ; analyse en deux états. Préférences locales passées en v2 avec migration depuis `rag-local-panels-v1`. |
| Petits écrans | Sous 1024 px, menu en Sheet gauche 304 px (`mobile-navigation-menu.tsx`) | **Adapté.** Aujourd'hui, sous 760 px, bibliothèque et analyse deviennent inatteignables : les ouvrir en Sheets gauche et droit depuis la topbar, seuil `lg` (1024 px). |
| Bandeau de contexte | Sous la topbar : puce d'état, compteurs, filtres actifs, une action principale, rien si vide (`sticky-business-header.tsx`) | **Adapté.** Remplace la barre de périmètre de 48 px : puce de périmètre, documents interrogeables et exclus par motif, un seul emplacement de message (fusion de `.readiness-notice` et `.workspace-error`). |
| En-têtes | `PageHeader` h1 24 px, fil d'Ariane tronqué, retour distinct du fil | **Adapté.** En-têtes de panneau à 56 px (titre 14-15 px semibold, actions à droite) ; fil de l'emplacement du document dans le lecteur ; « Revenir au passage précédent » reste distinct. |
| Pied de page | Bande de 33 px avec signature de build honnête (« build non tracé » si inconnue) | **Adapté.** Pas de bande globale (coût vertical dans un lecteur) ; signature de build dans un menu Aide / À propos qui liste aussi les raccourcis en `<kbd>`. |
| Accessibilité structurelle | Lien d'évitement, zones nommées, un seul `aria-current`, focus ramené, `motion-reduce` | **Repris.** Liens d'évitement vers le lecteur et la zone de question, `aside` Bibliothèque / `main` Lecteur / `aside` Analyse, anneau de focus sur un token `--ring`. |
| Arrondis décoratifs de 6 px sur les bords du shell, barre latérale sombre, sélecteur d'applications, épinglage, bouton flottant | — | **Écartés** : décoratifs ou propres à une plateforme multi-domaines. |

### Charte

| Sujet | Decodair | Décision pour agentragpdf |
|---|---|---|
| Couleurs | Triplets HSL sémantiques sur `:root` exposés à Tailwind 4 par `@theme inline` ; tons `success`/`warning`/`info`/`destructive` ; statuts centralisés dans `lib/status-tokens.ts` | **Structure reprise, teintes propres conservées** : papier `#F6F4EE` (background), surface `#FFFEFA` (card), encre `#172B33` (foreground), `#5A666D` (muted-foreground), filet `#D9D9D1` (border), rouille `#A94324` (primary et ring ; blanc ≈ 6,0:1 calculé), `#F8E9DF` (accent), `#2D6950` (success). Aucune couleur en dur hors du fichier de thème, sauf liste argumentée (surlignages PDF). |
| Thème | Clair uniquement, décision laissée ouverte chez decodair | **Clair uniquement** (`color-scheme: light`) : la page PDF reste blanche ; les tokens isolés sur `:root` permettront un thème sombre plus tard. |
| Typographie | IBM Plex chargée depuis Google Fonts ; échelle 10/11/12/14/16/18/24 px ; mono pour les identifiants, `tabular-nums` pour les nombres | **Échelle reprise, chargement écarté** (poste hors ligne) : pile système sans-serif et mono locale ; plus aucun texte courant sous 11 px (agentragpdf descend aujourd'hui à 9 px), 10 px réservé aux sur-titres en capitales ; mono pour `source_id`, empreintes, versions, révisions. Georgia et Bahnschrift retirés. |
| Icônes | lucide 16 px dans les boutons (`[&_svg]:size-4`), 14 secondaires, 12 en pastille, 32 pour les états | **Repris.** Remplace les tailles 13/14/15/17 dispersées. |
| Densité | Grille de 4 px ; contrôles 32/36/40/44 px ; cellules compactes 12×6 px ; ombres réservées aux éléments flottants | **Repris** avec cibles tactiles d'au moins 44 px sous `lg`, 32 px pour la barre d'outils du lecteur, lignes d'arborescence de 40 px ; rayon unique de base 6 px ; trois niveaux d'ombre. |
| Responsive | Points de rupture Tailwind 640/768/1024/1280/1536, ordre de dégradation écrit, QA à 320/360/768/1024/1280/1440 | **Repris** : remplace les seuils codés 1100 et 760 px ; QA Playwright aux six largeurs. |

### Composants et états

| Sujet | Decodair | Décision pour agentragpdf |
|---|---|---|
| Primitives | Button, Badge, Dialog, Sheet, Tabs, Tooltip en variantes `cva`, `cn()` | **Repris sur besoin réel** : Badge, ConfirmDialog (remplace `window.confirm` du retrait de version), Sheet (Suivi des traitements), un seul composant d'onglets. Une seule forme par besoin (pas deux styles de carte ni deux systèmes d'onglets, écart constaté chez decodair). |
| États | `LoadingState`, `EmptyState`, `ErrorState` ; garde « une panne n'est pas un vide » | **Repris** en `PanelLoading` / `PanelEmpty` / `PanelError` rendus sous l'en-tête du panneau sans effacer son contenu ; distinguer « aucun document », « aucun résultat pour ce filtre », « index incomplet », « service local indisponible ». |
| Retours | Pas de toast : erreur sous l'action (`role="alert"`), libellé d'attente, liste atténuée pendant l'actualisation | **Repris** en `ActionButton` pour importer, réindexer, retirer, poser la question ; pas d'`alert()`. |
| Statuts | Pastilles avec libellé du glossaire, couleur jamais seule | **Repris** : chaque point de statut de document reçoit un libellé ; la précision de citation suit la famille exacte / page seule / non localisée. |
| Filtres | Pastilles actives supprimables, compte « N sur M », réinitialisation, portée annoncée avec exclusions | **Adapté** à la bibliothèque (filtres rapides d'état avec compte) et surtout au périmètre de question : documents interrogeables et exclus par motif affichés avant l'envoi. |
| Cartes de source | Ordre fixe en-tête / résultat / détails, métadonnées en liste `dl` | **Adapté** : `source_id` en mono, document, page, badge de précision, extrait de 3 lignes, une seule action « Ouvrir le passage ». |
| Gardes statiques | Tests Jest qui lisent `src/` : texte ≥ 10 px, boutons-icônes nommés, libellés associés, contraste AA, pas de couleur brute, erreur ≠ vide | **Repris en `node:test`** (déjà utilisé par `apps/web`), chaque garde vérifiant qu'elle examine bien une population. |
| Tables denses, tri, pagination | Contrat `DataTable` complet | **Non créé par mimétisme** : agentragpdf n'a pas de table ; le contrat s'appliquera si le suivi ou la qualification en demandent une. |

### README et documentation

| Sujet | Decodair | Décision pour agentragpdf |
|---|---|---|
| README | Sommaire numéroté, parcours comprendre → installer → configurer → exploiter → dépanner, tables normalisées, liens vers le code et les tests, dépannage symptôme → cause → commande, aveux d'état explicites | **Repris** pour un README racine en 21 rubriques adaptées au poste Windows natif. Écartés : 14 badges shields.io (images distantes), valeurs volatiles recopiées, étude de fonctionnalité dans le README, Mermaid et arbres ASCII (règle SVG du dépôt). |
| Organisation | 72 dossiers de chantier à plat sans index, séparation vivant / stabilisé portée par des bandeaux | **Adapté** : `docs/` ne contient que le stabilisé, avec index et en-tête obligatoire (Rôle, Statut, Référence, Mis à jour, Source de vérité, Remplace) ; `RAG_Local_Agents/` reste le dossier vivant (non déplacé : `build_brief.py` et `verify_pack.py` en dépendent). |
| CHANGELOG | Keep a Changelog en français, source de version unique | **Repris** pour un `CHANGELOG.md` produit à la racine (`[Non publié]` en tête, version de `pyproject.toml` égale à `apps/web/package.json`), distinct du registre de corrections de la baseline documentaire. |
| Guide utilisateur | Généré par captures Playwright sur la stack réelle | **Repris** à partir des parcours Playwright existants, sur l'URL servie par l'API et avec les seules fixtures synthétiques. |

## Choix arrêtés par l'intégrateur

Choix techniques courants, pris sans arbitrage utilisateur conformément à la charte, et révisables sur mesure :

- thème clair uniquement ; tokens prêts pour un thème sombre ;
- aucune police distante : pile système ;
- accès aux panneaux sous 1024 px par Sheets gauche et droit (pas d'onglets bas en plus) ;
- raccourci de la bibliothèque Ctrl/⌘+B, ignoré pendant la saisie dans la zone de question ;
- document ouvert, version, page et citation dans l'URL (déjà le cas pour les liens de citation), largeurs et états des panneaux en stockage local ;
- superpositions : élément natif `<dialog>` pour la confirmation et le Suivi, afin de ne pas ajouter de dépendance tant qu'un besoin précis ne l'exige pas ;
- nom de produit affiché : « Atelier documentaire » (titre actuel de l'application), sous-titre « Poste documentaire local ».

## Suite

Mise en œuvre dans le lot R16 du [plan](../PLAN.md), après intégration des correctifs frontend du lot R4, sans régression : tests unitaires, typecheck, build, E2E existants rejoués, captures aux largeurs de QA relues.
