from pathlib import Path

from .contracts import ANSWER, prompt
from .corpus import retrieve
from .storage import normalize, read, digest
from .tools import REGISTRY, execute


def evidence_errors(answer, chunks):
    errors = []
    available = {c['id']: c for c in chunks}
    if answer['status'] not in {'answered', 'refused', 'clarify'}:
        errors.append('Invalid response status')
    if not answer['answer'].strip():
        errors.append('Empty answer')
    for evidence in answer['evidence']:
        source = available.get(evidence['chunk_id'])
        if not source:
            errors.append('Citation was not retrieved: ' + evidence['chunk_id'])
        elif not evidence['quote'].strip() or normalize(evidence['quote']) not in normalize(source['text']):
            errors.append('Quoted evidence does not occur in cited chunk: ' + evidence['chunk_id'])
    return errors


class Agent:
    def __init__(self, definition, corpus, root, model):
        self.definition, self.corpus, self.root, self.model = definition, corpus, Path(root), model
        if definition.get('schema_version') != 1:
            raise ValueError('Unsupported agent schema version')
        if any(t not in REGISTRY for t in definition['tools']):
            raise ValueError('Agent definition contains an unknown tool')

    @classmethod
    def load(cls, definition_path, model):
        path = Path(definition_path).resolve()
        definition = read(path)
        corpus_path = (path.parent / definition['corpus_file']).resolve()
        root = (path.parent / definition['documents_dir']).resolve()
        if not corpus_path.is_relative_to(path.parent) or not root.is_relative_to(path.parent):
            raise ValueError('Packaged corpus paths must stay inside the artifact directory')
        corpus = read(corpus_path)
        if digest(corpus) != definition['corpus_sha256']:
            raise ValueError('Corpus artifact has changed; regenerate the agent')
        for entry in corpus['manifest']:
            source = (root / entry['source']).resolve()
            if not source.is_relative_to(root) or digest(source.read_bytes()) != entry['sha256']:
                raise ValueError('Source document hash mismatch: ' + entry['source'])
        return cls(definition, corpus, root, model)

    def answer(self, question):
        config = self.definition['retrieval']
        chunks = retrieve(self.corpus['chunks'], question, config['top_k'], config['diversify'])
        tool_results = []
        if self.definition['tools']:
            plan = self.model.ask('tool-plan', prompt('tool_plan'),
                                  {'question': question, 'evidence': chunks,
                                   'attached_tools': {t: REGISTRY[t] for t in self.definition['tools']}},
                                  {'calls': [{'name': '', 'arguments': [{'key': '', 'value': ''}]}]}, 500)
            for call in plan['calls'][:2]:
                args = {a['key']: a['value'] for a in call['arguments']}
                try:
                    result = execute(call['name'], args, self.definition['tools'], self.root)
                    tool_results.append({'name': call['name'], 'arguments': args, 'result': result})
                except (ValueError, KeyError, OSError, SyntaxError, ArithmeticError) as exc:
                    tool_results.append({'name': call['name'], 'arguments': args, 'error': str(exc)})
        answer = self.model.ask('answer', prompt('answer') + '\nAGENT RULES:\n' + self.definition['system_prompt'],
                                {'question': question, 'scope': self.definition['requirements']['scope'],
                                 'unsupported_topics': self.definition['requirements']['gaps'],
                                 'retrieved': chunks, 'tool_results': tool_results}, ANSWER, 650)
        errors = evidence_errors(answer, chunks)
        if answer['status'] == 'answered' and not answer['evidence'] and not any('result' in t for t in tool_results):
            errors.append('An answer has no source evidence or successful tool result')
        # Preserve raw output for the evaluator; never silently repair a fabricated citation.
        raw = answer
        if errors:
            answer = {'status': 'refused', 'answer': 'I could not verify the evidence for this answer. Please narrow the question or provide a supporting document.', 'evidence': []}
        return {'response': answer, 'raw_response': raw, 'guard_errors': errors,
                'retrieved_ids': [c['id'] for c in chunks], 'retrieved': chunks, 'tool_results': tool_results}
