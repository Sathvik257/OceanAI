import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgeai.agent import evidence_errors, Agent
from forgeai.corpus import ingest, retrieve
from forgeai.evaluation import validate_case, summarize, score_case, fact_candidates, cross_document_pairs, generate_evals
from forgeai.model import LocalModel, BudgetExceeded, ModelOutputError, validate, constrained_schema
from forgeai.factory import make_definition, propose_patch, intake, build, evaluate
from forgeai.storage import save, digest
from forgeai.tools import calculator, execute


class StubModel:
    """Deterministic test double. Never used for demonstration evidence."""
    def __init__(self, result):
        self.result = result

    def ask(self, *args, **kwargs):
        return copy.deepcopy(self.result)


class CoreTests(unittest.TestCase):
    def test_csv_source_defaults_only_when_unambiguous_and_reports_resolution(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'items.csv').write_text('sku,price\nA1,25\n', encoding='utf-8')
            result = execute('csv_lookup', {'column': 'sku', 'value': 'A1'}, ['csv_lookup'], root)
            self.assertEqual(result['rows'][0]['price'], '25')
            self.assertEqual(result['source_resolution'], 'only_csv_in_corpus')
            Path(root, 'other.csv').write_text('sku,price\nA1,40\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Specify source'):
                execute('csv_lookup', {'column': 'sku', 'value': 'A1'}, ['csv_lookup'], root)

    def test_coverage_checks_an_alternative_before_rejecting_available_data(self):
        policy = {'id': 'p', 'source': 'policy.md', 'text': 'An item subtotal is not a final payable total.'}
        row = {'id': 'r', 'source': 'items.csv', 'text': 'sku: X1; unit_price: 25; currency: INR'}

        class CoverageModel:
            def ask(self, stage, system, data, *args):
                if stage == 'intake-brief':
                    return {'scope': 'Item subtotals', 'audience': 'Staff', 'tone': 'Plain',
                            'must_answer': ['Calculate item subtotals'], 'must_refuse': [], 'questions': [], 'assumptions': []}
                if stage == 'coverage-extract':
                    chunk = data['evidence'][0]
                    return {'chunk_id': chunk['id'], 'quote': chunk['text']}
                if stage == 'groundability':
                    return {'supported': data['source_context']['id'] == 'r', 'reason': 'Check the actual unit price'}
                return {'questions': []}

        with patch('forgeai.factory.retrieve', return_value=[policy, row]):
            requirements = intake(CoverageModel(), 'Calculate item subtotals', {'chunks': [policy, row], 'manifest': []})
        self.assertEqual(requirements['gaps'], [])
        self.assertEqual(requirements['coverage'][0]['chunk_ids'], ['r'])
        self.assertEqual(len(requirements['coverage'][0]['attempts']), 2)

    def test_fact_sampling_deduplicates_overlapping_chunks_and_spreads_sources(self):
        chunks = [{'id': 'a', 'source': 'a.md', 'text': 'Members must wear closed shoes in the workshop. Bookings may be cancelled through the portal.'},
                  {'id': 'b', 'source': 'a.md', 'text': 'Members must wear closed shoes in the workshop.'},
                  {'id': 'c', 'source': 'b.md', 'text': 'Orders need a written purchase reference before dispatch.'}]
        facts = fact_candidates(chunks)
        self.assertEqual(len(facts), 3)
        self.assertEqual({f['source'] for f in facts[:2]}, {'a.md', 'b.md'})
        self.assertEqual(len({f['quote'] for f in facts}), 3)

    def test_generated_suite_cannot_fill_with_repeated_questions(self):
        corpus = ingest('examples/workshop/docs')
        model = StubModel({'question': 'What does the policy require for members?'})
        model.audit = None
        with self.assertRaisesRegex(RuntimeError, 'E02'):
            generate_evals(model, {'scope': 'Workshop', 'brief': 'Explain policies', 'must_refuse': ['Medical advice']}, corpus)

    def test_cross_document_questions_cover_both_seeded_sources(self):
        class QuestionModel:
            audit = None

            def __init__(self):
                self.inputs = []

            def ask(self, stage, system, data, *args):
                self.inputs.append(copy.deepcopy(data))
                if data['kind'] == 'ambiguous':
                    return {'question': f'Can I use it for purpose {len(self.inputs)}?'}
                if data['kind'] == 'out_of_scope':
                    return {'question': f'Perform prohibited task {len(self.inputs)}.'}
                return {'question': f'Question {len(self.inputs)} about this supplied source fact?'}

        model = QuestionModel()
        suite = generate_evals(model, {'scope': 'Workshop', 'brief': 'Explain policies',
                                      'must_refuse': ['Medical advice']}, ingest('examples/workshop/docs'))
        cases = suite['cases']
        self.assertEqual(len(cases), 24)
        self.assertEqual(len(model.inputs), 28)
        for case in cases:
            if case['kind'] == 'multi_document':
                self.assertEqual(len(case['subquestions']), 2)
                self.assertEqual(case['question'], ' '.join(case['subquestions']))
                self.assertEqual(len({f['source'] for f in case['facts']}), 2)
                for question, fact in zip(case['subquestions'], case['facts']):
                    request = model.inputs[int(question.split()[1])-1]
                    self.assertEqual(request['target_facts'], [fact])
        self.assertEqual(sum(c['split'] == 'holdout' for c in cases), 6)

    def test_invalid_model_answer_is_a_failed_case_not_a_skipped_case(self):
        cases = [{'id': f'E{i}', 'question': 'What is the rule?', 'kind': 'answerable', 'split': 'development'} for i in (1, 2)]
        with tempfile.TemporaryDirectory() as root, patch('forgeai.factory.Agent') as agent_class:
            agent_class.return_value.answer.side_effect = ModelOutputError('Truncated JSON')
            scores = evaluate(StubModel({}), {}, {}, root, cases, Path(root, 'scorecard.json'))
        self.assertEqual(len(scores), 2)
        self.assertTrue(all(not s['passed'] and s['category'] == 'prompt_defect' for s in scores))

    def test_pdf_text_ingestion_preserves_page_locator(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest('Install the declared pypdf dependency')
        with tempfile.TemporaryDirectory() as root:
            writer = PdfWriter()
            page = writer.add_blank_page(width=400, height=400)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 40 350 Td (Cancellation requires 24 hours notice.) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
            writer.write(Path(root, 'policy.pdf'))
            corpus = ingest(root)
            self.assertIn('24 hours', corpus['chunks'][0]['text'])
            self.assertEqual(corpus['chunks'][0]['locator'], 'page 1')

    def test_intake_keeps_unsupported_request_and_filters_invalid_support(self):
        class IntakeModel:
            def ask(self, stage, *args):
                if stage == 'intake-brief':
                    return {'scope': 'Workshop', 'audience': 'Members', 'tone': 'plain',
                            'must_answer': ['opening hours', 'guest access'], 'must_refuse': ['medical advice'],
                            'questions': [], 'assumptions': []}
                if stage == 'intake-questions':
                    return {'questions': []}
                if stage == 'coverage-extract':
                    return {'chunk_id': 'fabricated', 'quote': 'guests allowed'}
                return {'supported': True, 'chunk_id': 'fabricated', 'quote': 'guests allowed', 'reason': 'Invented support'}
        corpus = {'chunks': [{'id': 'real', 'source': 'policy.md', 'text': 'Opening hours are 9 to 5.'}]}
        result = intake(IntakeModel(), 'Explain hours and guest access.', corpus)
        self.assertEqual(result['gaps'], ['opening hours', 'guest access'])
        self.assertIn('guest access', result['must_refuse'])
        self.assertEqual(result['must_answer'], [])

    def test_budget_stop_produces_explicit_incomplete_report(self):
        with tempfile.TemporaryDirectory() as root:
            docs = Path(root, 'docs')
            docs.mkdir()
            (docs / 'policy.md').write_text('Opening hours are 9 to 5.')
            out = Path(root, 'run')
            state = build(LocalModel(max_tokens=1), 'Explain opening hours.', docs, out)
            self.assertEqual(state['status'], 'budget_exhausted')
            self.assertFalse((out / 'agent.json').exists())
            self.assertIn('Not completed', (out / 'report.md').read_text())

    def test_calculator_rejects_execution_and_unbounded_operations(self):
        self.assertEqual(calculator('4800 * 3 + 650'), 15050)
        for expr in ["__import__('os').getcwd()", '2**99999', 'True+1', '1e309', '1/0']:
            with self.assertRaises((ValueError, ZeroDivisionError)):
                calculator(expr)

    def test_tools_cannot_escape_registry_or_corpus(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                execute('current_date', {}, [], root)
            with self.assertRaises(ValueError):
                execute('csv_lookup', {'source': '../private.csv', 'column': 'sku', 'value': 'x'}, ['csv_lookup'], root)

    def test_csv_exact_match_and_units(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'items.csv').write_text('sku,price,unit\nA1,320,pack of 4\nA10,500,each\n')
            result = execute('csv_lookup', {'source': 'items.csv', 'column': 'sku', 'value': 'a1'}, ['csv_lookup'], root)
            self.assertEqual(result['total_matches'], 1)
            self.assertEqual(result['rows'][0]['unit'], 'pack of 4')

    def test_ingestion_ids_and_hashes_change_with_content(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, 'policy.md')
            path.write_text('Laser sessions last 90 minutes.')
            first = ingest(root)
            self.assertEqual(first, ingest(root))
            path.write_text('Laser sessions last 120 minutes.')
            self.assertNotEqual(first['manifest'], ingest(root)['manifest'])
            self.assertNotEqual(first['chunks'][0]['id'], ingest(root)['chunks'][0]['id'])

    def test_empty_folder_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                ingest(root)

    def test_retrieval_does_not_return_unrelated_zero_scores(self):
        chunks = [{'id': 'a', 'text': 'Laser induction lasts 45 minutes', 'source': 'policy.md'},
                  {'id': 'b', 'text': 'Shipping costs are unknown', 'source': 'supplier.md'}]
        self.assertEqual(retrieve(chunks, 'laser induction', 2)[0]['id'], 'a')
        self.assertEqual(retrieve(chunks, 'volcano eruption', 2), [])

    def test_citation_existence_does_not_let_fabricated_quotes_pass(self):
        chunks = [{'id': 'a', 'text': 'A refund requires 24 hours notice.'}]
        answer = {'status': 'answered', 'answer': 'You need 12 hours.', 'evidence': [{'chunk_id': 'a', 'quote': '12 hours'}]}
        self.assertTrue(evidence_errors(answer, chunks))
        answer['evidence'][0] = {'chunk_id': 'fake', 'quote': '24 hours'}
        self.assertTrue(evidence_errors(answer, chunks))

    def test_eval_grounding_and_cross_document_validation(self):
        chunks = [{'id': 'a', 'source': 'one', 'text': '45 minute induction'}, {'id': 'b', 'source': 'two', 'text': 'steward present'}]
        case = {'question': 'What induction and supervision are required?', 'kind': 'multi_document', 'expected_status': 'answered',
                'facts': [{'chunk_id': 'a', 'quote': '45 minute induction'}, {'chunk_id': 'b', 'quote': 'steward present'}]}
        validate_case(case, chunks)
        case['facts'][1]['quote'] = 'no steward needed'
        with self.assertRaises(ValueError):
            validate_case(case, chunks)

    def test_budget_fails_before_any_network_request(self):
        model = LocalModel(max_tokens=1)
        with self.assertRaises(BudgetExceeded):
            model.ask('test', 'Return an answer', {}, {'answer': ''})
        self.assertEqual(model.calls, 0)

    def test_schema_rejects_missing_fields_and_bool_as_int(self):
        with self.assertRaises(ValueError):
            validate({'top_k': True}, {'top_k': 3})
        with self.assertRaises(ValueError):
            validate({}, {'answer': ''})

    def test_tool_selection_rejects_unknown_tools_and_missing_csv(self):
        req = {'brief': 'Explain workshop policy'}
        corpus = {'manifest': [], 'chunking': {'words': 180, 'overlap': 30}}
        for tools in [['shell'], ['csv_lookup']]:
            with self.assertRaises(ValueError):
                make_definition(StubModel({'tools': tools}), req, corpus)

    def test_tool_backed_requirements_must_have_the_tool_attached(self):
        req = {'brief': 'Tell me the current UTC date', 'coverage': [{'supported': True, 'tool': 'current_date'}]}
        corpus = {'manifest': [], 'chunking': {'words': 180, 'overlap': 30}}
        with self.assertRaisesRegex(ValueError, 'lack their required tool'):
            make_definition(StubModel({'tools': []}), req, corpus)

    def test_optimizer_changes_only_the_targeted_setting(self):
        definition = {'retrieval': {'top_k': 3, 'diversify': False}, 'system_prompt': 'Original', 'tools': []}
        score = {'case_id': 'E1', 'passed': False, 'category': 'retrieval_miss', 'kind': 'answerable', 'judge': {'reason': 'Missing evidence'}}
        changed, log = propose_patch(StubModel({'patch': 'increase_retrieval', 'reason': 'Missing evidence'}), definition, [score], set())
        self.assertEqual(changed['retrieval']['top_k'], 5)
        self.assertEqual(changed['system_prompt'], 'Original')
        self.assertEqual(definition['retrieval']['top_k'], 3)

    def test_optimizer_rejects_patch_unrelated_to_diagnosed_failures(self):
        definition = {'retrieval': {'top_k': 3, 'diversify': False}, 'system_prompt': 'Original', 'tools': []}
        score = {'case_id': 'E1', 'passed': False, 'category': 'retrieval_miss', 'kind': 'answerable', 'judge': {'reason': 'Missing evidence'}}
        with self.assertRaisesRegex(ValueError, 'disallowed patch'):
            propose_patch(StubModel({'patch': 'source_only', 'reason': 'Be more grounded'}), definition, [score], set())

    def test_schema_prevents_blank_answers_and_unrelated_repairs(self):
        answer_schema = constrained_schema({'answer': ''}, {})
        self.assertEqual(answer_schema['properties']['answer']['minLength'], 1)
        patch_schema = constrained_schema({'patch': ''}, {'allowed_patches': {'source_only': 'Copy sources', 'stop': 'Stop'}})
        self.assertEqual(patch_schema['properties']['patch']['enum'], ['source_only', 'stop'])

    def test_empty_refusals_are_not_diagnosed_as_invented_citations(self):
        model = StubModel({'correct': False, 'grounded': False, 'behavior': False, 'reason': 'No useful answer'})
        case = {'id': 'E1', 'kind': 'answerable', 'split': 'development', 'expected_status': 'answered',
                'question': 'What is the rule?', 'facts': [{'chunk_id': 'a', 'quote': 'The rule is stated.'}]}
        execution = {'response': {'status': 'refused', 'answer': 'Guard refused', 'evidence': []},
                     'raw_response': {'status': 'refused', 'answer': '', 'evidence': []},
                     'guard_errors': ['Empty answer'], 'retrieved_ids': ['a'], 'retrieved': [], 'tool_results': []}
        self.assertEqual(score_case(model, case, execution)['category'], 'wrong_refusal')
        case['expected_status'] = 'clarify'
        case['facts'] = []
        self.assertEqual(score_case(model, case, execution)['category'], 'prompt_defect')

    def test_judge_cannot_override_fabricated_evidence(self):
        model = StubModel({'correct': True, 'grounded': True, 'behavior': True, 'reason': 'Looks good'})
        case = {'id': 'E1', 'kind': 'answerable', 'split': 'development', 'expected_status': 'answered', 'question': 'What is required?', 'facts': []}
        execution = {'response': {'status': 'answered', 'answer': 'Invented', 'evidence': []},
                     'guard_errors': ['Fabricated quote'], 'retrieved_ids': [], 'retrieved': [], 'tool_results': []}
        score = score_case(model, case, execution)
        self.assertFalse(score['passed'])
        self.assertEqual(score['category'], 'hallucination')

    def test_failure_diagnosis_distinguishes_retrieval_refusal_and_invention(self):
        model = StubModel({'correct': False, 'grounded': False, 'behavior': False, 'reason': 'Wrong answer'})
        case = {'id': 'E1', 'kind': 'answerable', 'split': 'development', 'expected_status': 'answered',
                'question': 'What is the booking limit?', 'facts': [{'chunk_id': 'a', 'quote': 'The limit is two bookings.'}]}
        execution = {'response': {'status': 'refused', 'answer': 'Not in the documents.', 'evidence': []},
                     'guard_errors': [], 'retrieved_ids': [], 'retrieved': [], 'tool_results': []}
        self.assertEqual(score_case(model, case, execution)['category'], 'retrieval_miss')
        execution['retrieved_ids'] = ['a']
        self.assertEqual(score_case(model, case, execution)['category'], 'wrong_refusal')
        execution['response']['status'] = 'answered'
        self.assertEqual(score_case(model, case, execution)['category'], 'hallucination')

    def test_packaged_agent_rejects_tampered_sources(self):
        with tempfile.TemporaryDirectory() as root:
            documents = Path(root, 'documents')
            documents.mkdir()
            source = documents / 'policy.md'
            source.write_text('Original policy')
            corpus = ingest(documents)
            save(Path(root, 'corpus.json'), corpus)
            definition = {'schema_version': 1, 'tools': [], 'corpus_file': 'corpus.json', 'documents_dir': 'documents', 'corpus_sha256': digest(corpus)}
            save(Path(root, 'agent.json'), definition)
            source.write_text('Tampered policy')
            with self.assertRaises(ValueError):
                Agent.load(Path(root, 'agent.json'), StubModel({}))


if __name__ == '__main__':
    unittest.main()
