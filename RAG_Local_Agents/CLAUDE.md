# Adaptateur de lecture — agents Claude Code

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)).

Lire [AGENTS.md](AGENTS.md) pour les consignes persistantes de ce dépôt, puis [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) pour toute décision technique significative. Conserver les instructions préexistantes de l'environnement.

Choisir dans [SKILLS.md](SKILLS.md) la compétence correspondant à la tâche et ouvrir son vrai `SKILL.md` ; ne pas charger tous les skills ni le brief consolidé. Consulter les sources officielles actuelles et le contrat de la version réellement installée avant étude, changement ou mise à jour. Tracer source, décision et preuve.

Le fichier présent est un adaptateur de consignes, pas un plugin ni une installation de skills. La découverte native dépend de la version et de la configuration réelles du client. Les références et les skills projet restent canoniques dans ce dépôt.

Ne pas exposer les skills de développement au LLM documentaire local. Ne pas envoyer le corpus privé à un service externe. Ne pas remplacer les instructions existantes de `CLAUDE.md` dans un dépôt déjà utilisé : intégrer ce contenu sans les écraser.
