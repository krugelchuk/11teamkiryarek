"""Branch access, peak daily coverage, persistence and Gemini key-only setup."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta

import test_api
from test_api import Client
from app.database import connect, initialize, today, now
from app import model
from scripts.start_gemini import configure

BID = '70000001088185194'
OTHER = '70000001088245648'


class BranchTests(unittest.TestCase):
    setUpClass = classmethod(test_api.IntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(test_api.IntegrationTests.tearDownClass.__func__)
    tearDown = test_api.IntegrationTests.tearDown

    def setUp(self):
        test_api.IntegrationTests.setUp(self)
        for uid in (1, 2, 4):
            status, _, _ = self.hr.call('PATCH', f'/api/admin/users/{uid}/branch', {'branch_id': BID})
            self.assertEqual(status, 200)

    def test_public_locations_require_login_but_no_other_personnel_leak(self):
        self.assertEqual(Client(self.base).call('GET', '/api/branches')[0], 401)
        for client, expected in ((self.employee, {1}), (self.manager, {1, 2}), (self.hr, {1, 2, 4})):
            status, data, _ = client.call('GET', f'/api/branches/{BID}')
            self.assertEqual(status, 200)
            self.assertEqual({p['id'] for p in data['members']}, expected)
            self.assertTrue(all(r['user_id'] in expected for r in data['leaves']))
            items = client.call('GET', '/api/branches')[1]['items']
            self.assertEqual(len(items), 13)
            self.assertEqual(next(b['member_count'] for b in items if b['id'] == BID), len(expected))
            self.assertTrue(all('2gis.kz/astana/firm/' in b['source_url'] for b in items))
        self.assertEqual(self.employee.call('GET', '/api/profile')[1]['branch_id'], BID)

    def test_direct_employee_access_cannot_bypass_branch_or_team(self):
        for client, target, expected in ((self.employee, 1, 200), (self.employee, 4, 404),
                                         (self.manager, 1, 200), (self.manager, 4, 404), (self.hr, 4, 200)):
            self.assertEqual(client.call('GET', f'/api/branches/{BID}/employees/{target}')[0], expected)
        self.assertEqual(self.hr.call('GET', f'/api/branches/{OTHER}/employees/1')[0], 404)
        data = self.hr.call('GET', f'/api/branches/{BID}/employees/1')[1]
        self.assertNotIn('password_hash', json.dumps(data))
        self.assertEqual(data['profile']['vacation_balance'], 24)
        self.assertTrue(data['courses'])

    def test_only_hr_assigns_and_configures_and_csrf_still_required(self):
        for client in (self.employee, self.manager):
            self.assertEqual(client.call('PATCH', '/api/admin/users/1/branch', {'branch_id': OTHER})[0], 403)
            self.assertEqual(client.call('PATCH', f'/api/admin/branches/{BID}', {'min_staff': 1})[0], 403)
        self.assertEqual(self.hr.call('PATCH', '/api/admin/users/1/branch', {'branch_id': OTHER}, csrf=False)[0], 403)
        self.assertEqual(self.hr.call('PATCH', '/api/admin/users/1/branch', {'branch_id': 'fake'})[0], 400)
        self.assertEqual(self.hr.call('PATCH', '/api/admin/users/999999/branch', {'branch_id': OTHER})[0], 404)
        self.assertEqual(self.hr.call('PATCH', '/api/admin/users/1/branch', {'branch_id': None})[0], 200)
        self.assertIsNone(self.employee.call('GET', '/api/profile')[1]['branch_id'])

    def test_threshold_is_private_to_full_branch_scope_and_survives_initialize(self):
        self.assertEqual(self.hr.call('PATCH', f'/api/admin/branches/{BID}', {'min_staff': 2})[0], 200)
        initialize(self.db)
        for client, expected in ((self.hr, 2), (self.manager, None), (self.employee, None)):
            self.assertEqual(client.call('GET', f'/api/branches/{BID}')[1]['branch']['min_staff'], expected)
        self.assertEqual(self.employee.call('GET', '/api/profile')[1]['branch_id'], BID)
        for value in (True, -1, 1.5, '2', 10001):
            self.assertEqual(self.hr.call('PATCH', f'/api/admin/branches/{BID}', {'min_staff': value})[0], 400)
        self.assertEqual(self.hr.call('PATCH', f'/api/admin/branches/{BID}', {'min_staff': None})[0], 200)

    def test_coverage_counts_people_per_day_and_pending_never_removes_staff(self):
        start = today() + timedelta(days=100)
        with connect(self.db) as conn:
            # Disjoint absences must not be incorrectly added as simultaneous.
            for uid, offset, state in [(1, 0, 'approved'), (2, 1, 'approved'), (4, 0, 'pending'), (1, 0, 'approved')]:
                day = str(start + timedelta(days=offset))
                conn.execute('''INSERT INTO requests(user_id,start_date,end_date,days,comment,status,created_at,updated_at)
                    VALUES(?,?,?,1,'test',?,?,?)''', (uid, day, day, state, now(), now()))
        self.hr.call('PATCH', f'/api/admin/branches/{BID}', {'min_staff': 3})
        query = f'?from={start}&to={start + timedelta(days=1)}'
        result = self.hr.call('GET', f'/api/branches/{BID}' + query)[1]
        self.assertEqual([d['remaining'] for d in result['calendar']], [2, 2])
        self.assertEqual([d['approved'] for d in result['calendar']], [1, 1])
        self.assertEqual([d['pending'] for d in result['calendar']], [1, 0])
        self.assertTrue(all(d['shortage'] for d in result['calendar']))
        item = next(b for b in self.hr.call('GET', '/api/branches' + query)[1]['items'] if b['id'] == BID)
        self.assertEqual((item['min_remaining'], item['max_approved'], item['shortage_days']), (2, 1, 2))
        manager = self.manager.call('GET', f'/api/branches/{BID}' + query)[1]
        self.assertEqual([d['pending'] for d in manager['calendar']], [0, 0])
        self.assertFalse(any(d['shortage'] for d in manager['calendar']))

    def test_date_validation_and_nonexistent_branch(self):
        for query in ('?from=wrong', '?from=2026-02-30', '?from=2026-10-10&to=2026-10-09', '?from=2026-01-01&to=2026-12-31'):
            self.assertEqual(self.hr.call('GET', '/api/branches' + query)[0], 400)
        self.assertEqual(self.hr.call('GET', '/api/branches/999999')[0], 404)
        self.assertEqual(self.hr.call('GET', '/api/branches?from=9999-12-31')[0], 200)

    def test_demo_placement_is_once_only_and_preserves_hr_edits(self):
        from scripts.prepare_demo import prepare
        prepare(self.db)
        self.hr.call('PATCH', '/api/admin/users/1/branch', {'branch_id': OTHER})
        prepare(self.db)
        self.assertEqual(self.employee.call('GET', '/api/profile')[1]['branch_id'], OTHER)


class GeminiSetupTests(unittest.TestCase):
    def setUp(self):
        model._model_cache.clear()

    def test_auto_model_prefers_current_stable_text_flash_and_caches_without_key_in_url(self):
        response = {'models': [
            {'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/gemini-3.8-flash-lite', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/gemini-2.5-flash', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/gemini-9.0-flash-preview', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/gemini-9.0-flash', 'supportedGenerationMethods': ['embedContent']},
        ]}
        with patch('app.model.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as transport:
            self.assertEqual(model.gemini_model('private-test-key'), 'gemini-3.8-flash')
            self.assertEqual(model.gemini_model('private-test-key'), 'gemini-3.8-flash')
        self.assertEqual(transport.call_count, 1)
        self.assertNotIn('private-test-key', transport.call_args.args[0].full_url)
        self.assertEqual(transport.call_args.args[0].get_header('X-goog-api-key'), 'private-test-key')

    def test_discovery_failure_has_short_cache_and_safe_fallback(self):
        with patch('app.model.urllib.request.urlopen', side_effect=TimeoutError('secret-provider-body')) as transport:
            for _ in range(2):
                with self.assertRaises(model.ProviderUnavailable) as error:
                    model.gemini_model('secret')
                self.assertNotIn('secret', str(error.exception))
        self.assertEqual(transport.call_count, 1)

    def test_gemini_only_needs_key_but_still_requires_explicit_activation(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret'}, clear=True):
            self.assertFalse(model.configuration()['enabled'])
            os.environ['JANAMEN_AI_PROVIDER'] = 'gemini'
            self.assertTrue(model.configuration()['enabled'])
            self.assertEqual(model.configuration()['model'], 'auto')

    def test_launcher_saves_once_and_reuses_key_without_executing_config(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / 'data/gemini.json'
            with patch('scripts.start_gemini.getpass.getpass', return_value='fake-private-key') as prompt:
                configure(path)
            prompt.assert_called_once()
            self.assertEqual(model.configuration()['provider'], 'gemini')
            self.assertEqual(model.configuration()['model'], 'auto')
            os.environ.clear()
            with patch('scripts.start_gemini.getpass.getpass', side_effect=AssertionError('Should reuse saved key')):
                configure(path)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'fake-private-key')
