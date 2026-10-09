#!/bin/sh
# Installateur de l'atelier documentaire depuis un kit hors ligne Linux, copié à la racine du kit et de chaque version
# installée sous le nom installer.sh. Pour le compte de l'utilisateur, sans droit d'administration : refus en root, ni
# sudo, ni service, ni modification du PATH de la session. Écrit seulement dans les dossiers de l'atelier (par défaut sous
# $XDG_DATA_HOME/atelier-documentaire) et, sauf --sans-menu, l'entrée de menu, la commande ~/.local/bin/atelier et le
# registre des installations (XDG Base Directory) ; avec --sans-menu, rien hors des dossiers choisis.
# Contrôle le compte, l'architecture et la glibc du poste, puis l'interpréteur et les scripts du kit (présence, droit de
# lecture, empreinte, fichier ordinaire, aucun lien non déclaré sur leur chemin), refuse les fichiers ajoutés parmi les
# modules de l'installateur et, dans le dossier de l'interpréteur, tout fichier, lien ou fichier spécial non listé (un dossier
# ajouté n'y est refusé que par son contenu), toute entrée listée absente, sans droit de lecture ou de type changé (lien,
# dossier, fichier spécial), et passe la main au CPython du kit (bibliothèque standard seule, sans site), qui exécute
# tools/dist/linux_install.py : install (par défaut), update, rollback, uninstall, repair, status, verifier et modele.
# « installer.sh --controle-seul » (premier argument) fait les mêmes contrôles, en lecture seule, et s'arrête avant de lancer
# Python : code 0, ou le refus et son code 1 ; status les rejoue ainsi pour chaque version désignée.
# Modèle de menace : la vérification du kit protège contre l'altération ACCIDENTELLE (copie ou transport incomplets,
# fichiers ajoutés par erreur, déduplication ou fermes de liens, droits perdus). Elle ne protège pas contre une personne
# qui peut écrire dans le kit : installer.sh lui-même s'exécute sans vérification préalable, et son intégrité repose sur
# l'empreinte de l'archive (<kit_id>.tar.sha256) contrôlée avant extraction.
set -eu
# Le CPython du kit n'utilise que les bibliothèques du système : un LD_LIBRARY_PATH hérité du profil shell n'est pas
# transmis (un élément vide y désigne le répertoire courant pour le chargeur dynamique).
unset LD_LIBRARY_PATH
# Un élément vide ou relatif du PATH (« . », « :/usr/bin ») désigne le répertoire courant, souvent le kit lui-même
# (./installer.sh) : seuls les éléments absolus sont gardés, pour qu'aucune commande ne soit prise parmi les fichiers du
# kit avant sa vérification ; sans aucun, /usr/bin:/bin.
absolute_path=
saved_ifs=$IFS
IFS=:
set -f
for element in ${PATH-}; do
    case $element in
        /*) absolute_path=${absolute_path:+$absolute_path:}$element ;;
    esac
done
set +f
IFS=$saved_ifs
PATH=${absolute_path:-/usr/bin:/bin}
export PATH

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}
# Mot d'une commande citée, écrit comme shlex.quote : tel quel s'il ne contient que des caractères sûrs, sinon entre apostrophes.
shell_word() {
    case $1 in
        *[!A-Za-z0-9_@%+=:,./-]*) printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")" ;;
        *) printf '%s' "$1" ;;
    esac
}

# Contrôle seul (« installer.sh --controle-seul », lancé par status pour chaque version désignée) : mêmes contrôles, en lecture
# seule, puis arrêt avant le lancement de Python.
check_only=
[ "${1-}" != --controle-seul ] || check_only=1

# En root (sudo compris), le programme et les données appartiendraient à root, hors de portée du compte qui les emploie.
if [ "$(id -u 2>/dev/null)" = 0 ]; then
    fail "Ne pas lancer l'installateur avec sudo ni en root : l'atelier s'installe pour votre compte. Relancer ./installer.sh sans sudo ; rien n'a été installé."
fi

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
if [ -f "$here/kit-manifest.json" ]; then
    kit=$here
elif [ -f "$here/../../kit-manifest.json" ]; then
    kit=$(CDPATH='' cd -- "$here/../.." && pwd -P)
else
    # L'archive porte kit-manifest.json après les fichiers du kit : une extraction interrompue laisse un dossier sans lui.
    fail "kit-manifest.json introuvable à côté de l'installateur : lancer installer.sh depuis la racine d'un kit ou d'une installation. Si ce dossier vient d'une archive extraite, son extraction s'est arrêtée avant la fin (kit-manifest.json suit les fichiers du kit dans l'archive) : extraire de nouveau l'archive dans un dossier neuf ; rien n'a été exécuté."
fi
manifest=$kit/kit-manifest.json
kit_word=$(shell_word "$kit")

# Ce que le pointeur dit d'un dossier de version (lu sans être interprété : json.dumps, indentation 2, une clé par ligne ;
# l'historique, plus indenté, n'entre pas en compte) : « courante », « precedente », « abandonnee » (précédente abandonnée par
# un retour arrière) ou « non-designee », suivi de la version courante ; rien pour un pointeur d'un autre format.
pointer_role() {
    version=$1 LC_ALL=C awk '
        BEGIN { version = ENVIRON["version"]; block = "" }
        $0 == "  \"format\": \"atelier-installation-v1\"," { known = 1; next }
        $0 == "  \"current\": {" { block = "current"; next }
        $0 == "  \"previous\": {" { block = "previous"; next }
        /^  [^ ]/ { block = ""; next }
        block != "" && index($0, "    \"kit_id\": \"") == 1 {
            value = substr($0, 16)
            sub(/",?$/, "", value)
            id[block] = value
        }
        block == "previous" && /^    "rolled_back": true,?$/ { rolled = 1 }
        END {
            if (!known) exit
            if (id["current"] == version) role = "courante"
            else if (id["previous"] == version) role = rolled ? "abandonnee" : "precedente"
            else role = "non-designee"
            # Version courante citée dans le chemin de son installateur : seulement sous la forme d’un kit_id.
            current = id["current"]
            if (current !~ /^[0-9A-Za-z][0-9A-Za-z.+_-]*$/) current = ""
            print role " " current
        }' "$2" 2>/dev/null
}

# Kit ou programme installé : un programme installé a son pointeur, installation.json, dans le dossier parent (critère de
# rag.sh, sans exiger que le pointeur le désigne : une version qu'il ne désigne plus reste un programme installé). L'action
# des refus qui suivent en dépend : un kit se recopie depuis son archive ; un programme installé ne se remplace jamais sur
# place, et un fichier ajouté par erreur se retire. Seule la version courante se réinstalle depuis le kit de sa version
# (dépannage, section 10.4, qui retire toutes les versions et reprend les données actives) ou se met à jour depuis le kit d'une
# autre version ; une version précédente, abandonnée ou non désignée se retire par l'installateur de la version courante, sans
# être réinstallée (U6-02).
if [ -f "$kit/../installation.json" ]; then
    destination=$(dirname -- "$kit")
    version=${kit##*/}
    version_word=$(shell_word "$version")
    designation=$(pointer_role "$version" "$kit/../installation.json") || designation=
    role=${designation%% *}
    current_version=${designation#* }
    [ "$current_version" != "$designation" ] || current_version=
    shown=$(shell_word "$destination")
    status_command="« <dossier du kit>/installer.sh status --destination $shown »"
    kit_version="cette version depuis le dossier de son kit (docs/exploitation/DEPANNAGE.md, section 10.4, « Réparer un programme installé avec le seul kit de sa version »"
    if [ -n "$current_version" ]; then
        removal="« $(shell_word "$destination/$current_version/installer.sh") uninstall --kit-id $version_word »"
    else
        removal="« <dossier du kit>/installer.sh uninstall --destination $shown --kit-id $version_word »"
    fi
    # Action en deux formes, en tête de phrase ou après « sinon » : verbe (verb, Verb) et suite (rest).
    case $role in
        courante)
            verb=réinstaller Verb=Réinstaller
            rest=" $kit_version, à partir de $status_command), ou mettre à jour l'installation depuis le kit d'une autre version (« <dossier de cet autre kit>/installer.sh update --destination $shown »)" ;;
        precedente)
            verb=retirer Verb=Retirer
            rest=" cette version (version précédente de l'installation, à ne pas réinstaller ; le retour arrière ne sera plus possible) par $removal" ;;
        abandonnee)
            verb=retirer Verb=Retirer
            rest=" cette version (abandonnée par un retour arrière, à ne pas réinstaller) par $removal" ;;
        non-designee)
            verb=retirer Verb=Retirer
            rest=" cette version (que le pointeur de l'installation ne désigne pas, à ne pas réinstaller) par $removal" ;;
        *)
            # Pointeur d'un autre format : status, lancé depuis un kit, dit si cette version est la courante.
            verb=si Verb=Si
            rest=" $status_command montre que $version est la version courante, réinstaller $kit_version) ; sinon, la retirer sans la réinstaller par « <programme de la version courante>/installer.sh uninstall --kit-id $version_word »" ;;
    esac
    owner="de ce programme installé"
    place="à ce programme installé"
    redo=$verb$rest
    redo_sentence=$Verb$rest
    damaged="programme installé incomplet ou altéré, $redo"
    added="Le retirer s'il a été ajouté par erreur, sinon $redo"
