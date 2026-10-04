# Déploiement sur le poste de l'utilisateur

**Rôle :** procédures de préparation d'un clone et de distribution interne du kit Windows, avec cibles, contrôles et reprise · **Propriétaire :** exploitation et distribution locale · **Statut :** Stabilisé · **Référence :** commit `5ca3685` et rédaction documentaire locale R14-1 du 2026-10-02 ; scripts lus, aucune fabrication, installation, mise à jour ou désinstallation exécutée pour cette rédaction ; choix de modèle R23 relu dans le code intégré et modifications locales du 2026-10-04, sans qualification native transférée · **Mis à jour :** 2026-10-04 20:05 (UTC) · **Source de vérité :** `bootstrap.ps1`, `bootstrap.sh`, `rag.ps1`, `rag.sh`, `tools/dist/build_kit.py`, `install.ps1`, `shortcuts.ps1`, `uninstall.ps1` et `services/runtime/profile_setup.py` · **Remplace :** aucun document

## 1. Voies et conditions

Toutes les opérations s'effectuent avec le compte utilisateur standard. Le programme ne crée ni service système ni règle de pare-feu, ne modifie ni le PATH global ni le registre machine. Les chemins d'exemple ci-dessous sont à remplacer par des dossiers identifiés, accessibles au compte utilisé.

| Voie | Cible | État de la procédure et limite |
|---|---|---|
| Clone puis provisionnement | Windows 11 x86-64 | Scripts et parcours applicatifs exercés sur le poste Windows du chantier ; préparation intégrale d'une racine neuve encore à qualifier dans R10 |
| Clone puis provisionnement | Linux aarch64 à glibc | Préparation d'un clone neuf exercée sur le Jetson du chantier ; conditions et révision dans [DoD, qualification Linux](../../RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018) |
| Clone puis provisionnement | Linux x86-64 à glibc | Verrous et scripts présents ; aucune exécution sur un poste x86-64 déclarée |
| Kit hors ligne par utilisateur | Windows 11 x86-64 | Fabrication, installation, raccourcis, mise à jour et retrait écrits et testés sur cibles isolées ; kit réel, installation neuve et cycle complet restent ouverts dans R22 |

