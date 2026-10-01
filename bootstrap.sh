#!/bin/sh
# Provision uv/Python dans le projet (Linux aarch64 ou x86_64, W018), équivalent de bootstrap.ps1 ; aucune modification
# de PATH ni de fichier hors du projet.
set -eu
# uv, CPython et l'environnement isolé n'utilisent que les bibliothèques du système : un LD_LIBRARY_PATH hérité du
# profil shell n'est pas transmis (un élément vide y désigne le répertoire courant pour le chargeur dynamique).
unset LD_LIBRARY_PATH

usage() {
    cat <<'EOF'
Usage : ./bootstrap.sh [--offline] [--no-dev]

  --offline   aucun accès réseau : uv, CPython et le cache des roues doivent déjà être dans .runtime/
  --no-dev    installation d'un kit, sans le groupe de développement (outils de test et de typage)
EOF
}

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

offline=0
no_dev=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --offline) offline=1 ;;
        --no-dev) no_dev=1 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Option inconnue : $1 (./bootstrap.sh --help)." ;;
    esac
    shift
done

# Archive officielle uv 0.12.21 de l'architecture du poste et SHA-256 publié avec la release (fichier .sha256).
system=$(uname -s)
machine=$(uname -m)
case "$system/$machine" in
    Linux/aarch64)
        uv_archive_name=uv-aarch64-unknown-linux-gnu
        uv_sha256=030b69227b40af8c1981b7301793dc66e71ed3c796ea8688209dd268bd91ec51
        ;;
    Linux/x86_64)
        uv_archive_name=uv-x86_64-unknown-linux-gnu
        uv_sha256=23f02075b652bb1df64178cfae41b5caf160822e720e2663568f3f5d63bc52c0
        ;;
    *)
        fail "Plateforme non prise en charge : $system $machine. bootstrap.sh vise Linux aarch64 ou x86_64 ; utiliser bootstrap.ps1 sous Windows x86-64."
        ;;
esac
# Bibliothèque C, avant tout téléchargement : le verrou uv impose des roues manylinux_2_28 (torch, torchvision et
# onnxruntime sur les deux architectures), donc la glibc 2.28 ou plus récente ; uv et CPython sont aussi en variante gnu,
# et bin/ollama 0.35.0 arm64 réclame des symboles GLIBC_2.28.
# La glibc répond à `getconf GNU_LIBC_VERSION` (« glibc 2.31 »). Sans getconf, la première ligne de `ldd --version` la
# nomme et finit par sa version (« ldd (GNU libc) 2.39 », ou sur Ubuntu 20.04 « ldd (Ubuntu GLIBC 2.31-0ubuntu9.18) 2.31 ») ;
# musl s'y nomme aussi.
libc_requirement='bootstrap.sh exige la glibc 2.28 ou plus récente (roues manylinux_2_28 du verrou)'
# Version « majeur.mineur » de la glibc en nombres ; glibc_major vide si elle est illisible.
read_glibc_version() {
    glibc_version=$1
    glibc_major=${glibc_version%%.*}
    glibc_minor=${glibc_version#"$glibc_major".}
    glibc_minor=${glibc_minor%%.*}
    case "$glibc_version/$glibc_major/$glibc_minor" in
        [0-9]*.*/[0-9]*/[0-9]*)
            case "$glibc_major$glibc_minor" in
                *[!0-9]*) glibc_major= ;;
            esac
            ;;
        *) glibc_major= ;;
    esac
}
glibc_major=
libc=$(getconf GNU_LIBC_VERSION 2>/dev/null) || libc=
case "$libc" in
    'glibc '*) read_glibc_version "${libc#glibc }" ;;
esac
ldd_output=
if [ -z "$glibc_major" ]; then
    ldd_output=$(ldd --version 2>&1) || :
    ldd_banner=$(printf '%s\n' "$ldd_output" | sed -n 1p)
    case "$ldd_banner" in
        *'GNU libc'*|*GLIBC*) read_glibc_version "${ldd_banner##* }" ;;
    esac
