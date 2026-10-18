"""Explicit mock boundary for future enterprise adapters. Never makes network calls."""
from datetime import timedelta

from .database import now, today
from .service import fail, fields, require_role


class OneCZupStub:
    """Internal normalized contract, not a representation of an official 1C API."""
    def preview(self):
        return {
            'direction': '1С:ЗУП → Qadam11',
            'request': {'operation': 'employee.read', 'external_employee_id': 'DEMO-EMP-001'},
            'response': {
                'external_employee_id': 'DEMO-EMP-001', 'name': 'Демо-сотрудник',
                'position': 'Специалист', 'department': 'Учебный отдел',
                'hire_date': '2025-01-15', 'vacation_balance': 24,
            },
            'steps': ['Сформирован пример запроса кадровых данных.',
                      'Заглушка вернула вымышленные поля сотрудника.',
                      'Профили и остатки в базе приложения не изменены.'],
        }


class DocumentologStub:
    """Preview only: no document is sent, created in the DB, or signed."""
    def preview(self):
        start = today() + timedelta(days=14)
        return {
            'direction': 'Qadam11 → Documentolog',
            'request': {
                'operation': 'vacation_document.prepare', 'request_id': 'DEMO-REQ-001',
                'employee_external_id': 'DEMO-EMP-001',
                'start_date': str(start), 'end_date': str(start + timedelta(days=2)),
                'document_type': 'vacation_application',
            },
            'response': {'external_document_id': 'MOCK-DOC-001', 'status': 'mock_preview',
                         'signed': False},
            'steps': ['Сформирован пример данных согласованной заявки.',
                      'Заглушка вернула демонстрационный номер документа.',
                      'Отправка, согласование в Documentolog и подписание не выполнялись.'],
        }


CATALOG = (
    {'id': '1c-zup', 'title': '1С:ЗУП', 'caption': 'Кадровые данные и остатки отпусков',
     'direction': '1С:ЗУП → Qadam11', 'status': 'not_connected', 'mode': 'mock',
     'description': 'В будущем официальный профиль и доступные дни отпуска будут приходить из кадровой системы.',
     'fields': ['Сотрудник и внешний идентификатор', 'Должность и подразделение', 'Дата приёма', 'Остаток отпуска'],
     'next_step': 'Согласовать доступ к 1С:ЗУП, соответствие полей и правила обновления данных.',
     'adapter': 'OneCZupStub'},
    {'id': 'documentolog', 'title': 'Documentolog', 'caption': 'Документы и подписание',
     'direction': 'Qadam11 → Documentolog', 'status': 'not_connected', 'mode': 'mock',
     'description': 'После согласования заявки её данные можно будет передавать для оформления и подписания документа.',
     'fields': ['Идентификатор согласованной заявки', 'Сотрудник и даты отпуска', 'Номер и статус документа', 'Результат подписания'],
     'next_step': 'Согласовать доступ к Documentolog, маршрут документа и обработку изменения статуса.',
     'adapter': 'DocumentologStub'},
)
ADAPTERS = {'1c-zup': OneCZupStub(), 'documentolog': DocumentologStub()}


def listing(user):
    require_role(user, 'hr')
    return {'mode': 'mock', 'external_calls': False, 'items': list(CATALOG),
            'notice': 'Обе интеграции — заглушки. Реальные 1С:ЗУП и Documentolog не подключены. '
                      'Просмотр примера не меняет данные и не отправляет документы.'}


def preview(user, provider, data):
    require_role(user, 'hr')
    fields(data, set())
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        fail(404, 'not_found', 'Интеграция не найдена')
    return {'provider': provider, 'mode': 'mock', 'external_calls': False, 'persisted': False,
            'generated_at': now(), 'notice': 'Пример внутреннего контракта адаптера на вымышленных данных. '
            'Это не ответ внешней системы и не её официальная спецификация API.', **adapter.preview()}
