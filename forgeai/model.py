"""Local HTTP inference with schema validation, bounded retries and an audit trail."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .storage import save


class BudgetExceeded(RuntimeError):
    pass


class ModelOutputError(RuntimeError):
    pass


def schema(example):
    if isinstance(example, dict):
        return {'type': 'object', 'properties': {k: schema(v) for k, v in example.items()},
                'required': list(example), 'additionalProperties': False}
    if isinstance(example, list):
        return {'type': 'array', 'items': schema(example[0]) if example else {'type': 'string'}}
    return {'type': 'boolean' if isinstance(example, bool) else 'integer' if isinstance(example, int) else 'string'}


def validate(value, template, path='result'):
    if type(value) is not type(template):
        raise ValueError(f'{path}: expected {type(template).__name__}')
    if isinstance(template, dict):
        if set(value) != set(template):
            raise ValueError(f'{path}: wrong keys {set(value) ^ set(template)}')
        for key in template:
            validate(value[key], template[key], f'{path}.{key}')
    if isinstance(template, list) and template:
        for item in value:
            validate(item, template[0], path + '[]')


def constrained_schema(example, data):
    result = schema(example)
    evidence = data.get('retrieved', data.get('evidence', [])) if isinstance(data, dict) else []
    ids = [c['id'] for c in evidence if isinstance(c, dict) and 'id' in c] if isinstance(evidence, list) else []

    def visit(node):
        for key, value in node.get('properties', {}).items():
            if key == 'chunk_id' and ids:
                value['enum'] = ids + ['']
            if key in {'status', 'expected_status'}:
                value['enum'] = ['answered', 'refused', 'clarify']
            if key == 'kind':
                value['enum'] = ['answerable', 'multi_document', 'out_of_scope', 'ambiguous']
            if key == 'answer':
                value['minLength'] = 1
            if key == 'patch' and isinstance(data.get('allowed_patches'), dict):
                value['enum'] = list(data['allowed_patches'])
            visit(value)
        if 'items' in node:
            visit(node['items'])
    visit(result)
    return result


class LocalModel:
    def __init__(self, endpoint='http://127.0.0.1:8080/v1', model='qwen3-4b-instruct-2507',
                 audit=None, max_tokens=300000, seconds=10800, timeout=600):
        self.endpoint, self.model, self.audit = endpoint.rstrip('/'), model, Path(audit) if audit else None
        self.limit, self.seconds, self.timeout = max_tokens, seconds, timeout
        self.used, self.calls, self.start = 0, 0, time.monotonic()

    def stats(self):
        return {'model': self.model, 'endpoint': self.endpoint, 'calls': self.calls,
                'tokens': self.used, 'token_limit': self.limit,
                'elapsed_seconds': round(time.monotonic()-self.start, 2), 'seconds_limit': self.seconds}

    def request(self, url, payload, timeout):
        request = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def ask(self, stage, system, data, example, max_output=1400):
        user = json.dumps(data, ensure_ascii=False, indent=2)
        for attempt in range(2):
            # Conservative character-based reservation when tokenizer isn't exposed.
            reserve = len(system + user) + max_output
            remaining = self.seconds - (time.monotonic()-self.start)
            if self.used + reserve > self.limit or remaining <= 0:
                raise BudgetExceeded(f'Budget exhausted before {stage}')
            self.calls += 1
            messages = [{'role': 'system', 'content': system + '\nReturn JSON matching this example shape: ' + json.dumps(example)},
                        {'role': 'user', 'content': user}]
            if self.endpoint.endswith('/v1'):
                url = self.endpoint + '/chat/completions'
                payload = {'model': self.model, 'messages': messages, 'temperature': 0, 'seed': 42,
                           'max_tokens': max_output, 'response_format': {'type': 'json_object', 'schema': constrained_schema(example, data)}}
            else:
                url = self.endpoint + '/api/chat'
                payload = {'model': self.model, 'messages': messages, 'stream': False, 'format': constrained_schema(example, data),
                           'options': {'temperature': 0, 'seed': 42, 'num_predict': max_output, 'num_ctx': 6144}}
            record = {'stage': stage, 'attempt': attempt+1, 'request': payload}
            begin = time.monotonic()
            try:
                raw = self.request(url, payload, min(self.timeout, remaining))
                record['response'] = raw
                consumed = raw.get('usage', {}).get('total_tokens') or (raw.get('prompt_eval_count', 0) + raw.get('eval_count', 0)) or reserve
                self.used += consumed
                if self.endpoint.endswith('/v1'):
                    choice = raw['choices'][0]
                    if choice.get('finish_reason') == 'length':
                        raise ValueError('Model output was truncated')
                    content = choice['message']['content']
                else:
                    if raw.get('done_reason') == 'length':
                        raise ValueError('Model output was truncated')
                    content = raw['message']['content']
                parsed = json.loads(content)
                validate(parsed, example)
                record['valid'] = True
                return parsed
            except (ValueError, KeyError, IndexError) as exc:
                record['error'] = str(exc)
                if attempt:
                    raise ModelOutputError(f'{stage}: invalid model output after two attempts: {exc}') from exc
                user += '\nPrevious response was invalid: ' + str(exc) + '. Produce the required JSON only.'
            except (urllib.error.URLError, TimeoutError) as exc:
                self.used += reserve  # Timed-out work may have consumed tokens remotely.
                record['error'] = str(exc)
                raise RuntimeError(f'Local model request failed at {stage}: {exc}') from exc
            finally:
                record['elapsed_seconds'] = round(time.monotonic()-begin, 3)
                if getattr(self, 'last_replay', None):
                    record.update(self.last_replay)
                if self.audit:
                    save(self.audit / f'{self.calls:04d}-{stage}.json', record)
