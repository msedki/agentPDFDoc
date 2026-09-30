#!/usr/bin/env python3
"""Check the documentation pack and deterministic examples, not the future RAG app."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError as exc:
    raise SystemExit('PyYAML absent. Provisionner tools/requirements.txt avant ce contrôle hors ligne.') from exc

from build_brief import ORDER, OUTPUT, ROOT, render

RESULTS: list[dict] = []

def check(name, action):
    try:
        detail=action()
        RESULTS.append({'id':name,'status':'PASS','detail':detail})
    except Exception as exc:
        RESULTS.append({'id':name,'status':'FAIL','detail':f'{type(exc).__name__}: {exc}'})

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def outside_code(text: str) -> str:
    lines=[]
    active=None
    for line in text.splitlines():
        fence=re.match(r'^\s*(`{3,}|~{3,})',line)
        if fence:
            token=fence.group(1)
            if active is None:
                active=token[0]
            elif token[0]==active:
                active=None
            continue
        if active is None:
            lines.append(line)
    require(active is None,'Bloc de code Markdown non fermé')
    return '\n'.join(lines)

def local_links(p: Path, text: str):
    """Liens relatifs d'un Markdown hors blocs de code, URL et ancres, résolus depuis son dossier."""
    for target in re.findall(r'\[[^\]]+\]\(([^)\s]+)\)',outside_code(text)):
        if urlsplit(target).scheme or target.startswith('#'):
            continue
        rel=unquote(target.split('#',1)[0])
        if rel:
            yield target,(p.parent/rel).resolve()

def git_ignored(project: Path, rels: list[str]):
    """Chemins (relatifs au projet) ignorés par Git, fichiers suivis exclus ; (None, motif) si Git est inutilisable."""
    if not rels:
        return set(),None
    try:
        proc=subprocess.run(['git','-C',str(project),'check-ignore','-z','--stdin'],input='\0'.join(rels)+'\0',capture_output=True,text=True,encoding='utf-8',timeout=60)
    except (OSError,subprocess.TimeoutExpired) as exc:
        return None,f'git indisponible ({type(exc).__name__})'
    if proc.returncode not in (0,1):
        return None,f'git check-ignore code {proc.returncode} : {proc.stderr.strip()[:200]}'
    return set(filter(None,proc.stdout.split('\0'))),None

def link_fault(dest: Path, project: Path) -> str | None:
    if not dest.is_relative_to(project):
        return 'Lien hors projet'
    if dest.is_relative_to(project/'.runtime'):
        return 'Lien vers .runtime'
    if dest.is_relative_to(project/'.git'):
        return 'Lien vers .git'
    return None if dest.exists() else 'Lien absent'

def markdown_check(root: Path = ROOT):
    """Cibles admises : fichiers existants du projet (parent du pack), hors .runtime/ et chemins ignorés par Git."""
    root=root.resolve()
    project=root.parent
    faults,found=[],[]
    for p in sorted(root.rglob('*.md')):
        name=p.relative_to(root).as_posix()
        try:
            links=list(local_links(p,p.read_text(encoding='utf-8')))
        except AssertionError as exc:
            faults.append(f'{name} : {exc}')
            continue
        for target,dest in links:
            where=f'{name} → {target}'
            fault=link_fault(dest,project)
            if fault:
                faults.append(f'{fault} : {where}')
            else:
                found.append((dest.relative_to(project).as_posix(),dest.is_relative_to(root),where))
    ignored,reason=git_ignored(project,sorted({rel for rel,_,_ in found}))
    faults+=['Lien vers un chemin ignoré par Git : '+where for rel,_,where in found if ignored and rel in ignored]
    require(not faults,f'{len(faults)} lien(s) fautif(s) : '+' | '.join(faults))
    result={'local_links_checked':len(found),'links_to_project_outside_pack':sum(not inside for _,inside,_ in found),'git_ignore_check':'PASS' if reason is None else 'NOT_RUN: '+reason,'external_urls_fetched':False}
    if reason is not None:
        result['warnings']=['Contrôle git check-ignore NOT_RUN : '+reason]
    return result

