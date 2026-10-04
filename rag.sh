#!/bin/sh
# Entrée Linux native (W018), équivalent de rag.ps1. Les effets réseau sont limités à provision/pull-model.
set -eu

usage() {
    cat <<'EOF'
Usage : ./rag.sh [commande] [options]

Commandes : provision, doctor (par défaut), up, open, status, logs, down, pull-model, backup, restore,
            verify, init-profile, selftest

Options :
  --profile <fichier>        profil utilisateur explicite, exclusif de --model
  --model <tag>              qwen3.5:2b (défaut) ou qwen3.5:4b ; changement appliqué après down puis up
  --only <groupe>            provision : un seul groupe d'artefacts
  --offline                  aucun accès réseau (kit déjà provisionné)
  --skip-model               provision : sans modèle Ollama
  --path <dossier>           backup : destination ; restore, verify : sauvegarde source
  --target <dossier>         restore : racine neuve ; init-profile : racine des données
  --report <fichier>         rapport JSON
  --qdrant-storage <dossier> init-profile : dossier court du stockage Qdrant
  --ports <a,q,o>            init-profile : ports API, Qdrant et Ollama
  --no-browser               open : afficher le lien à usage unique au lieu d'ouvrir le navigateur
  -h, --help                 cette aide
EOF
}

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

command_name=doctor
command_seen=0
profile=config/local16.yaml
profile_seen=0
model=
only=
offline=0
skip_model=0
no_browser=0
path=
target=
report=
qdrant_storage=
ports=

while [ "$#" -gt 0 ]; do
    option=$1
    case "$option" in
        --*=*)
            value=${option#*=}
            option=${option%%=*}
            shift
            set -- "$option" "$value" "$@"
            ;;
    esac
    case "$option" in
        -h|--help)
            usage
            exit 0
            ;;
        --offline) offline=1 ;;
        --skip-model) skip_model=1 ;;
        --no-browser) no_browser=1 ;;
        --profile|--model|--only|--path|--target|--report|--qdrant-storage|--ports)
            [ "$#" -ge 2 ] || fail "Option $option : valeur manquante."
            case "$option" in
                --profile) profile=$2; profile_seen=1 ;;
                --model) model=$2 ;;
                --only) only=$2 ;;
                --path) path=$2 ;;
                --target) target=$2 ;;
                --report) report=$2 ;;
                --qdrant-storage) qdrant_storage=$2 ;;
                --ports) ports=$2 ;;
            esac
            shift
            ;;
        -*)
            fail "Option inconnue : $option (./rag.sh --help)."
            ;;
        *)
            [ "$command_seen" -eq 0 ] || fail "Commande en trop : $option (./rag.sh --help)."
            case "$option" in
                provision|doctor|up|open|status|logs|down|pull-model|backup|restore|verify|init-profile|selftest)
                    command_name=$option
                    command_seen=1
                    ;;
                *)
                    fail "Commande inconnue : $option (./rag.sh --help)."
                    ;;
            esac
            ;;
    esac
    shift
done

project_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
project_python=$project_root/.venv/bin/python
if [ ! -f "$project_python" ]; then
    fail 'Environnement isolé absent. Exécuter bootstrap.sh pour préparer uv et Python3.12, puis rag.sh provision.'
fi
case "$profile" in
    /*) resolved_profile=$profile ;;
    *) resolved_profile=$project_root/$profile ;;
esac

set -- -m services.runtime.cli "$command_name"
if [ -z "$model" ] || [ "$profile_seen" -eq 1 ]; then
    set -- "$@" --profile "$resolved_profile"
fi
[ -z "$model" ] || set -- "$@" --model "$model"
[ -z "$only" ] || set -- "$@" --only "$only"
[ "$offline" -eq 0 ] || set -- "$@" --offline
[ "$skip_model" -eq 0 ] || set -- "$@" --skip-model
[ -z "$path" ] || set -- "$@" --path "$path"
[ -z "$target" ] || set -- "$@" --target "$target"
[ -z "$report" ] || set -- "$@" --report "$report"
[ -z "$qdrant_storage" ] || set -- "$@" --qdrant-storage "$qdrant_storage"
[ -z "$ports" ] || set -- "$@" --ports "$ports"
[ "$no_browser" -eq 0 ] || set -- "$@" --no-browser

export PYTHONUTF8=1
# Le CLI et ses sondes (uv, pnpm, Tesseract) n'utilisent que les bibliothèques du système : un LD_LIBRARY_PATH hérité du
# profil shell n'est pas transmis (un élément vide y désigne le répertoire courant pour le chargeur dynamique).
unset LD_LIBRARY_PATH
cd -- "$project_root"
# exec : l'interpréteur remplace le lanceur, les signaux (Ctrl+C) l'atteignent directement et son code de sortie est celui du lanceur.
exec "$project_python" "$@"
