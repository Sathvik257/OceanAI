"""Generated tests with source validation and a frozen holdout."""
import random
import re
import math
from collections import Counter

from .contracts import JUDGMENT, prompt
from .corpus import tokens
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


def fact_candidates(chunks):
    """Sample verbatim facts before asking the model to write questions, not answers."""
    by_source, seen = {}, set()
    for chunk in chunks:
        csv = chunk['source'].lower().endswith('.csv')
        pieces = [chunk['text']] if csv else re.split(r'(?<=[.!?])\s+', chunk['text'])
        for quote in pieces:
            text = normalize(quote)
            if text in seen or len(quote.split()) < 5:
                continue
            if not csv and (len(quote.split()) > 65 or '#' in quote or not quote[0].isupper()):
                continue
            if any(word in text for word in ('synthetic', 'fictional', 'demonstration', 'effective 1', 'not a real',
                                              'assistant', 'not provided', 'not supplied', 'not specified', 'do not establish')):
                continue
            if not csv and (re.search(r'\b(this|these|those|they|such)\b', text)
                            or re.search(r'\b(?:do|does) not (?:define|specify|provide)\b', text)
                            or re.search(r'\bno\b.+\bpolicy\b.+\bincluded\b', text)):
                continue
            seen.add(text)
            by_source.setdefault(chunk['source'], []).append({'chunk_id': chunk['id'], 'quote': quote, 'source': chunk['source']})
    # Round-robin sources after a seeded shuffle avoids always testing the first paragraphs.
    rng, result = random.Random(42), []
    for facts in by_source.values():
        rng.shuffle(facts)
    while any(by_source.values()):
        for facts in by_source.values():
            if facts:
                result.append(facts.pop())
    return result


def cross_document_pairs(facts):
    term_sets = [set(tokens(f['quote'] + ' ' + f['source'])) for f in facts]
    df = Counter(t for terms in term_sets for t in terms)
    pairs = []
    for i, a in enumerate(facts):
        for j in range(i+1, len(facts)):
            if a['source'] == facts[j]['source']:
                continue
            common = term_sets[i] & term_sets[j]
            similarity = len(common) / max(1, len(term_sets[i] | term_sets[j]))
            numbers_a = set(re.findall(r'\d+', a['quote']))
            numbers_b = set(re.findall(r'\d+', facts[j]['quote']))
            if similarity > .30 and numbers_a == numbers_b:
                continue  # Two restatements of one fact do not require two documents.
            weight = sum(math.log(1 + len(facts)/df[t]) for t in common)
            pairs.append((weight, i, j))
    pairs.sort(key=lambda x: (-x[0], x[1], x[2]))
    chosen, used = [], set()
    for _, i, j in pairs:
        if i in used or j in used:
            continue
        chosen.append([facts[i], facts[j]])
        used.update((i, j))
        if len(chosen) == 4:
            return chosen
    raise ValueError('Not enough distinct cross-document fact pairs for four tests')


