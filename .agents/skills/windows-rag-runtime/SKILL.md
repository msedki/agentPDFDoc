---
name: windows-rag-runtime
description: Provisionner, superviser et qualifier les processus natifs Windows du RAG PDF local, avec environnements isolés, versions verrouillées, disponibilité et arrêt ciblé. Utiliser pour le lanceur, les runtimes, sauvegardes et contrôles de ressources de ce projet sans WSL ni Docker.
---

# Runtime RAG Windows

Lire la décision W001, `RAG_Local_Agents/EXPLOITATION_WINDOWS.md`, le plan actif et les critères D01/D07/D08/D09 avant de modifier cette frontière. Conserver Ollama et Qdrant serveur Windows ; aucun client vectoriel embarqué substitué au serveur. Python 3.12 dédié ; PowerShell 5.1 comme façade et aucune mutation de PATH, ExecutionPolicy ou configuration système.

## Préparer et verrouiller

Résoudre les métadonnées publiées par les mainteneurs, choisir une version exacte compatible et vérifier ses fichiers/hashes avant exécution. Conserver URL, licence, version, architecture et SHA-256 dans un manifeste réel. Installer uv et Python dans les répertoires du projet, pas dans l'environnement global. Le cache de dépendances, wheels Windows, assets web et modèles/tokenizers préparés constituent le kit offline. Un cache valide se réutilise ; ne pas multiplier les variantes GPU.

`provision` est la phase réseau autorisée par la réalisation. `up`, `doctor`, `status`, `down` et usage nominal ne résolvent ni version ni téléchargement. L'environnement de chaque enfant est construit explicitement et les chemins deviennent absolus. Ne pas importer Docling/torch dans le superviseur ou le processus API.

Accepter les profils relatifs au projet et les chemins absolus de restauration sans préfixer deux fois la racine. Valider avant tout lancement les URLs HTTP127.0.0.1 avec ports explicites, sans identifiants, query ni fragment ; ne pas déduire loopback du seul bind de l'API.

## Posséder et superviser

Vérifier les ports et prendre un verrou interprocessus sur la racine de stockage. Conserver instance ID, PID, date de création, exécutable et fingerprint ; revalider cette identité avant une action. Affecter les enfants et descendants à un Job Object Windows avec kill-on-close ; vérifier cet effet sur de vrais processus locaux isolés.

Lancer sans shell avec arguments structurés, répertoire explicite et fenêtres auxiliaires cachées. Préserver les logs bornés de démarrage en erreur. Une readiness HTTP réussie ne prouve pas stores/modèles/configuration ni chaîne RAG ; exposer leurs états précis. Un échec stoppe seulement les enfants de la tentative. Aucun kill global par nom, aucune appropriation silencieuse d'un service existant.

Sous NTFS, une lecture peut brièvement empêcher le remplacement d'un fichier ouvert sans `FILE_SHARE_DELETE`, et un remplacement peut brièvement refuser une nouvelle lecture. Chaque écrivain utilise son propre temporaire, flush/fsync puis remplacement atomique. Reprendre uniquement `PermissionError` dans une fenêtre bornée ; ne masquer ni JSON invalide ni refus permanent. Vérifier ce contrat avec de vrais handles Win32 et des lecteurs/écrivains concurrents, pas seulement un mock.

L'arrêt gracieux est coopératif : refuser mutations, checkpoint, annuler appels et fermer stores. Sous Windows `Popen.terminate()` appelle TerminateProcess : le marquer comme arrêt forcé et garder la reprise, jamais comme preuve de grâce. Ne pas inventer une API shutdown native. Tester les adaptateurs de chaque version réelle ; terminer les enfants par le Job Object en dernier recours borné.

## Ressources et données

Échantillonner mémoire disponible/privée/résidente, CPU et disque lors des travaux lourds. Respecter la réserve hôte 1,5 Gio et l'admission selon le pic prévu, avec génération et ingestion lourde exclusives. Distinguer commit, working set et mémoire partagée ; aucune PSS Linux prétendue sous Windows. Ne pas arrêter de processus utilisateur pour un test.

