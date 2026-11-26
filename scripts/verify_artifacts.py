"""Acceptance checks on real saved runs; never substitutes for running the model."""
import json
import sys
from pathlib import Path

from forgeai.agent import Agent
from forgeai.storage import read, digest
from forgeai.evaluation import validate_case


def verify(folder):
    root = Path(folder)
    state, suite, agent = (read(root / name) for name in ('state.json', 'evals.json', 'agent.json'))
    assert state['status'] == 'completed', f"Run is incomplete: {state['status']}"
    cases = suite['cases']
    assert len(cases) >= 20
    assert digest(cases) == suite['sha256'], 'Evaluation set changed after generation'
    if (root / 'recovery.json').exists():
        recovery = read(root / 'recovery.json')
        if 'frozen_evals_sha256' in recovery:
            assert suite['sha256'] == recovery['frozen_evals_sha256'], 'Recovery changed the frozen evaluation set'
    assert {'answerable', 'multi_document', 'ambiguous', 'out_of_scope'} <= {c['kind'] for c in cases}
    corpus = read(root / 'corpus.json')
    for case in cases:
        validate_case(case, corpus['chunks'])
    Agent.load(root / 'agent.json', None)  # Validates document and corpus hashes without inference.
    iterations = read(root / 'iterations.json')
    assert 1 <= len(iterations) <= 3
    selected = read(root / f"agent.v{state['selected_version']}.json")
    assert selected == agent
    dev_ids = {c['id'] for c in cases if c['split'] == 'development'}
    hold_ids = {c['id'] for c in cases if c['split'] == 'holdout'}
    assert not dev_ids & hold_ids
    for iteration in iterations:
        scorecard = read(root / f"scorecard.v{iteration['version']}.json")
        assert scorecard['complete']
        assert {s['case_id'] for s in scorecard['cases']} == dev_ids
        assert all(s['category'] in {'retrieval_miss', 'prompt_defect', 'hallucination', 'wrong_refusal'} for s in scorecard['cases'] if not s['passed'])
    hold = read(root / 'scorecard.holdout.json')
    assert hold['complete'] and {s['case_id'] for s in hold['cases']} == hold_ids
    assert list((root / 'model_calls').glob('*.json')), 'No actual model-call evidence'
    assert (root / 'report.md').is_file()
    assert (root / 'changes.json').is_file()
    return {'run': str(root), 'status': 'verified', 'cases': len(cases), 'iterations': len(iterations),
            'tools': agent['tools'], 'development': iterations[state['selected_version']-1]['summary'], 'holdout': hold['summary']}


if __name__ == '__main__':
    for folder in sys.argv[1:] or ['artifacts/workshop', 'artifacts/coastal']:
        print(json.dumps(verify(folder), indent=2))
