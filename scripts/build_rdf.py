"""Build the KG-DSE resource graph (RDF) from Master Table/master.json and Dataset Registry/registry.json.
Outputs (Resource Website and KG/):
  01_model/kgdse-vocab.ttl   the kd: vocabulary (classes and properties with labels and definitions)
  02_data/kgdse.ttl          the full graph (taxonomy, datasets, reports, studies, records, decisions)
  02_data/kgdse.nt           the same graph as N-Triples
Namespaces: base https://w3id.org/kgdse/ ; vocabulary https://w3id.org/kgdse/vocab#
Usage: py -3.13 build_rdf.py"""
import json, os, re, datetime, collections as C
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS, DCTERMS, PROV, FOAF, DCAT, VOID

import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as PT
m = json.load(open(PT.MASTER, encoding='utf-8'))
reg = json.load(open(PT.REGISTRY, encoding='utf-8'))
BASE = 'https://w3id.org/kgdse/'
K = Namespace(BASE); KD = Namespace(BASE + 'vocab#')
VERSION, BUILT = '0.1.0', datetime.date.today().isoformat()

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def u(kind, ident): return URIRef(f'{BASE}{kind}/{ident}')
def lit(g, s, p, v, lang=None):
    if v is None: return
    v = str(v).strip()
    if v: g.add((s, p, Literal(v, lang=lang) if lang else Literal(v)))

# ---------------- vocabulary ----------------
V = Graph(); V.bind('kd', KD); V.bind('owl', OWL)
VOCAB_IRI = URIRef(BASE + 'vocab')
V.add((VOCAB_IRI, RDF.type, OWL.Ontology)); V.add((VOCAB_IRI, RDFS.label, Literal('KG-DSE vocabulary', lang='en')))
V.add((VOCAB_IRI, OWL.versionInfo, Literal(VERSION))); V.add((VOCAB_IRI, DCTERMS.license, URIRef('https://creativecommons.org/licenses/by/4.0/')))
CLASSES = {
 'DatasetUseRecord': ('Dataset-use record', 'One documented use of one or more datasets in one included study, with its location in the report.', PROV.Entity),
 'PeripheralRecord': ('Peripheral record', 'A documented dataset use in a study with no KG component; kept apart and not counted in the analysis.', PROV.Entity),
 'Report': ('Report', 'A publication assessed in full text (included or excluded).', DCTERMS.BibliographicResource),
 'Study': ('Study', 'A unique study; one or more reports (duplicate publications merged).', None),
 'ResearchCategory': ('Research category', 'Top-level research category of the taxonomy.', SKOS.Concept),
 'Subtask': ('Subtask', 'Controlled task under a research category.', SKOS.Concept),
 'Facet': ('Facet', 'Cross-cutting characteristic of a record (e.g. temporal, multimodal).', SKOS.Concept),
 'Domain': ('Application domain', 'Application domain of a record.', SKOS.Concept),
 'Role': ('Documented-use role', 'Role a dataset played in a study (introduced, training, testing, ...).', SKOS.Concept),
 'Decision': ('Review decision', 'A logged decision of the reviewer that changed coding or data.', PROV.Activity),
 'DescriptorEvidence': ('Descriptor evidence', 'Source and quote supporting one descriptor value of a dataset.', None),
 'Sample': ('Dataset sample', 'One real item or record from a dataset, with its exact source and licence.', None),
}
for c, (lab, com, sup) in CLASSES.items():
    V.add((KD[c], RDF.type, OWL.Class)); V.add((KD[c], RDFS.label, Literal(lab, lang='en'))); V.add((KD[c], RDFS.comment, Literal(com, lang='en')))
    if sup is not None: V.add((KD[c], RDFS.subClassOf, sup))
