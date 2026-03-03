from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, timedelta, datetime

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.models import Base, Product, Sale, HREvent, HRDocument, HREventType, DocumentStatus


def _ensure_sqlite_dir(database_url: str) -> None:
    # sqlite:///./data/file.db  -> нужно создать ./data
    if database_url.startswith("sqlite:///"):
        path = database_url.replace("sqlite:///", "", 1)
        dirpath = os.path.dirname(path)
        if dirpath and dirpath not in (".", "/"):
            os.makedirs(dirpath, exist_ok=True)


def get_engine():
    settings = get_settings()
    _ensure_sqlite_dir(settings.database_url)
    engine = create_engine(
        settings.database_url,
        future=True,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Session:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db_and_seed() -> None:
    """Создаёт таблицы и гарантирует минимальное стартовое заполнение данных.
    Функция идемпотентна: при повторных запусках не «раздувает» таблицы,
    а доводит их до целевых порогов.
    """

    engine = get_engine()
    Base.metadata.create_all(engine)

    TARGET_PRODUCTS = 20
    TARGET_SALES = 320
    TARGET_HR_EVENTS = 20
    TARGET_HR_DOCS = 20

    seed_products: list[tuple[str, str, float]] = [
        ("Цемент М500 50кг", "Сухие смеси", 9.90),
        ("Цемент М400 50кг", "Сухие смеси", 8.70),
        ("Штукатурка гипсовая 30кг", "Сухие смеси", 8.20),
        ("Шпаклёвка финишная 20кг", "Сухие смеси", 6.60),
        ("Клей плиточный универсальный 25кг", "Сухие смеси", 7.10),
        ("Грунтовка глубокого проникновения 10л", "ЛКМ", 12.50),
        ("Краска водоэмульсионная белая 14кг", "ЛКМ", 18.40),
        ("Эмаль ПФ-115 2.7л", "ЛКМ", 10.90),
        ("Лак акриловый 2л", "ЛКМ", 9.40),
        ("Плитка керамическая 30x30", "Отделка", 1.30),
        ("Ламинат 32 класс 8мм (уп. 2.2м²)", "Отделка", 21.50),
        ("Плинтус ПВХ 2.5м", "Отделка", 2.10),
        ("Гипсокартон 12.5мм 1200x2500", "Отделка", 7.80),
        ("Профиль CD 60/27 3м", "Отделка", 3.20),
        ("Саморезы 3.5x35 (уп. 200шт)", "Крепёж", 3.40),
        ("Дюбель-гвоздь 6x40 (уп. 100шт)", "Крепёж", 4.10),
        ("Анкер клиновой 10x100 (уп. 20шт)", "Крепёж", 6.90),
        ("Пена монтажная 750мл", "Монтаж", 5.10),
        ("Герметик силиконовый санитарный 280мл", "Монтаж", 4.60),
        ("Пена-клей 750мл", "Монтаж", 6.20),
        ("Перфоратор 800Вт", "Инструменты", 79.90),
        ("Дрель-шуруповёрт 18В", "Инструменты", 64.50),
        ("Уровень пузырьковый 60см", "Инструменты", 8.90),
        ("Кабель ВВГнг 3x2.5 (1м)", "Электрика", 1.65),
        ("Розетка двойная внутренняя", "Электрика", 2.30),
        ("Выключатель одноклавишный", "Электрика", 1.75),
        ("Смеситель для раковины", "Сантехника", 24.90),
        ("Труба ПП 20мм (2м)", "Сантехника", 2.80),
        ("Фитинг ПП угол 20мм", "Сантехника", 0.55),
        ("Доска обрезная 25x150 (1м)", "Пиломатериалы", 3.10),
    ]

    stores = ["Склад (центр)", "Точка №1", "Точка №2", "Точка №3 (опт)"]
    employees = [
        "Иванов И.И.", "Петров П.П.", "Сидорова А.А.", "Кузнецов Д.Д.",
        "Смирнов Н.Н.", "Фёдорова Е.В.", "Орлов А.С.", "Морозова Т.К.",
    ]
    today = date.today()
    now = datetime.utcnow().replace(microsecond=0)

    with session_scope() as s:
        # -----------------------
        # Products (>= 20)
        # -----------------------
        existing_names = {name for (name,) in s.execute(select(Product.name)).all()}
        current_products = len(existing_names)

        if current_products < TARGET_PRODUCTS:
            for name, category, price in seed_products:
                if len(existing_names) >= TARGET_PRODUCTS:
                    break
                if name in existing_names:
                    continue
                s.add(Product(name=name, category=category, price=float(price)))
                existing_names.add(name)

        s.flush()
        products = s.execute(select(Product).order_by(Product.id)).scalars().all()
        if not products:
            return  

        # -----------------------
        # Sales (>= 320)
        # -----------------------
        sales_count = s.scalar(select(func.count(Sale.id))) or 0
        if sales_count < TARGET_SALES:
            min_day = today - timedelta(days=180)
            existing_sale_keys = set(
                s.execute(
                    select(
                        Sale.sale_date,
                        Sale.store,
                        Sale.product_id,
                        Sale.qty,
                        Sale.unit_price,
                        Sale.employee_name,
                    ).where(Sale.sale_date >= min_day)
                ).all()
            )

            to_add = TARGET_SALES - sales_count
            days = 90
            for d in range(days):
                day = today - timedelta(days=(days - 1 - d))
                for st_i, st_name in enumerate(stores):
                    n = (day.toordinal() + (st_i + 1) * 3) % 5
                    for i in range(n):
                        p = products[(day.toordinal() + i + st_i) % len(products)]
                        qty = ((day.day + i + st_i) % 10) + 1

                        factor = 0.96 + (((day.day + i + st_i) % 8) * 0.01)
                        unit_price = round(float(p.price) * factor, 2)

                        emp = employees[(day.toordinal() + i + st_i) % len(employees)]
                        key = (day, st_name, p.id, qty, unit_price, emp)
                        if key in existing_sale_keys:
                            continue

                        s.add(Sale(
                            sale_date=day,
                            product_id=p.id,
                            qty=int(qty),
                            unit_price=float(unit_price),
                            store=st_name,
                            employee_name=emp,
                        ))
                        existing_sale_keys.add(key)
                        to_add -= 1
                        if to_add <= 0:
                            break
                    if to_add <= 0:
                        break
                if to_add <= 0:
                    break

        # -----------------------
        # HR events (>= 20)
        # -----------------------
        hr_count = s.scalar(select(func.count(HREvent.id))) or 0
        if hr_count < TARGET_HR_EVENTS:
            existing_hr_keys = set(
                s.execute(select(HREvent.employee_name, HREvent.event_type, HREvent.start_date)).all()
            )

            to_add = TARGET_HR_EVENTS - hr_count
            types = [HREventType.hire, HREventType.vacation, HREventType.sick_leave, HREventType.fire]
            notes_by_type = {
                HREventType.hire: "Оформление нового сотрудника",
                HREventType.vacation: "Ежегодный оплачиваемый отпуск",
                HREventType.sick_leave: "Лист нетрудоспособности",
                HREventType.fire: "Увольнение (по соглашению сторон)",
            }

            for k in range(200):  
                if to_add <= 0:
                    break
                emp = employees[k % len(employees)]
                et = types[k % len(types)]
                start = today - timedelta(days=((k * 11) % 365))
                if et == HREventType.vacation:
                    end = start + timedelta(days=13)
                elif et == HREventType.sick_leave:
                    end = start + timedelta(days=3)
                elif et == HREventType.fire:
                    end = start
                else:
                    end = None

                key = (emp, et, start)
                if key in existing_hr_keys:
                    continue

                s.add(HREvent(
                    employee_name=emp,
                    event_type=et,
                    start_date=start,
                    end_date=end,
                    notes=notes_by_type.get(et, ""),
                ))
                existing_hr_keys.add(key)
                to_add -= 1

        # -----------------------
        # HR documents (>= 20)
        # -----------------------
        docs_count = s.scalar(select(func.count(HRDocument.id))) or 0
        if docs_count < TARGET_HR_DOCS:
            to_add = TARGET_HR_DOCS - docs_count

            doc_types = [
                "Трудовой договор",
                "Дополнительное соглашение",
                "Приказ",
                "Должностная инструкция",
                "Согласие на обработку ПДн",
                "График отпусков",
                "Инструктаж по охране труда",
                "Медосмотр",
            ]

            for k in range(200):
                if to_add <= 0:
                    break

                emp = employees[(k * 3) % len(employees)]
                dt = doc_types[k % len(doc_types)]
                status = DocumentStatus.signed if (k % 3 != 0) else DocumentStatus.uploaded

                uploaded_at = now - timedelta(days=(k * 4 + 2))
                signed_at = (uploaded_at + timedelta(days=1)) if status == DocumentStatus.signed else None
                comment = "Подписан ЭП" if status == DocumentStatus.signed else "Ожидает подписи/проверки"

                exists = s.scalar(
                    select(func.count(HRDocument.id)).where(
                        HRDocument.employee_name == emp,
                        HRDocument.doc_type == dt,
                        HRDocument.uploaded_at == uploaded_at,
                    )
                )
                if exists and exists > 0:
                    continue

                s.add(HRDocument(
                    employee_name=emp,
                    doc_type=dt,
                    status=status,
                    uploaded_at=uploaded_at,
                    signed_at=signed_at,
                    comment=comment,
                ))
                to_add -= 1