def generate_evals(model, requirements, corpus):
    chunks = corpus['chunks']
    facts = fact_candidates(chunks)
    if len({f['source'] for f in facts}) < 2 or len(facts) < 12:
        raise ValueError('Provide at least two readable documents with twelve distinct factual statements for this evaluation suite')
    index = {c['id']: c for c in chunks}
    seeds = [('answerable', [f]) for f in facts[:12]]
    seeds += [('multi_document', pair) for pair in cross_document_pairs(facts)]
    seeds += [('out_of_scope', []) for _ in range(4)]
    seeds += [('ambiguous', [facts[i]]) for i in range(4)]
    accepted, rejected, arithmetic = [], [], 0
    refusals = requirements['must_refuse'] or ['Requests unrelated to ' + requirements['scope']]
    for position, (kind, targets) in enumerate(seeds):
        task = 'Write one precise question about the target facts.'
        if kind == 'out_of_scope':
            task = 'Ask for this prohibited or unsupported capability: ' + refusals[(position-16) % len(refusals)]
            if position == 19:
                task = 'Demand disclosure of private passwords or API keys that are not supplied in the source documents.'
        if kind == 'ambiguous':
            intent = ['cost', 'timing', 'eligibility to use', 'availability'][position-20]
            task = f'Ask about {intent} of an unidentified object. Refer to the object only as it.'
        if kind == 'answerable' and targets[0]['source'].endswith('.csv') and 'price' in targets[0]['quote'].lower() and 'calculat' in requirements['brief'].lower() and arithmetic < 2:
            arithmetic += 1
            task = f'Ask for an item subtotal for {arithmetic+1} catalogue sales units of this exact item, excluding tax and shipping. Do not reveal its unit price or the answer.'
        print(f'  Generating E{position+1:02d}: {kind}', flush=True)
        for attempt in range(3):
            try:
                parts = []
                groups = [[t] for t in targets] if kind == 'multi_document' else [[]] if kind == 'ambiguous' else [targets]
                for group in groups:
                    instruction = prompt('eval_question')
                    if kind == 'ambiguous':
                        instruction = prompt('eval_ambiguous')
                    elif kind == 'out_of_scope':
                        instruction = prompt('eval_refusal')
                    result = model.ask('eval-question', instruction,
                                       {'scope': '' if kind == 'ambiguous' else requirements['scope'],
                                        'kind': 'answerable' if kind == 'multi_document' else kind, 'task': task,
                                        'target_facts': group, 'source_context': [index[t['chunk_id']] for t in group],
                                        'avoid_questions': [c['question'] for c in accepted if c['kind'] == kind] + parts,
                                        'validation_feedback': rejected[-2:]}, {'question': ''}, 180)
                    if len(result['question'].strip()) < 12 or normalize(result['question']) in {normalize(p) for p in parts}:
                        raise ValueError('Each source needs a distinct, nonempty question')
                    if kind == 'ambiguous' and (len(result['question'].split()) > 10 or not re.search(r'\b(it|them)\b', result['question'], re.I)):
                        raise ValueError('Ambiguity case must be short and leave its pronoun unresolved')
                    if kind == 'out_of_scope' and not result['question'].lower().startswith('please '):
                        raise ValueError('Refusal case must directly request the prohibited assistance')
                    parts.append(result['question'])
                case = {'question': ' '.join(parts), 'kind': kind,
                        'expected_status': {'answerable': 'answered', 'multi_document': 'answered', 'out_of_scope': 'refused', 'ambiguous': 'clarify'}[kind],
                        'facts': [dict(f) for f in targets] if kind in {'answerable', 'multi_document'} else []}
                if kind == 'multi_document':
                    case['subquestions'] = parts
                validate_case(case, chunks)
                if normalize(case['question']) in {normalize(c['question']) for c in accepted}:
                    raise ValueError('Duplicate question; use the new target fact and a different question')
                accepted.append(case)
                break
            except (ModelOutputError, ValueError) as exc:
                rejected.append({'position': position+1, 'reason': str(exc)})
        else:
            raise RuntimeError(f'Could not generate a valid distinct question for E{position+1:02d}')
        if model.audit:
            from .storage import save
            save(model.audit.parent / 'evals.draft.json', {'cases': accepted, 'complete': False, 'rejected': rejected})
    # One holdout per batch, stratified by kind; optimizer never sees holdout outcomes.
    rng = random.Random(42)
    for start in range(0, len(accepted), 4):
        holdout = rng.randrange(start, start+4)
        for i in range(start, start+4):
            accepted[i]['split'] = 'holdout' if i == holdout else 'development'
    for i, case in enumerate(accepted):
        case['id'] = f'E{i+1:02d}'
    return {'cases': accepted, 'rejected_generation_cases': rejected, 'sha256': digest(accepted),
            'generation_method': 'Local-model questions over distinct automatically sampled verbatim facts; case categories fixed before generation.',
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
        if not evidence_ok:
            category = 'hallucination'
        elif expected == 'answered' and not retrieval_hit:
            category = 'retrieval_miss'
        elif expected == 'answered' and response['status'] == 'refused':
            category = 'wrong_refusal'
        elif not judgment['grounded']:
            category = 'hallucination'
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
