"""HR-managed records. Values come from authenticated forms, never fixed fixtures."""
import json
import re
import sqlite3

from .database import password_hash, now, today, audit
from .service import fields, text, integer, fail, require_role, profile, parse_date

ROLES = {"employee", "manager", "hr"}


def setup_status(conn):
    mode = conn.execute("SELECT value FROM settings WHERE key='demo_mode'").fetchone()
    return {"setup_required": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0,
            "demo_mode": bool(mode and mode[0] == "1")}


def employee_values(data, bootstrap=False):
    allowed = {"name", "email", "password", "company"}
    if not bootstrap:
        allowed |= {"role", "position", "department", "manager_id", "hire_date", "vacation_balance"}
    fields(data, allowed)
    name = text(data.get("name"), "Имя", 150, True)
    email = text(data.get("email"), "Email", 254, True).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        fail(400, "validation_error", "Укажите корректный email")
    password = data.get("password")
    if not isinstance(password, str) or not 10 <= len(password) <= 256:
        fail(400, "validation_error", "Пароль должен содержать от 10 до 256 символов")
    role = "hr" if bootstrap else data.get("role", "employee")
    if not isinstance(role, str) or role not in ROLES:
        fail(400, "validation_error", "Неизвестная роль")
    balance = 0 if bootstrap else data.get("vacation_balance", 0)
    if type(balance) is not int or not 0 <= balance <= 365:
        fail(400, "validation_error", "Остаток отпуска: целое число от 0 до 365")
    manager = None if bootstrap else data.get("manager_id")
    if manager is not None:
        integer(manager, "manager_id")
    hire = today() if bootstrap else parse_date(data.get("hire_date", str(today())), "hire_date")
    return (name, email, password_hash(password), role,
            text(data.get("company"), "Компания", 150, True),
            "HR-администратор" if bootstrap else text(data.get("position", ""), "Должность", 150),
            "HR" if bootstrap else text(data.get("department", ""), "Подразделение", 150),
            manager, str(hire), balance)


def add_user(conn, values):
    manager = values[7]
    if manager is not None:
        row = conn.execute("SELECT role FROM users WHERE id=?", (manager,)).fetchone()
        if not row or row["role"] not in {"manager", "hr"}:
            fail(400, "validation_error", "Руководителем может быть существующий manager или HR")
    try:
        uid = conn.execute("INSERT INTO users(name,email,password_hash,role,company,position,department,manager_id,hire_date,vacation_balance) VALUES(?,?,?,?,?,?,?,?,?,?)", values).lastrowid
    except sqlite3.IntegrityError:
        fail(409, "email_exists", "Этот email уже используется")
    return uid


def setup(conn, data):
    if not setup_status(conn)["setup_required"]:
        fail(409, "already_configured", "Первый HR-аккаунт уже создан. Войдите в систему")
    values = employee_values(data, bootstrap=True)
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    if not setup_status(conn)["setup_required"]:
        fail(409, "already_configured", "Первый HR-аккаунт уже создан. Войдите в систему")
    uid = add_user(conn, values)
    audit(conn, uid, "setup.complete", "user", uid)
    return {"ok": True}


def create_user(conn, user, data):
    require_role(user, "hr")
    values = employee_values(data)
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    uid = add_user(conn, values)
    audit(conn, user["id"], "user.create", "user", uid)
    return profile(conn, uid)


def article_record(row):
    item = dict(row)
    item.pop("keywords", None)
    item["roles"] = item["roles"].split(",")
    item["is_active"] = bool(item["is_active"])
    return item


def articles(conn, user):
    require_role(user, "hr")
    return {"items": [article_record(r) for r in conn.execute("SELECT * FROM knowledge ORDER BY id DESC")]}