def syntax_check():
    files=[]
    for p in sorted((ROOT/'config').iterdir()):
        if p.suffix=='.json':
            json.loads(p.read_text(encoding='utf-8'))
        elif p.suffix=='.yaml':
            obj=yaml.safe_load(p.read_text(encoding='utf-8'))
            require(isinstance(obj,dict),str(p))
        elif p.suffix=='.env':
            for line in p.read_text(encoding='utf-8').splitlines():
                if line.strip() and not line.lstrip().startswith('#'):
                    require(re.match(r'^[A-Z][A-Z0-9_]*=',line) is not None,line)
        files.append(p.name)
    for p in (ROOT/'tools').glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'))
    return {'configuration_files':files,'native_runtime_schema_tested':False}

def config_check():
    c=yaml.safe_load((ROOT/'config/local16.yaml').read_text(encoding='utf-8'))
    v=json.loads((ROOT/'config/qdrant.collection.json').read_text(encoding='utf-8'))
    require(c['embedding']['dimensions']==c['qdrant']['vector_dimensions']==v['vectors']['dense']['size']==384,'Dimensions incohérentes')
    r=c['retrieval']
    llm=c['llm']
    require(c['chunking']['max_prefixed_tokens']<=c['embedding']['max_model_tokens'],'Embedding overflow')
    require(r['max_evidence_llm_tokens']+r['max_history_llm_tokens']+r['max_instructions_question_llm_tokens']+r['context_safety_tokens']+llm['num_predict']<=llm['num_ctx'],'Token budgets incohérents')
    require(all(b<=r['max_evidence_llm_tokens'] for b in r['evidence_tokens_by_mode'].values()),'Mode evidence overflow')
    require(c['resources']['scheduling']['kill_on_interactive_request'] is False,'Kill nominal interdit')
    require(c['resources']['scheduling']['auto_resume_ingestion'] is False,'Reprise automatique non qualifiée')
    require(r['exact_identifier_final_coverage_required'] is True,'Contrainte exact absente')
    require(r['history_is_evidence'] is False,'Historique ne doit pas être preuve')
    require(c['app']['offline'] and llm['num_gpu']==0,'Invariants local/CPU')
    e=c['evaluation_targets']
    require(e['development_questions']+e['heldout_questions']==e['qualification_questions']==200,'Dataset counts')
    return {'embedding_dimensions':384,'max_declared_tokens_with_output':sum([r['max_evidence_llm_tokens'],r['max_history_llm_tokens'],r['max_instructions_question_llm_tokens'],r['context_safety_tokens'],llm['num_predict']]),'parameters_are_unqualified_design_targets':True}

def config_identity_check(root: Path = ROOT):
    """La copie documentaire du profil runtime canonique doit rester identique octet pour octet."""
    runtime,copy=root.parent/'config/local16.yaml',root/'config/local16.yaml'
    require(runtime.is_file(),'Profil runtime canonique absent : config/local16.yaml')
    a,b=runtime.read_bytes(),copy.read_bytes()
    if a!=b:
        la,lb=a.decode('utf-8').splitlines(),b.decode('utf-8').splitlines()
        line=next((i for i,(x,y) in enumerate(zip(la,lb,strict=False),1) if x!=y),min(len(la),len(lb))+1)
        where='fins de ligne seules' if la==lb else f'première ligne différente : {line}'
        raise AssertionError(f'Copie documentaire divergente du profil runtime ({where}) : recopier config/local16.yaml octet pour octet')
    return {'runtime_profile':'config/local16.yaml','documentary_copy':'RAG_Local_Agents/config/local16.yaml','sha256':hashlib.sha256(a).hexdigest(),'byte_identical':True}