Le kit Windows contient des binaires, CPython et roues Windows. [build_kit.py](../../tools/dist/build_kit.py) refuse sa fabrication sous Linux ; aucun kit ni installateur Linux n'est livré. L'usage est interne selon [W030](../../RAG_Local_Agents/DECISIONS.md#w030-usage-interne--registre-des-licences-sans-validation-de-redistribution). Les avis présents et les manques restent déclarés ; une distribution hors de l'organisation rouvrirait le contrôle des licences.

Les prérequis communs (mémoire, disque, Node/pnpm, ports, GPU) sont dans le [README, prérequis](../../README.md#9-prérequis-du-poste). Les prérequis propres à Linux, dont glibc, compilateurs et bibliothèques de construction de Tesseract, sont dans l'[exploitation, préparation](../exploitation/EXPLOITATION.md#2-préparer-le-poste). Le projet ne les installe pas par un gestionnaire système ; un prérequis absent est un diagnostic à résoudre dans le périmètre autorisé.

## 2. Préparer un clone

Prérequis : clone dans un dossier appartenant à l'utilisateur, modèle choisi ([profil 2B par défaut](../../config/local16.yaml) ou [profil 4B](../../config/local16-4b.yaml)) relu, ports disponibles, ressources et outils prérequis présents. Le premier provisionnement accède aux sources officielles verrouillées ; un provisionnement hors ligne exige des caches déjà remplis. Ne pas mélanger le clone, ses données et une installation du kit.

Depuis la racine du clone, sous Windows PowerShell :

```powershell
.\bootstrap.ps1
.\rag.ps1 provision
.\rag.ps1 doctor
```

Sous Linux, depuis un shell POSIX à la racine du clone :

```bash
./bootstrap.sh
./rag.sh provision
./rag.sh doctor
```

Sans option de modèle ou de profil, ces commandes préparent `qwen3.5:2b` et son tokenizer. Pour le 4B, conserver `-Model qwen3.5:4b` sous Windows ou `--model qwen3.5:4b` sous Linux sur `provision`, `doctor`, `up` et `open`. Un profil utilisateur se transmet exclusivement par `-Profile`/`--profile` ; il n'est pas converti automatiquement vers le défaut. La [procédure de changement de modèle](../exploitation/EXPLOITATION.md#91-changer-le-modèle-de-génération) préserve ses chemins et prévoit la reprise. Les essais historiques de la section 1 ne qualifient pas par anticipation une installation 2B.

Effets persistants : environnement Python `.venv/`, outils, caches, binaires, modèles et manifestes sous `.runtime/`, export statique `apps/web/out/`. Le détail des étapes, options hors ligne et erreurs est tenu dans l'[exploitation, préparation](../exploitation/EXPLOITATION.md#2-préparer-le-poste) ; les versions et empreintes attendues proviennent des verrous, pas de valeurs choisies dans cette procédure.

Contrôles : examiner chaque rubrique de `doctor`, puis suivre l'[exploitation, démarrage et ouverture](../exploitation/EXPLOITATION.md#3-démarrer-et-ouvrir-latelier). `up` et une sonde de santé réussie ne valident pas le parcours complet : ouvrir un PDF, effectuer une recherche, poser une question si elle est admise et ouvrir sa citation. `selftest` exerce un document natif dans une instance temporaire ; il ne qualifie pas l'OCR ni D07.

Reprise d'un provisionnement interrompu : conserver les caches, lire le diagnostic, corriger le prérequis puis relancer la même commande ; les artefacts dont l'empreinte est valide sont réutilisés. Ne pas supprimer `.runtime/` ou une racine de données pour recommencer. En cas de services encore actifs, suivre l'[exploitation, incident](../exploitation/EXPLOITATION.md#8-reprendre-après-un-incident).

Pour préparer des données hors du dossier programme, `init-profile` est disponible sur les deux plateformes. Les options sont décrites dans l'[exploitation, conventions](../exploitation/EXPLOITATION.md#1-conventions), et la validation dans [profile_setup.py](../../services/runtime/profile_setup.py). Le profil généré ne remplace pas un profil existant. Plusieurs profils du même poste doivent partager `runtime.host_lock_path` s'ils doivent respecter ensemble le verrou de travail lourd.

## 3. Fabriquer et vérifier un kit Windows interne

Cette opération se réalise sur le poste Windows de fabrication, après un provisionnement complet et un build de l'interface. Prérequis : code et verrous de la révision retenue, artefacts et modèle vérifiés, cache uv contenant les roues nécessaires. Choisir une destination neuve hors du dépôt, sans données à conserver ; la fabrication refuse une destination non vide et retire son résultat si elle détecte un chemin privé du poste de fabrication.

Depuis la racine du dépôt Windows :

```powershell
.\.venv\Scripts\python.exe -B tools\dist\build_kit.py build --output D:\kits\AtelierPDF-version
.\.venv\Scripts\python.exe -B tools\dist\build_kit.py verify --kit D:\kits\AtelierPDF-version
```

La [liste blanche et les exclusions](../../tools/dist/build_kit.py) déterminent le contenu : code d'exécution, interface construite, outils et caches nécessaires, manifestes et avis. Corpus, données, jetons, évaluations, tests, dossier de chantier et dépôt Git sont exclus. Le constructeur génère `SHA256SUMS`, `kit-manifest.json`, `THIRD_PARTY_NOTICES.md` et `Installer l'atelier.cmd`. `verify` rend `status: verified` seulement si les fichiers attendus sont intacts et si aucun fichier supplémentaire n'est présent, hormis les deux fichiers de contrôle qu'il exclut de la comparaison.

Option `--without-gpu` : retire les dossiers CUDA et Vulkan de l'archive Windows d'Ollama ; les conséquences sur les diagnostics sont définies par `WITHOUT_GPU_HELP`. Cette option ne doit pas être employée pour masquer un échec de qualification. La voie GPU Windows reste non qualifiée par un essai réel.

Limite : `verify` compare le kit à son propre manifeste de hashes ; il ne certifie ni la provenance d'un kit reçu ni son aptitude à démarrer sur un poste vierge. La révision du fabricant, les contrôles de provisionnement et les essais R22 restent nécessaires. La lecture des scripts effectuée pour ce document ne constitue pas un kit fabriqué.

La liste blanche embarque `docs/` mais exclut le dossier de chantier et les tests ; elle n'inclut pas `packages/`. Les renvois de ces documents vers les exigences, preuves, tests et contrats partagés ne seront donc pas tous résolus dans le kit. Les liens sont contrôlés dans le dépôt ; leur disponibilité dans un kit autonome reste à vérifier avec R22.

## 4. Installer le kit par utilisateur

Prérequis : kit reçu par le canal interne retenu, compte standard, Windows 11 64 bits. [install.ps1](../../tools/dist/install.ps1) vérifie le build système, la mémoire visible, la place sur le volume du programme et la longueur du stockage Qdrant, restaurations comprises, avant la copie. Une stratégie de groupe qui interdit les scripts reste une limite de l'environnement ; cette procédure ne la modifie pas.

Depuis la racine du kit, `Installer l'atelier.cmd` appelle le script PowerShell. Pour choisir explicitement les cibles :

```powershell
.\tools\dist\install.ps1 -Destination D:\applications\AtelierPDF -DataRoot D:\donnees\APDF -QdrantStorage D:\apdfq -Ports '18785,16333,21434'
```

| Option | Effet persistant ou contrôle |
|---|---|
| `-Destination` | Installe le programme dans un sous-dossier nommé par la version du kit ; une version déjà présente n'est pas remplacée |
| `-DataRoot` | Racine du profil et des écritures de l'utilisateur ; doit être hors du programme. Le profil existant déclenche la procédure de mise à jour |
| `-QdrantStorage` | Stockage court dédié ; sa longueur et celle des restaurations sont vérifiées avant la copie |
| `-Ports` | Chaîne CSV entre guillemets, contenant trois ports distincts et disponibles dans l'ordre API, Qdrant, Ollama ; validés à la création du profil |
| `-Menu` | Dossier des quatre raccourcis de l'utilisateur ; le défaut est son menu Démarrer. Un essai isolé indique un autre dossier |
| `-NoStart` | Installe le programme, prépare le profil, contrôle les rubriques et crée les raccourcis ; ne démarre pas la nouvelle instance, n'exécute pas son `selftest` et n'ouvre pas le navigateur. Avec `-Update`, l'ancienne instance est néanmoins démarrée pour la sauvegarde, puis arrêtée |

Les valeurs par défaut sont celles du bloc `param` du script. La copie hache chaque fichier attendu, l'environnement est préparé hors ligne sans outils de développement, puis le bytecode est précompilé. Le profil contient les chemins de données et ports de l'utilisateur. Une rubrique rouge de `doctor` avant démarrage arrête l'installation ; un verdict orange peut laisser l'installation continuer. Sans `-NoStart`, le script démarre l'instance, affiche `doctor`, exécute `selftest`, refuse un résultat rouge de celui-ci, puis appelle `open`.

Contrôles : conserver le rapport `install-<date>.json` dans `DataRoot`, vérifier ses étapes, le programme et le profil indiqués. Depuis le programme installé, lancer `doctor` et `status` avec ce profil ; ouvrir l'atelier et examiner son rendu. Le script peut annoncer l'appel d'ouverture sans prouver que le navigateur a affiché l'atelier. `selftest` orange peut signifier que la réponse n'a pas été admise faute de mémoire ; ce cas ne vaut pas recette complète.

Reprise : la copie partielle est retirée si son contrôle d'empreinte échoue. Une erreur ultérieure peut laisser le dossier versionné installé ; une relance à l'identique refuserait alors cette version. Lire le rapport avant toute action. Reprendre un diagnostic, un démarrage ou `selftest` depuis cette version lorsque c'est l'étape en échec ; ne pas effacer la racine de données pour relancer l'installation.

## 5. Mettre à jour et revenir à la version précédente

Prérequis : nouvelle version du kit, profil existant dans la même `DataRoot`, ancienne version encore présente et capable de démarrer. Le script retrouve son dossier par le raccourci ou par `-Previous`. Suspendre les travaux en cours avant cette opération ; la sauvegarde est la condition de reprise après une migration.

Depuis le nouveau kit :

```powershell
.\tools\dist\install.ps1 -Update -Previous D:\applications\AtelierPDF\ancienne-version -Destination D:\applications\AtelierPDF -DataRoot D:\donnees\APDF -QdrantStorage D:\apdfq
```

Effets : l'ancienne version est démarrée ou retrouvée, une sauvegarde est faite puis vérifiée, l'instance est arrêtée, la nouvelle version est installée à côté et le profil est repris. Ces étapes sur l'ancienne version s'exécutent aussi avec `-NoStart`. Les raccourcis sont basculés avant les contrôles finaux de démarrage et de `selftest`. L'ancienne version et la sauvegarde sont conservées. Le rapport garde `previous` et `backup` ; il ne faut pas déduire du seul dossier installé que la mise à jour a réussi.

En cas d'échec avant la bascule, les anciens raccourcis restent utilisables. Après la bascule, arrêter la nouvelle instance avec son profil. Si elle n'a pas migré les données, les raccourcis peuvent être remis sur l'ancienne version :

```powershell
& 'D:\applications\AtelierPDF\ancienne-version\tools\dist\shortcuts.ps1' -Program 'D:\applications\AtelierPDF\ancienne-version' -Profile 'D:\donnees\APDF\profile.yaml'
```

Si la nouvelle version a déjà démarré sur les données, le retour arrière requiert la sauvegarde préalable restaurée dans une racine neuve avec l'ancienne version, puis des raccourcis dirigés vers son profil restauré. Ne pas faire lire une base migrée au code ancien. La [procédure de restauration et de retour arrière](../exploitation/SAUVEGARDE-RESTAURATION.md#6-retour-arrière-et-relocalisation) est la référence de cette opération ; elle comprend les contrôles des anciennes citations et de la recherche.

## 6. Retirer une version installée

Cette action supprime le programme visé. Prérequis : version exacte identifiée, inventaire des chemins persistants du profil, et vérification que tous les chemins à conserver sont hors de ce dossier programme : profil, données applicatives et originaux, stockage Qdrant, sauvegardes et stockages de restauration. Un profil externe ne suffit pas : [profile_setup.py](../../services/runtime/profile_setup.py) accepte un `QdrantStorage` situé dans le programme, et le script de retrait ne contrôle pas ce cas. Si un chemin à conserver est interne, ne pas lancer le retrait ; préparer d'abord une sauvegarde vérifiée et une restauration vers des chemins externes selon la [procédure de relocalisation](../exploitation/SAUVEGARDE-RESTAURATION.md#6-retour-arrière-et-relocalisation). Depuis le dossier de la version, uniquement après décision de la retirer et vérification de cet inventaire :

```powershell
.\tools\dist\uninstall.ps1 -Profile D:\donnees\APDF\profile.yaml
```

[uninstall.ps1](../../tools/dist/uninstall.ps1) exige les marqueurs `kit-manifest.json` et `SHA256SUMS`, refuse un fichier de profil situé dans le programme, arrête l'instance qui tourne depuis cette version, retire ses raccourcis puis son dossier programme. Il ne traverse pas les jonctions lors de cette suppression. Une instance et des raccourcis d'une autre version sont conservés. Les données restent intactes seulement si leurs chemins sont réellement hors du dossier retiré ; le script ne vérifie pas cette condition pour les chemins désignés par le profil.

Contrôles : rapport `atelier-uninstall-<date>.json` dans le dossier temporaire de l'utilisateur, état `uninstalled`, absence de cette version et présence de chaque chemin à conserver dans l'inventaire préalable. Un échec reste accompagné du chemin ou de la cause ; résoudre un fichier encore ouvert avant de relancer sur la même version. Pour remettre le programme, réinstaller un kit identifié en conservant les données ; une racine déjà munie d'un profil suit la voie `-Update` et exige une ancienne version valide. Conserver une version précédente utilisable avant le retrait lorsqu'une reprise immédiate est nécessaire.

## 7. Preuves et travaux encore ouverts

Les tests de [fabrication](../../tests/unit/test_dist_build_kit.py), [installation](../../tests/unit/test_dist_install_script.py), [raccourcis](../../tests/unit/test_dist_shortcuts.py) et [désinstallation](../../tests/unit/test_dist_uninstall.py) exercent des cibles isolées et des kits de test. Les résultats réels de `doctor` et `selftest` sont référencés par l'[exploitation](../exploitation/EXPLOITATION.md), la [DoD](../../RAG_Local_Agents/DEFINITION_OF_DONE.md) et le [journal](../../RAG_Local_Agents/journal/README.md).

Le suivi canonique R10/R22 du [plan](../../RAG_Local_Agents/PLAN.md) garde la fabrication d'un kit réel, l'installation dans une racine neuve, la stabilité des hashes du programme après un cycle, la mise à jour avec retour arrière, la désinstallation et le poste Windows vierge. Ce dossier ne coche aucun de ces essais. Les corrections d'ingestion en cours n'y sont pas réputées validées.
