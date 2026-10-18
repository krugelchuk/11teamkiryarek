# Задача для второго ИИ — фронтенд Qadam11 Digital HR

Мы делаем КЕЙС №02 Jana Post / Terricon Hackathon 2026: единая HR-платформа Qadam11. Первый кейс с адресами не относится к нашей задаче. Другой разработчик делает Python backend, SQLite, авторизацию, права доступа и API по контракту ниже. Твоя зона — только frontend. Не меняй backend и этот контракт; при необходимости сделай адаптер в клиенте.

Сделай готовый адаптивный интерфейс на React + Vite (или Vanilla JS, если быстрее). Не используй настоящие персональные данные. Весь текст по-русски. Визуальный стиль — удобный корпоративный кабинет Jana Post: светлые карточки, тёмная боковая навигация, оранжевый акцент, аккуратная типографика. Сначала рабочие сценарии, потом украшения.

## Экраны и поведение

1. Вход по email и паролю. Кнопки заполнения трёх демо-аккаунтов. После входа показывать имя и роль. Выход из аккаунта.
2. Главная: профиль, остаток отпуска, свои последние заявки, обучение и непрочитанные уведомления. Профиль read-only.
3. Мои заявки: форма отпуска (даты, комментарий), список, статусы pending/approved/rejected/cancelled; карточка с историей. Отмена только собственной pending-заявки.
4. Согласование: для manager — заявки своей команды; для hr — всех сотрудников. Одобрить или отклонить с комментарием. Свою заявку согласовать нельзя. Для отклонения комментарий обязателен.
5. Academy: назначенные курсы, уроки, фиксация прочтения, итоговый тест, прогресс. После прохождения обновлять карточки и уведомления.
6. Помощник: чат с POST /api/assistant/ask, показывать источники как ссылки на документы базы знаний. Корректно показывать found=false. Это MVP с извлечением ответа из базы знаний, не выдавай его за подключённую генеративную модель.
7. Уведомления: список, прочтение одного/всех, счётчик. HR может назначать курс сотруднику через простой выбор сотрудника и курса.
8. На каждый запрос показывать loading/error/empty state. Обновлять данные после изменений. Не подменять успешные ответы API моками при ошибках.

## Подключение

- API по умолчанию: `http://localhost:8000`. Для Vite — `VITE_API_URL`, с fallback на этот адрес. Открывай frontend тоже через `localhost`, а не `127.0.0.1`.
- Разрешённые dev origins: `http://localhost:5173`, `http://localhost:3000`, `http://localhost:4173` и соответствующие варианты с `127.0.0.1` (при выборе хоста используй одинаковый хост для frontend и API).
- Во ВСЕХ fetch ставь `credentials: 'include'`. Сессия находится в HttpOnly cookie; JWT и Bearer не используются.
- JSON-запросы: `Content-Type: application/json`. Для POST/PATCH после входа передавай `X-CSRF-Token` из ответа login/me. CSRF token храни в памяти; при обновлении страницы вызывай GET /api/auth/me. Для login токен не нужен.
- Обёртки списков: `{ "items": [...] }`. Ошибка: `{ "error": { "code": "forbidden", "message": "Текст для пользователя" } }` с HTTP 400/401/403/404/409/429.
- Все id — числа. Даты отпуска — YYYY-MM-DD, timestamps — ISO 8601 UTC.
- Три роли: `employee`, `manager`, `hr`. Профили только read-only, смены роли через API нет.

## Демо-вход

| Роль | Email | Тестовый пароль |
|---|---|---|
| Сотрудник | employee@demo.local | Demo2026! |
| Руководитель | manager@demo.local | Demo2026! |
| HR | hr@demo.local | Demo2026! |

Это специально созданные локальные демо-аккаунты, не реальные учётные данные.

## Точный контракт API v1

### Авторизация и профиль

- `GET /api/health` → `{status:"ok", service:"JanaMen Digital HR", version:"0.1.0", assistant_mode:"extractive"}`.
- `POST /api/auth/login` body `{email,password}` → `{user:Profile, csrf_token:string}` + cookie.
- `GET /api/auth/me` → `{user:Profile, csrf_token:string}` или 401.
- `POST /api/auth/logout` body `{}` → `{ok:true}`.
- `GET /api/profile` → `Profile`.
- `GET /api/dashboard` → `{profile:Profile, stats:{my_pending,unread_notifications,assigned_courses,completed_courses,pending_approvals}, recent_requests:Request[], courses:CourseSummary[]}`.
- `GET /api/team` → `{items:Profile[]}`; manager — только прямые подчинённые, hr — все; employee получает 403.

`Profile = {id,name,email,role,company,position,department,manager_id,manager_name,hire_date,vacation_balance}`. manager_id/manager_name могут быть null. vacation_balance — целое число дней.

### Отпуск

- `GET /api/requests?scope=mine` → `{items:Request[]}`. scope: mine (все роли), team (manager/hr), all (только hr). По умолчанию mine.
- `POST /api/requests` body `{type:"vacation",start_date:"2026-11-02",end_date:"2026-11-04",comment:"Семейные планы"}` → `Request` (201). Даты в примере заменять на актуальные будущие.
- `GET /api/requests/{id}` → `Request` с `history:History[]`.
- `POST /api/requests/{id}/decision` body `{decision:"approved"|"rejected",comment:string}` → `Request`.
- `POST /api/requests/{id}/cancel` body `{comment?:string}` → `Request`.

`Request = {id,user_id,employee_name,department,type,start_date,end_date,days,comment,status,created_at,updated_at,reviewer_id,reviewer_name,decision_comment}`. nullable: reviewer_id, reviewer_name, decision_comment. `type` в MVP только vacation. `status`: pending, approved, rejected, cancelled. `History = {id,status,actor_id,actor_name,comment,created_at}`.

