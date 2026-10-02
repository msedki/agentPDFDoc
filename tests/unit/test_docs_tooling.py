"""Tests de l'outillage documentaire RAG_Local_Agents/tools (lot R4, zone docs-tooling).

Ils exercent les vraies fonctions de verify_pack.py et build_brief.py, sur le dépôt réel
et sur des arborescences temporaires ; seul le cas « git absent » remplace subprocess.run.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Racine du dépôt : ancêtre du fichier de test (tests/unit/) ou répertoire courant de pytest.
PROJECT = next(p for p in [*Path(__file__).resolve().parents, Path.cwd()]
               if (p / 'RAG_Local_Agents' / 'tools' / 'verify_pack.py').is_file())
TOOLS = PROJECT / 'RAG_Local_Agents' / 'tools'
sys.path.insert(0, str(TOOLS))

import build_brief  # noqa: E402
import verify_pack as vp  # noqa: E402

GIT = shutil.which('git')


def write(path: Path, text: str, newline: str = '\n') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace('\n', newline).encode('utf-8'))
    return path


def skill(name: str, description: str = 'Usage précis.', body: str = '') -> str:
    return f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n\n{body}\n'


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """Projet temporaire versionné : RAG_Local_Agents/, apps/, .runtime/ et un chemin ignoré."""
    project = tmp_path / 'proj'
    root = project / 'RAG_Local_Agents'
    write(root / 'INDEX.md', 'Voir [a](A.md).\n')
    write(root / 'A.md', 'Titre\n')
    write(project / 'apps/web/reports/r.md', 'rapport\n')
    write(project / '.runtime/x.json', '{}\n')
    write(project / 'ignored/out.log', 'log\n')
    write(project / '.gitignore', '.runtime/\nignored/\n')
    write(tmp_path / 'outside.md', 'hors projet\n')
    if GIT:
        subprocess.run([GIT, 'init', '-q', str(project)], check=True, capture_output=True)
    return root


# --- Tâche 1 : liens Markdown -------------------------------------------------------------

def test_markdown_real_repository_accepts_project_reports():
    """Cas réel du défaut : la DoD et le PLAN pointent vers ../apps/web/reports/…"""
    detail = vp.markdown_check()
    assert detail['links_to_project_outside_pack'] >= 1
    assert detail['git_ignore_check'] == 'PASS'


def test_markdown_accepts_existing_project_link(pack: Path):
    write(pack / 'B.md', 'Preuve [UI](../apps/web/reports/r.md) et [ancre](#x) et [web](https://example.org/a).\n')
    detail = vp.markdown_check(pack)
    assert detail['local_links_checked'] == 2
    assert detail['links_to_project_outside_pack'] == 1


@pytest.mark.skipif(GIT is None, reason='git requis pour check-ignore')
def test_markdown_reports_every_faulty_link(pack: Path):
    write(pack / 'B.md', '[r](../.runtime/x.json) [m](../missing.md) [o](../../outside.md) [i](../ignored/out.log)\n')
    write(pack / 'sub/C.md', '[absent](../nope.md) [ok](../../apps/web/reports/r.md)\n')
    with pytest.raises(AssertionError) as exc:
        vp.markdown_check(pack)
    message = str(exc.value)
    assert message.startswith('5 lien(s) fautif(s)')
    for expected in ['Lien vers .runtime : B.md → ../.runtime/x.json', 'Lien absent : B.md → ../missing.md',
                     'Lien hors projet : B.md → ../../outside.md',
                     'Lien vers un chemin ignoré par Git : B.md → ../ignored/out.log',
                     'Lien absent : sub/C.md → ../nope.md']:
        assert expected in message


def test_markdown_unclosed_fence_does_not_hide_other_faults(pack: Path):
    write(pack / 'B.md', '```\ncode\n')
    write(pack / 'C.md', '[m](missing.md)\n')
    with pytest.raises(AssertionError) as exc:
        vp.markdown_check(pack)
    assert 'B.md : Bloc de code Markdown non fermé' in str(exc.value)
    assert 'Lien absent : C.md → missing.md' in str(exc.value)


def test_markdown_without_git_keeps_runtime_rule_and_declares_not_run(pack: Path, monkeypatch):
    def no_git(*args, **kwargs):  # substitution explicite : exécutable git introuvable
        raise FileNotFoundError('git')
    monkeypatch.setattr(vp.subprocess, 'run', no_git)
    detail = vp.markdown_check(pack)
    assert detail['git_ignore_check'].startswith('NOT_RUN')
    write(pack / 'B.md', '[r](../.runtime/x.json)\n')
    with pytest.raises(AssertionError, match='Lien vers .runtime'):
        vp.markdown_check(pack)


def test_report_option_never_writes_default_report(tmp_path: Path, monkeypatch):
    default = PROJECT / 'RAG_Local_Agents' / 'CONTROLES_DOSSIER.json'
    before = (default.read_bytes(), default.stat().st_mtime_ns)
    report = tmp_path / 'sub' / 'report.json'
    monkeypatch.setattr(sys, 'argv', ['verify_pack.py', '--report', str(report)])
    vp.main()
    assert (default.read_bytes(), default.stat().st_mtime_ns) == before
    data = json.loads(report.read_text(encoding='utf-8'))
    assert {r['id'] for r in data['results']} >= {'markdown_links', 'runtime_profile_copy', 'agents_skill_format',
                                                  'skills_registry'}
    assert len(data['results']) == len({r['id'] for r in data['results']})


def test_default_report_path_is_unchanged(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(vp, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['verify_pack.py'])
    vp.main()
    assert (tmp_path / 'CONTROLES_DOSSIER.json').is_file()


# --- Tâche 3 : identité du profil runtime et format des skills .agents ---------------------

def test_runtime_profile_copy_real_repository():
    detail = vp.config_identity_check()
    runtime = (PROJECT / 'config' / 'local16.yaml').read_bytes()
    assert detail['byte_identical'] and detail['sha256'] == hashlib.sha256(runtime).hexdigest()


@pytest.mark.parametrize(('copy', 'reason'), [
    ('a: 1\nb: 2\n', None), ('a: 1\r\nb: 2\r\n', 'fins de ligne seules'), ('a: 1\nb: 3\n', 'première ligne différente : 2'),
])
def test_runtime_profile_copy_detects_divergence(tmp_path: Path, copy: str, reason: str | None):
    root = tmp_path / 'RAG_Local_Agents'
    (tmp_path / 'config').mkdir()
    (root / 'config').mkdir(parents=True)
    (tmp_path / 'config' / 'local16.yaml').write_bytes(b'a: 1\nb: 2\n')
    (root / 'config' / 'local16.yaml').write_bytes(copy.encode())
    if reason is None:
        assert vp.config_identity_check(root)['byte_identical']
    else:
        with pytest.raises(AssertionError, match=reason):
            vp.config_identity_check(root)


def test_agents_skills_real_repository():
    detail = vp.agents_skills_check()
    assert {'hybrid-rag-api', 'pdf-ingestion-windows', 'pdf-workspace-web', 'rag-qualification-fixtures',
            'windows-rag-runtime', 'embedding-comparison-windows'} <= set(detail['skills'])
    assert any('.agents/skills/SKILL.md' in w for w in detail['warnings'])
    assert any('python-fastapi-web-server-security.md' in w for w in detail['warnings'])


def test_agents_skills_format_errors_and_misplaced_files(pack: Path):
    base = pack.parent / '.agents' / 'skills'
    write(base / 'good/SKILL.md', skill('good', body='[doc](../../../RAG_Local_Agents/A.md)'))
    write(base / 'wrong-dir/SKILL.md', skill('other-name'))
    write(base / 'long/SKILL.md', skill('long', 'x' * 1025))
    write(base / 'bad-yaml/SKILL.md', '---\nname: [bad\n---\n')
    write(base / 'no-front/SKILL.md', '# sans front matter\n')
    write(base / 'broken/SKILL.md', skill('broken', body='[x](missing.md)'))
    write(base / 'SKILL.md', skill('security-best-practices'))
    write(base / 'python-security.md', 'référence\n')
    (base / 'empty').mkdir()
    with pytest.raises(AssertionError) as exc:
        vp.agents_skills_check(pack)
    message = str(exc.value)
    assert message.startswith('5 skill(s) invalide(s)')
    for name in ['wrong-dir', 'long', 'bad-yaml', 'no-front', 'broken']:
        assert f'.agents/skills/{name}/SKILL.md' in message
    assert 'good/SKILL.md' not in message
    for bad in ['wrong-dir', 'long', 'bad-yaml', 'no-front', 'broken']:
        shutil.rmtree(base / bad)
    detail = vp.agents_skills_check(pack)
    assert detail['skills'] == ['good']
    assert len(detail['warnings']) == 3
    assert any('SKILL.md hors dossier de skill' in w for w in detail['warnings'])


# --- Tâche 5 : registre SKILLS.md ------------------------------------------------------------

def registry_row(root: Path, path: Path, category: str) -> str:
    link = path.relative_to(root).as_posix() if path.is_relative_to(root) else '../' + path.relative_to(root.parent).as_posix()
    return f'| {path.parent.name} | {category} | [{path.name}]({link}) | `{hashlib.sha256(path.read_bytes()).hexdigest()}` |\n'


def test_registry_real_repository():
    detail = vp.registry_check()
    assert len(detail['pack']) == 5 and len(detail['project']) == 8
    assert 'project-documentation' in detail['project']
    assert set(detail['third_party']) >= {'backend-patterns', 'agent-introspection-debugging', 'frontend-design',
                                          'frontend-skill', 'SKILL.md', 'openai.yaml'}


def test_registry_detects_stale_hash_missing_entry_and_category(pack: Path):
    base = pack.parent / '.agents' / 'skills'
    own = write(pack / 'skills/own/SKILL.md', skill('own'))
    proj = write(base / 'proj/SKILL.md', skill('proj'))
    loose = write(base / 'SKILL.md', skill('loose'))
    rows = [registry_row(pack, own, 'pack'), registry_row(pack, proj, 'projet'), registry_row(pack, loose, 'tiers')]
    write(pack / 'SKILLS.md', '| Nom | Catégorie | Chemin | SHA-256 |\n|---|---|---|---|\n' + ''.join(rows))
    assert vp.registry_check(pack) == {'pack': ['own'], 'project': ['proj'], 'third_party': ['SKILL.md'],
                                       'sha256_checked': 3, 'behavior_tested': False}
    write(base / 'proj/SKILL.md', skill('proj', 'Modifié.'))
    write(base / 'extra/SKILL.md', skill('extra'))
    write(pack / 'SKILLS.md', '| Nom | Catégorie | Chemin | SHA-256 |\n|---|---|---|---|\n' + rows[0] + rows[1]
          + rows[2].replace('| tiers |', '| pack |'))
    with pytest.raises(AssertionError) as exc:
        vp.registry_check(pack)
    message = str(exc.value)
    for expected in ['SHA-256 périmé : .agents/skills/proj/SKILL.md', 'Non enregistré : .agents/skills/extra/SKILL.md',
                     'Catégorie pack invalide : .agents/skills/SKILL.md']:
        assert expected in message


# --- Tâche 2 : brief ---------------------------------------------------------------------------

def test_brief_order_and_header_describe_repository_generation():
    order = build_brief.ORDER
    assert order[order.index('CONFIGURATION.md') + 1] == 'EXPLOITATION_WINDOWS.md'
    text = build_brief.render()
    header, footer = text.split('\n---\n', 1)[0], text.rsplit('\n---\n', 1)[1]
    assert 'ZIP' not in header and 'ZIP' not in footer
    assert 'Baseline documentaire : 29 septembre 2026' not in header
    assert 'build_brief.py' in header and 'RAG_Local_Agents/' in header
    assert '## Fichier : `EXPLOITATION_WINDOWS.md`' in text
    assert '# Outils inclus dans le ZIP' not in text


def test_brief_rewrites_skill_links_leaving_the_pack(tmp_path: Path):
    root = tmp_path / 'RAG_Local_Agents'
    source = write(root / 'skills/x/SKILL.md', '[r](../../../apps/r.md) [d](../../A.md) [u](https://e.org)\n')
    rewritten = build_brief.rewrite_links(source.read_text(encoding='utf-8'), source, root)
    assert rewritten == '[r](../apps/r.md) [d](A.md) [u](https://e.org)\n'


def test_links_into_git_directory_are_refused(tmp_path):
    project = tmp_path / 'project'
    pack = project / 'RAG_Local_Agents'
    write(project / '.git' / 'config', '[core]\n')
    write(pack / 'README.md', '[config](../.git/config)\n')
    with pytest.raises(AssertionError, match='Lien vers .git'):
        vp.markdown_check(pack)


def test_git_check_unavailable_is_reported_as_warning(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    pack = project / 'RAG_Local_Agents'
    write(project / 'doc.md', '# doc\n')
    write(pack / 'README.md', '[doc](../doc.md)\n')

    def unavailable(*args, **kwargs):
        raise OSError('git absent')

    monkeypatch.setattr(vp.subprocess, 'run', unavailable)
    detail = vp.markdown_check(pack)
    assert detail['git_ignore_check'].startswith('NOT_RUN')
    assert detail['warnings'] and 'NOT_RUN' in detail['warnings'][0]


def test_collection_config_copy_is_checked_like_the_profile(tmp_path: Path):
    root = tmp_path / 'RAG_Local_Agents'
    (tmp_path / 'config').mkdir()
    (root / 'config').mkdir(parents=True)
    for folder in (tmp_path, root):
        (folder / 'config' / 'local16.yaml').write_bytes(b'a: 1\n')
    (root / 'config' / 'qdrant.collection.json').write_bytes(b'{"x": 1}\n')
    with pytest.raises(AssertionError, match='qdrant.collection.json'):
        vp.config_identity_check(root)
    (tmp_path / 'config' / 'qdrant.collection.json').write_bytes(b'{"x": 1}\n')
    assert vp.config_identity_check(root)['collection_config']['byte_identical']
    assert vp.config_identity_check()['collection_config']['runtime'] == 'config/qdrant.collection.json'
