# I5 — addendum préalable : points d’entrée du générateur unique

Date : 2026-11-08, avant modification des points d’entrée. Le protocole initial
reste figé ; cet addendum précise son invariant D07 « générateur 4B seul » à la
suite d’un défaut de configuration découvert par revue indépendante.

## Référence constatée

Au commit `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, `Settings.load()` sans
argument choisit `config/local16.yaml` (2B). Un chemin d’environnement absent peut
retomber sur la copie historique. Le CLI choisit Qwen3.5-4B sans les contrôles
`enhanced`. Le catalogue et les kits historiques proposent aussi le 2B. Les
campagnes I1–I4 utilisaient explicitement le profil enhanced et ne prouvent donc
pas la conformité de ces autres points d’entrée.

## Critères fixés avant correction

1. Sans choix de profil, ASGI et lanceurs sélectionnent `enhanced-4b`, Qwen3-4B
   Q4_K_M, avec contrôles de preuves et contrat de réponse activés.
2. Un chemin explicite ou `RAG_PROFILE` inexistant est une erreur, jamais un repli
   sur un autre modèle. Un profil 2B ou un profil sans les contrôles obligatoires
   est refusé avant lancement des services de génération.
3. Les commandes de lecture, d’arrêt et de sauvegarde d’une ancienne instance
   restent disponibles avec son chemin explicite ; aucun profil utilisateur
   historique n’est réécrit silencieusement.
4. Le catalogue nominal ne propose qu’un générateur ; il ne prétend pas qu’une
   plateforme ou un seuil RAM est qualifié. Le verrou des artefacts et le contrôle
   natif de famille, taille et quantification restent nécessaires au démarrage.
5. Le provisionnement du modèle enhanced utilise le GGUF/tokenizer verrouillés
   et l’import officiel existant, jamais un pull implicite d’un alias local.
6. Les outils de distribution sélectionnent uniquement ce générateur ou refusent
   explicitement un ensemble incompatible. Une construction/installation native
   non exécutée reste NON EXÉCUTÉE ; ni un test de filtre ni une copie de fichiers
   ne constitue une qualification du kit.

## Vérification prévue

Tests des points d’entrée, chemins invalides, profils historiques refusés,
contrôles désactivés, modèle/famille/taille/quantification altérés, arrêt historique
préservé, sélection du catalogue et filtres de distribution ; relecture de leurs
régressions existantes. Aucun changement des paramètres d’inférence, du corpus,
des délais, des plafonds de contexte ou de la réserve mémoire n’est autorisé par
cet addendum. Les essais natifs demeurent exécutés avec le même Qwen3-4B et les
mêmes poids que la référence.
