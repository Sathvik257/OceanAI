"""Explicit state machine: intake -> definition -> frozen evals -> bounded repair."""
import copy
import json
import re
import shutil
import platform
from datetime import datetime, timezone
from pathlib import Path

from .agent import Agent
from .contracts import DEFINITION, prompt
from .corpus import ingest, retrieve
from .evaluation import generate_evals, score_case, summarize
from .model import BudgetExceeded, ModelOutputError
from .storage import digest, normalize, save
from .tools import REGISTRY

PATCHES = {
    'increase_retrieval': 'Increase retrieval top_k by 2, capped at 8.',
    'diversify_retrieval': 'Retrieve from distinct documents before additional chunks from one document.',
    'source_only': 'State only claims directly entailed by quoted evidence. Preserve numbers, exceptions and conditions. Refuse unsupported additions.',
    'reduce_wrong_refusal': 'Do not refuse merely because the question uses different words from the policy. When evidence answers the question within scope, answer with its exact facts.',
    'clarify_and_cover': 'When the requested entity or policy is unspecified, ask a targeted clarifying question. Otherwise cover every part of the question, including conditions from different documents.',
}


def intake(model, brief, corpus, interactive=False):
    # First capture user intent WITHOUT allowing the corpus to erase unsupported requests.
    shape = {'scope': '', 'audience': '', 'tone': '', 'must_answer': [''], 'must_refuse': [''],
             'questions': [''], 'assumptions': ['']}
    req = model.ask('intake-brief', prompt('brief'), {'brief': brief}, shape, 950)
    answers = {}
    # Preserve explicit brief constraints even if a small model omits them.
    explicit = re.findall(r'[^.!?]*(?:\bdo not\b|\bmust not\b|\bnever\b)[^.!?]*[.!?]?', brief, re.I)
    req['must_refuse'] = list(dict.fromkeys(req['must_refuse'] + [s.strip() for s in explicit]))
    if not req['must_answer'] or len(req['must_answer']) > 20:
        raise ValueError('Intake must identify 1-20 requested topics')
    req['coverage'], req['gaps'] = [], []
    # Inspect every source through topic retrieval; lack of a supporting quote is conservative.
    for topic in req['must_answer']:
        if re.search(r"\b(?:current\s+(?:utc\s+)?date|today(?:'s|’s)?\s+date)\b", topic, re.I):
            req['coverage'].append({'topic': topic, 'supported': True, 'chunk_ids': [], 'quote': '',
                                    'tool': 'current_date', 'reason': 'The registered current_date tool supplies the current UTC date; this is tool-backed, not a document claim.'})
            continue
        evidence = retrieve(corpus['chunks'], topic, top_k=4, diversify=True)
        candidate = model.ask('coverage-extract', prompt('coverage_extract'), {'topic': topic, 'evidence': evidence},
                              {'chunk_id': '', 'quote': ''}, 250)
        coverage = {**candidate, 'supported': False, 'reason': 'No verifiable relevant quote was found.'}
        chunk = next((c for c in evidence if c['id'] == candidate['chunk_id']), None)
        quote_valid = bool(chunk and candidate['quote'].strip() and normalize(candidate['quote']) in normalize(chunk['text']))
        if quote_valid:
            verdict = model.ask('groundability', prompt('groundability'), {'topic': topic, 'quote': candidate['quote']},
                                 {'supported': True, 'reason': ''}, 160)
            coverage.update(verdict)
        item = {'topic': topic, **coverage, 'chunk_ids': [coverage['chunk_id']] if quote_valid else []}
        req['coverage'].append(item)
        if not coverage['supported']:
            req['gaps'].append(topic)
    req['requested_topics'] = list(req['must_answer'])
    req['must_answer'] = [c['topic'] for c in req['coverage'] if c['supported']]
    req['must_refuse'] = list(dict.fromkeys(req['must_refuse'] + req['gaps']))
    interview = model.ask('intake-questions', prompt('questions'),
                          {'brief': brief, 'requirements': req, 'source_inventory': corpus.get('manifest', [])},
                          {'questions': ['']}, 400)
    req['questions'] = interview['questions'][:5]
    if interactive:
        for question in req['questions']:
            answers[question] = input(question + '\n> ').strip()
        if any(answers.values()):
            revised = intake(model, brief + '\nRequester clarifications:\n' + json.dumps(answers), corpus, False)
            revised['questions'] = list(answers)
            req = revised
    req['brief'] = brief
    req['clarification_answers'] = answers
    req['mode'] = 'interactive' if interactive else 'unattended'
    if not interactive and req['questions']:
        req['assumptions'].append('Clarifying questions were not answered; use only supported document scope and refuse missing information.')
    req['groundability_method'] = 'Brief-only intent extraction, per-topic retrieval and model support assessment, plus exact evidence validation. Conservative gaps may include retrieval misses.'
    return req