def sql_check():
    conn=sqlite3.connect(':memory:')
    try:
        conn.executescript((ROOT/'config/lexical.sql').read_text(encoding='utf-8'))
        conn.execute('INSERT INTO chunks(chunk_uuid,generation_id,version_id,section_title,text) VALUES(?,?,?,?,?)',('a','g1','v1','Alimentation','La tolérance est documentée pour CCU-21.'))
        conn.execute('INSERT INTO chunks(chunk_uuid,generation_id,version_id,section_title,text) VALUES(?,?,?,?,?)',('b','g2','v2','Autre','La tolérance pour CCU-22 diffère.'))
        rows=conn.execute('SELECT c.chunk_uuid FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid WHERE chunks_fts MATCH ? AND c.generation_id=? ORDER BY bm25(chunks_fts,2.0,1.0) ASC',('tolérance','g1')).fetchall()
        require(rows==[('a',)],'Filtre generation ou FTS')
        conn.execute('UPDATE chunks SET text=? WHERE chunk_uuid=?',('Remplacé par un contenu différent.','a'))
        rows=conn.execute('SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?',('tolérance',)).fetchall()
        require(len(rows)==1,'Trigger update')
        conn.execute('DELETE FROM chunks WHERE chunk_uuid=?',('b',))
        rows=conn.execute('SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?',('tolérance',)).fetchall()
        require(not rows,'Trigger delete')
        return {'sqlite_version':sqlite3.sqlite_version,'checked':['create','insert','scope-filter','update','delete'],'full_app_schema_tested':False}
    finally:
        conn.close()

def skill_meta(p: Path) -> dict:
    """Front matter Agent Skills (S17) : YAML valide, nom = dossier, description et compatibility bornées, liens présents."""
    text=p.read_text(encoding='utf-8')
    require(text.startswith('---\n'),'Front matter absent')
    end=text.find('\n---\n',3)
    require(end>0,'YAML delimiter')
    meta=yaml.safe_load(text[4:end])
    require(isinstance(meta,dict),'Front matter non mapping')
    name,desc=meta.get('name',''),meta.get('description','')
    require(isinstance(name,str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) is not None and len(name)<=64,'Nom invalide')
    require(name==p.parent.name,f'Nom != dossier ({name} / {p.parent.name})')
    require(isinstance(desc,str) and 1<=len(desc)<=1024,'Description invalide')
    require(len(meta.get('compatibility',''))<=500,'Compatibility trop longue')
    missing=[target for target,dest in local_links(p,text) if not dest.exists()]
    require(not missing,'Lien absent : '+', '.join(missing))
    return meta

def skills_check(root: Path = ROOT):
    files=sorted((root/'skills').glob('*/SKILL.md'))
    require(len(files)==5,'Cinq skills projet attendus')
    names=[]
    for p in files:
        text,meta=p.read_text(encoding='utf-8'),skill_meta(p)
        name=meta['name']
        require(meta['metadata']['origin']=='project-authored','Origine ambiguë')
        require(all(isinstance(k,str) and isinstance(v,str) for k,v in meta['metadata'].items()),'Metadata non string')
        require(len(text.splitlines())<=150,'Skill trop long selon règle projet')
        require('allowed-tools' not in meta,'Permissions non qualifiées')
        require('RECHERCHE_ET_SKILLS.md' in text,'Règle officielle absente')
        names.append(name)
    return {'skills':names,'syntax_and_links_only':True,'native_client_discovery_tested':False}

