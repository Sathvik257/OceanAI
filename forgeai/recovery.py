"""Recover interrupted work by replaying an exact audited request prefix.

This is recorded inference reuse, never synthetic model output. Any request
mismatch stops recovery before new inference can mix incompatible histories.
"""
import copy
from pathlib import Path

from .model import LocalModel
from .storage import read, save


class RecoveryModel(LocalModel):
    def __init__(self, source, **kwargs):
        super().__init__(**kwargs)
        self.source = Path(source).resolve()
        files = sorted((self.source / 'model_calls').glob('*.json'))
        self.records = [(p, read(p)) for p in files]
        if not files or any('response' not in r for _, r in self.records):
            raise ValueError('Recovery needs a contiguous audited prefix with recorded model responses')
        if [int(p.name.split('-')[0]) for p in files] != list(range(1, len(files)+1)):
            raise ValueError('Recovery audit prefix has missing or duplicate calls')
        old = read(self.source / 'recovery.json') if (self.source / 'recovery.json').exists() else {}
        # The last unrecorded request may have consumed resources before interruption.
        self.lost_tokens = old.get('unrecorded_token_reservation', 0) + 10000
        self.lost_seconds = old.get('unrecorded_seconds_reservation', 0) + self.timeout
        elapsed = sum(r.get('original_elapsed_seconds', r['elapsed_seconds']) for _, r in self.records)
        self.used = self.lost_tokens
        self.start -= elapsed + self.lost_seconds
        self.replayed = 0
        self.last_replay = None
        self.provenance = {
            'source_run': str(self.source), 'recorded_prefix_calls': len(files),
            'unrecorded_token_reservation': self.lost_tokens,
            'unrecorded_seconds_reservation': self.lost_seconds,
            'original_inference_seconds': elapsed,
            'note': 'Exact request-prefix replay of actual saved inference. Replayed calls are not new model executions. A mismatch stops recovery. Budgets include prior usage and a conservative allowance for the lost in-flight request.',
        }
        suite = self.source / 'evals.json'
        if suite.exists():
            self.provenance['frozen_evals_sha256'] = read(suite)['sha256']

    def request(self, url, payload, timeout):
        self.last_replay = None
        if self.calls <= len(self.records):
            path, record = self.records[self.calls-1]
            if payload != record['request']:
                raise RuntimeError(f'Recovery request {self.calls} differs from the saved request; use a new run instead')
            self.replayed += 1
            self.last_replay = {'replayed_from': str(path),
                                'original_elapsed_seconds': record.get('original_elapsed_seconds', record['elapsed_seconds'])}
            if self.audit:
                save(self.audit.parent / 'recovery.json', self.provenance)
            return copy.deepcopy(record['response'])
        return super().request(url, payload, timeout)

    def stats(self):
        return {**super().stats(), 'replayed_calls': self.replayed,
                'new_calls': self.calls-self.replayed,
                'unrecorded_token_reservation': self.lost_tokens,
                'unrecorded_seconds_reservation': self.lost_seconds}