PROPS = {  # name: (label, comment, kind) kind: o=object, d=datatype
 'fromReport': ('from report', 'The report in which the use is documented.', 'o'), 'study': ('study', 'The study a report or record belongs to.', 'o'),
 'usesDataset': ('uses dataset', 'Canonical dataset used in the record.', 'o'), 'usesVariant': ('uses variant', 'Dataset variant used in the record.', 'o'),
 'researchCategory': ('research category', 'Research category of the record.', 'o'), 'originalCategory': ('original category', 'Category before a logged category move.', 'o'),
 'subtask': ('subtask', 'Controlled subtask of the record.', 'o'), 'facet': ('facet', 'Facet of the record.', 'o'), 'domain': ('domain', 'Application domain of the record.', 'o'),
 'role': ('role', 'Documented-use role.', 'o'), 'introducedIn': ('introduced in', 'Study in the corpus that introduced or derived the dataset.', 'o'),
 'variantOf': ('variant of', 'Canonical dataset this variant belongs to.', 'o'), 'duplicateOf': ('duplicate of', 'Report this one duplicates (merged study).', 'o'),
 'supersededBy': ('superseded by', 'Record replacing this one after a duplicate merge.', 'o'), 'decidedBy': ('decided by', 'Agent who decided.', 'o'),
 'descriptorEvidence': ('descriptor evidence', 'Evidence for a descriptor value.', 'o'), 'sample': ('sample', 'A real sample of the dataset.', 'o'),
 'taskDescription': ('task description', 'Task as described in the source (free text).', 'd'), 'datasetVersionText': ('dataset version text', 'Dataset, version and size as stated in the source.', 'd'),
 'documentedUse': ('documented use', 'What the study did with the dataset.', 'd'), 'evidenceLocation': ('evidence location', 'Section, table and page of the evidence.', 'd'),
 'pageConvention': ('page convention', 'Whether pages are printed or PDF pages.', 'd'), 'limitationDataset': ('dataset limitation (DL)', 'Author-reported limitation of the dataset.', 'd'),
 'scopeStudy': ('study scope (SS)', 'Scope or limitation of the study.', 'd'), 'reviewerInterpretation': ('reviewer interpretation (RI)', 'Reviewer observation, kept apart from author statements.', 'd'),
 'versionStatus': ('version status', '"version stated" or "version not stated".', 'd'), 'versionBasis': ('version basis', 'Text that established the version.', 'd'),
 'metric': ('metric', 'Evaluation metric named in the record (keyword rules).', 'd'), 'recordStatus': ('record status', 'active or superseded.', 'd'),
 'codingNote': ('coding note', 'Note on how the record was coded.', 'd'), 'subtaskBasis': ('subtask basis', 'Rule or evidence that set the subtask.', 'd'),
 'decision': ('screening decision', 'Include or Exclude.', 'd'), 'reason': ('reason', 'Reason for the screening decision.', 'd'),
 'identificationRoute': ('identification route', 'How the report was found.', 'd'), 'authorsShort': ('authors (short)', 'Short author list.', 'd'),
 'reviewedVersion': ('reviewed version', 'Version actually reviewed, where the citation gives a published version.', 'd'), 'publicationStatus': ('publication status', 'Published, preprint only, ...', 'd'),
 'accessNote': ('access note', 'Code and data availability as stated in the report.', 'd'), 'objective': ('objective', 'Objective of the study (paraphrased).', 'd'),
 'batch': ('batch', 'Review batch number.', 'd'), 'recordCount': ('record count', 'Active records linked to the dataset.', 'd'), 'studyCount': ('study count', 'Distinct studies among them.', 'd'),
 'resourceKind': ('resource kind', 'Task benchmark, knowledge graph, ontology, ...', 'd'), 'introducingSource': ('introducing source', 'Citation of the source that introduced the dataset.', 'd'),
 'derivedFromNote': ('derived from (note)', 'Stated parent dataset(s).', 'd'), 'inputUnit': ('input unit', '', 'd'), 'inputType': ('input type', '', 'd'),
 'outputUnit': ('output unit', '', 'd'), 'outputType': ('output type', '', 'd'), 'inputSource': ('input source', '', 'd'), 'targetSource': ('target source', '', 'd'),
 'creationMethod': ('creation method', '', 'd'), 'humanVerification': ('human verification', '', 'd'), 'size': ('size', 'As stated in the introducing source.', 'd'),
 'accessStatus': ('access status', 'Checked on the release page.', 'd'), 'licenceText': ('licence (as stated)', '', 'd'), 'descriptorStatus': ('descriptor status', 'coded / not checked / merged.', 'd'),
 'field': ('field', 'Descriptor field the evidence supports.', 'd'), 'quote': ('quote', 'Verbatim quote of at most 25 words.', 'd'), 'note': ('note', '', 'd'),
 'sampleInput': ('sample input', '', 'd'), 'sampleOutput': ('sample output', '', 'd'), 'selection': ('selection', 'First item or chosen for readability.', 'd'),
 'reproduce': ('reproduce', 'Whether the licence permits reproducing the sample.', 'd'), 'officialExampleURL': ('official example URL', '', 'd'),
 'decisionGroup': ('decision group', '', 'd'), 'proposal': ('proposal', '', 'd'), 'outcome': ('outcome', '', 'd'), 'variantType': ('variant type', '', 'd'),
}
for p, (lab, com, kind) in PROPS.items():
    V.add((KD[p], RDF.type, OWL.ObjectProperty if kind == 'o' else OWL.DatatypeProperty)); V.add((KD[p], RDFS.label, Literal(lab, lang='en')))
    if com: V.add((KD[p], RDFS.comment, Literal(com, lang='en')))

