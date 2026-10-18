"""Application rules. All data authorization is enforced here, on the server."""
import json
import re
from datetime import date

from .database import audit, notify, now, today


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def fail(status, code, message):
    raise APIError(status, code, message)


def text(value, name, maximum=2000, required=False):
    if not isinstance(value, str):
        fail(400, "validation_error", f"{name}: ожидается строка")
    value = value.strip()
    if len(value) > maximum or (required and not value):
        fail(400, "validation_error", f"{name}: заполните поле, максимум {maximum} символов")
    return value


def integer(value, name):
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        fail(400, "validation_error", f"{name}: ожидается положительное целое число")
    return value


def fields(data, allowed):
    unexpected = set(data) - set(allowed)
    if unexpected:
        fail(400, "validation_error", "Неизвестные поля: " + ", ".join(sorted(unexpected)))


def profile(conn, uid):
    row = conn.execute(
        "SELECT u.id,u.name,u.email,u.role,u.company,u.position,u.department,u.manager_id,"
        "m.name AS manager_name,u.hire_date,u.vacation_balance,eb.branch_id,b.address AS branch_address "
        "FROM users u LEFT JOIN users m ON m.id=u.manager_id "
        "LEFT JOIN employee_branches eb ON eb.user_id=u.id LEFT JOIN branches b ON b.id=eb.branch_id WHERE u.id=?", (uid,)
    ).fetchone()
    if not row:
        fail(404, "not_found", "Сотрудник не найден")
    return dict(row)


def require_role(user, *roles):
    if user["role"] not in roles:
        fail(403, "forbidden", "Недостаточно прав для этого действия")


REQUEST_SELECT = """SELECT r.*, u.name AS employee_name,u.department,m.name AS reviewer_name
 FROM requests r JOIN users u ON u.id=r.user_id LEFT JOIN users m ON m.id=r.reviewer_id """


def can_review(conn, user, owner_id):
    if user["id"] == owner_id:
        return False
    if user["role"] == "hr":
        return True
    owner = conn.execute("SELECT manager_id FROM users WHERE id=?", (owner_id,)).fetchone()
    return bool(owner and user["role"] == "manager" and owner["manager_id"] == user["id"])


def request_record(conn, user, rid, include_history=True):
    row = conn.execute(REQUEST_SELECT + "WHERE r.id=?", (rid,)).fetchone()
    if not row or (row["user_id"] != user["id"] and not can_review(conn, user, row["user_id"])):
        # Do not reveal whether an inaccessible resource exists.
        fail(404, "not_found", "Заявка не найдена")
    result = dict(row)
    if include_history:
        result["history"] = [dict(r) for r in conn.execute(
            "SELECT h.id,h.status,h.actor_id,u.name AS actor_name,h.comment,h.created_at "
            "FROM request_history h JOIN users u ON u.id=h.actor_id WHERE h.request_id=? ORDER BY h.id", (rid,))]
    return result


def list_requests(conn, user, scope="mine"):
    if scope == "mine":
        where, params = "r.user_id=?", (user["id"],)
    elif scope == "team":
        require_role(user, "manager", "hr")
        where, params = "u.manager_id=?", (user["id"],)
    elif scope == "all":
        require_role(user, "hr")
        where, params = "1=1", ()
    else:
        fail(400, "validation_error", "scope: допустимы mine, team, all")
    return {"items": [dict(r) for r in conn.execute(REQUEST_SELECT + "WHERE " + where + " ORDER BY r.id DESC", params)]}


def team(conn, user):
    require_role(user, "manager", "hr")
    rows = conn.execute("SELECT id FROM users WHERE manager_id=? ORDER BY id", (user["id"],)) if user["role"] == "manager" else conn.execute("SELECT id FROM users ORDER BY id")
    return {"items": [profile(conn, row["id"]) for row in rows.fetchall()]}


