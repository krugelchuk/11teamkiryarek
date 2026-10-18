"""Complete backend acceptance on a blank database, with arbitrary created users."""
from datetime import timedelta
import secrets
import unittest

import test_admin
from app.database import today
from test_api import Client


class BackendAcceptance(unittest.TestCase):
    # Reuse the empty-workspace lifecycle, not demo fixtures or IDs.
    setUp = test_admin.ManagedDataTests.setUp
    tearDown = test_admin.ManagedDataTests.tearDown
    sign_in = test_admin.ManagedDataTests.sign_in
    employee = test_admin.ManagedDataTests.employee
    course = test_admin.ManagedDataTests.course
    article = test_admin.ManagedDataTests.article

    def request(self, client, offset, days=3):
        start = today() + timedelta(days=offset)
        status, record, _ = client.call('POST', '/api/requests', {
            'type': 'vacation', 'start_date': str(start), 'end_date': str(start + timedelta(days=days-1)), 'comment': 'Проверка на новых данных'})
        self.assertEqual(status, 201, record)
        return record

    def restart(self):
        import threading
        from server import HRServer
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.server = HRServer(('127.0.0.1', 0), self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def test_full_workflow_and_persistence_without_demo_records(self):
        manager, boss = self.employee('lead@example.test', 'manager')
        employee, worker = self.employee('worker@example.test', manager=boss['id'])
        _, other_boss = self.employee('other-lead@example.test', 'manager')
        other, _ = self.employee('other-worker@example.test', manager=other_boss['id'])
        hidden = self.request(other, 10)
        self.assertEqual(manager.call('GET', f"/api/requests/{hidden['id']}")[0], 404)
        self.assertEqual(manager.call('POST', f"/api/requests/{hidden['id']}/decision", {'decision': 'approved'})[0], 404)
        self.assertEqual(employee.call('GET', f"/api/requests/{hidden['id']}")[0], 404)

        approved = self.request(employee, 10)
        manager_list = manager.call('GET', '/api/requests?scope=team')[1]['items']
        self.assertEqual([r['id'] for r in manager_list], [approved['id']])
        self.assertEqual(employee.call('POST', f"/api/requests/{approved['id']}/decision", {'decision': 'approved'})[0], 403)
        self.assertEqual(manager.call('POST', f"/api/requests/{approved['id']}/decision", {'decision': 'approved', 'comment': 'Согласовано'})[0], 200)
        self.assertEqual(manager.call('POST', f"/api/requests/{approved['id']}/decision", {'decision': 'approved'})[0], 409)
        self.assertEqual(employee.call('GET', '/api/profile')[1]['vacation_balance'], 15)
        history = employee.call('GET', f"/api/requests/{approved['id']}")[1]['history']
        self.assertEqual([h['status'] for h in history], ['pending','approved'])
        self.assertEqual(history[-1]['actor_id'], boss['id'])

        rejected = self.request(employee, 20, 2)
        self.assertEqual(manager.call('POST', f"/api/requests/{rejected['id']}/decision", {'decision': 'rejected'})[0], 400)
        manager.call('POST', f"/api/requests/{rejected['id']}/decision", {'decision': 'rejected', 'comment': 'Укажите другие даты'})
        cancelled = self.request(employee, 30, 2)
        employee.call('POST', f"/api/requests/{cancelled['id']}/cancel", {})
        self.assertEqual(employee.call('GET', '/api/profile')[1]['vacation_balance'], 15)
        self.assertEqual(employee.call('PATCH', '/api/profile', {'vacation_balance': 99})[0], 404)

        own_manager_request = self.request(manager, 40)
        self.assertEqual(manager.call('POST', f"/api/requests/{own_manager_request['id']}/decision", {'decision': 'approved'})[0], 403)

        course = self.hr.call('POST', '/api/admin/courses', self.course())[1]
        self.assertEqual(self.hr.call('POST', '/api/admin/assignments', {'user_id': worker['id'], 'course_id': course['id']})[0], 201)
        self.assertEqual(employee.call('POST', f"/api/courses/{course['id']}/quiz", {'answer_index': 2})[0], 409)
        lessons = employee.call('GET', f"/api/courses/{course['id']}")[1]['lessons']
        for lesson in lessons:
            employee.call('POST', f"/api/courses/{course['id']}/lessons/{lesson['id']}/complete", {})
        self.assertFalse(employee.call('POST', f"/api/courses/{course['id']}/quiz", {'answer_index': 0})[1]['passed'])
        self.assertTrue(employee.call('POST', f"/api/courses/{course['id']}/quiz", {'answer_index': 2})[1]['passed'])

        doc, body = self.article()
        answer = employee.call('POST', '/api/assistant/ask', {'question': 'Когда выплачивается зарплата?'})[1]
        self.assertEqual(answer['sources'][0]['id'], doc['id'])
        self.assertEqual(answer['answer'], body['content'])
        self.assertFalse(employee.call('POST', '/api/assistant/ask', {'question': 'Как купить вертолёт?'})[1]['found'])

        notes = employee.call('GET', '/api/notifications')[1]['items']
        self.assertTrue(any(n['entity_id'] == approved['id'] and n['type'] == 'request_status' for n in notes))
        self.assertTrue(any(n['entity_id'] == course['id'] and n['type'] == 'course_completed' for n in notes))
        note_count = len(notes)
        self.restart()
        employee.base = manager.base = self.hr.base = self.base
        # Persisted sessions are valid after restarting the application process.
        self.assertEqual(employee.call('GET', '/api/auth/me')[1]['user']['id'], worker['id'])
        self.assertEqual(employee.call('GET', '/api/profile')[1]['vacation_balance'], 15)
        self.assertEqual(employee.call('GET', f"/api/requests/{approved['id']}")[1]['status'], 'approved')
        self.assertEqual(employee.call('GET', f"/api/requests/{rejected['id']}")[1]['status'], 'rejected')
        self.assertEqual(employee.call('GET', f"/api/requests/{cancelled['id']}")[1]['status'], 'cancelled')
        self.assertEqual(employee.call('GET', f"/api/courses/{course['id']}")[1]['course']['progress'], 100)
        self.assertEqual(len(employee.call('GET', '/api/notifications')[1]['items']), note_count)
        self.assertFalse(self.hr.call('GET', '/api/setup/status')[1]['demo_mode'])
        employee.call('POST', '/api/auth/logout', {})
        self.assertEqual(employee.call('GET', '/api/auth/me')[0], 401)

    def test_parallel_creation_cannot_duplicate_overlapping_requests(self):
        from concurrent.futures import ThreadPoolExecutor
        employee, person = self.employee('parallel@example.test')
        start = today() + timedelta(days=60)
        body = {'type':'vacation','start_date':str(start),'end_date':str(start+timedelta(days=2))}
        def create(_):
            client = Client(self.base)
            self.sign_in(client, person['email'])
            return client.call('POST', '/api/requests', body)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(create, range(2)))
        self.assertEqual(sorted(statuses), [201,409])
        self.assertEqual(len(employee.call('GET','/api/requests')[1]['items']), 1)