def make_definition(model, req, corpus):
    selection = model.ask('tool-selection', prompt('tool_selection'),
                          {'brief': req['brief'], 'registry': REGISTRY,
                           'has_csv': any(m['source'].lower().endswith('.csv') for m in corpus['manifest'])},
                          {'tools': ['']}, 120)
    selected = list(dict.fromkeys(selection['tools']))
    if any(name not in REGISTRY for name in selected):
        raise ValueError('Tool selector proposed an unknown registry tool')
    if 'csv_lookup' in selected and not any(m['source'].lower().endswith('.csv') for m in corpus['manifest']):
        raise ValueError('Tool selector requested CSV lookup without a CSV source')
    required = {c['tool'] for c in req.get('coverage', []) if c.get('supported') and c.get('tool')}
    if not required.issubset(selected):
        raise ValueError('Tool-backed requirements lack their required tool attachment')
    generated = model.ask('agent-generation', prompt('generate'),
                           {'brief': req['brief'], 'requirements': req,
                            'attached_tools': {name: REGISTRY[name] for name in selected}}, DEFINITION, 900)
    return {'schema_version': 1, 'name': generated['name'], 'system_prompt': generated['system_prompt'],
            'requirements': req, 'chunking': corpus['chunking'],
            'retrieval': {'method': 'bm25', 'top_k': max(2, min(6, generated['top_k'])), 'diversify': False},
            'tools': selected, 'tool_selection': {'method': 'Isolated local-model selection from the brief, followed by registry and corpus validation.',
                                                'brief': req['brief'], 'registry': REGISTRY},
            'output_contract': {'status': ['answered', 'refused', 'clarify'], 'answer': 'string',
                                'evidence': [{'chunk_id': 'retrieved ID', 'quote': 'verbatim source text'}]},
            'corpus_file': 'corpus.json', 'documents_dir': 'documents', 'corpus_sha256': digest(corpus)}


def propose_patch(model, definition, scores, used):
    failures = [{'id': s['case_id'], 'category': s['category'], 'reason': s['judge']['reason']} for s in scores if not s['passed']]
    targets = {'increase_retrieval': 'retrieval_miss', 'diversify_retrieval': 'retrieval_miss',
               'source_only': 'hallucination', 'reduce_wrong_refusal': 'wrong_refusal',
               'clarify_and_cover': 'prompt_defect'}
    categories = {s['category'] for s in failures}
    allowed = {k: v for k, v in PATCHES.items() if k not in used and targets[k] in categories}
    if definition['retrieval']['top_k'] >= 8:
        allowed.pop('increase_retrieval', None)
    if definition['retrieval']['diversify']:
        allowed.pop('diversify_retrieval', None)
    result = model.ask('critic', prompt('critic'),
                       {'failures': failures, 'configuration': definition['retrieval'],
                        'score': summarize(scores), 'allowed_patches': {**allowed, 'stop': 'No justified fix remains'}},
                       {'patch': '', 'reason': ''}, 400)
    if result['patch'] == 'stop':
        return None, result
    if result['patch'] not in allowed:
        raise ValueError('Critic proposed a disallowed patch')
    changed = copy.deepcopy(definition)
    name = result['patch']
    addressed = [s['id'] for s in failures if s['category'] == targets[name]]
    if not addressed:
        return None, {'patch': 'stop', 'reason': 'The critic proposed a patch with no matching diagnosed failures; no change applied.'}
    if name == 'increase_retrieval':
        changed['retrieval']['top_k'] = min(8, changed['retrieval']['top_k']+2)
    elif name == 'diversify_retrieval':
        changed['retrieval']['diversify'] = True
    else:
        changed['system_prompt'] += '\n' + PATCHES[name]
    result.update({'addressed_failures': addressed,
                   'unaddressed_failures': [s['id'] for s in failures if s['id'] not in addressed], 'change': PATCHES[name],
                   'before_definition_sha256': digest(definition), 'after_definition_sha256': digest(changed)})
    return changed, result