def save_article(conn, user, data, kid=None):
    require_role(user, "hr")
    fields(data, {"title", "summary", "content", "roles", "is_active"})
    title = text(data.get("title"), "Название", 200, True)
    summary = text(data.get("summary", ""), "Описание", 500)
    content = text(data.get("content"), "Текст документа", 40000, True)
    roles = data.get("roles")
    if not isinstance(roles, list) or not roles or any(not isinstance(r, str) or r not in ROLES for r in roles):
        fail(400, "validation_error", "Выберите хотя бы одну корректную роль доступа")
    active = data.get("is_active", True)
    if type(active) is not bool:
        fail(400, "validation_error", "is_active: ожидается boolean")
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    if kid is None:
        kid = conn.execute("INSERT INTO knowledge(title,summary,content,keywords,roles,is_active,updated_at) VALUES(?,?,?,'',?,?,?)", (title, summary, content, ",".join(sorted(set(roles))), int(active), now())).lastrowid
    else:
        if not conn.execute("SELECT id FROM knowledge WHERE id=?", (kid,)).fetchone():
            fail(404, "not_found", "Документ не найден")
        conn.execute("UPDATE knowledge SET title=?,summary=?,content=?,roles=?,is_active=?,updated_at=? WHERE id=?", (title, summary, content, ",".join(sorted(set(roles))), int(active), now(), kid))
    audit(conn, user["id"], "knowledge.save", "knowledge", kid)
    return article_record(conn.execute("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone())


def course_record(conn, cid):
    row = conn.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
    if not row:
        fail(404, "not_found", "Курс не найден")
    result = dict(row)
    result["options"] = json.loads(result.pop("options_json"))
    result["lessons"] = [dict(r) for r in conn.execute("SELECT id,title,content FROM lessons WHERE course_id=? ORDER BY position", (cid,))]
    result["assignment_count"] = conn.execute("SELECT COUNT(*) FROM enrollments WHERE course_id=?", (cid,)).fetchone()[0]
    return result


def course_catalog(conn, user, cid=None):
    require_role(user, "hr")
    if cid is not None:
        return course_record(conn, cid)
    return {"items": [course_record(conn, row[0]) for row in conn.execute("SELECT id FROM courses ORDER BY id DESC").fetchall()]}


def save_course(conn, user, data, cid=None):
    require_role(user, "hr")
    fields(data, {"title", "description", "duration_minutes", "lessons", "question", "options", "correct_index"})
    title = text(data.get("title"), "Название курса", 200, True)
    desc = text(data.get("description", ""), "Описание", 2000)
    minutes = integer(data.get("duration_minutes"), "duration_minutes")
    if minutes > 10000:
        fail(400, "validation_error", "Слишком большая продолжительность")
    question = text(data.get("question"), "Вопрос теста", 1000, True)
    options = data.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 8:
        fail(400, "validation_error", "Нужно от 2 до 8 вариантов ответа")
    options = [text(option, "Вариант ответа", 500, True) for option in options]
    correct = data.get("correct_index")
    if type(correct) is not int or not 0 <= correct < len(options):
        fail(400, "validation_error", "Выберите правильный вариант ответа")
    lessons = data.get("lessons")
    if not isinstance(lessons, list) or not 1 <= len(lessons) <= 20:
        fail(400, "validation_error", "В курсе должно быть от 1 до 20 уроков")
    normalized = []
    for lesson in lessons:
        if not isinstance(lesson, dict):
            fail(400, "validation_error", "Некорректный урок")
        fields(lesson, {"title", "content"})
        normalized.append((text(lesson.get("title"), "Название урока", 200, True), text(lesson.get("content"), "Содержание урока", 20000, True)))
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    values = (title, desc, minutes, question, json.dumps(options, ensure_ascii=False), correct)
    if cid is None:
        cid = conn.execute("INSERT INTO courses(title,description,duration_minutes,question,options_json,correct_index) VALUES(?,?,?,?,?,?)", values).lastrowid
    else:
        record = course_record(conn, cid)
        if record["assignment_count"]:
            fail(409, "course_in_use", "Курс уже назначен сотрудникам. Создайте новую версию курса, чтобы сохранить их прогресс")
        conn.execute("UPDATE courses SET title=?,description=?,duration_minutes=?,question=?,options_json=?,correct_index=? WHERE id=?", (*values, cid))
        conn.execute("DELETE FROM lessons WHERE course_id=?", (cid,))
    for position, (lesson_title, content) in enumerate(normalized, 1):
        conn.execute("INSERT INTO lessons(course_id,title,content,position) VALUES(?,?,?,?)", (cid, lesson_title, content, position))
    audit(conn, user["id"], "course.save", "course", cid)
    return course_record(conn, cid)
