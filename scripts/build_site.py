"""Build the static website data (04_website/site/data/site.json) from the same inputs as the graph.
The HTML/CSS/JS live in 04_website/site/ (index.html, app.js, style.css). Usage: py -3.13 build_site.py"""
import json, os, re, sys, datetime, collections as C
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as PT
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.dirname(HERE)
SITE = os.path.join(RES, '04_website', 'site') if not PT.REPO else os.path.join(os.path.dirname(HERE), 'docs')
os.makedirs(os.path.join(SITE, 'data'), exist_ok=True)
m = json.load(open(PT.MASTER, encoding='utf-8')); reg = json.load(open(PT.REGISTRY, encoding='utf-8'))
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
A = [r for r in m['evidence'] if r['status'] == 'active']
REP = {r['report_key']: r for r in m['reports']}
links = C.defaultdict(list)
for l in reg['links']:
    if l['first_for_dataset']: links[l['row_key']].append(l['canonical_id'])
sv = m['subtask_vocabulary']
cats = C.OrderedDict()
for c in sorted({r['research_category'] for r in A}):
    rs = [r for r in A if r['research_category'] == c]
    cats[c] = {'id': slug(c), 'label': c, 'records': len(rs), 'studies': len({r['study_id'] for r in rs}),
               'datasets': len({d for r in rs for d in links[r['row_key']]}), 'subtasks': []}
subcount = C.Counter(r['subtask_id'] for r in A)
for s in sv['subtasks']:
    if s['research_category'] in cats:
        cats[s['research_category']]['subtasks'].append({'id': s['subtask_id'], 'label': s['subtask'], 'def': s.get('definition', ''), 'records': subcount.get(s['subtask_id'], 0),
                                                       'status': s.get('status', 'active')})
F = ['resource_kind', 'introducing_source', 'derived_from', 'input_unit', 'input_type', 'output_unit', 'output_type', 'input_source', 'target_source',
     'creation_method', 'human_verification', 'size', 'access_status', 'licence']
VAR = C.defaultdict(list)
for v in reg['variants']: VAR[v['variant_of_id']].append([v['variant_id'], v['variant_name'], v['variant_type']])
datasets = []
for d in reg['registry']:
    x = {'id': d['dataset_id'], 'name': d['canonical_name'], 'aliases': d['aliases'], 'records': d['records'], 'studies': d['studies'],
         'categories': d['categories'], 'roles': d['roles'], 'notes': d.get('notes', ''), 'status': d.get('descriptor_status', 'not checked'), 'variants': VAR.get(d['dataset_id'], [])}
    ds = d.get('descriptors')
    if ds:
        x['desc'] = {f: ds[f]['value'] for f in F if f in ds}
        x['ev'] = {f: [ds[f].get('source', ''), ds[f].get('quote', '')] for f in F if f in ds and (ds[f].get('quote') or ds[f].get('source'))}
        s = ds.get('sample') or {}
        if s: x['sample'] = {k: s.get(k, '') for k in ('sample_input', 'sample_output', 'selection', 'source_url', 'source_label', 'licence', 'reproduce', 'official_example_url', 'status')}
    datasets.append(x)
used = {r['report_key'] for r in A}
records = [{'k': r['row_key'], 'rep': r['report_key'], 'study': r['study_id'], 'cat': slug(r['research_category']), 'sub': r['subtask_id'], 'ds': links[r['row_key']],
            'roles': r['roles'], 'loc': r['evidence_location'], 'pc': r['page_convention'], 'vs': r['version_status'], 'use': r['documented_use'],
            'dv': r['dataset_version'], 'task': r['task_subtask'], 'dl': r['limitation_dataset'], 'ss': r['scope_study'], 'ri': r['reviewer_interpretation'],
            'met': r.get('metrics', ''), 'dom': r['domains'], 'fac': r['facets']} for r in A]
reports = {k: {'c': REP[k]['citation'], 'a': REP[k]['authors'], 'acc': REP[k].get('access', ''), 'ps': REP[k].get('publication_status', '')} for k in used}
inc = [r for r in m['reports'] if r['decision'] == 'Include']
meta = {'version': '0.1.0', 'built': datetime.date.today().isoformat(), 'reports_assessed': len(m['reports']), 'included': len(inc),
        'excluded': len(m['reports']) - len(inc), 'studies': len({r['study_id'] for r in inc}), 'records': len(A),
        'datasets': sum(1 for d in reg['registry'] if d['records'] > 0), 'variants': len(reg['variants']), 'described': sum(1 for d in reg['registry'] if d.get('descriptors')),
        'categories': len(cats), 'subtasks': len({r['subtask_id'] for r in A}), 'decisions': len(m['decision_log'])}
site = {'meta': meta, 'categories': list(cats.values()), 'facets': [[f['facet_id'], f['facet']] for f in sv['facets']],
        'roles': [[r['role'], r['definition']] for r in m['documented_use_roles']['roles']], 'datasets': datasets, 'records': records, 'reports': reports}
json.dump(site, open(os.path.join(SITE, 'data', 'site.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('site.json', round(os.path.getsize(os.path.join(SITE, 'data', 'site.json')) / 1e6, 2), 'MB |', meta)