else
    owner="du kit"
    place="au kit"
    redo="recopier le kit depuis son archive"
    redo_sentence="Recopier le kit depuis son archive"
    damaged="kit incomplet ou altéré, le recopier depuis son archive"
    added=$redo_sentence
fi

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
[ -n "$kit_arch" ] && [ -n "$python_relative" ] ||
    fail "kit-manifest.json illisible ou d'un autre format : $damaged ; rien n'a été exécuté."
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
    # Repère : système de référence du kit et glibc du poste de fabrication, lus au manifeste (absents pour un kit sans référence).
    reference_os=$(read_field reference_os)
    reference_glibc=$(read_field glibc)
    reference=
    [ -z "$reference_os" ] || reference=" ; poste de référence : $reference_os${reference_glibc:+, glibc $reference_glibc}"
    fail "glibc $glibc_version trop ancienne : ce kit exige la glibc $required ou plus récente (binaires et roues livrés$reference). Rien n'a été installé."
fi

python=$kit/$python_relative
[ -f "$python" ] || fail "Interpréteur $owner absent ($python_relative) : $damaged ; rien n'a été exécuté."
# Avant toute exécution : empreintes de l'interpréteur, des scripts de l'installateur et de SYMLINKS contre SHA256SUMS
# (lignes « empreinte  chemin » ; le chemin commence à la colonne 67), type de chaque fichier vérifié et des dossiers de son
# chemin, refus des fichiers ajoutés que Python ou le chargeur dynamique liraient à la place de fichiers vérifiés, puis, en
# Python, la vérification ciblée (SHA256SUMS contre le manifeste, listes déclarées, fichiers soumis à ldd et fichiers
# exécutés avant la copie) et l'empreinte de chaque fichier pendant la copie. La bibliothèque standard du kit, dont seuls
# les fichiers listés sont admis, n'est hachée qu'à la copie.
# Outils de contrôle pris dans un chemin système fixe : le PATH de l'utilisateur ne choisit pas l'outil qui contrôle le kit.
system_tool() {
    tool=
    for candidate in "/usr/bin/$1" "/bin/$1"; do
        if [ -f "$candidate" ] && [ -x "$candidate" ]; then
            tool=$candidate
            return 0
        fi
    done
    return 1
}
system_tool sha256sum ||
    fail "sha256sum (coreutils) absent de /usr/bin et /bin : nécessaire pour vérifier l'interpréteur et l'installateur $owner avant de les exécuter ; le faire installer par l'administrateur du poste ; rien n'a été exécuté."
