"""Mock adapters are explicit, HR-only, side-effect-free, and never networked."""
import unittest
from unittest.mock import patch

import test_api
from test_api import Client
from app.database import connect


class IntegrationStubTests(unittest.TestCase):
    setUpClass = classmethod(test_api.IntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(test_api.IntegrationTests.tearDownClass.__func__)
    setUp = test_api.IntegrationTests.setUp
    tearDown = test_api.IntegrationTests.tearDown

    def test_catalog_and_previews_require_hr_on_the_server(self):
        path = '/api/admin/integrations'
        self.assertEqual(Client(self.base).call('GET', path)[0], 401)
        for client in (self.employee, self.manager):
            self.assertEqual(client.call('GET', path)[0], 403)
            self.assertEqual(client.call('POST', path + '/1c-zup/preview', {})[0], 403)
        status, catalog, _ = self.hr.call('GET', path)
        self.assertEqual(status, 200)
        self.assertEqual({p['id'] for p in catalog['items']}, {'1c-zup', 'documentolog'})
        self.assertFalse(catalog['external_calls'])
        self.assertTrue(all(p['mode'] == 'mock' and p['status'] == 'not_connected' for p in catalog['items']))

    def test_preview_never_sends_network_data_or_changes_application_records(self):
        def snapshot():
            with connect(self.db) as conn:
                return {t: [tuple(row) for row in conn.execute('SELECT * FROM ' + t + ' ORDER BY 1')]
                        for t in ['users', 'requests', 'request_history', 'audit_log', 'notifications']}
        before = snapshot()
        # urllib is used by real providers; neither mock adapter may invoke it.
        # The HTTP client uses its own opener, so this patch covers server outbound traffic.
        with patch('urllib.request.urlopen', side_effect=AssertionError('No external calls in a mock preview')):
            for provider in ('1c-zup', 'documentolog'):
                status, result, _ = self.hr.call('POST', f'/api/admin/integrations/{provider}/preview', {})
                self.assertEqual(status, 200)
                self.assertEqual(result['mode'], 'mock')
                self.assertFalse(result['external_calls'])
                self.assertFalse(result['persisted'])
                self.assertTrue(result['steps'])
                self.assertIn('DEMO-EMP-001', str(result['request']))
                if provider == 'documentolog':
                    self.assertEqual(result['response']['status'], 'mock_preview')
                    self.assertFalse(result['response']['signed'])
        self.assertEqual(snapshot(), before)

    def test_preview_rejects_missing_csrf_unknown_provider_and_real_payloads(self):
        path = '/api/admin/integrations/1c-zup/preview'
        self.assertEqual(self.hr.call('POST', path, {}, csrf=False)[0], 403)
        self.assertEqual(self.hr.call('POST', path, {'api_key': 'not-accepted'})[0], 400)
        self.assertEqual(self.hr.call('POST', '/api/admin/integrations/unknown/preview', {})[0], 404)
