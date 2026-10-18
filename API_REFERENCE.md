# Серверный API Qadam11

Приложение и API раздаются с одного origin, по умолчанию http://localhost:8000. Сессия в HttpOnly cookie `jana_session`. Все запросы клиента используют credentials include. POST/PATCH после входа требуют X-CSRF-Token из login/me. Токен хранится в памяти клиента, после обновления страницы восстанавливается через me.

Ошибка: `{"error":{"code":"forbidden","message":"Недостаточно прав для этого действия"}}`. Типовые коды HTTP: 400 — валидация, 401 — нет сессии, 403 — запрет, 404 — ресурс не найден/недоступен, 409 — конфликт состояния, 413 — слишком большое тело, 415 — неверный Content-Type, 429 — лимит входов, 503 — недоступна БД.

## Маршруты

| Метод | Путь | Доступ |
|---|---|---|
| GET | /api/health | Публично; 200 при доступной БД, иначе 503 |
| GET | /api/setup/status | Публично; требуется ли первый HR, включён ли demo |
| POST | /api/setup | Публично только до создания первого пользователя |
| POST | /api/auth/login | Email + password, возвращает user и csrf_token |
| GET | /api/auth/me | Текущая сессия, user и csrf_token |
| POST | /api/auth/logout | Отзывает текущую сессию |
| GET | /api/profile | Собственный профиль, только чтение |
| GET | /api/dashboard | Собственные сводные данные; число согласований по роли |
| GET | /api/team | manager — прямые подчинённые; HR — сотрудники |
| GET | /api/requests?scope=mine | Свои заявки; team — manager/HR, all — только HR |
| POST | /api/requests | Собственная заявка type=vacation, start_date,end_date,comment |
| GET | /api/requests/{id} | Владелец или уполномоченный согласующий; включая историю |
| POST | /api/requests/{id}/decision | manager/HR; decision=approved/rejected, comment |
| POST | /api/requests/{id}/cancel | Только владелец pending-заявки |
| GET | /api/notifications | Только собственные, items и unread_count |
| PATCH | /api/notifications/{id}/read | Только собственное уведомление |
| POST | /api/notifications/read-all | Только собственные уведомления |
| GET | /api/courses | Собственные назначения |
| GET | /api/courses/{id} | Назначенный курс, уроки, тест без правильного ответа |
| POST | /api/courses/{id}/lessons/{lesson_id}/complete | Только собственное назначение |
| POST | /api/courses/{id}/quiz | answer_index; доступны после прочтения уроков |
| GET | /api/knowledge | Только опубликованные и доступные роли документы |
| GET | /api/knowledge/{id} | Документ с той же проверкой прав |
| GET | /api/assistant/status | Авторизованный: mode, model_enabled, provider, note; настройка не подтверждает доступность провайдера |
| GET | /api/admin/learning-pack | Только HR: состав набора и счётчики импорта |
| POST | /api/admin/learning-pack/import | Только HR, тело {}: created/skipped_documents/courses, 201; повторный импорт без дубликатов |
| POST | /api/assistant/ask | question; ответ, found, mode и sources |
| POST | /api/admin/users | Только HR: создание сотрудника |
| GET/POST | /api/admin/knowledge | Только HR: список/создание документов |
| PATCH | /api/admin/knowledge/{id} | Только HR: содержимое, роли и публикация |
| GET/POST | /api/admin/courses | Только HR: каталог/создание курса |
| GET/PATCH | /api/admin/courses/{id} | Только HR; изменение до назначения |
| POST | /api/admin/assignments | Только HR: user_id,course_id |

## Форматы и ограничения

- Идентификаторы числовые; даты отпуска YYYY-MM-DD, временные отметки ISO 8601 UTC.
- Списки находятся в `items`, кроме дополнительных полей notifications/dashboard.
- Начало отпуска не в прошлом; окончание не раньше начала. Дни календарные, обе даты включаются.
- Пересечения проверяются по pending/approved. Остаток проверяется при создании и повторно при одобрении.
- Повторное решение и отмена решённой заявки возвращают 409. Причина отказа обязательна.
- Данные пользователя/роль не принимаются из тела заявки: автор определяется сессией.
- Профиль не имеет маршрута записи. Новый аккаунт создаёт HR, пароль хранится как хеш с солью.
- Параметры HR-форм и расширенный контракт — DATA_MANAGEMENT.md. Полные модели прежних запросов — API_CONTRACT.md.

## Границы будущих интеграций

Сейчас profile/team получают данные из локального справочника SQLite. Будущий адаптер 1С:ЗУП синхронизирует официальные кадровые поля и остатки; собственный профиль остаётся read-only. Заявки/история выделены в сервисном слое; будущий адаптер Documentolog сможет синхронизировать документ и внешний статус. Реальные внешние вызовы в текущей сборке не выполняются.

## Режимы помощника

ask возвращает mode=extractive или grounded_llm. sources содержат только разрешённые документы либо собственный профиль. evidence содержит выбранные цитаты; при аварийном переходе с модели добавляется notice. found=false означает отказ без источников. По умолчанию внешняя модель отключена. Условия подключения и ограничения — NURS_DONE.md.