def agents_skills_check(root: Path = ROOT):
    """Skills du dépôt sous .agents/skills/<nom>/SKILL.md ; les fichiers posés à la racine sont des avertissements."""
    project=root.resolve().parent
    base=project/'.agents'/'skills'
    require(base.is_dir(),'Dossier .agents/skills absent')
    names,errors,warnings=[],[],[]
    for p in sorted(base.iterdir()):
        rel=p.relative_to(project).as_posix()
        if p.is_file():
            warnings.append('Fichier tiers mal rangé : '+rel+(' (SKILL.md hors dossier de skill, non découvrable)' if p.name=='SKILL.md' else ''))
        elif not (p/'SKILL.md').is_file():
            warnings.append('Dossier sans SKILL.md : '+rel)
        else:
            try:
                skill_meta(p/'SKILL.md')
                names.append(p.name)
            except Exception as exc:
                errors.append(f'{rel}/SKILL.md : {type(exc).__name__}: {exc}')
    require(not errors,f'{len(errors)} skill(s) invalide(s) : '+' | '.join(errors))
    return {'skills':names,'warnings':warnings,'syntax_and_links_only':True,'native_client_discovery_tested':False}

def skill_registry(root: Path = ROOT) -> dict:
    """Lignes de tableau de SKILLS.md portant un lien et un SHA-256 : {chemin relatif au projet: (catégorie, sha256)}."""
    source,project,entries=root/'SKILLS.md',root.resolve().parent,{}
    for line in outside_code(source.read_text(encoding='utf-8')).splitlines():
        sha=re.search(r'`([0-9a-f]{64})`',line)
        links=list(local_links(source,line)) if line.startswith('|') else []
        if sha and links:
            cells={c.strip().strip('`') for c in line.strip().strip('|').split('|')}
            entries[links[0][1].relative_to(project).as_posix()]=(next(iter(cells&{'projet','pack','tiers'}),''),sha.group(1))
    return entries

def registry_check(root: Path = ROOT):
    """SKILLS.md recense chaque skill du pack et chaque fichier de .agents/skills avec son SHA-256 réel."""
    project=root.resolve().parent
    base=project/'.agents'/'skills'
    entries,faults,kinds=skill_registry(root),[],{'pack':[],'projet':[],'tiers':[]}
    expected=[(p,{'pack'}) for p in sorted((root/'skills').glob('*/SKILL.md'))]
    expected+=[(p,{'tiers'}) for p in sorted(base.iterdir()) if p.is_file()]+[(p/'SKILL.md',{'projet','tiers'}) for p in sorted(base.iterdir()) if (p/'SKILL.md').is_file()]
    for p,allowed in expected:
        rel=p.resolve().relative_to(project).as_posix()
        category,sha=entries.pop(rel,('',None))
        if sha is None:
            faults.append('Non enregistré : '+rel)
            continue
        if sha!=hashlib.sha256(p.read_bytes()).hexdigest():
            faults.append('SHA-256 périmé : '+rel)
        if category in allowed:
            kinds[category].append(p.parent.name if p.name=='SKILL.md' and p.parent!=base else p.name)
        else:
            faults.append(f'Catégorie {category or "absente"} invalide : {rel}')
    faults+=['Entrée hors périmètre du registre : '+rel for rel in entries]
    require(not faults,f'{len(faults)} écart(s) de registre SKILLS.md : '+' | '.join(faults))
    return {'pack':kinds['pack'],'project':kinds['projet'],'third_party':kinds['tiers'],'sha256_checked':len(expected),'behavior_tested':False}

def policy_check():
    for name in ['AGENTS.md','PROMPT_IMPLEMENTATION.md','CLAUDE.md','SPEC_ARCHITECTURE.md','IMPLEMENTATION.md','CONFIGURATION.md','QUALIFICATION.md','PLAN.md','DECISIONS.md']:
        require('RECHERCHE_ET_SKILLS.md' in (ROOT/name).read_text(encoding='utf-8'),f'Consigne non propagée : {name}')
    dod=(ROOT/'DEFINITION_OF_DONE.md').read_text(encoding='utf-8')
    require('D11 — Sources officielles' in dod,'D11 absent')
    for p in [ROOT/n for n in ORDER]+list((ROOT/'skills').glob('*/SKILL.md')):
        txt=p.read_text(encoding='utf-8')
        require('baseline documentaire 2.0' not in txt,'Baseline obsolète')
        require(not re.search(r'(?im)^.*\bTODO\b|\bFIXME\b|\bPLACEHOLDER\b',txt),'Placeholder dans '+str(p))
    return {'policy_in_primary_instructions':True,'source_and_skill_acceptance':'D11'}