def evaluate(model, definition, corpus, root, cases, destination):
    agent, scores = Agent(definition, corpus, root, model), []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['id']} {case['kind']}", flush=True)
        execution = None
        try:
            execution = agent.answer(case['question'])
            scores.append(score_case(model, case, execution))
        except ModelOutputError as exc:
            # A malformed answer/judgment is a failed case, not permission to skip it.
            scores.append({'case_id': case['id'], 'kind': case['kind'], 'split': case['split'],
                           'passed': False, 'category': 'prompt_defect', 'evidence_valid': False,
                           'status_correct': False, 'retrieval_hit': False, 'evaluation_error': str(exc),
                           'judge': {'correct': False, 'grounded': False, 'behavior': False,
                                     'reason': 'Structured-output failure; semantic correctness was not established: ' + str(exc)},
                           'execution': execution})
        save(destination, {'summary': summarize(scores), 'cases': scores, 'complete': len(scores) == len(cases)})
    return scores


def report(out, state, iterations, patches, holdout, stats):
    lines = ['# ForgeAI quality report', '', f"Run status: **{state['status']}**", '',
             f"Model: `{stats['model']}`. Real local inference; {stats['calls']} calls, {stats['tokens']} reported/reserved tokens.", '',
             '## Development evaluations', '', '| Version | Passed | Rate | Selected |', '|---|---:|---:|---|']
    for item in iterations:
        s = item['summary']
        lines.append(f"| {item['version']} | {s['passed']}/{s['total']} | {s['pass_rate']:.1%} | {'yes' if item['version'] == state.get('selected_version') else 'no'} |")
    lines += ['', '## Holdout (never used to choose patches)', '']
    if holdout:
        h = summarize(holdout)
        lines.append(f"{h['passed']}/{h['total']} passed ({h['pass_rate']:.1%}). This small, model-generated sample is not an estimate of production accuracy.")
    else:
        lines.append('Not completed. No holdout quality claim is made.')
    lines += ['', '## Remaining observed failures', '']
    if stats.get('replayed_calls'):
        lines += [f"Recovery reused {stats['replayed_calls']} exact recorded model responses; {stats['new_calls']} calls were newly executed. See recovery.json. Reuse is not new inference; resource totals include prior usage and a conservative interrupted-request reservation.", '']
    selected = next((i for i in iterations if i['version'] == state.get('selected_version')), None)
    failures = ([s for s in selected['cases'] if not s['passed']] if selected else []) + [s for s in holdout if not s['passed']]
    lines += [f"- {s['case_id']} ({s['split']}, {s['category']}): {s['judge']['reason']}" for s in failures] or ['No failures observed in the completed cases; this does not establish perfect correctness.']
    if state.get('error'):
        lines += ['', '## Incomplete work', '', state['error']]
    lines += ['', '## Changes and tradeoffs', '']
    lines += [f"- {p.get('patch')}: {p.get('reason')} Accepted: {p.get('accepted', False)}; before {p.get('score_before')}, after {p.get('score_after')}." for p in patches] or ['No repair was applied.']
    lines += ['', '## Limits of this evidence', '',
              '- The same small model generates tests and supplies semantic judgments: correlated mistakes and self-preference remain possible. The judge sees no model identity or competing answer and receives no reward for verbosity; deterministic quote checks cannot establish semantic entailment.',
              '- Expected facts are verified verbatim against sources; the questions, refusal labels and coverage claims still require human review. A wrong test oracle can distort scores.',
              '- BM25 can miss paraphrases. PDFs need extractable text; scanned pages have no automatic OCR. Tables in PDFs may lose layout.',
              '- The optimizer sees development failures only. Holdout remains a small in-domain check, not an unseen-domain benchmark.',
              '- Demo artifacts were inspected during development. Holdout is hidden from the in-run optimizer, not an untouched external benchmark of the development process.',
              '- Corpus text and model call transcripts are stored locally in artifacts. Do not publish runs containing confidential input.',
              '- Source prompt injection, model errors and incorrect tool arguments remain risks. Tools are read-only and bounded; no generated code is executed.',
              '- Live date values depend on the run date. No external weather or paid service is required.', '']
    (out / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def build(model, brief, documents, output, interactive=False, max_iterations=3):
    if not 1 <= max_iterations <= 3:
        raise ValueError('The assignment permits at most three evaluated iterations')
    out = Path(output).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty to preserve previous run evidence')
    out.mkdir(parents=True, exist_ok=True)
    model.audit = out / 'model_calls'
    state = {'status': 'running', 'stage': 'ingest', 'started_utc': datetime.now(timezone.utc).isoformat()}
    iterations, patches, holdout = [], [], []
    save(out / 'state.json', state)
    source_root = Path(__file__).parent
    save(out / 'implementation.json', {
        'python': platform.python_version(), 'platform': platform.platform(),
        'source_sha256': {p.relative_to(source_root).as_posix(): digest(p.read_bytes())
                          for p in sorted(source_root.rglob('*')) if p.is_file() and p.suffix in {'.py', '.txt'}},
        'model_configuration': {'endpoint': model.endpoint, 'model': model.model, 'temperature': 0, 'seed': 42},
    })
    try:
        corpus = ingest(documents)
        save(out / 'corpus.json', corpus)
        for entry in corpus['manifest']:
            target = out / 'documents' / entry['source']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(documents) / entry['source'], target)
        for name in ['brief', 'coverage_extract', 'groundability', 'questions', 'tool_selection', 'generate', 'eval_question', 'eval_ambiguous', 'eval_refusal', 'answer', 'tool_plan', 'judge', 'critic']:
            target = out / 'prompts' / (name + '.txt')
            target.parent.mkdir(exist_ok=True)
            target.write_text(prompt(name), encoding='utf-8')
        print('Intake and groundability assessment', flush=True)
        state['stage'] = 'intake'
        save(out / 'state.json', state)
        req = intake(model, brief, corpus, interactive)
        save(out / 'requirements.json', req)
        print(f"Groundability: {len(req['gaps'])} gap(s) flagged", flush=True)
        if not any(c['supported'] for c in req['coverage']):
            raise ValueError('No requested topic has verified source references; supply supporting documents')
        state['stage'] = 'definition'
        save(out / 'state.json', state)
        definition = make_definition(model, req, corpus)
        save(out / 'agent.json', definition)
        print('Generating and validating the frozen evaluation suite', flush=True)
        state['stage'] = 'eval_generation'
        save(out / 'state.json', state)
        suite = generate_evals(model, req, corpus)
        save(out / 'evals.json', suite)
        dev = [c for c in suite['cases'] if c['split'] == 'development']
        hold = [c for c in suite['cases'] if c['split'] == 'holdout']
        best, best_scores, best_rate, used = definition, [], -1, set()
        pending = None
        for version in range(1, max_iterations+1):
            state['stage'] = f'iteration_{version}'
            save(out / 'state.json', state)
            save(out / f'agent.v{version}.json', definition)
            print(f'Evaluating version {version}', flush=True)
            scores = evaluate(model, definition, corpus, out / 'documents', dev, out / f'scorecard.v{version}.json')
            summary = summarize(scores)
            iterations.append({'version': version, 'summary': summary, 'cases': scores})
            if pending:
                pending['score_after'] = summary['pass_rate']
                pending['accepted'] = summary['pass_rate'] > best_rate
                before = {s['case_id'] for s in best_scores if s['passed']}
                after = {s['case_id'] for s in scores if s['passed']}
                pending['regressions'] = sorted(before-after)
                pending['improvements'] = sorted(after-before)
                pending['evaluation_completed'] = True
                save(out / 'changes.json', patches)
            if summary['pass_rate'] > best_rate:
                best, best_scores, best_rate = definition, scores, summary['pass_rate']
                state['selected_version'] = version
                save(out / 'agent.json', best)
            print(f"Version {version}: {summary['passed']}/{summary['total']} passed", flush=True)
            if best_rate == 1 or version == max_iterations or (pending and not pending['accepted']):
                break
            definition, pending = propose_patch(model, best, best_scores, used)
            if definition is None:
                patches.append({**pending, 'accepted': False, 'score_before': best_rate})
                break
            used.add(pending['patch'])
            pending['score_before'] = best_rate
            pending['evaluation_completed'] = False
            pending['accepted'] = False
            patches.append(pending)
            save(out / 'changes.json', patches)
        save(out / 'changes.json', patches)
        state['stage'] = 'holdout'
        save(out / 'state.json', state)
        print('Evaluating held-out cases once on the selected definition', flush=True)
        holdout = evaluate(model, best, corpus, out / 'documents', hold, out / 'scorecard.holdout.json')
        state['status'] = 'completed'
        state['stage'] = 'done'
    except KeyboardInterrupt:
        state['status'] = 'interrupted'
        state['error'] = 'Run interrupted before completion; partial scores are not a completed demonstration.'
    except (BudgetExceeded, RuntimeError, ValueError, OSError, ImportError) as exc:
        state['status'] = 'budget_exhausted' if isinstance(exc, BudgetExceeded) else 'failed'
        state['error'] = str(exc)
        print(f"Stopped honestly: {exc}", flush=True)
    finally:
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save(out / 'state.json', state)
        save(out / 'usage.json', model.stats())
        save(out / 'iterations.json', [{'version': i['version'], 'summary': i['summary']} for i in iterations])
        report(out, state, iterations, patches, holdout, model.stats())
    return state
