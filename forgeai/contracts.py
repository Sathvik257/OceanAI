from pathlib import Path

DEFINITION = {'name': '', 'system_prompt': '', 'top_k': 3,
              'tools': [{'name': '', 'brief_quote': '', 'reason': ''}]}
CASE = {'question': '', 'kind': '', 'expected_status': '', 'facts': [{'chunk_id': '', 'quote': ''}]}
ANSWER = {'status': '', 'answer': '', 'evidence': [{'chunk_id': '', 'quote': ''}]}
JUDGMENT = {'reason': '', 'correct': True, 'grounded': True, 'behavior': True}


def prompt(name):
    return (Path(__file__).parent / 'prompts' / (name + '.txt')).read_text(encoding='utf-8')
