#!/usr/bin/env python3
"""Check the documentation pack and deterministic examples, not the future RAG app."""
from __future__ import annotations
import argparse
import ast
import importlib.metadata
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    raise SystemExit('PyYAML absent. Provisionner tools/requirements.txt avant ce contrôle hors ligne.')

from build_brief import ROOT, OUTPUT, ORDER, render

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
    lines=[]; active=None
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

def markdown_check():
    count=0
    for p in ROOT.rglob('*.md'):
        text=outside_code(p.read_text(encoding='utf-8'))
        for target in re.findall(r'\[[^\]]+\]\(([^)\s]+)\)',text):
            if urlsplit(target).scheme or target.startswith('#'):
                continue
            rel=unquote(target.split('#',1)[0])
            if not rel:
                continue
            dest=(p.parent/rel).resolve()
            require(dest.is_relative_to(ROOT),'Lien hors dossier : '+target)
            require(dest.exists(),f'Lien absent : {p.relative_to(ROOT)} → {target}')
            count+=1
    return {'local_links_checked':count,'external_urls_fetched':False}

def syntax_check():
    files=[]
    for p in sorted((ROOT/'config').iterdir()):
        if p.suffix=='.json': json.loads(p.read_text(encoding='utf-8'))
        elif p.suffix=='.yaml':
            obj=yaml.safe_load(p.read_text(encoding='utf-8')); require(isinstance(obj,dict),str(p))
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
    r=c['retrieval']; llm=c['llm']
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

def skills_check():
    files=sorted((ROOT/'skills').glob('*/SKILL.md'))
    require(len(files)==5,'Cinq skills projet attendus')
    names=[]
    for p in files:
        text=p.read_text(encoding='utf-8')
        require(text.startswith('---\n'),'Front matter absent')
        parts=text.split('---',2); require(len(parts)==3,'YAML delimiter')
        meta=yaml.safe_load(parts[1]); name=meta.get('name',''); desc=meta.get('description','')
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) is not None and len(name)<=64,'Nom invalide')
        require(name==p.parent.name,'Nom != dossier')
        require(isinstance(desc,str) and 1<=len(desc)<=1024,'Description invalide')
        require(len(meta.get('compatibility',''))<=500,'Compatibility trop longue')
        require(meta['metadata']['origin']=='project-authored','Origine ambiguë')
        require(all(isinstance(k,str) and isinstance(v,str) for k,v in meta['metadata'].items()),'Metadata non string')
        require(len(text.splitlines())<=150,'Skill trop long selon règle projet')
        require('allowed-tools' not in meta,'Permissions non qualifiées')
        require('RECHERCHE_ET_SKILLS.md' in text,'Règle officielle absente')
        names.append(name)
    return {'skills':names,'syntax_and_links_only':True,'native_client_discovery_tested':False}

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
        try: return len(text.encode('utf-16-le')[:byte_length].decode('utf-16-le'))
        except UnicodeDecodeError as exc: raise ValueError('Offset dans une paire surrogate') from exc
    require(all(to_cp(to_utf16(i))==i for i in range(len(text)+1)),'Roundtrip offsets')
    try: to_cp(2)
    except ValueError: pass
    else: raise AssertionError('Offset dans surrogate accepté')
    n=30;p=27/n;z=1.959963984540054
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
    for name,action in [('markdown_links',markdown_check),('syntax',syntax_check),('configuration_consistency',config_check),('sqlite_fts5_reference',sql_check),('skill_format',skills_check),('policy_propagation',policy_check),('deterministic_examples',deterministic_examples),('consolidated_brief',brief_check)]:
        check(name,action)
    passed=all(r['status']=='PASS' for r in RESULTS)
    report={'pack':'RAG-LOCAL-16-v2.1','checked_at_utc':datetime.now(timezone.utc).isoformat(),'overall_status':'PASS' if passed else 'FAIL','scope':'Documentation, configuration syntax, SQLite reference and deterministic examples ONLY','python_version':sys.version.split()[0],'pyyaml_version':importlib.metadata.version('PyYAML'),'results':RESULTS,'not_executed':['LLM inference','Docling or OCR','Qdrant server/API','Frontend or browser E2E','16 GB target qualification','Native skill installation/discovery/invocation','External source link accessibility in this offline script']}
    path=Path(args.report); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if passed else 1

if __name__=='__main__':
    raise SystemExit(main())
