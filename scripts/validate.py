"""Validate the KG-DSE graph: (1) SHACL (01_model/kgdse-shapes.ttl) with pyshacl; (2) SPARQL counts
compared with master.json and registry.json; (3) values in the source that did not map to a concept.
Writes 02_data/validation_report.txt. Usage: py -3.13 validate.py"""
import json, os, collections as C
from rdflib import Graph
from pyshacl import validate
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as PT
g = Graph().parse(os.path.join(PT.DATA, 'kgdse.ttl'), format='turtle')
sh = Graph().parse(os.path.join(PT.MODEL, 'kgdse-shapes.ttl'), format='turtle')
m = json.load(open(PT.MASTER, encoding='utf-8'))
reg = json.load(open(PT.REGISTRY, encoding='utf-8'))
out = []
conforms, _, text = validate(g, shacl_graph=sh, inference='none', abort_on_first=False, allow_warnings=True)
nres = text.count('Constraint Violation')
out.append(f'SHACL conforms: {conforms} | violations: {nres}')
if not conforms:
    paths = C.Counter(l.strip() for l in text.splitlines() if l.strip().startswith('Result Path') or l.strip().startswith('Source Shape'))
    out += ['  ' + f'{n} x {p}' for p, n in paths.most_common(30)]
PFX = 'PREFIX kd: <https://w3id.org/kgdse/vocab#> PREFIX dcat: <http://www.w3.org/ns/dcat#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> '
def q(s): return [tuple(str(x) for x in r) for r in g.query(PFX + s)]
A = [r for r in m['evidence'] if r['status'] == 'active']
checks = [
 ('active records', q('SELECT (COUNT(?r) AS ?n) WHERE { ?r a kd:DatasetUseRecord ; kd:recordStatus "active" }')[0][0], len(A)),
 ('included reports', q('SELECT (COUNT(?r) AS ?n) WHERE { ?r a kd:Report ; kd:decision "Include" }')[0][0], sum(1 for r in m['reports'] if r['decision'] == 'Include')),
 ('excluded reports', q('SELECT (COUNT(?r) AS ?n) WHERE { ?r a kd:Report ; kd:decision "Exclude" }')[0][0], sum(1 for r in m['reports'] if r['decision'] == 'Exclude')),
 ('included studies', q('SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?r a kd:Report ; kd:decision "Include" ; kd:study ?s }')[0][0], len({r['study_id'] for r in m['reports'] if r['decision'] == 'Include'})),
 ('live datasets (records > 0)', q('SELECT (COUNT(?d) AS ?n) WHERE { ?d kd:recordCount ?c FILTER(?c > 0) }')[0][0], sum(1 for d in reg['registry'] if d['records'] > 0)),
 ('records with RI', q('SELECT (COUNT(?r) AS ?n) WHERE { ?r kd:recordStatus "active" ; kd:reviewerInterpretation ?x }')[0][0], sum(1 for r in A if r['reviewer_interpretation'])),
 ('version not stated', q('SELECT (COUNT(?r) AS ?n) WHERE { ?r kd:recordStatus "active" ; kd:versionStatus "version not stated" }')[0][0], sum(1 for r in A if r['version_status'] == 'version not stated')),
]
cat = dict(q('SELECT ?l (COUNT(?r) AS ?n) WHERE { ?r kd:recordStatus "active" ; kd:researchCategory ?c . ?c skos:prefLabel ?l } GROUP BY ?l'))
mc = C.Counter(r['research_category'] for r in A)
checks += [(f'category: {k}', cat.get(k, '0'), v) for k, v in sorted(mc.items())]
rol = dict(q('SELECT ?l (COUNT(?r) AS ?n) WHERE { ?r kd:recordStatus "active" ; kd:role ?c . ?c skos:prefLabel ?l } GROUP BY ?l'))
mr = C.Counter(x for r in A for x in r['roles'].split('; ') if x)
checks += [(f'role: {k}', rol.get(k, '0'), v) for k, v in sorted(mr.items())]
bad = [c for c in checks if int(c[1]) != int(c[2])]
out.append(f'Count checks: {len(checks)} run, {len(bad)} mismatches')
out += [f'  MISMATCH {n}: graph {a} vs source {b}' for n, a, b in bad]
for n, a, b in checks[:7]: out.append(f'  {n}: {a}')
# unmapped source values
sv = m['subtask_vocabulary']; known_f = {f['facet_id'] for f in sv['facets']}; known_d = set(sv['domains']) | {'General (no domain)', 'Unresolved', 'Political events'}
known_r = {r['role'] for r in m['documented_use_roles']['roles']}; known_s = {s['subtask_id'] for s in sv['subtasks']}
um = C.Counter()
for r in A:
    for f in (r['facets'] or '').split('; '):
        if f and f not in known_f: um[('facet', f)] += 1
    for d in (r['domains'] or '').split('; '):
        if d and d not in known_d: um[('domain', d)] += 1
    for x in (r['roles'] or '').split('; '):
        if x and x not in known_r: um[('role', x)] += 1
    if r['subtask_id'] not in known_s: um[('subtask', r['subtask_id'])] += 1
out.append(f'Unmapped source values: {sum(um.values())}' + ''.join(f'\n  {k}: {v}' for k, v in um.most_common()))
rep = '\n'.join(out); print(rep)
open(os.path.join(PT.DATA, 'validation_report.txt'), 'w', encoding='utf-8').write(rep + '\n')