SQLite se sauvegarde par API backup, Qdrant par snapshot cohérent, mutations suspendues ; compléter avec originaux, extractions et manifestes. Restaurer dans une autre racine et vérifier comptes/hashes/recherche/ancienne citation. Les tests utilisent des racines et ports isolés identifiés, sans reset des données du corpus.

Les routes de snapshot sont vérifiées dans `src/actix/api/snapshot_api.rs` de Qdrant 1.19.1 : création par collection, téléchargement puis restauration par upload dans un serveur isolé vide. Ne restaurer aucun snapshot sur une collection existante. Le backup garde les chemins relatifs et les hashes ; seule la base restaurée reçoit le changement de racine de ses chemins de stockage. Conserver la base originale et vérifier l'intégrité SQLite et les comptes des points après restauration.

Qualifier aussi une racine Unicode avec espaces et des fichiers internes dépassant MAX_PATH. Une restauration courte réussie ne couvre pas ce cas. Pour les chemins natifs transmis à Qdrant, essayer des chemins absolus étendus `\\?\` (ou `\\?\UNC\`), avec antislashs et sans `.`/`..`, puis vérifier le snapshot peuplé réel et le redémarrage. Ne modifier ni le registre LongPathsEnabled ni le manifeste du binaire officiel pour contourner un échec ; conserver les deux essais et vérifier ce que le binaire accepte réellement.

Si le binaire officiel refuse aussi cette forme étendue, utiliser un emplacement Qdrant explicite et court dans le profil (`qdrant.storage_dir`). La racine SQLite/originaux/extractions peut rester Unicode et longue. Une restauration vers une racine longue alloue un nouveau stockage Qdrant court sous `.runtime/q/`, sans réutiliser une collection existante, et écrit ce chemin dans son rapport et son profil. Pour le schéma verrouillé, la récupération temporaire ajoute202 caractères au chemin storage (les fichiers finaux ajoutent175) ; contrôler aussi ce temporaire. Les snapshots restent la source de restauration ; ne copier ou déplacer aucun stockage actif pour raccourcir ses chemins. Vérifier hashes, comptes et parcours sur la racine longue réelle.

## Sources officielles consultées le 30 septembre 2026

- [uv installation](https://docs.astral.sh/uv/getting-started/installation/) et [Python géré](https://docs.astral.sh/uv/guides/install-python/) : installation isolée, emplacements explicites.
- [Ollama Windows](https://docs.ollama.com/windows) et [API modèles](https://docs.ollama.com/api/tags) : CLI autonome, service et identités modèles.
- [Qdrant artefacts Windows v1.19.1](https://github.com/qdrant/qdrant/releases/expanded_assets/v1.19.1) et [CLI de cette version](https://github.com/qdrant/qdrant/blob/v1.19.1/src/main.rs) : binaire officiel et options réelles.
- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) : propriété des enfants, descendants et kill-on-close.
- [Microsoft CreateFileW, partage des handles](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), consulté le30/09/2026 : compatibilité des accès concurrents et `FILE_SHARE_DELETE` pour renommage ; mécanisme Windows, indépendamment de la version Python.
- [Microsoft, Maximum Path Length Limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation), ouverte le30/09/2026 à03:30 UTC : MAX_PATH260, chemins absolus étendus et règles de syntaxe ; document actualisé16/07/2024. Source du mécanisme, pas preuve de compatibilité Qdrant1.19.1.
- [Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html) : création et arrêt Windows ; [SQLite backup](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup).
- [Qdrant 1.19.1 snapshots](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/api/snapshot_api.rs) : contrats versionnés de création, téléchargement et récupération des snapshots. Les pages courantes qdrant.tech étaient inaccessibles au navigateur lors de cette consultation ; elles ne sont pas données comme lues.

Les sources prouvent les mécanismes et disponibilités documentés ; les critères ne sont clos qu'après leur exécution sur la machine cible. Enregistrer les échecs et reprises séparément.
