"""Optional demo importer. Application logic does not depend on these records/IDs."""
import json
import os
from datetime import timedelta
from pathlib import Path

from .database import now, today, password_hash, notify


def load_demo(conn):
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures/demo.json").read_text(encoding="utf-8"))
    password = os.getenv("DEMO_PASSWORD", "Demo2026!")
    conn.execute("PRAGMA defer_foreign_keys=ON")
    for item in fixture["users"]:
        conn.execute("INSERT INTO users(id,name,email,password_hash,role,company,position,department,manager_id,hire_date,vacation_balance) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (item["id"], item["name"], item["email"], password_hash(password), item["role"], item["company"], item["position"], item["department"], item["manager_id"], item["hire_date"], item["vacation_balance"]))
    for item in fixture["courses"]:
        conn.execute("INSERT INTO courses VALUES(?,?,?,?,?,?,?)", (item["id"], item["title"], item["description"], item["duration_minutes"], item["question"], json.dumps(item["options"], ensure_ascii=False), item["correct_index"]))
    for item in fixture["lessons"]:
        conn.execute("INSERT INTO lessons VALUES(?,?,?,?,?)", (item["id"], item["course_id"], item["title"], item["content"], item["position"]))
    for item in fixture["knowledge"]:
        conn.execute("INSERT INTO knowledge(id,title,summary,content,keywords,roles,is_active,updated_at) VALUES(?,?,?,?,?,?,1,?)", (item["id"], item["title"], item["summary"], item["content"], "", ",".join(item["roles"]), now()))
    for item in fixture["enrollments"]:
        conn.execute("INSERT INTO enrollments(user_id,course_id,assigned_at) VALUES(?,?,?)", (item["user_id"], item["course_id"], now()))
        title = conn.execute("SELECT title FROM courses WHERE id=?", (item["course_id"],)).fetchone()[0]
        notify(conn, item["user_id"], "course_assigned", "Вам назначен курс", title, "course", item["course_id"])
    for item in fixture["lesson_progress"]:
        conn.execute("INSERT INTO lesson_progress VALUES(?,?,?,?)", (item["user_id"], item["course_id"], item["lesson_id"], now()))
    for item in fixture["requests"]:
        start = today() + timedelta(days=item["offset_days"])
        end = start + timedelta(days=item["days"] - 1)
        rid = conn.execute("INSERT INTO requests(user_id,start_date,end_date,days,comment,status,created_at,updated_at,reviewer_id,decision_comment) VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (item["user_id"], str(start), str(end), item["days"], item["comment"], item["status"], now(), now(), item.get("reviewer_id"), item.get("decision_comment"))).lastrowid
        conn.execute("INSERT INTO request_history(request_id,status,actor_id,comment,created_at) VALUES(?,'pending',?,?,?)", (rid, item["user_id"], item["comment"], now()))
        if item.get("reviewer_id"):
            conn.execute("INSERT INTO request_history(request_id,status,actor_id,comment,created_at) VALUES(?,?,?,?,?)", (rid, item["status"], item["reviewer_id"], item["decision_comment"], now()))
        else:
            manager = conn.execute("SELECT manager_id FROM users WHERE id=?", (item["user_id"],)).fetchone()[0]
            if manager:
                notify(conn, manager, "request_created", "Заявка ожидает решения", f"Учебная заявка №{rid}", "request", rid)
        notify(conn, item["user_id"], "request_status", "Статус вашей заявки", f"Учебная заявка №{rid}: {item['status']}", "request", rid)
    conn.execute("INSERT OR REPLACE INTO settings VALUES('demo_mode','1')")