# ---------------- data graph ----------------
G = Graph()
for pfx, ns in (('kgdse', K), ('kd', KD), ('skos', SKOS), ('dcterms', DCTERMS), ('prov', PROV), ('dcat', DCAT), ('foaf', FOAF), ('void', VOID)): G.bind(pfx, ns)
RESOURCE = URIRef(BASE)
REVIEWER = u('agent', 'reviewer'); G.add((REVIEWER, RDF.type, PROV.Agent)); G.add((REVIEWER, RDF.type, FOAF.Person))
G.add((REVIEWER, FOAF.name, Literal('Boniface Chukwuemeka Godwin'))); G.add((REVIEWER, RDFS.comment, Literal('Sole reviewer: screening, extraction and coding decisions.', lang='en')))
G.add((RESOURCE, RDF.type, DCAT.Catalog)); G.add((RESOURCE, RDF.type, VOID.Dataset))
G.add((RESOURCE, DCTERMS.title, Literal('KG-DSE: a traceable evidence graph of dataset use in knowledge graph research', lang='en')))
G.add((RESOURCE, DCTERMS.license, URIRef('https://creativecommons.org/licenses/by/4.0/'))); G.add((RESOURCE, OWL.versionInfo, Literal(VERSION)))
G.add((RESOURCE, DCTERMS.issued, Literal(BUILT, datatype=XSD.date))); G.add((RESOURCE, VOID.vocabulary, URIRef(BASE + 'vocab')))
for n in ('Boniface Chukwuemeka Godwin', 'Petar Tomov'): G.add((RESOURCE, DCTERMS.creator, Literal(n)))

# taxonomy
SCHEMES = {k: u('scheme', k) for k in ('taxonomy', 'facets', 'domains', 'roles')}
for k, s in SCHEMES.items(): G.add((s, RDF.type, SKOS.ConceptScheme)); G.add((s, RDFS.label, Literal(f'KG-DSE {k}', lang='en')))
sv = m['subtask_vocabulary']
CAT = {}
for cat in sorted({s['research_category'] for s in sv['subtasks']} | {r['research_category'] for r in m['evidence']}):
    c = u('category', slug(cat)); CAT[cat] = c
    G.add((c, RDF.type, KD.ResearchCategory)); G.add((c, SKOS.prefLabel, Literal(cat, lang='en'))); G.add((c, SKOS.inScheme, SCHEMES['taxonomy'])); G.add((c, SKOS.topConceptOf, SCHEMES['taxonomy']))
