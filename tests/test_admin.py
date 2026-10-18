"""No fixture IDs: initialize an empty workspace and create all data through HTTP."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import HRServer
from test_api import Client


class ManagedDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "empty.db"
        self.server = HRServer(("127.0.0.1", 0), self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.hr = Client(self.base)
        self.initial_status = self.hr.call("GET", "/api/setup/status")[1]
        status, _, _ = self.hr.call("POST", "/api/setup", {"name": "Первый HR", "email": "owner@example.test", "password": "LocalTest123!", "company": "Моя организация"})
        self.assertEqual(status, 201)
        self.sign_in(self.hr, "owner@example.test")

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.temp.cleanup()

    def sign_in(self, client, email):
        status, data, _ = client.call("POST", "/api/auth/login", {"email": email, "password": "LocalTest123!"})
        self.assertEqual(status, 200, data)
        client.csrf = data["csrf_token"]
        return data["user"]

    def employee(self, email="colleague@example.test", role="employee", manager=None):
        body = {"name": "Новый коллега", "email": email, "password": "LocalTest123!", "company": "Моя организация", "position": "Специалист", "department": "Новый отдел", "role": role, "manager_id": manager, "hire_date": "2026-01-20", "vacation_balance": 18}
        status, person, _ = self.hr.call("POST", "/api/admin/users", body)
        self.assertEqual(status, 201, person)
        client = Client(self.base); self.sign_in(client, email)
        return client, person

    def article(self, **overrides):
        body = {"title": "Зарплата", "summary": "Дата выплаты зарплаты", "content": "Зарплата выплачивается 7 числа. Это новый локальный документ организации.", "roles": ["employee", "manager", "hr"], "is_active": True}
        body.update(overrides)
        status, article, _ = self.hr.call("POST", "/api/admin/knowledge", body)
        self.assertEqual(status, 201, article)
        return article, body

    def course(self):
        return {"title": "Авторский курс", "description": "Новые материалы", "duration_minutes": 23, "lessons": [{"title": "Новый урок", "content": "Для работы с системой используйте выданный организацией аккаунт."}], "question": "Какой вариант верный?", "options": ["Первый", "Второй", "Третий"], "correct_index": 2}

    def test_empty_bootstrap_only_once_and_no_demo_data(self):
        self.assertEqual(self.initial_status, {"setup_required": True, "demo_mode": False})
        self.assertFalse(self.hr.call("GET", "/api/setup/status")[1]["setup_required"])
        self.assertEqual(len(self.hr.call("GET", "/api/team")[1]["items"]), 1)
        self.assertEqual(self.hr.call("GET", "/api/admin/courses")[1]["items"], [])
        self.assertEqual(self.hr.call("GET", "/api/knowledge")[1]["items"], [])
        self.assertEqual(self.hr.call("GET", "/api/requests")[1]["items"], [])
        self.assertEqual(Client(self.base).call("POST", "/api/setup", {"name": "attacker"})[0], 409)

    def test_new_accounts_and_dynamic_manager_relationship(self):
        manager, boss = self.employee("boss@example.test", "manager")
        employee, person = self.employee(manager=boss["id"])
        self.assertEqual(person["vacation_balance"], 18)
        self.assertEqual([p["id"] for p in manager.call("GET", "/api/team")[1]["items"]], [person["id"]])
        self.assertEqual(employee.call("POST", "/api/admin/users", {})[0], 403)
        self.assertEqual(employee.call("GET", "/api/admin/knowledge")[0], 403)
        self.assertEqual(employee.call("POST", "/api/admin/knowledge", {})[0], 403)
        self.assertEqual(manager.call("POST", "/api/admin/courses", {})[0], 403)

    def test_user_validation_duplicate_email_and_unknown_manager(self):
        _, person = self.employee()
        body = {"name": "Another", "email": person["email"], "password": "LocalTest123!", "company": "Org"}
        self.assertEqual(self.hr.call("POST", "/api/admin/users", body)[0], 409)
        body.update(email="new@example.test", manager_id=person["id"])
        self.assertEqual(self.hr.call("POST", "/api/admin/users", body)[0], 400)
        body.update(manager_id=None, role=[])
        self.assertEqual(self.hr.call("POST", "/api/admin/users", body)[0], 400)
        body.update(role="employee", password="short")
        self.assertEqual(self.hr.call("POST", "/api/admin/users", body)[0], 400)

    def test_new_document_immediately_changes_answer_without_keyword_list(self):
        employee, _ = self.employee()
        question = {"question": "Когда выплачивается зарплата?"}
        self.assertFalse(employee.call("POST", "/api/assistant/ask", question)[1]["found"])
        article, body = self.article()
        result = employee.call("POST", "/api/assistant/ask", question)[1]
        self.assertTrue(result["found"])
        self.assertEqual(result["answer"], body["content"])
        self.assertEqual(result["sources"][0]["id"], article["id"])
        body["content"] = "Зарплата выплачивается 15 числа. Обновлённый текст документа."
        self.assertEqual(self.hr.call("PATCH", f"/api/admin/knowledge/{article['id']}", body)[0], 200)
        self.assertIn("15", employee.call("POST", "/api/assistant/ask", question)[1]["answer"])
        body["is_active"] = False
        self.hr.call("PATCH", f"/api/admin/knowledge/{article['id']}", body)
        self.assertFalse(employee.call("POST", "/api/assistant/ask", question)[1]["found"])
        self.assertEqual(employee.call("GET", f"/api/knowledge/{article['id']}")[0], 404)
        self.assertFalse(self.hr.call("GET", "/api/admin/knowledge")[1]["items"][0]["is_active"])

    def test_new_document_role_filter_and_no_named_person_rules(self):
        employee, _ = self.employee()
        article, _ = self.article(roles=["hr"])
        self.assertEqual(employee.call("GET", f"/api/knowledge/{article['id']}")[0], 404)
        self.assertFalse(employee.call("POST", "/api/assistant/ask", {"question": "Когда выплачивается зарплата?"})[1]["found"])
        self.assertTrue(self.hr.call("POST", "/api/assistant/ask", {"question": "Когда выплачивается зарплата?"})[1]["found"])
        self.assertFalse(employee.call("POST", "/api/assistant/ask", {"question": "Какой у меня и у Алексея остаток отпуска?"})[1]["found"])
        own = employee.call("POST", "/api/assistant/ask", {"question": "Какой у меня остаток отпуска?"})[1]
        self.assertTrue(own["found"]); self.assertIn("18", own["answer"])

    def test_author_course_custom_correct_answer_assignment_and_immutable_progress(self):
        employee, person = self.employee()
        body = self.course()
        status, course, _ = self.hr.call("POST", "/api/admin/courses", body)
        self.assertEqual(status, 201)
        body["title"] = "Курс после редактирования"
        self.assertEqual(self.hr.call("PATCH", f"/api/admin/courses/{course['id']}", body)[0], 200)
        self.assertEqual(self.hr.call("POST", "/api/admin/assignments", {"user_id": person["id"], "course_id": course["id"]})[0], 201)
        self.assertEqual(self.hr.call("PATCH", f"/api/admin/courses/{course['id']}", body)[0], 409)
        details = employee.call("GET", f"/api/courses/{course['id']}")[1]
        self.assertNotIn("correct_index", details["quiz"])
        for lesson in details["lessons"]:
            self.assertEqual(employee.call("POST", f"/api/courses/{course['id']}/lessons/{lesson['id']}/complete", {})[0], 200)
        self.assertFalse(employee.call("POST", f"/api/courses/{course['id']}/quiz", {"answer_index": 1})[1]["passed"])
        result = employee.call("POST", f"/api/courses/{course['id']}/quiz", {"answer_index": 2})[1]
        self.assertTrue(result["passed"]); self.assertEqual(result["course"]["progress"], 100)

    def test_invalid_course_and_article_are_rejected(self):
        body = self.course(); body["correct_index"] = 10
        self.assertEqual(self.hr.call("POST", "/api/admin/courses", body)[0], 400)
        body = self.course(); body["lessons"] = []
        self.assertEqual(self.hr.call("POST", "/api/admin/courses", body)[0], 400)
        self.assertEqual(self.hr.call("POST", "/api/admin/knowledge", {"title": "x", "content": "Text", "roles": ["owner"]})[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