sha256=$tool
system_tool find ||
    fail "find (findutils) absent de /usr/bin et /bin : nécessaire pour contrôler le dossier de l'interpréteur $owner avant de l'exécuter ; le faire installer par l'administrateur du poste ; rien n'a été exécuté."
find=$tool
[ -f "$kit/SHA256SUMS" ] || fail "SHA256SUMS absent $owner : $damaged ; rien n'a été exécuté."
# Dossier de CPython du kit (<CPython>) : python.executable du manifeste sans bin/<exécutable>.
python_root=${python_relative%/bin/*}
[ "$python_root" != "$python_relative" ] && [ -d "$kit/$python_root" ] ||
    fail "kit-manifest.json illisible ou d'un autre format : $damaged ; rien n'a été exécuté."

# Type des entrées vérifiées (copie par liens, déduplication, copie qui a suivi les liens) : un fichier de SHA256SUMS est un
# fichier ordinaire, et un lien n'est admis que déclaré dans SYMLINKS (« chemin<TAB>cible »). Un lien à la place d'un fichier
# ou d'un dossier vérifié ferait suivre sa cible : sha256sum hacherait la cible, puis le chargeur dynamique ($ORIGIN) et
# Python (préfixe, modules voisins) liraient les fichiers voisins de cette cible, que rien n'a vérifiés.
link_instead_of_file() {
    refused=$1
    fail "$refused est un lien, absent de SYMLINKS, à la place du fichier inscrit dans SHA256SUMS (copie par liens ou déduplication) : le chargeur dynamique ou Python liraient alors les fichiers voisins de sa cible, non vérifiés. $redo_sentence ; rien n'a été exécuté."
}
link_instead_of_folder() {
    refused=$1
    fail "$refused est un lien, absent de SYMLINKS, à la place d'un dossier $owner (copie par liens ou déduplication) : l'interpréteur ou l'installateur y liraient des fichiers non vérifiés. $redo_sentence ; rien n'a été exécuté."
}
not_regular() {
    refused=$1
    fail "$refused n'est pas un fichier ordinaire, alors que SHA256SUMS l'inscrit comme tel. $redo_sentence ; rien n'a été exécuté."
}
no_longer_link() {
    refused=$1
    fail "$refused n'est plus un lien, alors que SYMLINKS l'inscrit comme tel (copie qui a suivi les liens) : son contenu n'est vérifié par rien. $redo_sentence ; rien n'a été exécuté."
}
# Copie ou extraction incomplètes (R5S-02), droits perdus (U6-05) : nommés avant tout calcul d'empreinte, qui annoncerait
# sinon un fichier « altéré », et avant le lancement de Python, qu'un module illisible ou absent arrêterait sur une trace.
missing() {
    refused=$1
    fail "$refused absent $owner, alors que SHA256SUMS ou SYMLINKS l'inscrit : copie incomplète ou fichier supprimé. $redo_sentence ; rien n'a été exécuté."
}
unreadable() {
    refused=$1
    fail "$refused sans droit de lecture (droits perdus à la copie ou à l'extraction) : rétablir les droits de lecture $owner (« chmod -R u+rX $kit_word ») ou $redo ; rien n'a été exécuté."
}
regular_file() {
    if [ -L "$kit/$1" ]; then
        link_instead_of_file "$1"
    fi
    if [ -e "$kit/$1" ] && [ ! -f "$kit/$1" ]; then
        not_regular "$1"
    fi
}
declared_link() {
    entry=$1 LC_ALL=C awk 'BEGIN { entry = ENVIRON["entry"]; found = 1 }
        index($0, entry "\t") == 1 { found = 0; exit }
        END { exit found }' "$kit/SYMLINKS" 2>/dev/null
}
# Dossiers du chemin $1, relatif au kit : aucun lien, sauf déclaré dans SYMLINKS (lu après la vérification de son empreinte).
real_folders() {
    rest=$1
    folder=
    while :; do
        case $rest in
            */*) ;;
            *) break ;;
        esac
        folder=${folder:+$folder/}${rest%%/*}
        rest=${rest#*/}
        if [ -L "$kit/$folder" ] && ! declared_link "$folder"; then
            link_instead_of_folder "$folder"
        fi
    done
}