Дни считаются календарно включительно — явно подпиши это возле формы как упрощение MVP. Доступный остаток проверяется и списывается только при одобрении. Пересекающиеся pending/approved-заявки запрещены. Прошедшие даты запрещены. На повторное решение — 409.

### Уведомления

- `GET /api/notifications` → `{items:Notification[],unread_count:number}`.
- `PATCH /api/notifications/{id}/read` body `{}` → `Notification`.
- `POST /api/notifications/read-all` body `{}` → `{ok:true}`.

`Notification = {id,type,title,body,entity_type,entity_id,is_read,created_at}`. entity_type: request/course, entity_id — число; is_read — boolean.

### Обучение

- `GET /api/courses` → `{items:CourseSummary[]}` — только свои назначения.
- `GET /api/courses/{id}` → `{course:CourseSummary,lessons:Lesson[],quiz:{question,options:string[]}}`. Без правильного ответа.
- `POST /api/courses/{id}/lessons/{lesson_id}/complete` body `{}` → `CourseSummary`.
- `POST /api/courses/{id}/quiz` body `{answer_index:number}` → `{passed:boolean,score:number,course:CourseSummary}`. Сначала нужно прочесть все уроки.
- `GET /api/admin/courses` → `{items:[{id,title,description,duration_minutes}]}` — только hr, каталог для назначения.
- `POST /api/admin/assignments` body `{user_id:number,course_id:number}` → `{ok:true}` (201) — только hr; существующее назначение → 409.

`CourseSummary = {id,title,description,duration_minutes,progress,status,assigned_at,completed_at,score,lesson_count,completed_lessons}`. status: assigned/in_progress/completed, progress 0..100, score/ completed_at nullable. После прочтения уроков прогресс максимум 90%; 100% после правильного ответа.
`Lesson = {id,title,content,completed:boolean}`. content — обычный текст, не HTML.

### Помощник и источники

- `POST /api/assistant/ask` body `{question:string}` → `{answer:string,found:boolean,mode:"extractive",sources:[{id,title,url}]}`.
- `GET /api/knowledge` → `{items:[{id,title,summary}]}` — только разрешённые роли документы.
- `GET /api/knowledge/{id}` → `{id,title,content}`.
- url источника — относительный `/api/knowledge/{id}`; при ссылке добавь базовый URL API или открой документ в модальном окне через fetch.
- Подсказки: «Как оформить отпуск?», «Какой у меня остаток отпуска?», «Как пройти обучение?», «Когда выплачивается зарплата?».
- Последний вопрос должен дать found=false: такой политики в демо-базе нет. Не выдумывать ответ.

## Запуск и передача

Сделай README, `.env.example`, `npm run dev -- --host 127.0.0.1`, `npm run build`. Не клади node_modules в архив. Если backend пока недоступен — заверши клиент строго по контракту; покажи честное сообщение о недоступности. Сохрани готовый проект и zip. В конце перечисли команды запуска и реализованные экраны.


## Дополнение: управляемые данные

Обычный новый запуск теперь пустой, первый HR создаётся через GET /api/setup/status и POST /api/setup. Кнопки демо-входа удалены; примерные аккаунты остаются только в --demo. Дополнительные HR-маршруты и формы описаны в DATA_MANAGEMENT.md. Прежние API авторизации, заявок, уведомлений и прохождения курсов сохранены.

## Дополнение: карта филиалов

- GET `/api/branches?from=YYYY-MM-DD&to=YYYY-MM-DD`: каталог, scope, demo_mode, source_url; у точки member_count, min_remaining, max_approved/max_pending, shortage_days, is_mine. Период 1–62 дня, по умолчанию сегодня +13 дней.
- GET `/api/branches/{branch_id}` с теми же датами: branch, members, leaves, days, calendar и scope. Все люди, отпуска и агрегаты ограничены ролью. Полный min_staff и shortage только у HR.
- GET `/api/branches/{branch_id}/employees/{user_id}`: profile, courses, requests. Только собственная карточка / прямой подчинённый / HR, привязка к указанному филиалу обязательна, иначе 404.
- PATCH `/api/admin/users/{user_id}/branch` body `{branch_id: string|null}`: только HR, CSRF. Назначение или удаление привязки.
- PATCH `/api/admin/branches/{branch_id}` body `{min_staff: integer|null}`: только HR, CSRF; 0–10000, null отключает порог.
- В profile добавлены nullable branch_id и branch_address. Branch id — строковый id публичной карточки 2ГИС. Новый контракт типов frontend: src/api/branches.ts. Содержимое и правила: MAP_AND_CALENDAR.md.

### Будущие корпоративные интеграции (mock)

- GET /api/admin/integrations: только HR, `{mode:"mock",external_calls:false,notice,items}`. Каждый элемент: id, title, caption, direction, status="not_connected", mode="mock", description, fields, next_step, adapter.
- POST /api/admin/integrations/{provider}/preview, body `{}`: только HR + CSRF. provider: 1c-zup или documentolog. Возвращает mode="mock", external_calls=false, persisted=false, generated_at, notice, direction, request, response, steps. Данные вымышленные, записи приложения не меняются. Неверный provider → 404, лишние поля → 400.
- Это внутренний пример контракта адаптера, не официальная спецификация внешнего API. Страница frontend: /integrations. Подробности: ENTERPRISE_INTEGRATIONS.md.

### Приветствие помощника

Ответ assistant/ask может иметь mode=conversation: приветствие, помощь или благодарность, без источников. found=false в этом режиме означает отсутствие поиска HR-фактов, а не отказ. UI показывает текст без заголовка ошибки. Смешанные вопросы и чужие кадровые данные этим режимом не обходят обычные проверки.
