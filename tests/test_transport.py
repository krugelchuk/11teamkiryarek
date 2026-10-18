"""Transport regressions beyond ordinary form validation."""
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from server import Handler, HRServer
import test_api


class TransportTests(unittest.TestCase):
    setUpClass = classmethod(test_api.IntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(test_api.IntegrationTests.tearDownClass.__func__)
    setUp = test_api.IntegrationTests.setUp
    tearDown = test_api.IntegrationTests.tearDown

    def test_idle_socket_logging_before_request_does_not_crash(self):
        handler = object.__new__(Handler)
        with patch('server.LOG.info') as output:
            handler.log_message('Request timed out')
        output.assert_called_once_with('%s %s', '?', '/')

    def test_second_server_cannot_share_the_existing_port(self):
        with self.assertRaises(OSError):
            HRServer(('127.0.0.1', self.server.server_port), self.db.with_name('second.db'))

    def test_unicode_csrf_is_rejected_without_500(self):
        status, data, _ = self.employee.call('POST', '/api/notifications/read-all', {}, headers={'X-CSRF-Token': '\u00e9'})
        self.assertEqual((status, data['error']['code']), (403, 'csrf_failed'))

    def test_non_finite_numbers_are_not_json(self):
        for constant in ('NaN', 'Infinity', '-Infinity'):
            req = urllib.request.Request(self.base + '/api/assistant/ask', data=('{"question":' + constant + '}').encode(), method='POST',
                                         headers={'Content-Type': 'application/json', 'X-CSRF-Token': self.employee.csrf})
            try:
                response = self.employee.opener.open(req, timeout=5)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                result = json.loads(response.read())
                self.assertEqual(response.status, 400)
                self.assertEqual(result['error']['code'], 'invalid_json')

    def test_health_checks_database_without_creating_missing_file(self):
        original = self.server.db_path
        missing = self.db.with_name('not-present.db')
        self.server.db_path = str(missing)
        try:
            status, result, _ = self.employee.call('GET', '/api/health')
            self.assertEqual(status, 503)
            self.assertEqual(result['database'], 'unavailable')
            self.assertFalse(missing.exists())
        finally:
            self.server.db_path = original
