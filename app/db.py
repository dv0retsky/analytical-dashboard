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


def _add_demo_sales(
    session: Session,
    products: list[Product],
    stores: list[str],
    employees: list[str],
    date_from: date,
    date_to: date,
    rows_to_add: int,
    salt: int = 0,
) -> int:
    """Добавляет детерминированные демонстрационные операции без дублей."""
    if rows_to_add <= 0 or not products:
        return 0

    existing_sale_keys = set(
        session.execute(
            select(
                Sale.sale_date,
                Sale.store,
                Sale.product_id,
                Sale.qty,
                Sale.unit_price,
                Sale.employee_name,
            ).where(Sale.sale_date >= date_from, Sale.sale_date <= date_to)
        ).all()
    )

    days_count = (date_to - date_from).days + 1
    if days_count <= 0:
        return 0

    added = 0
    cycle = 0
    # Несколько проходов нужны на случай, если часть строк уже была добавлена раньше.
    while added < rows_to_add and cycle < 12:
        for day_offset in range(days_count):
            day = date_from + timedelta(days=day_offset)
            # В каждом стенде каждый день появляется несколько операций, чтобы графики
            # по дням, компонентам и категориям не были пустыми даже на коротких периодах.
            for st_i, st_name in enumerate(stores):
                operations_per_stand = 2 + ((day.toordinal() + st_i + cycle + salt) % 3)
                for i in range(operations_per_stand):
                    p = products[(day.toordinal() + i + st_i * 3 + cycle + salt) % len(products)]
                    qty = ((day.day + i + st_i + cycle + salt) % 12) + 1
                    factor = 0.92 + (((day.toordinal() + i + st_i + cycle + salt) % 17) * 0.01)
                    unit_price = round(float(p.price) * factor, 2)
                    emp = employees[(day.toordinal() + i + st_i + cycle + salt) % len(employees)]

                    key = (day, st_name, p.id, qty, unit_price, emp)
                    if key in existing_sale_keys:
                        continue

                    session.add(
                        Sale(
                            sale_date=day,
                            product_id=p.id,
                            qty=int(qty),
                            unit_price=float(unit_price),
                            store=st_name,
                            employee_name=emp,
                        )
                    )
                    existing_sale_keys.add(key)
                    added += 1
                    if added >= rows_to_add:
                        return added
        cycle += 1

    return added


def _ensure_recent_engineering_events(
    session: Session,
    employees: list[str],
    today: date,
    min_recent_events: int = 16,
) -> None:
    """Гарантирует наличие событий команды в актуальном периоде для графиков дашборда."""
    recent_from = today - timedelta(days=60)
    recent_count = session.scalar(
        select(func.count(HREvent.id)).where(
            HREvent.start_date >= recent_from,
            HREvent.start_date <= today,
        )
    ) or 0
    if recent_count >= min_recent_events:
        return

    existing_keys = set(
        session.execute(
            select(HREvent.employee_name, HREvent.event_type, HREvent.start_date).where(
                HREvent.start_date >= recent_from,
                HREvent.start_date <= today,
            )
        ).all()
    )

    types = [HREventType.hire, HREventType.vacation, HREventType.sick_leave, HREventType.fire]
    notes_by_type = {
        HREventType.hire: "Ввод инженера в проект СВЧ-изделий и допуск к стендам",
        HREventType.vacation: "Плановый отпуск специалиста СВЧ-лаборатории",
        HREventType.sick_leave: "Отсутствие инженера по болезни",
        HREventType.fire: "Вывод специалиста из проектной команды",
    }

    to_add = int(min_recent_events - recent_count)
    for k in range(160):
        if to_add <= 0:
            break
        emp = employees[(k * 2) % len(employees)]
        et = types[k % len(types)]
        start = today - timedelta(days=((k * 4 + 1) % 55))
        if et == HREventType.vacation:
            end = start + timedelta(days=10)
        elif et == HREventType.sick_leave:
            end = start + timedelta(days=3)
        elif et == HREventType.fire:
            end = start
        else:
            end = None

        key = (emp, et, start)
        if key in existing_keys:
            continue

        session.add(
            HREvent(
                employee_name=emp,
                event_type=et,
                start_date=start,
                end_date=end,
                notes=notes_by_type.get(et, ""),
            )
        )
        existing_keys.add(key)
        to_add -= 1


