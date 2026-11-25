"""Generated tests with source validation and a frozen holdout."""
import random
from collections import Counter

from .contracts import CASE, JUDGMENT, prompt
from .storage import digest, normalize
from .model import ModelOutputError


def validate_case(case, chunks):
    index = {c['id']: c for c in chunks}
    expected = {'answerable': 'answered', 'multi_document': 'answered', 'out_of_scope': 'refused', 'ambiguous': 'clarify'}
    if case['kind'] not in expected or case['expected_status'] != expected[case['kind']]:
        raise ValueError('Case kind/status mismatch')
    if len(case['question'].strip()) < 12:
        raise ValueError('Question is too short')
    if case['expected_status'] == 'answered' and not case['facts']:
        raise ValueError('Answerable case has no expected facts')
    if case['expected_status'] != 'answered' and case['facts']:
        raise ValueError('Refusal/ambiguity case must not prescribe an answer')
    sources = set()
    for fact in case['facts']:
        chunk = index.get(fact['chunk_id'])
        if not chunk or len(fact['quote'].strip()) < 3 or normalize(fact['quote']) not in normalize(chunk['text']):
            raise ValueError('Expected fact is not a verbatim source quote')
        fact['source'] = chunk['source']
        sources.add(chunk['source'])
    if case['kind'] == 'multi_document' and len(sources) < 2:
        raise ValueError('Multi-document case must cite two distinct documents')


def generate_evals(model, requirements, corpus):
    chunks = corpus['chunks']
    if len({c['source'] for c in chunks}) < 2:
        raise ValueError('At least two readable source documents are required for cross-document evaluations')
    accepted, rejected = [], []
    rng = random.Random(42)
    schedule = [('answerable', 4), ('answerable', 4), ('answerable', 4),
                ('multi_document', 4), ('out_of_scope', 4), ('ambiguous', 4)]
    for batch, (kind, target) in enumerate(schedule):
        batch_cases = []
        # Spread excerpts across documents; avoid stuffing the entire corpus into a small context.
        rotated = chunks[(batch * 3) % len(chunks):] + chunks[:(batch * 3) % len(chunks)]
        evidence, sources = [], set()
        for c in rotated:
            if c['source'] not in sources:
                evidence.append(c)
                sources.add(c['source'])
        evidence += [c for c in rotated if c not in evidence]
        evidence = evidence[:8]
        for attempt in range(3):
            try:
                result = model.ask('eval-generation', prompt('eval'),
                                   {'requirements': requirements, 'kind': kind, 'count': target-len(batch_cases),
                                    'evidence': evidence, 'existing_questions': [c['question'] for c in accepted+batch_cases],
                                    'validation_feedback': rejected[-3:]}, {'cases': [CASE]}, 2200)
            except ModelOutputError as exc:
                rejected.append({'question': '', 'reason': str(exc)})
                continue
            for case in result['cases']:
                try:
                    if case['kind'] != kind:
                        raise ValueError('Wrong requested kind')
                    validate_case(case, chunks)
                    if normalize(case['question']) in {normalize(c['question']) for c in accepted+batch_cases}:
                        raise ValueError('Duplicate question')
                    batch_cases.append(case)
                except ValueError as exc:
                    rejected.append({'question': case.get('question', ''), 'reason': str(exc)})
                if len(batch_cases) == target:
                    break
            if len(batch_cases) == target:
                break
        if len(batch_cases) < target:
            raise RuntimeError(f'Evaluation generation failed: only {len(batch_cases)}/{target} valid {kind} cases; do not claim completion')
        accepted += batch_cases
    # One holdout per batch, stratified by kind; optimizer never sees holdout outcomes.
    for start in range(0, len(accepted), 4):
        holdout = rng.randrange(start, start+4)
        for i in range(start, start+4):
            accepted[i]['split'] = 'holdout' if i == holdout else 'development'
    for i, case in enumerate(accepted):
        case['id'] = f'E{i+1:02d}'
    return {'cases': accepted, 'rejected_generation_cases': rejected, 'sha256': digest(accepted),
            'warning': 'Source quotes are verified; semantic validity of model-generated questions and labels still needs human review.'}


def score_case(model, case, run):
    response = run['response']
    expected = case['expected_status']
    evidence_ok = not run['guard_errors']
    status_ok = response['status'] == expected
    cited = {e['chunk_id'] for e in response['evidence']}
    required = {f['chunk_id'] for f in case['facts']}
    # Exact chunk identity is a diagnostic, not a hard correctness condition (overlap can hold the same fact).
    retrieval_hit = required.issubset(set(run['retrieved_ids']))
    judgment = model.ask('judge', prompt('judge'),
                         {'question': case['question'], 'expected_status': expected,
                          'expected_facts': case['facts'], 'candidate': response,
                          'cited_sources': [c for c in run['retrieved'] if c['id'] in cited],
                          'tool_results': run['tool_results']}, JUDGMENT, 260)
    passed = evidence_ok and status_ok and all(judgment[k] for k in ('correct', 'grounded', 'behavior'))
    category = None
    if not passed:
        if not evidence_ok or not judgment['grounded']:
            category = 'hallucination'
        elif expected == 'answered' and not retrieval_hit:
            category = 'retrieval_miss'
        elif expected == 'answered' and response['status'] == 'refused':
            category = 'wrong_refusal'
        else:
            category = 'prompt_defect'
    return {'case_id': case['id'], 'kind': case['kind'], 'split': case['split'], 'passed': passed,
            'category': category, 'evidence_valid': evidence_ok, 'status_correct': status_ok,
            'retrieval_hit': retrieval_hit, 'judge': judgment, 'execution': run}


def summarize(scores):
    total = len(scores)
    passed = sum(s['passed'] for s in scores)
    return {'passed': passed, 'total': total, 'pass_rate': round(passed/total, 4) if total else None,
            'failure_categories': dict(Counter(s['category'] for s in scores if not s['passed'])),
            'by_kind': {kind: {'passed': sum(s['passed'] for s in scores if s['kind'] == kind),
                               'total': sum(s['kind'] == kind for s in scores)} for kind in sorted({s['kind'] for s in scores})}}