def parse_date(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(400, "validation_error", f"{name}: используйте YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(400, "validation_error", f"{name}: несуществующая дата")


def create_request(conn, user, data):
    fields(data, {"type", "start_date", "end_date", "comment"})
    if data.get("type") != "vacation":
        fail(400, "validation_error", "В MVP поддерживается только type=vacation")
    start, end = parse_date(data.get("start_date"), "start_date"), parse_date(data.get("end_date"), "end_date")
    if start < today() or end < start:
        fail(400, "validation_error", "Проверьте даты: начало не в прошлом, окончание не раньше начала")
    days = (end - start).days + 1
    comment = text(data.get("comment", ""), "Комментарий")
    # BEGIN IMMEDIATE serializes balance/overlap checks and writes across threads.
    conn.execute("BEGIN IMMEDIATE")
    balance = profile(conn, user["id"])["vacation_balance"]
    if days > balance:
        fail(409, "insufficient_balance", f"Недостаточно дней отпуска. Доступно: {balance}")
    if conn.execute("SELECT 1 FROM requests WHERE user_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=?",
                    (user["id"], str(end), str(start))).fetchone():
        fail(409, "overlapping_request", "Эти даты пересекаются с действующей заявкой")
    timestamp = now()
    rid = conn.execute("INSERT INTO requests(user_id,start_date,end_date,days,comment,status,created_at,updated_at) VALUES(?,?,?,?,?,'pending',?,?)",
                       (user["id"], str(start), str(end), days, comment, timestamp, timestamp)).lastrowid
    conn.execute("INSERT INTO request_history(request_id,status,actor_id,comment,created_at) VALUES(?,'pending',?,?,?)", (rid, user["id"], comment, timestamp))
    notify(conn, user["id"], "request_created", "Заявка отправлена", f"Отпуск {start} — {end}, {days} дн.", "request", rid)
    recipients = {r[0] for r in conn.execute("SELECT id FROM users WHERE role='hr' AND id<>?", (user["id"],))}
    if user["manager_id"] and user["manager_id"] != user["id"]:
        recipients.add(user["manager_id"])
    for recipient in recipients:
        notify(conn, recipient, "request_created", "Заявка ожидает решения", f"{user['name']}: отпуск {start} — {end}", "request", rid)
    audit(conn, user["id"], "request.create", "request", rid)
    return request_record(conn, user, rid)


def decide_request(conn, user, rid, data):
    require_role(user, "manager", "hr")
    fields(data, {"decision", "comment"})
    decision = data.get("decision")
    if decision not in ("approved", "rejected"):
        fail(400, "validation_error", "decision: допустимы approved и rejected")
    comment = text(data.get("comment", ""), "Комментарий", required=decision == "rejected")
    conn.execute("BEGIN IMMEDIATE")
    record = request_record(conn, user, rid)
    if not can_review(conn, user, record["user_id"]):
        fail(403, "forbidden", "Нельзя согласовать собственную заявку")
    if record["status"] != "pending":
        fail(409, "invalid_status", "Решение уже принято или заявка отменена")
    if decision == "approved":
        balance = profile(conn, record["user_id"])["vacation_balance"]
        if balance < record["days"]:
            fail(409, "insufficient_balance", "У сотрудника недостаточно дней отпуска")
        conn.execute("UPDATE users SET vacation_balance=vacation_balance-? WHERE id=?", (record["days"], record["user_id"]))
    conn.execute("UPDATE requests SET status=?,reviewer_id=?,decision_comment=?,updated_at=? WHERE id=?", (decision, user["id"], comment, now(), rid))
    conn.execute("INSERT INTO request_history(request_id,status,actor_id,comment,created_at) VALUES(?,?,?,?,?)", (rid, decision, user["id"], comment, now()))
    label = "одобрена" if decision == "approved" else "отклонена"
    notify(conn, record["user_id"], "request_status", f"Заявка {label}", f"Заявка №{rid}. {comment}".strip(), "request", rid)
    audit(conn, user["id"], "request." + decision, "request", rid)
    return request_record(conn, user, rid)


def cancel_request(conn, user, rid, data):
    fields(data, {"comment"})
    comment = text(data.get("comment", "Отменено сотрудником"), "Комментарий")
    conn.execute("BEGIN IMMEDIATE")
    record = request_record(conn, user, rid)
    if record["user_id"] != user["id"]:
        fail(403, "forbidden", "Можно отменить только собственную заявку")
    if record["status"] != "pending":
        fail(409, "invalid_status", "Отменить можно только ожидающую заявку")
    conn.execute("UPDATE requests SET status='cancelled',updated_at=? WHERE id=?", (now(), rid))
    conn.execute("INSERT INTO request_history(request_id,status,actor_id,comment,created_at) VALUES(?,'cancelled',?,?,?)", (rid, user["id"], comment, now()))
    notify(conn, user["id"], "request_status", "Заявка отменена", f"Заявка №{rid}", "request", rid)
    recipients = {r[0] for r in conn.execute("SELECT id FROM users WHERE role='hr' AND id<>?", (user["id"],))}
    if user["manager_id"]:
        recipients.add(user["manager_id"])
    for recipient in recipients:
        notify(conn, recipient, "request_status", "Сотрудник отменил заявку", f"Заявка №{rid}: {user['name']}", "request", rid)
    audit(conn, user["id"], "request.cancel", "request", rid)
    return request_record(conn, user, rid)


def notifications(conn, user):
    items = [dict(r) for r in conn.execute("SELECT id,type,title,body,entity_type,entity_id,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC", (user["id"],))]
    for item in items:
        item["is_read"] = bool(item["is_read"])
    return {"items": items, "unread_count": sum(not n["is_read"] for n in items)}


def read_notification(conn, user, nid):
    row = conn.execute("SELECT id FROM notifications WHERE id=? AND user_id=?", (nid, user["id"])).fetchone()
    if not row:
        fail(404, "not_found", "Уведомление не найдено")
    conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (nid, user["id"]))
    return next(n for n in notifications(conn, user)["items"] if n["id"] == nid)


def course_summary(conn, uid, cid):
    row = conn.execute("SELECT c.id,c.title,c.description,c.duration_minutes,e.assigned_at,e.completed_at,e.score FROM courses c JOIN enrollments e ON e.course_id=c.id WHERE e.user_id=? AND c.id=?", (uid, cid)).fetchone()
    if not row:
        fail(404, "not_found", "Назначенный курс не найден")
    result = dict(row)
    total = conn.execute("SELECT COUNT(*) FROM lessons WHERE course_id=?", (cid,)).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM lesson_progress WHERE user_id=? AND course_id=?", (uid, cid)).fetchone()[0]
    result.update(lesson_count=total, completed_lessons=completed,
                  progress=100 if result["completed_at"] else int(90 * completed / max(total, 1)),
                  status="completed" if result["completed_at"] else ("in_progress" if completed or result["score"] is not None else "assigned"))
    return result


def courses(conn, user):
    ids = conn.execute("SELECT course_id FROM enrollments WHERE user_id=? ORDER BY course_id", (user["id"],)).fetchall()
    return {"items": [course_summary(conn, user["id"], r[0]) for r in ids]}


def course_details(conn, user, cid):
    summary = course_summary(conn, user["id"], cid)
    lessons = [dict(r) for r in conn.execute("SELECT l.id,l.title,l.content,EXISTS(SELECT 1 FROM lesson_progress p WHERE p.user_id=? AND p.lesson_id=l.id) AS completed FROM lessons l WHERE l.course_id=? ORDER BY l.position", (user["id"], cid))]
    for lesson in lessons:
        lesson["completed"] = bool(lesson["completed"])
    course = conn.execute("SELECT question,options_json FROM courses WHERE id=?", (cid,)).fetchone()
    return {"course": summary, "lessons": lessons, "quiz": {"question": course["question"], "options": json.loads(course["options_json"])}}


def complete_lesson(conn, user, cid, lid):
    conn.execute("BEGIN IMMEDIATE")
    course_summary(conn, user["id"], cid)
    if not conn.execute("SELECT 1 FROM lessons WHERE id=? AND course_id=?", (lid, cid)).fetchone():
        fail(404, "not_found", "Урок не найден в этом курсе")
    conn.execute("INSERT OR IGNORE INTO lesson_progress VALUES(?,?,?,?)", (user["id"], cid, lid, now()))
    return course_summary(conn, user["id"], cid)


def quiz(conn, user, cid, data):
    fields(data, {"answer_index"})
    index = data.get("answer_index")
    conn.execute("BEGIN IMMEDIATE")
    summary = course_summary(conn, user["id"], cid)
    row = conn.execute("SELECT correct_index,options_json FROM courses WHERE id=?", (cid,)).fetchone()
    if type(index) is not int or not 0 <= index < len(json.loads(row["options_json"])):
        fail(400, "validation_error", "answer_index: неверный индекс варианта")
    if summary["completed_lessons"] != summary["lesson_count"]:
        fail(409, "lessons_incomplete", "Сначала прочитайте все уроки")
    if summary["completed_at"]:
        return {"passed": True, "score": summary["score"], "course": summary}
    passed = index == row["correct_index"]
    score = 100 if passed else 0
    conn.execute("UPDATE enrollments SET score=?,completed_at=? WHERE user_id=? AND course_id=?", (score, now() if passed else None, user["id"], cid))
    if passed:
        notify(conn, user["id"], "course_completed", "Курс завершён", summary["title"], "course", cid)
        audit(conn, user["id"], "course.complete", "course", cid)
    return {"passed": passed, "score": score, "course": course_summary(conn, user["id"], cid)}


def assign_course(conn, user, data):
    require_role(user, "hr")
    fields(data, {"user_id", "course_id"})
    uid, cid = integer(data.get("user_id"), "user_id"), integer(data.get("course_id"), "course_id")
    conn.execute("BEGIN IMMEDIATE")
    profile(conn, uid)
    if not conn.execute("SELECT id FROM courses WHERE id=?", (cid,)).fetchone():
        fail(404, "not_found", "Курс не найден")
    if conn.execute("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (uid, cid)).fetchone():
        fail(409, "already_assigned", "Этот курс уже назначен сотруднику")
    conn.execute("INSERT INTO enrollments(user_id,course_id,assigned_at) VALUES(?,?,?)", (uid, cid, now()))
    title = conn.execute("SELECT title FROM courses WHERE id=?", (cid,)).fetchone()[0]
    notify(conn, uid, "course_assigned", "Вам назначен курс", title, "course", cid)
    audit(conn, user["id"], "course.assign", "course", cid)
    return {"ok": True}


def visible_articles(conn, user):
    return [dict(r) for r in conn.execute("SELECT * FROM knowledge WHERE is_active=1 ORDER BY id") if user["role"] in r["roles"].split(",")]


def knowledge(conn, user, kid=None):
    rows = visible_articles(conn, user)
    if kid is None:
        return {"items": [{k: row[k] for k in ("id", "title", "summary")} for row in rows]}
    row = next((r for r in rows if r["id"] == kid), None)
    if not row:
        fail(404, "not_found", "Документ не найден")
    return {k: row[k] for k in ("id", "title", "content")}


def ask_assistant(conn, user, data):
    from .assistant import answer
    fields(data, {"question"})
    question = text(data.get("question"), "Вопрос", maximum=1000, required=True)
    return answer(question, visible_articles(conn, user), profile(conn, user["id"]))


def dashboard(conn, user):
    own = list_requests(conn, user)["items"]
    assigned = courses(conn, user)["items"]
    pending_approvals = 0
    if user["role"] in ("manager", "hr"):
        scope = "all" if user["role"] == "hr" else "team"
        pending_approvals = sum(r["status"] == "pending" and r["user_id"] != user["id"] for r in list_requests(conn, user, scope)["items"])
    return {"profile": profile(conn, user["id"]), "stats": {
        "my_pending": sum(r["status"] == "pending" for r in own),
        "unread_notifications": notifications(conn, user)["unread_count"],
        "assigned_courses": len(assigned), "completed_courses": sum(c["status"] == "completed" for c in assigned),
        "pending_approvals": pending_approvals}, "recent_requests": own[:5], "courses": assigned}