def init_db_and_seed() -> None:
    """Создаёт таблицы и гарантирует стартовое заполнение данных.

    Функция идемпотентна: при повторных запусках она не «раздувает» таблицы
    бесконтрольно, но добавляет недостающие СВЧ-компоненты и актуальные
    операции за последние недели. Поэтому графики дашборда не остаются пустыми
    даже если в папке data уже лежит старая демонстрационная SQLite-БД.
    """

    engine = get_engine()
    Base.metadata.create_all(engine)

    TARGET_SALES_TOTAL = 360
    TARGET_RECENT_SALES = 220
    TARGET_HR_EVENTS_TOTAL = 28
    TARGET_HR_DOCS = 24

    seed_products: list[tuple[str, str, float]] = [
        ("GaN HEMT транзистор 6–18 ГГц", "Активные СВЧ-компоненты", 145.00),
        ("МШУ X-диапазона 8–12 ГГц", "Активные СВЧ-компоненты", 220.00),
        ("СВЧ-усилитель мощности 10 Вт, 2.4 ГГц", "Активные СВЧ-компоненты", 310.00),
        ("Смеситель 2–18 ГГц", "Активные СВЧ-компоненты", 180.00),
        ("PIN-диодный аттенюатор 0–31 дБ", "Активные СВЧ-компоненты", 95.00),
        ("Полосовой фильтр 5.8 ГГц", "Пассивные СВЧ-компоненты", 42.00),
        ("Направленный ответвитель 10 дБ, 1–8 ГГц", "Пассивные СВЧ-компоненты", 68.00),
        ("Циркулятор S-диапазона", "Пассивные СВЧ-компоненты", 115.00),
        ("Коаксиальный переход SMA–N", "Коаксиальные тракты", 18.50),
        ("Кабельная сборка SMA 0.5 м", "Коаксиальные тракты", 24.00),
        ("Поглотитель СВЧ 2–18 ГГц", "Измерительная оснастка", 52.00),
        ("Калибровочный набор SOLT SMA", "Измерительная оснастка", 480.00),
        ("Волновод WR-90, секция 100 мм", "Волноводные устройства", 130.00),
        ("Волноводный фланец WR-90", "Волноводные устройства", 55.00),
        ("Рупорная антенна 8–12 ГГц", "Антенны", 260.00),
        ("Патч-антенна 2.4 ГГц", "Антенны", 35.00),
        ("Фазовращатель 0–360°, 6 ГГц", "Фазированные решётки", 150.00),
        ("T/R модуль L-диапазона", "СВЧ-модули", 390.00),
        ("Приёмопередающий модуль X-диапазона", "СВЧ-модули", 620.00),
        ("Подложка Rogers RO4350B 0.508 мм", "Материалы и подложки", 75.00),
        ("Подложка AlN для мощных СВЧ-узлов", "Материалы и подложки", 110.00),
        ("Теплоотвод медно-молибденовый", "Материалы и подложки", 88.00),
        ("Детектор мощности 10 МГц–8 ГГц", "Измерительные узлы", 135.00),
        ("Синтезатор частоты 100 МГц–6 ГГц", "Измерительные узлы", 340.00),
        ("СВЧ-переключатель SPDT 18 ГГц", "Коаксиальные тракты", 125.00),
        ("Нагрузка 50 Ом 18 ГГц", "Коаксиальные тракты", 29.00),
        ("Ограничитель мощности 1–12 ГГц", "Защита СВЧ-тракта", 70.00),
        ("Фильтр нижних частот 3 ГГц", "Пассивные СВЧ-компоненты", 38.00),
        ("Делитель мощности 2-way, 0.7–6 ГГц", "Пассивные СВЧ-компоненты", 90.00),
        ("Переход микрополосковая линия — SMA", "Измерительная оснастка", 31.00),
    ]
    seed_product_names = [name for name, _, _ in seed_products]

    stores = [
        "Стенд ВНА/S-параметров",
        "Безэховая камера",
        "Участок сборки СВЧ-модулей",
        "Термовакуумный стенд",
    ]
    employees = [
        "Иванов И.И.", "Петров П.П.", "Сидорова А.А.", "Кузнецов Д.Д.",
        "Смирнов Н.Н.", "Фёдорова Е.В.", "Орлов А.С.", "Морозова Т.К.",
    ]
    today = date.today()
    now = datetime.utcnow().replace(microsecond=0)

    with session_scope() as s:
        # -----------------------
        # Products: добавляем все СВЧ-позиции, даже если старая БД уже содержит
        # 20+ записей другой предметной области.
        # -----------------------
        existing_names = {name for (name,) in s.execute(select(Product.name)).all()}
        for name, category, price in seed_products:
            if name not in existing_names:
                s.add(Product(name=name, category=category, price=float(price)))
                existing_names.add(name)

        s.flush()
        products = (
            s.execute(select(Product).where(Product.name.in_(seed_product_names)).order_by(Product.id))
            .scalars()
            .all()
        )
        if not products:
            return

        # -----------------------
        # Sales / испытания и поставки.
        # 1) Доводим общий набор до разумного объёма.
        # 2) Отдельно гарантируем свежие записи в последние 30-45 дней,
        #    иначе дашборд с периодом по умолчанию может показывать «нет данных».
        # -----------------------
        sales_count = s.scalar(select(func.count(Sale.id))) or 0
        if sales_count < TARGET_SALES_TOTAL:
            _add_demo_sales(
                session=s,
                products=products,
                stores=stores,
                employees=employees,
                date_from=today - timedelta(days=89),
                date_to=today,
                rows_to_add=TARGET_SALES_TOTAL - int(sales_count),
                salt=0,
            )
            s.flush()

        recent_from = today - timedelta(days=44)
        recent_sales_count = s.scalar(
            select(func.count(Sale.id))
            .join(Product, Sale.product_id == Product.id)
            .where(
                Sale.sale_date >= recent_from,
                Sale.sale_date <= today,
                Product.name.in_(seed_product_names),
            )
        ) or 0
        if recent_sales_count < TARGET_RECENT_SALES:
            _add_demo_sales(
                session=s,
                products=products,
                stores=stores,
                employees=employees,
                date_from=recent_from,
                date_to=today,
                rows_to_add=TARGET_RECENT_SALES - int(recent_sales_count),
                salt=1000,
            )
            s.flush()

        # -----------------------
        # Engineering team events.
        # -----------------------
        hr_count = s.scalar(select(func.count(HREvent.id))) or 0
        if hr_count < TARGET_HR_EVENTS_TOTAL:
            existing_hr_keys = set(
                s.execute(select(HREvent.employee_name, HREvent.event_type, HREvent.start_date)).all()
            )

            to_add = TARGET_HR_EVENTS_TOTAL - int(hr_count)
            types = [HREventType.hire, HREventType.vacation, HREventType.sick_leave, HREventType.fire]
            notes_by_type = {
                HREventType.hire: "Ввод инженера в проект СВЧ-изделий и допуск к стендам",
                HREventType.vacation: "Плановый отпуск специалиста СВЧ-лаборатории",
                HREventType.sick_leave: "Отсутствие инженера по болезни",
                HREventType.fire: "Вывод специалиста из проектной команды",
            }

            for k in range(240):
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

                s.add(
                    HREvent(
                        employee_name=emp,
                        event_type=et,
                        start_date=start,
                        end_date=end,
                        notes=notes_by_type.get(et, ""),
                    )
                )
                existing_hr_keys.add(key)
                to_add -= 1

        _ensure_recent_engineering_events(s, employees, today, min_recent_events=16)

        # -----------------------
        # Technical documents.
        # -----------------------
        docs_count = s.scalar(select(func.count(HRDocument.id))) or 0
        if docs_count < TARGET_HR_DOCS:
            to_add = TARGET_HR_DOCS - int(docs_count)

            doc_types = [
                "Протокол измерения S-параметров",
                "Карта настройки СВЧ-модуля",
                "Акт входного контроля компонентов",
                "Заключение ЭМС/помехоустойчивости",
                "Паспорт СВЧ-изделия",
                "Журнал калибровки ВНА",
                "Инструкция по работе с СВЧ-стендом",
                "Маршрутная карта сборки модуля",
            ]

            for k in range(240):
                if to_add <= 0:
                    break

                emp = employees[(k * 3) % len(employees)]
                dt = doc_types[k % len(doc_types)]
                status = DocumentStatus.signed if (k % 3 != 0) else DocumentStatus.uploaded

                uploaded_at = now - timedelta(days=(k * 3 + 1))
                signed_at = (uploaded_at + timedelta(days=1)) if status == DocumentStatus.signed else None
                comment = "Подписан ЭП инженером/ОТК" if status == DocumentStatus.signed else "Ожидает проверки ведущим инженером"

                exists = s.scalar(
                    select(func.count(HRDocument.id)).where(
                        HRDocument.employee_name == emp,
                        HRDocument.doc_type == dt,
                        HRDocument.uploaded_at == uploaded_at,
                    )
                )
                if exists and exists > 0:
                    continue

                s.add(
                    HRDocument(
                        employee_name=emp,
                        doc_type=dt,
                        status=status,
                        uploaded_at=uploaded_at,
                        signed_at=signed_at,
                        comment=comment,
                    )
                )
                to_add -= 1