checks=
names=
for name in "$python_relative" tools/dist/linux_install.py tools/dist/linux_kit.py tools/dist/build_kit.py SYMLINKS; do
    line=$(awk -v name="$name" 'substr($0, 67) == name' "$kit/SHA256SUMS")
    count=$(printf '%s' "$line" | grep -c . || true)
    [ "$count" -eq 1 ] || fail "$name absent de SHA256SUMS : $damaged ; rien n'a été exécuté."
    regular_file "$name"
    checks="$checks$line
"
    names="$names$name
"
done
# Fichiers étrangers parmi les modules de l'installateur. linux_install.py charge build_kit.py et linux_kit.py par leur
# chemin, sans recherche par nom dans le kit ; ce qu'une recherche par nom trouverait à leur place est en outre refusé ici :
# à la racine, un module tools ; dans tools/, un module dist ou un __init__ ; un module compilé (.so, chargé avant le .py du
# même nom) ou un bytecode sans source (.pyc) ; un dossier de paquet (<nom>/__init__.*, trouvé avant <nom>.py, PEP 420).
# Présent, chacun doit figurer dans SHA256SUMS, être un fichier ordinaire et y correspondre.
for pattern in tools.py tools.pyc tools.so 'tools.*.so' tools/__init__.py tools/dist.py tools/dist/__init__.py 'tools/*.pyc' \
        'tools/*.so' 'tools/dist/*.pyc' 'tools/dist/*.so' 'tools/*/__init__.py' 'tools/*/__init__.pyc' 'tools/*/__init__.so' \
        'tools/*/__init__.*.so' 'tools/dist/*/__init__.py' 'tools/dist/*/__init__.pyc' 'tools/dist/*/__init__.so' \
        'tools/dist/*/__init__.*.so'; do
    for path in "$kit"/$pattern; do
        [ -e "$path" ] || [ -L "$path" ] || continue
        name=${path#"$kit"/}
        line=$(awk -v name="$name" 'substr($0, 67) == name' "$kit/SHA256SUMS")
        [ -n "$line" ] ||
            fail "$name ajouté $place, absent de SHA256SUMS : fichier étranger parmi les modules de l'installateur. $added ; rien n'a été exécuté."
        regular_file "$name"
        checks="$checks$line
"
        names="$names$name
"
    done
done
# Fichiers lus par l'interpréteur à son démarrage, malgré -I -S, qui changeraient ses chemins de modules (initialisation de
# sys.path, Python 3.12) : un ._pth à côté de l'exécutable remplace sys.path ; un pyvenv.cfg à côté de l'exécutable ou un
# niveau au-dessus déplace le préfixe (clé home) ; lib/python312.zip vient en tête de sys.path ; un pybuilddir.txt à côté
# de l'exécutable désigne un dossier de construction (observé sur CPython 3.12.14). Présent, chacun doit figurer dans
# SHA256SUMS et y correspondre ; la règle du dossier de l'interpréteur, plus bas, couvre aussi ces fichiers.
for path in "$kit/$python_root"/bin/*._pth "$kit/$python_root/bin/pyvenv.cfg" "$kit/$python_root/pyvenv.cfg" \
        "$kit/$python_root/bin/pybuilddir.txt" "$kit/$python_root"/lib/python3*.zip; do
    [ -e "$path" ] || [ -L "$path" ] || continue
    name=${path#"$kit"/}
    line=$(awk -v name="$name" 'substr($0, 67) == name' "$kit/SHA256SUMS")
    [ -n "$line" ] ||
        fail "$name ajouté $place, absent de SHA256SUMS : il changerait les chemins de modules de l'interpréteur $owner à son démarrage. $added ; rien n'a été exécuté."
    regular_file "$name"
    checks="$checks$line
"
done
check_sums() {
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        checked=${line#*  }
        [ -e "$kit/$checked" ] || [ -L "$kit/$checked" ] || missing "$checked"
        [ -r "$kit/$checked" ] || unreadable "$checked"
    done <<EOF
$1
EOF
    printf '%s' "$1" | (cd -- "$kit" && "$sha256" --check --quiet --strict -) >/dev/null 2>&1 ||
        fail "Interpréteur ou installateur $owner altéré (empreintes différentes de SHA256SUMS) : $redo ; rien n'a été exécuté."
}
check_sums "$checks"
# SYMLINKS est vérifié : les dossiers du chemin de chaque fichier vérifié, et ceux de <CPython>, ne sont pas des liens non
# déclarés (le dossier de départ du parcours ci-dessous est suivi par find -H).
while IFS= read -r name; do
    [ -z "$name" ] || real_folders "$name"
done <<EOF
$names
EOF
# Les droits perdus à la copie (volume sans droits Unix) arrêteraient l'exécution sans message utile.
[ -x "$python" ] ||
    fail "Interpréteur $owner sans droit d'exécution ($python_relative) : droits perdus à la copie ou à l'extraction, $redo ; rien n'a été exécuté."
# Dossier de l'interpréteur (<CPython>), une règle par type d'entrée : un lien doit figurer dans SYMLINKS, un fichier
# ordinaire dans SHA256SUMS, hormis le bytecode des dossiers __pycache__, et aucune autre entrée (tube, socket,
# périphérique) n'est admise ; un dossier ajouté n'est refusé que par son contenu (un dossier vide n'est ni chargé ni importé à
# la place d'un module listé). Le chargeur dynamique y cherche les bibliothèques de l'interpréteur avant celles du système :
# DT_RPATH $ORIGIN/../lib du binaire, sous-dossiers de capacités matérielles compris (tls/, <architecture>/, glibc-hwcaps/…,
# ld.so(8)) ; Python y lit ses fichiers de démarrage et sa bibliothèque standard, où un fichier ou un dossier de paquet
# ajouté serait importé à la place d'un module listé. Le bytecode des dossiers __pycache__, écrit par compileall dans un
# programme installé, n'est pas lu par Python (-X pycache_prefix=/dev/null). Chaque entrée de SHA256SUMS (fichier ordinaire)
# et de SYMLINKS (lien) sous <CPython> doit être présente, avec son type, et chaque fichier listé lisible ; les bibliothèques
# listées sous <CPython>/lib (lib*.so*, sous-dossiers compris) sont contrôlées par empreinte.
# Cinq parcours de find -H (qui suit le dossier de départ s'il est un lien déclaré, jamais ses entrées) : les liens depuis
# <CPython>, les fichiers ordinaires depuis <CPython>/., les autres entrées depuis <CPython>/./., les dossiers depuis
# <CPython>/././. et les fichiers ordinaires sans droit de lecture pour leur propriétaire (-perm, POSIX) depuis
# <CPython>/./././. ; aucune entrée ne pouvant s'appeler « . », le début de chaque ligne dit son parcours. Une ligne vide
# signale un parcours en échec (dossier illisible) ; une ligne qui ne commence par aucun départ, reste d'un nom coupé par un
# saut de ligne, est étrangère. Chemins passés par l'environnement (ENVIRON), qu'awk ne réinterprète pas. Codes d'awk : 3
# entrée ajoutée, 4 parcours en échec, 5 lien à la place d'un fichier inscrit, 6 lien inscrit devenu fichier ou dossier, 7
# fichier inscrit devenu dossier ou fichier spécial, 8 lien à la place d'un dossier de fichiers inscrits, 9 entrée inscrite
# absente, 10 fichier inscrit sans droit de lecture. Une entrée inscrite sous un lien de dossier déclaré n'est pas cherchée :
# find ne parcourt pas ce lien (beneath_link).
start=$kit/$python_root
status=0
listing=$(
    { "$find" -H "$start" -type l -print && "$find" -H "$start/." -type f -print &&
        "$find" -H "$start/./." ! -type d ! -type l ! -type f -print && "$find" -H "$start/././." -type d -print &&
        "$find" -H "$start/./././." -type f ! -perm -u+r -print || printf '\n'; } 2>/dev/null |
        sums=$kit/SHA256SUMS links=$kit/SYMLINKS start=$start/ root=$python_root/ LC_ALL=C awk '
            function beneath_link(name,    parent) {
                for (parent = name; sub(/\/[^\/]*$/, "", parent) && index(parent, root) == 1; )
                    if (parent in linked) return 1
                return 0
            }
            BEGIN {
                sums = ENVIRON["sums"]; links = ENVIRON["links"]; root = ENVIRON["root"]
                links_start = ENVIRON["start"]; files_start = links_start "./"; others_start = files_start "./"
                folders_start = others_start "./"; unreadable_start = folders_start "./"; folders_root = others_start "."
                while ((getline line < sums) > 0) listed[substr(line, 67)] = line
                while ((getline line < links) > 0) {
                    tab = index(line, "\t")
                    if (tab > 1) linked[substr(line, 1, tab - 1)] = 1
                }
                failed = 0
                count = 0
            }
            $0 == "" { failed = 4; exit }
            $0 == folders_root { next }
            {
                if (index($0, unreadable_start) == 1) { kind = "u"; name = root substr($0, length(unreadable_start) + 1) }
                else if (index($0, folders_start) == 1) { kind = "d"; name = root substr($0, length(folders_start) + 1) }
                else if (index($0, others_start) == 1) { kind = "o"; name = root substr($0, length(others_start) + 1) }
                else if (index($0, files_start) == 1) { kind = "f"; name = root substr($0, length(files_start) + 1) }
                else if (index($0, links_start) == 1) { kind = "l"; name = root substr($0, length(links_start) + 1) }
                else { kind = ""; name = $0 }
                if (kind == "d") {
                    if (name in listed) { failed = 7; exit }
                    if (name in linked) { failed = 6; exit }
                    next
                }
                if (kind == "u") {
                    if (name in listed) { failed = 10; exit }
                    next
                }
                if (kind == "l") seen_link[name] = 1
                if (kind == "f") seen_file[name] = 1
                if (kind == "l" && (name in linked)) next
                if (kind == "f" && (name in listed)) {
                    if (index(name, root "lib/") == 1 && name ~ /\/lib[^\/]*\.so[^\/]*$/) hashed[++count] = listed[name]
                    next
                }
                if (kind == "f" && name ~ /\/__pycache__\/[^\/]*\.pyc$/) next
                if (kind == "l" && (name in listed)) failed = 5
                else if (kind == "o" && (name in listed)) failed = 7
                else if (kind != "l" && (name in linked)) failed = 6
                else {
                    failed = 3
                    for (parent = name; sub(/\/[^\/]*$/, "", parent) && index(parent, root) == 1; )
                        if (parent in linked) { name = parent; failed = 6; break }
                    if (failed == 3 && kind == "l")
                        for (other in listed) if (index(other, name "/") == 1) { failed = 8; break }
                }
                exit
            }
            END {
                if (failed == 0) {
                    for (entry in listed)
                        if (index(entry, root) == 1 && !(entry in seen_file) && !beneath_link(entry)) { name = entry; failed = 9; break }
                }
                if (failed == 0) {
                    for (entry in linked)
                        if (index(entry, root) == 1 && !(entry in seen_link) && !beneath_link(entry)) { name = entry; failed = 9; break }
                }
                if (failed != 0 && failed != 4) print name
                if (failed) exit failed
                for (i = 1; i <= count; i++) print hashed[i]
            }'
) || status=$?
case $status in
    0) ;;
    3) fail "$listing ajouté $place, absent de SHA256SUMS et de SYMLINKS : fichier étranger dans le dossier de l'interpréteur $owner, que le chargeur dynamique ou Python pourraient charger avant toute vérification. $added ; rien n'a été exécuté." ;;
    5) link_instead_of_file "$listing" ;;
    6) no_longer_link "$listing" ;;
    7) not_regular "$listing" ;;
    8) link_instead_of_folder "$listing" ;;
    9) missing "$listing" ;;
    10) unreadable "$listing" ;;
    *) fail "Dossier de l'interpréteur $owner illisible ($python_root) : rétablir les droits de lecture $owner ou $redo ; rien n'a été exécuté." ;;
esac
[ -z "$listing" ] || check_sums "$listing
"
# -I : ni variables PYTHON*, ni site utilisateur, ni dossier du script dans sys.path ; -S : ni module site, ni fichier .pth,
# ni sitecustomize du CPython du kit (bibliothèque standard seule) ; -B : aucun bytecode écrit dans le kit ;
# pycache_prefix=/dev/null : le bytecode est cherché sous /dev/null, qui n'est pas un dossier, donc aucun .pyc de __pycache__
# n'est lu à la place des sources vérifiées (un .pyc « unchecked-hash » serait chargé sans comparaison avec sa source).
# Contrôle seul : tous les contrôles sont passés ; rien n'est lancé.
[ -z "$check_only" ] || exit 0
exec "$python" -B -I -S -X utf8 -X pycache_prefix=/dev/null "$kit/tools/dist/linux_install.py" --kit "$kit" "$@"