fi
if [ -z "$glibc_major" ]; then
    if printf '%s\n' "$ldd_output" | grep -qi musl; then
        fail "Bibliothèque C musl détectée : $libc_requirement ; utiliser une distribution Linux à glibc."
    fi
    fail "Bibliothèque C non reconnue (ni getconf GNU_LIBC_VERSION ni ldd --version ne donnent de version de glibc) : $libc_requirement."
fi
if [ "$glibc_major" -lt 2 ] || { [ "$glibc_major" -eq 2 ] && [ "$glibc_minor" -lt 28 ]; }; then
    fail "glibc $glibc_version trop ancienne : $libc_requirement ; utiliser une distribution plus récente."
fi
# CPython géré par uv, demandé par sa clé complète : la variante de base de l'architecture (x86_64 et non x86_64_v2
# à v4), qui s'exécute sur tout processeur de cette architecture, dans un dossier au nom connu.
python_key=cpython-3.12.14-linux-$machine-gnu

project_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
bootstrap_root=$project_root/.runtime/bootstrap
uv_path=$bootstrap_root/bin/uv

if [ ! -f "$uv_path" ]; then
    [ "$offline" -eq 0 ] || fail 'uv local absent du kit offline.'
    command -v curl >/dev/null 2>&1 || fail 'curl absent : nécessaire pour télécharger uv.'
    command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum absent : nécessaire pour vérifier uv.'
    archive_path=$bootstrap_root/uv-0.12.21-linux-$machine.tar.gz
    mkdir -p -- "$bootstrap_root"
    uri=https://github.com/astral-sh/uv/releases/download/0.12.21/$uv_archive_name.tar.gz
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --output "$archive_path" "$uri"
    digest=$(sha256sum -- "$archive_path" | cut -d ' ' -f 1)
    if [ "$digest" != "$uv_sha256" ]; then
        fail 'Archive officielle uv : SHA-256 non conforme, aucune exécution.'
    fi
    listing=$(tar -tzf "$archive_path")
    staging=$(mktemp -d "$bootstrap_root/.extraction.XXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    for name in uv uvx; do
        count=$(printf '%s\n' "$listing" | grep -c "^$uv_archive_name/$name\$" || true)
        [ "$count" -le 1 ] || fail 'Archive uv ambiguë.'
        if [ "$count" -eq 1 ]; then
            tar -xzf "$archive_path" -C "$staging" --no-same-owner --no-same-permissions "$uv_archive_name/$name"
            mkdir -p -- "$bootstrap_root/bin"
            mv -f -- "$staging/$uv_archive_name/$name" "$bootstrap_root/bin/$name"
            chmod 0755 "$bootstrap_root/bin/$name"
        fi
    done
    rm -rf -- "$staging"
    trap - EXIT
fi

version=$("$uv_path" --version) || fail 'Version uv différente du verrou.'
case "$version" in
    'uv 0.12.21'|'uv 0.12.21 '*) ;;
    *) fail 'Version uv différente du verrou.' ;;
esac

managed_python_root=$project_root/.runtime/python
cache_directory=$project_root/.runtime/cache/uv
managed_python=$managed_python_root/$python_key/bin/python3.12
set -- --cache-dir "$cache_directory"
[ "$offline" -eq 0 ] || set -- "$@" --offline
if [ ! -f "$managed_python" ]; then
    "$uv_path" python install "$python_key" --install-dir "$managed_python_root" --no-bin "$@" ||
        fail 'Installation Python isolé échouée.'
fi

cd -- "$project_root"
# --no-dev : installation d'un kit, sans le groupe de développement (outils de test et de typage).
[ "$no_dev" -eq 0 ] || set -- "$@" --no-dev
"$uv_path" sync --locked --python "$managed_python" --no-python-downloads "$@" ||
    fail 'Synchronisation Python verrouillée échouée.'
printf '%s\n' 'Environnement Python isolé prêt. Exécuter ./rag.sh provision pour artefacts et modèle.'