SUB = {}
for s in sv['subtasks']:
    c = u('subtask', s['subtask_id']); SUB[s['subtask_id']] = c
    G.add((c, RDF.type, KD.Subtask)); G.add((c, SKOS.notation, Literal(s['subtask_id']))); G.add((c, SKOS.prefLabel, Literal(s['subtask'], lang='en')))
    lit(G, c, SKOS.definition, s.get('definition'), 'en'); G.add((c, SKOS.inScheme, SCHEMES['taxonomy'])); G.add((c, SKOS.broader, CAT[s['research_category']]))
    if s.get('status') and s['status'] != 'active': lit(G, c, SKOS.scopeNote, f"status: {s['status']}", 'en')
FAC = {}
for f in sv['facets']:
    c = u('facet', f['facet_id']); FAC[f['facet_id']] = c
    G.add((c, RDF.type, KD.Facet)); G.add((c, SKOS.notation, Literal(f['facet_id']))); G.add((c, SKOS.prefLabel, Literal(f['facet'], lang='en')))
    lit(G, c, SKOS.definition, f.get('definition'), 'en'); G.add((c, SKOS.inScheme, SCHEMES['facets']))
DOM = {}
for d in list(sv['domains']) + ['General (no domain)', 'Unresolved', 'Political events']:
    if d in DOM: continue
    c = u('domain', slug(d)); DOM[d] = c
    G.add((c, RDF.type, KD.Domain)); G.add((c, SKOS.prefLabel, Literal(d, lang='en'))); G.add((c, SKOS.inScheme, SCHEMES['domains']))
ROLE = {}
for r in m['documented_use_roles']['roles']:
    c = u('role', slug(r['role'])); ROLE[r['role']] = c
    G.add((c, RDF.type, KD.Role)); G.add((c, SKOS.prefLabel, Literal(r['role'], lang='en'))); lit(G, c, SKOS.definition, r['definition'], 'en'); G.add((c, SKOS.inScheme, SCHEMES['roles']))

# datasets and variants
DSU = {}
for d in reg['registry']:
    x = u('dataset', d['dataset_id']); DSU[d['dataset_id']] = x
    G.add((x, RDF.type, DCAT.Dataset)); G.add((x, DCTERMS.identifier, Literal(d['dataset_id']))); G.add((x, RDFS.label, Literal(d['canonical_name'])))
    for a in re.split(r';\s*', d.get('aliases') or ''):
        lit(G, x, SKOS.altLabel, a)
    G.add((x, KD.recordCount, Literal(int(d['records'])))); G.add((x, KD.studyCount, Literal(int(d['studies']))))
    lit(G, x, KD.accessNote, d.get('access')); lit(G, x, KD.note, d.get('notes')); lit(G, x, KD.descriptorStatus, d.get('descriptor_status'))
    for sid in re.split(r',\s*', (d.get('introduced_in') or '').replace(' ...', '')):
        if sid.strip(): G.add((x, KD.introducedIn, u('study', sid.strip())))
    ds = d.get('descriptors')
    if ds:
        P2 = {'resource_kind': KD.resourceKind, 'introducing_source': KD.introducingSource, 'derived_from': KD.derivedFromNote, 'input_unit': KD.inputUnit, 'input_type': KD.inputType,
              'output_unit': KD.outputUnit, 'output_type': KD.outputType, 'input_source': KD.inputSource, 'target_source': KD.targetSource, 'creation_method': KD.creationMethod,
              'human_verification': KD.humanVerification, 'size': KD.size, 'access_status': KD.accessStatus, 'licence': KD.licenceText}
        for f, p in P2.items():
            if f not in ds: continue
            lit(G, x, p, ds[f]['value'])
            if ds[f].get('quote') or ds[f].get('source'):
                e = u('evidence', f"{d['dataset_id']}-{f.replace('_', '-')}")
                G.add((x, KD.descriptorEvidence, e)); G.add((e, RDF.type, KD.DescriptorEvidence)); G.add((e, KD.field, Literal(f)))
                lit(G, e, DCTERMS.source, ds[f].get('source')); lit(G, e, KD.quote, ds[f].get('quote')); lit(G, e, KD.note, ds[f].get('note'))
        s = ds.get('sample')
        if s:
            sx = u('sample', d['dataset_id']); G.add((x, KD.sample, sx)); G.add((sx, RDF.type, KD.Sample))
            for f, p in (('sample_input', KD.sampleInput), ('sample_output', KD.sampleOutput), ('selection', KD.selection), ('split_or_part', KD.note), ('licence', KD.licenceText),
                         ('reproduce', KD.reproduce), ('official_example_url', KD.officialExampleURL), ('note', KD.note), ('status', KD.descriptorStatus)):
                lit(G, sx, p, s.get(f))
            lit(G, sx, DCTERMS.source, s.get('source_url')); lit(G, sx, RDFS.comment, s.get('source_label'))
            if s.get('checked_on'): G.add((sx, DCTERMS.date, Literal(s['checked_on'], datatype=XSD.date)))
