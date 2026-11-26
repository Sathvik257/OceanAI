import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgeai.model import LocalModel
from forgeai.recovery import RecoveryModel


class RecoveryTests(unittest.TestCase):
    def make_prefix(self, root):
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":"Test response"}'}}],
                    'usage': {'total_tokens': 25}}
        model = LocalModel(audit=Path(root, 'source', 'model_calls'))
        with patch.object(model, 'request', return_value=response):
            model.ask('test', 'Test-only prompt', {'question': 'Test input'}, {'answer': ''})
        return response

    def test_exact_prefix_reuses_actual_record_without_network_and_keeps_budget(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.make_prefix(root)
            model = RecoveryModel(Path(root, 'source'), audit=Path(root, 'resumed', 'model_calls'))
            with patch.object(LocalModel, 'request', return_value=response) as network:
                result = model.ask('test', 'Test-only prompt', {'question': 'Test input'}, {'answer': ''})
                network.assert_not_called()
                self.assertEqual(result['answer'], 'Test response')
                self.assertEqual(model.used, 10025)
                self.assertEqual(model.stats()['replayed_calls'], 1)
                model.ask('next', 'New test prompt', {}, {'answer': ''})
                network.assert_called_once()
                self.assertEqual(model.stats()['new_calls'], 1)

    def test_changed_request_stops_recovery_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_prefix(root)
            model = RecoveryModel(Path(root, 'source'))
            with patch.object(LocalModel, 'request') as network:
                with self.assertRaisesRegex(RuntimeError, 'differs from the saved request'):
                    model.ask('test', 'Changed prompt', {}, {'answer': ''})
                network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
