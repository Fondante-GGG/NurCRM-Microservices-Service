import uuid
from typing import Dict, List, Any
from django.db import connection

INDUSTRY_PROFILES: Dict[str, Dict[str, List[str]]] = {
    "barber": {
        "positions": ["Барбер", "Топ-барбер", "Старший барбер", "Стажёр"],
        "categories": ["Стрижки", "Борода и бритьё", "Комплексы", "Уход и спа"],
    },
    "beauty": {
        "positions": ["Стилист-парикмахер", "Колорист", "Мастер маникюра", "Бровист-лэшмейкер"],
        "categories": ["Волосы и укладка", "Ногтевой сервис", "Брови и ресницы", "Эстетический уход"],
    },
    "procedure": {
        "positions": ["Процедурный специалист", "Медицинская сестра", "Врач-косметолог"],
        "categories": ["Инъекционные процедуры", "Капельницы и инфузии", "Анализы и забор биоматериала", "Перевязки и уход"],
    },
    "massage": {
        "positions": ["Массажист", "Топ-массажист", "Мастер спа-программ"],
        "categories": ["Классический массаж", "Спортивный массаж", "Релакс и ароматерапия", "Коррекция фигуры"],
    },
}


def apply_industry_profile(company_id: uuid.UUID, industry: str, reset_employees: bool = False) -> None:
    """
    Populates starter categories and positions for a company based on selected industry.
    If reset_employees is True, sets employee role_display to 'Специалист' (as required on industry change).
    """
    profile = INDUSTRY_PROFILES.get(industry)
    if not profile:
        return

    with connection.cursor() as cursor:
        # 1. Insert starter categories in catalog.service_categories if not already present
        for cat_name in profile["categories"]:
            cursor.execute("""
                INSERT INTO catalog.service_categories (id, company_id, name, is_active, version, created_at, updated_at)
                VALUES (uuid_generate_v4(), %s, %s, true, 1, now(), now())
                ON CONFLICT DO NOTHING
            """, [str(company_id), cat_name])

        # 2. If reset_employees is requested, reset role_display to 'Специалист'
        if reset_employees:
            cursor.execute("""
                UPDATE auth.employees
                SET role_display = 'Специалист', updated_at = now()
                WHERE company_id = %s AND role = 'master'
            """, [str(company_id)])
