#!/bin/sh
# Installateur de l'atelier documentaire depuis un kit hors ligne Linux (R26-KIT-01). Copié à la racine du kit sous le
# nom installer.sh. Sans droit administrateur : ni sudo, ni service, ni PATH, ni fichier hors des dossiers choisis.
# Contrôle l'architecture et la glibc du poste, puis passe la main au CPython du kit (bibliothèque standard seule),
# qui exécute tools/dist/linux_install.py : install, update, rollback, uninstall, status.
set -eu
# Le CPython du kit n'utilise que les bibliothèques du système : un LD_LIBRARY_PATH hérité du profil shell n'est pas
# transmis (un élément vide y désigne le répertoire courant pour le chargeur dynamique).
unset LD_LIBRARY_PATH

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
if [ -f "$here/kit-manifest.json" ]; then
    kit=$here
elif [ -f "$here/../../kit-manifest.json" ]; then
    kit=$(CDPATH='' cd -- "$here/../.." && pwd -P)
else
    fail "kit-manifest.json introuvable à côté de l'installateur : lancer installer.sh depuis la racine d'un kit ou d'une installation."
fi
manifest=$kit/kit-manifest.json

system=$(uname -s)
machine=$(uname -m)
[ "$system" = Linux ] || fail "Système non pris en charge : $system. Ce kit vise Linux ; sous Windows, utiliser le kit Windows."
# Valeurs écrites par le fabricant (json.dumps, une clé par ligne) : architecture, glibc minimale et interpréteur.
read_field() {
    sed -n "s/^ *\"$1\": \"\([^\"]*\)\".*/\1/p" "$manifest" | sed -n 1p
}
kit_arch=$(read_field arch)
kit_glibc=$(read_field glibc_min)
python_relative=$(read_field executable)
[ -n "$kit_arch" ] && [ -n "$python_relative" ] || fail "kit-manifest.json illisible : kit incomplet ou d'un autre format."
if [ "$machine" != "$kit_arch" ]; then
    fail "Ce kit vise Linux $kit_arch ; ce poste est en $machine. Utiliser le kit de cette architecture : rien n'a été installé."
fi

# Bibliothèque C : même lecture que bootstrap.sh (getconf, puis la première ligne de ldd --version).
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
        fail "Bibliothèque C musl détectée : ce kit exige la glibc ${kit_glibc:-2.28} ou plus récente."
    fi
    fail "Bibliothèque C non reconnue (ni getconf GNU_LIBC_VERSION ni ldd --version ne donnent de version de glibc)."
fi
required=${kit_glibc:-2.28}
required_major=${required%%.*}
required_minor=${required#"$required_major".}
required_minor=${required_minor%%.*}
if [ "$glibc_major" -lt "$required_major" ] || { [ "$glibc_major" -eq "$required_major" ] && [ "$glibc_minor" -lt "$required_minor" ]; }; then
    fail "glibc $glibc_version trop ancienne : ce kit exige la glibc $required ou plus récente (binaires et roues livrés). Rien n'a été installé."
fi

python=$kit/$python_relative
[ -f "$python" ] || fail "Interpréteur du kit absent ($python_relative) : kit incomplet, le recopier."
# Avant toute exécution : empreintes de l'interpréteur, de libpython et des scripts de l'installateur contre SHA256SUMS
# (lignes « empreinte  chemin » ; le chemin commence à la colonne 67). La vérification complète du kit suit, en Python.
# Vérificateur pris dans un chemin système fixe : le PATH de l'utilisateur ne choisit pas l'outil qui contrôle le kit.
sha256=
for candidate in /usr/bin/sha256sum /bin/sha256sum; do
    if [ -x "$candidate" ]; then
        sha256=$candidate
        break
    fi
done
[ -n "$sha256" ] || fail "sha256sum (coreutils) absent de /usr/bin et /bin : nécessaire pour vérifier le kit avant de l'exécuter."
[ -f "$kit/SHA256SUMS" ] || fail "SHA256SUMS absent du kit : le recopier."
python_root=${python_relative%/bin/*}
checks=
for name in "$python_relative" "$python_root/lib/libpython3.12.so.1.0" tools/dist/linux_install.py tools/dist/linux_kit.py \
        tools/dist/build_kit.py; do
    line=$(awk -v name="$name" 'substr($0, 67) == name' "$kit/SHA256SUMS")
    count=$(printf '%s' "$line" | grep -c . || true)
    if [ "$count" -ne 1 ]; then
        case "$name" in
            */libpython3.12.so.1.0) continue ;;
            *) fail "$name absent de SHA256SUMS : kit incomplet ou altéré, le recopier." ;;
        esac
    fi
    checks="$checks$line
"
done
printf '%s' "$checks" | (cd -- "$kit" && "$sha256" --check --quiet --strict -) >/dev/null 2>&1 ||
    fail "Interpréteur ou installateur du kit altéré (empreintes différentes de SHA256SUMS) : recopier le kit ; rien n'a été exécuté."
# -I : ni variables PYTHON*, ni site utilisateur, ni dossier du script dans sys.path ; -B : aucun bytecode écrit dans le kit.
exec "$python" -B -I -X utf8 "$kit/tools/dist/linux_install.py" --kit "$kit" "$@"