for mg in reg.get('merged_ids', []):
    G.add((DSU[mg['dataset_id']], DCTERMS.isReplacedBy, DSU[mg['merged_into']])); G.add((DSU[mg['dataset_id']], OWL.sameAs, DSU[mg['merged_into']]))
VAR = {}
for v in reg['variants']:
    x = u('variant', v['variant_id']); VAR[v['variant_id']] = x
    G.add((x, RDF.type, DCAT.Dataset)); G.add((x, DCTERMS.identifier, Literal(v['variant_id']))); G.add((x, RDFS.label, Literal(v['variant_name'])))
    G.add((x, KD.variantOf, DSU[v['variant_of_id']])); G.add((x, PROV.wasDerivedFrom, DSU[v['variant_of_id']])); lit(G, x, KD.variantType, v.get('variant_type'))

# studies and reports
STU = set()
for r in m['reports']:
    x = u('report', r['report_key']); st = u('study', r['study_id']); STU.add(r['study_id'])
    G.add((x, RDF.type, KD.Report)); G.add((x, DCTERMS.identifier, Literal(r['report_key']))); G.add((x, KD.study, st))
    lit(G, x, DCTERMS.bibliographicCitation, r['citation']); lit(G, x, KD.authorsShort, r['authors']); lit(G, x, KD.decision, r['decision']); lit(G, x, KD.reason, r['reason'])
    lit(G, x, KD.identificationRoute, r['identification_route']); lit(G, x, KD.reviewedVersion, r.get('reviewed_version')); lit(G, x, KD.publicationStatus, r.get('publication_status'))
    lit(G, x, KD.accessNote, r.get('access')); lit(G, x, KD.objective, r.get('objective')); G.add((x, KD.batch, Literal(int(r['batch']))))
    if r.get('published_doi'): G.add((x, DCTERMS.identifier, Literal('doi:' + r['published_doi']))); G.add((x, RDFS.seeAlso, URIRef('https://doi.org/' + r['published_doi'])))
    if r.get('duplicate_publication_of'): G.add((x, KD.duplicateOf, u('report', r['duplicate_publication_of'])))
for sid in STU:
    G.add((u('study', sid), RDF.type, KD.Study)); G.add((u('study', sid), DCTERMS.identifier, Literal(sid)))

