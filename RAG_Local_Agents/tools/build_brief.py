#!/usr/bin/env python3
"""Generate the single Markdown brief from canonical files, without network access."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 'RAG_LOCAL_BRIEF_COMPLET.md'
ORDER = [
    '00_LIRE_AVANT.md', 'PROMPT_IMPLEMENTATION.md', 'AGENTS.md', 'CLAUDE.md',
    'RECHERCHE_ET_SKILLS.md', 'SKILLS.md', 'SPEC_ARCHITECTURE.md',
    'IMPLEMENTATION.md', 'CONFIGURATION.md', 'QUALIFICATION.md',
    'DEFINITION_OF_DONE.md', 'PLAN.md', 'DECISIONS.md', 'CHANGELOG.md', 'SOURCES.md',
]

def rewrite_links(text: str, source: Path, root: Path) -> str:
    """Make skill-relative links usable from the root-level consolidated brief."""
    if source.parent == root:
        return text
    def replace(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
            return match.group(0)
        path, sep, anchor = target.partition('#')
        resolved = (source.parent / path).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            return match.group(0)
        return f'[{label}]({relative}{sep}{anchor})'
    return re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', replace, text)

def render(root: Path = ROOT) -> str:
    parts = [
        '# RAG PDF local — brief complet V2.1 pour agents\n\n'
        'Baseline documentaire : 29 septembre 2026.\n\n'
        'Ce fichier regroupe les documents corrigés, les consignes de recherche officielle, '
        'les skills projet et les configurations. Il est généré : modifier les sources séparées '
        'puis le régénérer, jamais maintenir deux versions à la main. '
        'Lire ce brief OU les fichiers canoniques pertinents, pas leurs deux copies.\n\n'
        'Les sections « Fichier » identifient leur chemin dans le ZIP. '
        'Aucune application, performance cible ou installation native de skill '
        'n’est déclarée validée par ce dossier documentaire.\n'
    ]
    docs = ORDER + [p.relative_to(root).as_posix() for p in sorted((root/'skills').glob('*/SKILL.md'))]
    for name in docs:
        path = root/name
        text = rewrite_links(path.read_text(encoding='utf-8'), path, root)
        parts.append(f'\n---\n\n## Fichier : `{name}`\n\n{text.rstrip()}\n')
    parts.append('\n---\n\n# Configurations complètes\n')
    languages = {'.yaml':'yaml','.json':'json','.sql':'sql','.env':'dotenv','.mjs':'javascript'}
    for path in sorted((root/'config').iterdir()):
        if path.is_file():
            language = languages.get(path.suffix, '')
            name = path.relative_to(root).as_posix()
            text = path.read_text(encoding='utf-8').rstrip()
            parts.append(f'\n## Fichier : `{name}`\n\n```{language}\n{text}\n```\n')
    parts.append('\n---\n\n# Outils inclus dans le ZIP\n\n'
                 '`tools/build_brief.py` régénère ou contrôle cette copie. '
                 '`tools/verify_pack.py` contrôle les fichiers et des exemples déterministes, '
                 'sans valider le produit ni ses performances. '
                 '`CONTROLES_DOSSIER.json` enregistre le résultat de cette vérification.\n')
    return ''.join(parts)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Fail if the generated brief differs.')
    args=parser.parse_args()
    target=ROOT/OUTPUT
    expected=render()
    if args.check:
        ok=target.is_file() and target.read_text(encoding='utf-8')==expected
        print('PASS: brief synchronisé' if ok else 'FAIL: régénérer avec python tools/build_brief.py')
        return 0 if ok else 1
    target.write_text(expected,encoding='utf-8')
    print(f'Écrit : {target}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
