"""Regression checks for imported AI adapters and concurrent startup requests."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.assistant import answer, status
from app.learning import pack
from app.model import ProviderUnavailable, select_quotes
from test_api import Client
import test_api


class AssistantRegressionTests(unittest.TestCase):
    def setUp(self):
        self.article = {'id': 81, 'title': 'Оформление отпуска', 'summary': 'Как оформить отпуск',
                        'content': 'Оформить отпуск можно в разделе «Мои заявки». Выберите даты.'}
        self.own = {'id': 7, 'vacation_balance': 18}
        self.selected = {'found': True, 'excerpts': [{'source_id': 81, 'quote': 'Оформить отпуск можно в разделе «Мои заявки».'}]}

    def test_greetings_and_help_do_not_refuse_or_claim_a_model_call(self):
        with patch('app.model.urllib.request.urlopen') as transport:
            for question in ('Привет!', 'првиет', 'Здравствуйте.', 'Сәлем!', 'Что ты умеешь?', 'Спасибо'):
                result = answer(question, [], self.own)
                self.assertEqual(result['mode'], 'conversation')
                self.assertFalse(result['found'])
                self.assertEqual(result['sources'], [])
                self.assertNotIn('нет надёжного ответа', result['answer'])
            transport.assert_not_called()

    def test_greeting_cannot_hide_foreign_profile_or_override_hr_retrieval(self):
        with patch.dict(os.environ, {'JANAMEN_AI_PROVIDER': 'disabled'}):
            self.assertFalse(answer('Привет, сколько дней отпуска у директора Иванова?', [self.article], self.own)['found'])
            result = answer('Привет, как оформить отпуск?', [self.article], self.own)
            self.assertTrue(result['found'])
            self.assertEqual(result['mode'], 'extractive')

    def test_demo_launcher_is_repeatable_and_does_not_duplicate_assignments(self):
        from scripts.prepare_demo import prepare
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'demo.db'
            initial = prepare(db)
            repeated = prepare(db)
        self.assertEqual((initial['created_documents'], initial['created_courses'], initial['assigned_courses']), (12, 2, 2))
        self.assertEqual((repeated['created_documents'], repeated['created_courses'], repeated['assigned_courses']), (0, 0, 0))

    def test_key_alone_does_not_enable_network_and_models_are_explicit(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test', 'OPENAI_MODEL': 'test'}, clear=True):
            self.assertFalse(status()['model_enabled'])
        with patch.dict(os.environ, {'JANAMEN_AI_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test'}, clear=True):
            self.assertFalse(status()['model_enabled'])
            with self.assertRaises(ProviderUnavailable):
                select_quotes('Как оформить отпуск?', [self.article])

    def test_passive_status_is_not_an_instruction_to_perform_action(self):
        visible = [{**item['data'], 'id': i + 1} for i, item in enumerate(pack()['documents']) if 'employee' in item['data']['roles']]
        with patch.dict(os.environ, {'JANAMEN_AI_PROVIDER': 'disabled'}):
            self.assertFalse(answer('Как отклонить заявку?', visible, self.own)['found'])
            self.assertTrue(answer('Где посмотреть историю заявки?', visible, self.own)['found'])

    def test_gemini_and_chat_transport_validate_quotes_and_keep_key_out_of_url(self):
        encoded = json.dumps(self.selected, ensure_ascii=False)
        variants = [
            ({'JANAMEN_AI_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'test-secret', 'GEMINI_MODEL': 'test'},
             {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': encoded}]}}]}),
            ({'JANAMEN_AI_PROVIDER': 'chat', 'OPENAI_API_KEY': 'test-secret', 'OPENAI_MODEL': 'test', 'OPENAI_BASE_URL': 'https://example.test/v1'},
             {'choices': [{'finish_reason': 'stop', 'message': {'content': encoded}}]}),
        ]
        for env, response in variants:
            with self.subTest(provider=env['JANAMEN_AI_PROVIDER']), patch.dict(os.environ, env, clear=True), patch(
                'app.model.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as transport:
                result = answer('Как оформить отпуск?', [self.article], self.own)
            self.assertEqual(result['mode'], 'grounded_llm')
            self.assertEqual(result['answer'], self.selected['excerpts'][0]['quote'])
            request = transport.call_args.args[0]
            self.assertNotIn('test-secret', request.full_url)
            self.assertNotIn('vacation_balance', request.data.decode())

    def test_malformed_or_incomplete_provider_response_has_safe_fallback(self):
        env = {'JANAMEN_AI_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test', 'OPENAI_MODEL': 'test'}
        malformed = [[], {'status': 'completed', 'output': [None]}, {'status': 'incomplete'}, {'status': 'completed', 'output': []}]
        for response in malformed:
            with self.subTest(response=response), patch.dict(os.environ, env, clear=True), patch(
                'app.model.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
                result = answer('Как оформить отпуск?', [self.article], self.own)
            self.assertEqual(result['mode'], 'extractive')
            self.assertIn('notice', result)
        with patch.dict(os.environ, {**env, 'JANAMEN_AI_TIMEOUT': 'invalid'}, clear=True):
            self.assertEqual(answer('Как оформить отпуск?', [self.article], self.own)['mode'], 'extractive')


class ConcurrentBootTests(unittest.TestCase):
    setUp = test_api.IntegrationTests.setUp
    tearDown = test_api.IntegrationTests.tearDown

    @classmethod
    def setUpClass(cls):
        # Reuse fixture preparation without inheriting/rerunning the existing tests.
        test_api.IntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_api.IntegrationTests.tearDownClass.__func__(cls)

    def test_simultaneous_setup_session_notifications_reads_do_not_lock_database(self):
        def boot(_):
            client = Client(self.base)
            client.login()
            return [client.call('GET', route)[0] for route in ('/api/setup/status', '/api/auth/me', '/api/dashboard', '/api/notifications')]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(boot, range(6)))
        self.assertTrue(all(codes == [200] * 4 for codes in results), results)