# records
LINKS = C.defaultdict(list)
for l in reg['links']: LINKS[l['row_key']].append(l)
MOVES = {mv['row_key']: mv for mv in m['category_moves']}
def record(r, cls, kind):
    x = u(kind, r['row_key'])
    G.add((x, RDF.type, cls)); G.add((x, DCTERMS.identifier, Literal(r['row_key'])))
    G.add((x, KD.fromReport, u('report', r['report_key']))); G.add((x, KD.study, u('study', r['study_id']))); G.add((x, PROV.wasDerivedFrom, u('report', r['report_key'])))
    G.add((x, PROV.wasAttributedTo, REVIEWER)); G.add((x, KD.researchCategory, CAT[r['research_category']]))
    for f, p in (('task_subtask', KD.taskDescription), ('dataset_version', KD.datasetVersionText), ('documented_use', KD.documentedUse), ('evidence_location', KD.evidenceLocation),
                 ('page_convention', KD.pageConvention), ('limitation_dataset', KD.limitationDataset), ('scope_study', KD.scopeStudy), ('reviewer_interpretation', KD.reviewerInterpretation),
                 ('version_status', KD.versionStatus), ('version_basis', KD.versionBasis), ('coding_note', KD.codingNote), ('subtask_basis', KD.subtaskBasis), ('status', KD.recordStatus)):
        lit(G, x, p, r.get(f))
    if r.get('limitations_and_scope') and not any(r.get(k) for k in ('limitation_dataset', 'scope_study', 'reviewer_interpretation')): lit(G, x, KD.note, r['limitations_and_scope'])
    if r.get('subtask_id') in SUB: G.add((x, KD.subtask, SUB[r['subtask_id']]))
    for f in (r.get('facets') or '').split('; '):
        if f in FAC: G.add((x, KD.facet, FAC[f]))
    for d in (r.get('domains') or '').split('; '):
        if d in DOM: G.add((x, KD.domain, DOM[d]))
    for ro in (r.get('roles') or '').split('; '):
        if ro in ROLE: G.add((x, KD.role, ROLE[ro]))
    for mt in (r.get('metrics') or '').split('; '):
        lit(G, x, KD.metric, mt)
    if r.get('superseded_by'): G.add((x, KD.supersededBy, u('record', r['superseded_by'])))
    if r.get('research_category_original') and r['research_category_original'] != r['research_category'] and r['research_category_original'] in CAT:
        G.add((x, KD.originalCategory, CAT[r['research_category_original']]))
    for l in LINKS.get(r['row_key'], []):
        if l['first_for_dataset'] and l['canonical_id'] in DSU: G.add((x, KD.usesDataset, DSU[l['canonical_id']]))
        if l.get('variant_id') and l['variant_id'] in VAR: G.add((x, KD.usesVariant, VAR[l['variant_id']]))
    return x
for r in m['evidence']: record(r, KD.DatasetUseRecord, 'record')
for r in m['peripheral']:
    if r['research_category'] not in CAT:
        c = u('category', slug(r['research_category'])); CAT[r['research_category']] = c; G.add((c, RDF.type, SKOS.Concept)); G.add((c, SKOS.prefLabel, Literal(r['research_category'], lang='en')))
    record(r, KD.PeripheralRecord, 'peripheral')

# decisions
for e in m['decision_log']:
    x = u('decision', e['no']); G.add((x, RDF.type, KD.Decision)); G.add((x, DCTERMS.identifier, Literal(str(e['no']))))
    lit(G, x, KD.decisionGroup, e['group']); lit(G, x, RDFS.label, e['item']); lit(G, x, KD.proposal, e['proposal']); lit(G, x, DCTERMS.source, e['evidence'])
    lit(G, x, KD.outcome, e['decision']); G.add((x, PROV.wasAssociatedWith, REVIEWER)); G.add((x, DCTERMS.date, Literal(e['date'], datatype=XSD.date)))
for rk, mv in MOVES.items():
    G.add((u('record', rk), PROV.wasInfluencedBy, u('decision-move', rk)))
    x = u('decision-move', rk); G.add((x, RDF.type, KD.Decision)); lit(G, x, KD.decisionGroup, 'Category move'); lit(G, x, KD.proposal, f"{mv['from']} -> {mv['to']} ({mv['rule']}): {mv['reason']}")
    G.add((x, PROV.wasAssociatedWith, REVIEWER)); G.add((x, DCTERMS.date, Literal(mv['date'], datatype=XSD.date)))

G.add((RESOURCE, VOID.triples, Literal(len(G) + 1)))
os.makedirs(PT.DATA, exist_ok=True)
V.serialize(os.path.join(PT.MODEL, 'kgdse-vocab.ttl'), format='turtle')
G.serialize(os.path.join(PT.DATA, 'kgdse.ttl'), format='turtle')
G.serialize(os.path.join(PT.DATA, 'kgdse.nt'), format='nt', encoding='utf-8')
cnt = C.Counter(o for _, _, o in G.triples((None, RDF.type, None)))
print('triples', len(G), '| vocab', len(V))
for c, n in sorted(cnt.items(), key=lambda kv: -kv[1])[:16]: print(f'  {G.namespace_manager.normalizeUri(c)}: {n}')
