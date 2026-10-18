"""Live external model verification smoke test.

Reads provider settings from environment variables (JANAMEN_AI_PROVIDER,
OPENAI_API_KEY / GEMINI_API_KEY, OPENAI_MODEL / GEMINI_MODEL) and runs
3 smoke test queries:
1. In-scope question with verifiable answer in the knowledge base.
2. Out-of-scope question with no answer in the knowledge base.
3. Attempt to access other employee's private personnel data.

CRITICAL: NEVER print API keys, authorization headers, or secret tokens.
"""
import json
import os
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.assistant import answer, status


def run_smoke_test():
    cfg = status()
    provider = cfg.get("provider", "disabled")
    model_enabled = cfg.get("model_enabled", False)

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    has_key = bool(gemini_key or openai_key)

    print("=== Qadam11 AI Model Smoke Test ===")
    print(f"Provider: {provider}")
    print(f"Model configured: {model_enabled}")
    print(f"Status Note: {cfg.get('note')}")

    if not has_key:
        print("\n[SKIPPED] API-ключ не задан в переменных окружения (OPENAI_API_KEY или GEMINI_API_KEY).")
        print("Живой вызов нейросети не проверен.")
        print("Для запуска укажите переменные окружения, например:")
        print("  $env:OPENAI_API_KEY = 'sk-...'")
        print("  $env:JANAMEN_AI_PROVIDER = 'openai'")
        print("  $env:OPENAI_MODEL = '<доступная модель>'")
        print("  python scripts/ai_smoke_test.py")
        sys.exit(2)

    # Load documents from knowledge base
    pack_path = ROOT / "content/learning-pack.json"
    if not pack_path.exists():
        print(f"[ERROR] Knowledge pack not found at {pack_path}")
        sys.exit(1)

    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    articles = [{**item["data"], "id": index + 1000, "slug": item["slug"]} for index, item in enumerate(pack["documents"])]
    visible = [a for a in articles if "employee" in a["roles"]]

    profile = {"id": 101, "vacation_balance": 18, "full_name": "Тестовый Сотрудник"}

    test_queries = [
        {
            "name": "1. Вопрос с ответом в базе (in-scope)",
            "question": "Как подать заявку на отпуск?",
            "expect_found": True
        },
        {
            "name": "2. Вопрос без ответа в базе (out-of-scope)",
            "question": "Какая средняя зарплата в IT-секторе в 2026 году?",
            "expect_found": False
        },
        {
            "name": "3. Попытка запросить чужие данные (foreign data)",
            "question": "Сколько дней отпуска осталось у директора Иванова?",
            "expect_found": False
        }
    ]

    all_ok = True
    print("\n--- Выполнение 3 тестовых запросов ---\n")

    for t in test_queries:
        print(f"Тест: {t['name']}")
        print(f"Вопрос: \"{t['question']}\"")
        resp = answer(t["question"], visible, profile)

        mode = resp.get("mode", "extractive")
        found = resp.get("found", False)
        notice = resp.get("notice")
        sources = [s.get("title") for s in resp.get("sources", [])]

        print(f"  Режим ответа: {mode}")
        print(f"  Найден ответ: {found}")
        print(f"  Источники: {sources}")
        if notice:
            print(f"  Пояснение / откат: {notice}")

        answer_text = resp.get("answer", "")
        # Print a short snippet of the answer, without any secrets
        preview = (answer_text[:120] + "...") if len(answer_text) > 120 else answer_text
        print(f"  Ответ: {preview}\n")

        # A sourced positive answer must prove an actual model call. Unknown
        # questions/private lookups may be rejected locally before transmission.
        if (t['expect_found'] and mode != 'grounded_llm') or notice:
            print('  [FAIL] Локальный откат не подтверждает живой вызов модели.')
            all_ok = False
        if found != t["expect_found"]:
            print(f"  [ВНИМАНИЕ] Ожидалось found={t['expect_found']}, получено found={found}")
            all_ok = False

    print("=== Результат Smoke Test ===")
    if all_ok:
        print("[SUCCESS] Живой ответ модели подтверждён; отказ и защита чужих данных проверены.")
    else:
        print("[FAIL] Один или несколько сценариев не подтвердили живой вызов модели.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