def deterministic_examples():
    k=60
    lexical=['exact']+[f'near{i}' for i in range(1,7)]
    dense=[f'near{i}' for i in range(1,7)]
    scores={}
    for order in [lexical,dense]:
        for rank,key in enumerate(order,1):
            scores[key]=scores.get(key,0)+1/(k+rank)
    unconstrained=sorted(scores,key=lambda key:(-scores[key],key))[:6]
    require('exact' not in unconstrained,'Contre-exemple RRF non démontré')
    required={'exact'}
    reference_selection=list(required)+[key for key in sorted(scores,key=lambda key:(-scores[key],key)) if key not in required][:5]
    require('exact' in reference_selection and len(reference_selection)==6,'Sélection illustrative')
    text='A😀e\u0301Z'
    def to_utf16(cp): return len(text[:cp].encode('utf-16-le'))//2
    def to_cp(units):
        byte_length=units*2
        try:
            return len(text.encode('utf-16-le')[:byte_length].decode('utf-16-le'))
        except UnicodeDecodeError as exc:
            raise ValueError('Offset dans une paire surrogate') from exc
    require(all(to_cp(to_utf16(i))==i for i in range(len(text)+1)),'Roundtrip offsets')
    try:
        to_cp(2)
    except ValueError:
        pass
    else:
        raise AssertionError('Offset dans surrogate accepté')
    n=30
    p=27/n
    z=1.959963984540054
    center=(p+z*z/(2*n))/(1+z*z/n)
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return {'rrf_counterexample':{'exact_score':scores['exact'],'top6_without_exact':unconstrained,'illustrative_selection':reference_selection},'unicode_roundtrip':True,'dense_25000x384_float32_bytes':25000*384*4,'wilson_27_of_30_95pct':[center-radius,center+radius],'not_a_test_of_future_application':True}

def brief_check():
    require((ROOT/OUTPUT).read_text(encoding='utf-8')==render(),'Brief désynchronisé')
    return {'output':OUTPUT,'canonical_docs_and_configs_included':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',default=str(ROOT/'CONTROLES_DOSSIER.json'))
    args=parser.parse_args()
    RESULTS.clear()
    for name,action in [('markdown_links',markdown_check),('syntax',syntax_check),('configuration_consistency',config_check),('runtime_profile_copy',config_identity_check),('sqlite_fts5_reference',sql_check),('skill_format',skills_check),('agents_skill_format',agents_skills_check),('skills_registry',registry_check),('policy_propagation',policy_check),('deterministic_examples',deterministic_examples),('consolidated_brief',brief_check)]:
        check(name,action)
    passed=all(r['status']=='PASS' for r in RESULTS)
    warnings=[w for r in RESULTS if isinstance(r['detail'],dict) for w in r['detail'].get('warnings',[])]
    report={'pack':'RAG-LOCAL-16-v2.1','checked_at_utc':datetime.now(UTC).isoformat(),'overall_status':'PASS' if passed else 'FAIL','scope':'Documentation, configuration syntax, runtime profile copy, skill format/registry, SQLite reference and deterministic examples ONLY','python_version':sys.version.split()[0],'pyyaml_version':importlib.metadata.version('PyYAML'),'results':RESULTS,'warnings':warnings,'not_executed':['LLM inference','Docling or OCR','Qdrant server/API','Frontend or browser E2E','16 GB target qualification','Native skill installation/discovery/invocation','External source link accessibility in this offline script']}
    path=Path(args.report)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if passed else 1

if __name__=='__main__':
    raise SystemExit(main())
