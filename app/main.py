from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.logger import setup_logger
from app.db import init_db_and_seed, session_scope
from app.models import Product, Sale, HREvent, HRDocument, HREventType, DocumentStatus
from app.pdf_report import ReportFigure, ReportSection, ReportTable, build_pdf_report
from app.report_charts import (
    png_documents_donut_status,
    png_documents_status,
    png_hr_events_by_month,
    png_revenue_boxplot_by_store,
    png_revenue_by_day,
    png_revenue_share_by_category,
    png_scatter_price_qty,
    png_top_products,
)



# ----------------------------
# UI Theme (palette)
# ----------------------------
PALETTE = {
    "bg": "#222629",          # основной фон
    "surface": "#474B4F",     # карточки/вторичный фон
    "muted": "#6B6E70",       # бордеры/вторичный текст
    "primary": "#86C232",     # основной акцент
    "primary_dark": "#61892F",# ховер/акцент 2
    "text": "#F5F7F7",        # основной текст (для контраста)
    "text_muted": "#D6D7D9",  # вторичный текст
}


def apply_ui_theme() -> None:

    css = f"""
    <style>
      :root {{
        --bg: {PALETTE["bg"]};
        --surface: {PALETTE["surface"]};
        --muted: {PALETTE["muted"]};
        --primary: {PALETTE["primary"]};
        --primary-dark: {PALETTE["primary_dark"]};
        --text: {PALETTE["text"]};
        --text-muted: {PALETTE["text_muted"]};
      }}

      /* Base */
      .stApp {{
        background: var(--bg);
        color: var(--text);
      }}
      h1, h2, h3, h4, h5, h6 {{
        color: var(--text) !important;
      }}
      p, li, label, small, span {{
        color: var(--text) !important;
      }}
      a {{
        color: var(--primary);
      }}

      /* Sidebar */
      section[data-testid="stSidebar"] {{
        background: var(--surface);
        border-right: 1px solid rgba(107, 110, 112, 0.55);
      }}
      section[data-testid="stSidebar"] * {{
        color: var(--text) !important;
      }}
      section[data-testid="stSidebar"] a {{
        color: var(--primary) !important;
      }}

      /* Main container padding */
      div.block-container {{
        padding-top: 1.4rem;
        padding-bottom: 2rem;
      }}

      /* Metrics as cards */
      div[data-testid="stMetric"] {{
        background: rgba(71, 75, 79, 0.75);
        border: 1px solid rgba(107, 110, 112, 0.55);
        border-radius: 16px;
        padding: 12px 14px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.22);
      }}
      div[data-testid="stMetric"] label {{
        color: var(--text-muted) !important;
      }}

      /* Dataframes */
      div[data-testid="stDataFrame"] {{
        border: 1px solid rgba(107, 110, 112, 0.55);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 10px 26px rgba(0,0,0,0.20);
      }}

      /* Inputs / selects */
      .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input {{
        background: rgba(71, 75, 79, 0.55) !important;
        color: var(--text) !important;
        border: 1px solid rgba(107, 110, 112, 0.60) !important;
        border-radius: 12px !important;
      }}
      .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
        color: rgba(214, 215, 217, 0.65) !important;
      }}
      .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus, .stDateInput input:focus {{
        border-color: rgba(134, 194, 50, 0.9) !important;
        box-shadow: 0 0 0 0.20rem rgba(134, 194, 50, 0.22) !important;
      }}

      /* Selectbox dropdown */
      div[data-baseweb="select"] > div {{
        background: rgba(71, 75, 79, 0.55) !important;
        border: 1px solid rgba(107, 110, 112, 0.60) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
      }}

      /* Buttons */
      div.stButton > button {{
        border-radius: 12px;
        font-weight: 700;
      }}
      div.stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {{
        background: var(--primary) !important;
        color: #0B0F0B !important;
        border: 0 !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.22);
      }}
      div.stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {{
        background: var(--primary-dark) !important;
        color: #0B0F0B !important;
      }}
      div.stButton > button[kind="secondary"], button[data-testid="baseButton-secondary"] {{
        background: transparent !important;
        color: var(--text) !important;
        border: 1px solid rgba(107, 110, 112, 0.65) !important;
      }}
      div.stButton > button[kind="secondary"]:hover, button[data-testid="baseButton-secondary"]:hover {{
        border-color: rgba(134, 194, 50, 0.75) !important;
        color: var(--primary) !important;
      }}

      /* Divider */
      hr {{
        border-color: rgba(107, 110, 112, 0.55) !important;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _apply_plotly_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["bg"],
        font=dict(color=PALETTE["text"]),
        title=dict(font=dict(color=PALETTE["text"])),
        legend=dict(font=dict(color=PALETTE["text_muted"])),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(gridcolor="rgba(255, 255, 255, 0.08)", zerolinecolor="rgba(255, 255, 255, 0.12)")
    fig.update_yaxes(gridcolor="rgba(255, 255, 255, 0.08)", zerolinecolor="rgba(255, 255, 255, 0.12)")
    return fig


# ----------------------------
# App bootstrap
# ----------------------------
settings = get_settings()
logger = setup_logger("svch_electronics_app", settings.log_level)

st.set_page_config(
    page_title=settings.app_name,
    layout="wide",
)

apply_ui_theme()

init_db_and_seed()


# ----------------------------
# Helpers (queries -> DataFrames)
# ----------------------------
@st.cache_data(ttl=30)
def load_products_df() -> pd.DataFrame:
    with session_scope() as s:
        rows = s.execute(select(Product).order_by(Product.id)).scalars().all()
        data = [{
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "price": p.price,
            "created_at": p.created_at,
        } for p in rows]
    return pd.DataFrame(data)


@st.cache_data(ttl=30)
def load_sales_df(period_from: date, period_to: date) -> pd.DataFrame:
    with session_scope() as s:
        q = (
            select(Sale)
            .options(joinedload(Sale.product))
            .where(Sale.sale_date >= period_from, Sale.sale_date <= period_to)
            .order_by(Sale.sale_date, Sale.id)
        )
        rows = s.execute(q).scalars().all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "sale_date": r.sale_date,
                "store": r.store,
                "employee_name": r.employee_name,
                "product_id": r.product_id,
                "product_name": r.product.name if r.product else "",
                "category": r.product.category if r.product else "",
                "qty": r.qty,
                "unit_price": r.unit_price,
                "revenue": float(r.qty) * float(r.unit_price),
                "created_at": r.created_at,
            })
    return pd.DataFrame(data)


@st.cache_data(ttl=30)
def load_hr_events_df(period_from: date, period_to: date) -> pd.DataFrame:
    with session_scope() as s:
        q = (
            select(HREvent)
            .where(HREvent.start_date >= period_from, HREvent.start_date <= period_to)
            .order_by(HREvent.start_date, HREvent.id)
        )
        rows = s.execute(q).scalars().all()
        data = [{
            "id": r.id,
            "employee_name": r.employee_name,
            "event_type": r.event_type.value,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "notes": r.notes or "",
            "created_at": r.created_at,
        } for r in rows]
    return pd.DataFrame(data)


@st.cache_data(ttl=30)
def load_documents_df() -> pd.DataFrame:
    with session_scope() as s:
        q = select(HRDocument).order_by(desc(HRDocument.uploaded_at), HRDocument.id)
        rows = s.execute(q).scalars().all()
        data = [{
            "id": r.id,
            "employee_name": r.employee_name,
            "doc_type": r.doc_type,
            "status": r.status.value,
            "uploaded_at": r.uploaded_at,
            "signed_at": r.signed_at,
            "comment": r.comment or "",
        } for r in rows]
    return pd.DataFrame(data)


def invalidate_caches() -> None:
    load_products_df.clear()
    load_sales_df.clear()
    load_hr_events_df.clear()
    load_documents_df.clear()


# ----------------------------
# Plotly figures
# ----------------------------
def fig_revenue_by_day(sales_df: pd.DataFrame) -> go.Figure:
    if sales_df.empty:
        return go.Figure().update_layout(title="Объём работ по дням (нет данных)")

    by_day = sales_df.groupby("sale_date", as_index=False)["revenue"].sum().sort_values("sale_date")
    fig = px.line(by_day, x="sale_date", y="revenue", markers=True, title="Объём работ по дням")
    fig.update_layout(xaxis_title="Дата", yaxis_title="Объём работ, усл. ед.")
    _apply_plotly_theme(fig)
    return fig


def fig_top_products(sales_df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    if sales_df.empty:
        return go.Figure().update_layout(title="Топ СВЧ-компонентов по объёму работ (нет данных)")

    by_prod = (
        sales_df.groupby(["product_name"], as_index=False)["revenue"].sum()
        .sort_values("revenue", ascending=False)
        .head(top_n)
    )
    fig = px.bar(by_prod, x="product_name", y="revenue", title=f"Топ-{top_n} СВЧ-компонентов по объёму работ")
    fig.update_layout(xaxis_title="СВЧ-компонент", yaxis_title="Объём работ, усл. ед.")
    fig.update_xaxes(tickangle=20)
    _apply_plotly_theme(fig)
    return fig


def fig_revenue_share_by_category(sales_df: pd.DataFrame) -> go.Figure:
    if sales_df.empty:
        return go.Figure().update_layout(title="Доля объёма работ по категориям (нет данных)")

    by_cat = sales_df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    fig = px.pie(by_cat, names="category", values="revenue", title="Доля объёма работ по категориям")
    fig.update_traces(hole=0.45)
    _apply_plotly_theme(fig)
    return fig
def fig_hr_events_by_month(hr_df: pd.DataFrame) -> go.Figure:
    if hr_df.empty:
        return go.Figure().update_layout(title="События инженерной команды по месяцам (нет данных)")

    df = hr_df.copy()
    df["month"] = pd.to_datetime(df["start_date"]).dt.to_period("M").astype(str)
    by = df.groupby(["month", "event_type"], as_index=False).size()
    fig = px.bar(by, x="month", y="size", color="event_type", barmode="stack", title="События инженерной команды по месяцам")
    fig.update_layout(xaxis_title="Месяц", yaxis_title="Количество")
    _apply_plotly_theme(fig)
    return fig


def fig_documents_status(doc_df: pd.DataFrame) -> go.Figure:
    if doc_df.empty:
        return go.Figure().update_layout(title="Статусы технических документов (нет данных)")

    by = doc_df.groupby("status", as_index=False).size().sort_values("size", ascending=False)
    fig = px.bar(by, x="status", y="size", title="Статусы технических документов (всего)")
    fig.update_layout(xaxis_title="Статус", yaxis_title="Количество")
    _apply_plotly_theme(fig)
    return fig



def fig_revenue_boxplot_by_store(sales_df: pd.DataFrame, max_stores: int = 8) -> go.Figure:

    if sales_df.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Распределение дневного объёма работ по стендам/участкам (нет данных)"))

    by = (
        sales_df.groupby(["store", "sale_date"], as_index=False)["revenue"].sum()
        .dropna(subset=["store", "sale_date"])
    )
    if by.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Распределение дневного объёма работ по стендам/участкам (нет данных)"))

    top_stores = (
        by.groupby("store")["revenue"].sum().sort_values(ascending=False).head(max_stores).index.tolist()
    )
    by = by[by["store"].isin(top_stores)]
    fig = px.box(by, x="store", y="revenue", points="outliers", title="Распределение дневного объёма работ по стендам/участкам")
    fig.update_layout(xaxis_title="Стенд/участок", yaxis_title="Дневной объём работ")
    fig.update_xaxes(tickangle=15)
    _apply_plotly_theme(fig)
    return fig


def fig_scatter_price_qty(sales_df: pd.DataFrame, max_points: int = 2000) -> go.Figure:

    if sales_df.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Нормо-стоимость vs Количество образцов (нет данных)"))

    df = sales_df.dropna(subset=["unit_price", "qty"]).copy()
    df = df[(df["unit_price"] > 0) & (df["qty"] > 0)]
    if df.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Нормо-стоимость vs Количество образцов (нет данных)"))

    if len(df) > max_points:
        df = df.sample(n=max_points, random_state=42)

    fig = px.scatter(
        df,
        x="unit_price",
        y="qty",
        color="category" if "category" in df.columns else None,
        size="revenue" if "revenue" in df.columns else None,
        hover_data=["product_name", "store", "employee_name"],
        title="Нормо-стоимость vs Количество образцов (строки операций)",
    )
    fig.update_layout(xaxis_title="Нормо-стоимость за единицу", yaxis_title="Количество образцов")
    _apply_plotly_theme(fig)
    return fig


def fig_documents_donut_status(doc_df: pd.DataFrame) -> go.Figure:

    if doc_df.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Доля статусов технических документов (нет данных)"))

    by = doc_df.groupby("status", as_index=False).size().sort_values("size", ascending=False)
    if by.empty:
        return _apply_plotly_theme(go.Figure().update_layout(title="Доля статусов технических документов (нет данных)"))

    fig = px.pie(by, names="status", values="size", title="Доля статусов технических документов")
    fig.update_traces(hole=0.45)
    _apply_plotly_theme(fig)
    return fig


# ----------------------------
# CRUD UI blocks
# ----------------------------
def ui_products():
    st.subheader("Справочник СВЧ-компонентов и изделий")

    df = load_products_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Добавить СВЧ-компонент")
        with st.form("add_product", clear_on_submit=True):
            name = st.text_input("Наименование", value="")
            category = st.text_input("Категория", value="Пассивные СВЧ-компоненты")
            price = st.number_input("Нормо-стоимость (за единицу)", min_value=0.01, value=9.90, step=0.10)
            submitted = st.form_submit_button("Добавить")
            if submitted:
                name = name.strip()
                category = category.strip()
                if not name:
                    st.error("Наименование не может быть пустым.")
                elif not category:
                    st.error("Категория не может быть пустой.")
                else:
                    try:
                        with session_scope() as s:
                            exists = s.scalar(select(func.count(Product.id)).where(Product.name == name))
                            if exists and exists > 0:
                                st.error("СВЧ-компонент с таким наименованием уже существует.")
                            else:
                                s.add(Product(name=name, category=category, price=float(price)))
                        invalidate_caches()
                        st.success("СВЧ-компонент добавлен.")
                    except Exception as e:
                        logger.exception("add_product failed")
                        st.error(f"Ошибка добавления: {e}")

    with col2:
        st.markdown("### Редактировать / удалить СВЧ-компонент")
        if df.empty:
            st.info("Нет компонентов для редактирования.")
            return

        product_id = st.selectbox("Выберите СВЧ-компонент по ID", options=df["id"].tolist(), index=0)
        row = df[df["id"] == product_id].iloc[0]

        with st.form("edit_product"):
            name_e = st.text_input("Наименование", value=str(row["name"]))
            category_e = st.text_input("Категория", value=str(row["category"]))
            price_e = st.number_input("Нормо-стоимость", min_value=0.01, value=float(row["price"]), step=0.10)

            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Сохранить изменения")
            delete = c2.form_submit_button("Удалить компонент")

            if save:
                name_e = name_e.strip()
                category_e = category_e.strip()
                if not name_e:
                    st.error("Наименование не может быть пустым.")
                elif not category_e:
                    st.error("Категория не может быть пустой.")
                else:
                    try:
                        with session_scope() as s:
                            p = s.get(Product, int(product_id))
                            if p is None:
                                st.error("СВЧ-компонент не найден.")
                            else:
                                # контроль уникальности имени
                                if p.name != name_e:
                                    exists = s.scalar(select(func.count(Product.id)).where(Product.name == name_e))
                                    if exists and exists > 0:
                                        st.error("СВЧ-компонент с таким наименованием уже существует.")
                                        return
                                p.name = name_e
                                p.category = category_e
                                p.price = float(price_e)
                        invalidate_caches()
                        st.success("Изменения сохранены.")
                    except Exception as e:
                        logger.exception("edit_product failed")
                        st.error(f"Ошибка сохранения: {e}")

            if delete:
                try:
                    with session_scope() as s:
                        p = s.get(Product, int(product_id))
                        if p is None:
                            st.error("СВЧ-компонент не найден.")
                        else:
                            s.delete(p)
                    invalidate_caches()
                    st.success("СВЧ-компонент удалён (вместе с операциями по нему).")
                except Exception as e:
                    logger.exception("delete_product failed")
                    st.error(f"Ошибка удаления: {e}")


def ui_sales(period_from: date, period_to: date):
    st.subheader("Испытания и поставки")

    products_df = load_products_df()
    if products_df.empty:
        st.warning("Сначала добавьте СВЧ-компоненты или изделия в справочник.")
        return

    df = load_sales_df(period_from, period_to)
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Добавить операцию испытаний/поставки")
        with st.form("add_sale", clear_on_submit=True):
            sale_date = st.date_input("Дата операции", value=period_to)
            store = st.text_input("Стенд/участок", value="Стенд ВНА/S-параметров")
            employee_name = st.text_input("Инженер/специалист", value="Иванов И.И.")

            product_id = st.selectbox(
                "СВЧ-компонент",
                options=products_df["id"].tolist(),
                format_func=lambda pid: f"{pid} — {products_df.loc[products_df['id']==pid, 'name'].iloc[0]}",
            )

            qty = st.number_input("Количество образцов", min_value=1, value=1, step=1)

            base_price = float(products_df.loc[products_df["id"] == product_id, "price"].iloc[0])
            unit_price = st.number_input("Нормо-стоимость за единицу", min_value=0.01, value=base_price, step=0.10)

            submitted = st.form_submit_button("Добавить")
            if submitted:
                store = store.strip()
                employee_name = employee_name.strip()
                if not store:
                    st.error("Поле 'Стенд/участок' не может быть пустым.")
                elif not employee_name:
                    st.error("Поле 'Инженер/специалист' не может быть пустым.")
                else:
                    try:
                        with session_scope() as s:
                            s.add(Sale(
                                sale_date=sale_date,
                                product_id=int(product_id),
                                qty=int(qty),
                                unit_price=float(unit_price),
                                store=store,
                                employee_name=employee_name,
                            ))
                        invalidate_caches()
                        st.success("Операция испытаний/поставки добавлена.")
                    except Exception as e:
                        logger.exception("add_sale failed")
                        st.error(f"Ошибка добавления: {e}")

    with col2:
        st.markdown("### Редактировать / удалить операцию")
        if df.empty:
            st.info("Нет операций испытаний/поставок в выбранном периоде.")
            return

        sale_id = st.selectbox("Выберите операцию испытаний/поставки по ID", options=df["id"].tolist(), index=0)
        row = df[df["id"] == sale_id].iloc[0]

        with st.form("edit_sale"):
            sale_date_e = st.date_input("Дата операции", value=row["sale_date"])
            store_e = st.text_input("Стенд/участок", value=str(row["store"]))
            employee_e = st.text_input("Инженер/специалист", value=str(row["employee_name"]))

            product_id_e = st.selectbox(
                "СВЧ-компонент",
                options=products_df["id"].tolist(),
                index=products_df["id"].tolist().index(int(row["product_id"])),
                format_func=lambda pid: f"{pid} — {products_df.loc[products_df['id']==pid, 'name'].iloc[0]}",
            )
            qty_e = st.number_input("Количество образцов", min_value=1, value=int(row["qty"]), step=1)
            unit_price_e = st.number_input("Нормо-стоимость за единицу", min_value=0.01, value=float(row["unit_price"]), step=0.10)

            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Сохранить изменения")
            delete = c2.form_submit_button("Удалить операцию")

            if save:
                store_e = store_e.strip()
                employee_e = employee_e.strip()
                if not store_e:
                    st.error("Поле 'Стенд/участок' не может быть пустым.")
                elif not employee_e:
                    st.error("Поле 'Инженер/специалист' не может быть пустым.")
                else:
                    try:
                        with session_scope() as s:
                            r = s.get(Sale, int(sale_id))
                            if r is None:
                                st.error("Операция испытаний/поставки не найдена.")
                            else:
                                r.sale_date = sale_date_e
                                r.store = store_e
                                r.employee_name = employee_e
                                r.product_id = int(product_id_e)
                                r.qty = int(qty_e)
                                r.unit_price = float(unit_price_e)
                        invalidate_caches()
                        st.success("Изменения сохранены.")
                    except Exception as e:
                        logger.exception("edit_sale failed")
                        st.error(f"Ошибка сохранения: {e}")

            if delete:
                try:
                    with session_scope() as s:
                        r = s.get(Sale, int(sale_id))
                        if r is None:
                            st.error("Операция испытаний/поставки не найдена.")
                        else:
                            s.delete(r)
                    invalidate_caches()
                    st.success("Операция испытаний/поставки удалена.")
                except Exception as e:
                    logger.exception("delete_sale failed")
                    st.error(f"Ошибка удаления: {e}")


def ui_hr_events(period_from: date, period_to: date):
    st.subheader("События команды")

    df = load_hr_events_df(period_from, period_to)
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Добавить событие команды")
        with st.form("add_hr_event", clear_on_submit=True):
            employee = st.text_input("Инженер/специалист", value="Иванов И.И.")
            event_type = st.selectbox("Тип события", options=[e.value for e in HREventType], index=2)
            start = st.date_input("Дата начала", value=period_to)
            end = st.date_input("Дата окончания (если применимо)", value=period_to)
            notes = st.text_area("Комментарий", value="")

            submitted = st.form_submit_button("Добавить")
            if submitted:
                employee = employee.strip()
                notes = notes.strip()
                if not employee:
                    st.error("Инженер/специалист не может быть пустым.")
                else:
                    end_value: Optional[date] = None if end == start and event_type in ("Найм", "Увольнение") else end
                    try:
                        with session_scope() as s:
                            enum_val = next(x for x in HREventType if x.value == event_type)
                            s.add(HREvent(
                                employee_name=employee,
                                event_type=enum_val,
                                start_date=start,
                                end_date=end_value,
                                notes=notes if notes else None,
                            ))
                        invalidate_caches()
                        st.success("Событие команды добавлено.")
                    except Exception as e:
                        logger.exception("add_hr_event failed")
                        st.error(f"Ошибка добавления: {e}")

    with col2:
        st.markdown("### Редактировать / удалить событие команды")
        if df.empty:
            st.info("Нет событий команды в выбранном периоде.")
            return

        event_id = st.selectbox("Выберите событие по ID", options=df["id"].tolist(), index=0)
        row = df[df["id"] == event_id].iloc[0]

        with st.form("edit_hr_event"):
            employee_e = st.text_input("Инженер/специалист", value=str(row["employee_name"]))
            event_type_e = st.selectbox(
                "Тип события",
                options=[e.value for e in HREventType],
                index=[e.value for e in HREventType].index(str(row["event_type"])),
            )
            start_e = st.date_input("Дата начала", value=row["start_date"])
            # если end отсутствует, ставим start как “нейтральное” значение
            end_base = row["end_date"] if pd.notna(row["end_date"]) else row["start_date"]
            end_e = st.date_input("Дата окончания", value=end_base)
            notes_e = st.text_area("Комментарий", value=str(row["notes"]))

            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Сохранить изменения")
            delete = c2.form_submit_button("Удалить событие")

            if save:
                employee_e = employee_e.strip()
                notes_e = notes_e.strip()
                if not employee_e:
                    st.error("Инженер/специалист не может быть пустым.")
                else:
                    end_value: Optional[date] = None if (end_e == start_e and event_type_e in ("Найм", "Увольнение")) else end_e
                    try:
                        with session_scope() as s:
                            r = s.get(HREvent, int(event_id))
                            if r is None:
                                st.error("Событие не найдено.")
                            else:
                                r.employee_name = employee_e
                                r.event_type = next(x for x in HREventType if x.value == event_type_e)
                                r.start_date = start_e
                                r.end_date = end_value
                                r.notes = notes_e if notes_e else None
                        invalidate_caches()
                        st.success("Изменения сохранены.")
                    except Exception as e:
                        logger.exception("edit_hr_event failed")
                        st.error(f"Ошибка сохранения: {e}")

            if delete:
                try:
                    with session_scope() as s:
                        r = s.get(HREvent, int(event_id))
                        if r is None:
                            st.error("Событие не найдено.")
                        else:
                            s.delete(r)
                    invalidate_caches()
                    st.success("Событие удалено.")
                except Exception as e:
                    logger.exception("delete_hr_event failed")
                    st.error(f"Ошибка удаления: {e}")


def ui_documents():
    st.subheader("Технические документы — регистрация/подписание (статусы)")

    df = load_documents_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Добавить документ")
        with st.form("add_doc", clear_on_submit=True):
            employee = st.text_input("Инженер/специалист", value="Петров П.П.")
            doc_type = st.text_input("Тип технического документа", value="Протокол измерения S-параметров")
            status = st.selectbox("Статус", options=[s.value for s in DocumentStatus], index=0)
            comment = st.text_area("Комментарий", value="")

            submitted = st.form_submit_button("Добавить")
            if submitted:
                employee = employee.strip()
                doc_type = doc_type.strip()
                comment = comment.strip()
                if not employee:
                    st.error("Инженер/специалист не может быть пустым.")
                elif not doc_type:
                    st.error("Тип технического документа не может быть пустым.")
                else:
                    try:
                        with session_scope() as s:
                            enum_status = next(x for x in DocumentStatus if x.value == status)
                            signed_at = datetime.utcnow() if enum_status == DocumentStatus.signed else None
                            s.add(HRDocument(
                                employee_name=employee,
                                doc_type=doc_type,
                                status=enum_status,
                                uploaded_at=datetime.utcnow(),
                                signed_at=signed_at,
                                comment=comment if comment else None,
                            ))
                        invalidate_caches()
                        st.success("Документ добавлен.")
                    except Exception as e:
                        logger.exception("add_doc failed")
                        st.error(f"Ошибка добавления: {e}")

    with col2:
        st.markdown("### Редактировать / удалить документ")
        if df.empty:
            st.info("Нет документов.")
            return

        doc_id = st.selectbox("Выберите документ по ID", options=df["id"].tolist(), index=0)
        row = df[df["id"] == doc_id].iloc[0]

        with st.form("edit_doc"):
            employee_e = st.text_input("Инженер/специалист", value=str(row["employee_name"]))
            doc_type_e = st.text_input("Тип технического документа", value=str(row["doc_type"]))
            status_e = st.selectbox(
                "Статус",
                options=[s.value for s in DocumentStatus],
                index=[s.value for s in DocumentStatus].index(str(row["status"])),
            )
            comment_e = st.text_area("Комментарий", value=str(row["comment"]))

            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Сохранить изменения")
            delete = c2.form_submit_button("Удалить документ")

            if save:
                employee_e = employee_e.strip()
                doc_type_e = doc_type_e.strip()
                comment_e = comment_e.strip()
                if not employee_e:
                    st.error("Инженер/специалист не может быть пустым.")
                elif not doc_type_e:
                    st.error("Тип технического документа не может быть пустым.")
                else:
                    try:
                        with session_scope() as s:
                            r = s.get(HRDocument, int(doc_id))
                            if r is None:
                                st.error("Документ не найден.")
                            else:
                                enum_status = next(x for x in DocumentStatus if x.value == status_e)
                                r.employee_name = employee_e
                                r.doc_type = doc_type_e
                                # если переводим в signed — выставляем signed_at при отсутствии
                                if enum_status == DocumentStatus.signed and r.signed_at is None:
                                    r.signed_at = datetime.utcnow()
                                if enum_status == DocumentStatus.uploaded:
                                    r.signed_at = None
                                r.status = enum_status
                                r.comment = comment_e if comment_e else None
                        invalidate_caches()
                        st.success("Изменения сохранены.")
                    except Exception as e:
                        logger.exception("edit_doc failed")
                        st.error(f"Ошибка сохранения: {e}")

            if delete:
                try:
                    with session_scope() as s:
                        r = s.get(HRDocument, int(doc_id))
                        if r is None:
                            st.error("Документ не найден.")
                        else:
                            s.delete(r)
                    invalidate_caches()
                    st.success("Документ удалён.")
                except Exception as e:
                    logger.exception("delete_doc failed")
                    st.error(f"Ошибка удаления: {e}")


# ----------------------------
# Dashboard page
# ----------------------------
def ui_dashboard(period_from: date, period_to: date):
    st.subheader("Дашборд: СВЧ-компоненты + испытания + технические документы")

    sales_df = load_sales_df(period_from, period_to)
    hr_df = load_hr_events_df(period_from, period_to)
    doc_df = load_documents_df()

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    revenue = float(sales_df["revenue"].sum()) if not sales_df.empty else 0.0
    orders = int(len(sales_df)) if not sales_df.empty else 0
    hr_events = int(len(hr_df)) if not hr_df.empty else 0
    docs_signed = int((doc_df["status"] == DocumentStatus.signed.value).sum()) if not doc_df.empty else 0

    k1.metric("Объём работ, усл. ед.", f"{revenue:,.2f}".replace(",", " "))
    k2.metric("Кол-во операций", f"{orders}")
    k3.metric("Событий команды в периоде", f"{hr_events}")
    k4.metric("Подписанных техдокументов", f"{docs_signed}")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_revenue_by_day(sales_df), use_container_width=True)
    with c2:
        st.plotly_chart(fig_top_products(sales_df, top_n=10), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(fig_revenue_share_by_category(sales_df), use_container_width=True)
    with c4:
        st.plotly_chart(fig_hr_events_by_month(hr_df), use_container_width=True)

    st.plotly_chart(fig_documents_status(doc_df), use_container_width=True)

    with st.expander("Дополнительная аналитика", expanded=False):
        a1, a2 = st.columns(2)
        with a1:
            st.plotly_chart(fig_revenue_boxplot_by_store(sales_df), use_container_width=True)
        with a2:
            st.plotly_chart(fig_scatter_price_qty(sales_df), use_container_width=True)

        st.plotly_chart(fig_documents_donut_status(doc_df), use_container_width=True)


# ----------------------------
# PDF export page
# ----------------------------
def ui_pdf_export(period_from: date, period_to: date):
    st.subheader("Выгрузка отчёта в PDF (аналитика + графики)")

    sales_df = load_sales_df(period_from, period_to)
    hr_df = load_hr_events_df(period_from, period_to)
    doc_df = load_documents_df()

    png1 = png_revenue_by_day(sales_df)
    png2 = png_top_products(sales_df, top_n=10)
    png3 = png_revenue_share_by_category(sales_df)
    png4 = png_hr_events_by_month(hr_df)
    png5 = png_documents_status(doc_df)
    png6 = png_revenue_boxplot_by_store(sales_df)
    png7 = png_scatter_price_qty(sales_df)
    png8 = png_documents_donut_status(doc_df)

    # ----------------------------
    # Test/supply operations analytics
    # ----------------------------
    revenue = float(sales_df["revenue"].sum()) if not sales_df.empty else 0.0
    orders = int(len(sales_df)) if not sales_df.empty else 0
    avg_ticket = (revenue / orders) if orders else 0.0

    by_day = sales_df.groupby("sale_date", as_index=False)["revenue"].sum() if not sales_df.empty else pd.DataFrame()
    avg_daily = float(by_day["revenue"].mean()) if not by_day.empty else 0.0
    best_day = None
    worst_day = None
    if not by_day.empty:
        best = by_day.loc[by_day["revenue"].idxmax()]
        best_day = (str(best["sale_date"]), float(best["revenue"]))
        nonzero = by_day[by_day["revenue"] > 0]
        if not nonzero.empty:
            worst = nonzero.loc[nonzero["revenue"].idxmin()]
            worst_day = (str(worst["sale_date"]), float(worst["revenue"]))

    fig1_desc_parts = [
        "Описание: график показывает динамику суммарного объёма работ по дням за выбранный период.<br/>",
    ]
    if by_day.empty:
        fig1_desc_parts.append("&bull; Операций в периоде нет — динамика не рассчитывается.<br/>")
    else:
        days_with_sales = int(len(by_day))
        fig1_desc_parts.append(f"&bull; Дней с зафиксированным объёмом работ: <b>{days_with_sales}</b><br/>")
        if best_day is not None:
            fig1_desc_parts.append(
                f"&bull; Пик: <b>{best_day[0]}</b> — {best_day[1]:,.2f}<br/>".replace(",", " ")
            )
        if worst_day is not None:
            fig1_desc_parts.append(
                f"&bull; Минимум (ненулевой): <b>{worst_day[0]}</b> — {worst_day[1]:,.2f}<br/>".replace(",", " ")
            )
        if days_with_sales >= 2 and float(by_day.iloc[0]["revenue"]) != 0:
            first = float(by_day.iloc[0]["revenue"])
            last = float(by_day.iloc[-1]["revenue"])
            delta_pct = (last / first - 1.0) * 100.0
            fig1_desc_parts.append(
                f"&bull; Сдвиг от первого к последнему дню: <b>{delta_pct:+.1f}%</b><br/>"
            )
        mean_rev = float(by_day["revenue"].mean()) if days_with_sales else 0.0
        std_rev = float(by_day["revenue"].std(ddof=0)) if days_with_sales else 0.0
        if mean_rev > 0:
            cv = std_rev / mean_rev
            fig1_desc_parts.append(f"&bull; Волатильность (σ/μ): <b>{cv:.2f}</b><br/>")
    fig1_desc = "".join(fig1_desc_parts)

    top_prod_rows = [["СВЧ-компонент", "Объём работ, усл. ед.", "Доля"], ["—", "—", "—"]]
    top_cat_rows = [["Категория", "Объём работ, усл. ед.", "Доля"], ["—", "—", "—"]]
    store_rows = [["Стенд/участок", "Объём работ, усл. ед.", "Доля"], ["—", "—", "—"]]

    if not sales_df.empty and revenue > 0:
        by_prod = (
            sales_df.groupby("product_name", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        )
        by_cat = (
            sales_df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        )
        by_store = (
            sales_df.groupby("store", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        )

        top_prod_rows = [["СВЧ-компонент", "Объём работ, усл. ед.", "Доля"]]
        for _, r in by_prod.head(5).iterrows():
            share = float(r["revenue"]) / revenue * 100.0
            top_prod_rows.append([
                str(r["product_name"]),
                f"{float(r['revenue']):,.2f}".replace(",", " "),
                f"{share:.1f}%",
            ])

        top_cat_rows = [["Категория", "Объём работ, усл. ед.", "Доля"]]
        for _, r in by_cat.head(5).iterrows():
            share = float(r["revenue"]) / revenue * 100.0
            top_cat_rows.append([
                str(r["category"]),
                f"{float(r['revenue']):,.2f}".replace(",", " "),
                f"{share:.1f}%",
            ])

        store_rows = [["Стенд/участок", "Объём работ, усл. ед.", "Доля"]]
        for _, r in by_store.iterrows():
            share = float(r["revenue"]) / revenue * 100.0
            store_rows.append([
                str(r["store"]),
                f"{float(r['revenue']):,.2f}".replace(",", " "),
                f"{share:.1f}%",
            ])

    fig2_desc_parts = [
        "Описание: горизонтальная диаграмма сравнивает вклад СВЧ-компонентов в общий объём работ (топ по сумме).<br/>",
    ]
    if sales_df.empty or revenue <= 0:
        fig2_desc_parts.append("&bull; Недостаточно данных для ранжирования компонентов.<br/>")
    else:
        by_prod_full = sales_df.groupby("product_name", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        top3 = by_prod_full.head(3)
        top3_share = float(top3["revenue"].sum()) / revenue * 100.0 if not top3.empty else 0.0
        if not top3.empty:
            items = []
            for _, r in top3.iterrows():
                sh = float(r["revenue"]) / revenue * 100.0
                items.append(f"{str(r['product_name'])}: <b>{sh:.1f}%</b>")
            fig2_desc_parts.append("&bull; Топ-3 по доле объёма работ: " + ", ".join(items) + "<br/>")
            fig2_desc_parts.append(f"&bull; Совокупная доля топ-3: <b>{top3_share:.1f}%</b><br/>")
    fig2_desc = "".join(fig2_desc_parts)

    fig3_desc_parts = [
        "Описание: круговая диаграмма показывает структуру объёма работ по категориям СВЧ-компонентов.<br/>",
    ]
    if sales_df.empty or revenue <= 0:
        fig3_desc_parts.append("&bull; Нет данных для расчёта долей по категориям.<br/>")
    else:
        by_cat_full = sales_df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        if not by_cat_full.empty:
            top_cat = by_cat_full.iloc[0]
            top_share = float(top_cat["revenue"]) / revenue * 100.0
            fig3_desc_parts.append(
                f"&bull; Лидер: <b>{str(top_cat['category'])}</b> — доля <b>{top_share:.1f}%</b><br/>"
            )
            hh = by_cat_full.head(3)
            top3_share_cat = float(hh["revenue"].sum()) / revenue * 100.0 if not hh.empty else 0.0
            fig3_desc_parts.append(f"&bull; Доля топ-3 категорий: <b>{top3_share_cat:.1f}%</b><br/>")
    fig3_desc = "".join(fig3_desc_parts)

    fig6_desc_parts = [
        "Описание: боксплот показывает распределение дневного объёма работ по стендам/участкам (медиана, разброс и выбросы).<br/>",
    ]
    by_store_day = (
        sales_df.groupby(["store", "sale_date"], as_index=False)["revenue"].sum()
        if not sales_df.empty
        else pd.DataFrame()
    )
    if by_store_day.empty:
        fig6_desc_parts.append("&bull; Недостаточно данных, чтобы построить распределения по стендам/участкам.<br/>")
    else:
        med = by_store_day.groupby("store")["revenue"].median().sort_values(ascending=False)
        if not med.empty:
            best_store = str(med.index[0])
            fig6_desc_parts.append(f"&bull; Максимальный медианный дневной объём работ: <b>{best_store}</b><br/>")
        # Вариативность по IQR
        iqr = by_store_day.groupby("store")["revenue"].quantile(0.75) - by_store_day.groupby("store")["revenue"].quantile(0.25)
        iqr = iqr.sort_values(ascending=False)
        if not iqr.empty:
            var_store = str(iqr.index[0])
            fig6_desc_parts.append(f"&bull; Наибольший разброс (IQR): <b>{var_store}</b><br/>")
        fig6_desc_parts.append(f"&bull; Стендов/участков в графике: <b>{by_store_day['store'].nunique()}</b><br/>")
        fig6_desc_parts.append(f"&bull; Дней (стенд×день) в выборке: <b>{len(by_store_day)}</b><br/>")
    fig6_desc = "".join(fig6_desc_parts)

    fig7_desc_parts = [
        "Описание: диаграмма рассеивания показывает связь между нормо-стоимостью единицы и количеством образцов в строках операций (размер точки ~ объёму работ).<br/>",
    ]
    sc = sales_df.dropna(subset=["unit_price", "qty"]).copy() if not sales_df.empty else pd.DataFrame()
    if sc.empty:
        fig7_desc_parts.append("&bull; Недостаточно данных для оценки связи нормо-стоимости и количества.<br/>")
    else:
        sc = sc[(sc["unit_price"] > 0) & (sc["qty"] > 0)]
        if len(sc) < 2:
            fig7_desc_parts.append("&bull; Слишком мало точек для расчёта корреляции.<br/>")
        else:
            corr = float(sc["unit_price"].corr(sc["qty"]))
            fig7_desc_parts.append(f"&bull; Корреляция (нормо-стоимость ↔ количество): <b>{corr:+.2f}</b><br/>")
        if "revenue" in sc.columns and not sc["revenue"].isna().all():
            top = sc.loc[sc["revenue"].idxmax()]
            fig7_desc_parts.append(
                ("&bull; Максимальный объём работ в одной строке: "
                 f"<b>{float(top['revenue']):,.2f}</b> — {top.get('product_name','')} (стенд/участок: {top.get('store','')})<br/>")
                .replace(",", " ")
            )
        fig7_desc_parts.append(f"&bull; Точек на графике: <b>{len(sc)}</b><br/>")
    fig7_desc = "".join(fig7_desc_parts)

    desc_sales_parts = [
        "Ключевые выводы:<br/>",
        f"&bull; Итоговый объём работ: <b>{revenue:,.2f}</b><br/>".replace(",", " "),
        f"&bull; Кол-во операций (строк): <b>{orders}</b><br/>",
        f"&bull; Средняя стоимость операции: <b>{avg_ticket:,.2f}</b><br/>".replace(",", " "),
        f"&bull; Средний дневной объём работ: <b>{avg_daily:,.2f}</b><br/>".replace(",", " "),
    ]
    if best_day is not None:
        desc_sales_parts.append(
            f"&bull; Лучший день: <b>{best_day[0]}</b> — {best_day[1]:,.2f}<br/>".replace(",", " ")
        )
    if worst_day is not None:
        desc_sales_parts.append(
            f"&bull; Минимальный (ненулевой) день: <b>{worst_day[0]}</b> — {worst_day[1]:,.2f}<br/>".replace(",", " ")
        )
    desc_sales = "".join(desc_sales_parts)

    # ----------------------------
    # Engineering team analytics
    # ----------------------------
    hr_total = int(len(hr_df)) if not hr_df.empty else 0
    hr_employees = int(hr_df["employee_name"].nunique()) if not hr_df.empty else 0
    hr_counts = hr_df["event_type"].value_counts().to_dict() if not hr_df.empty else {}

    hr_days_vac = 0
    hr_days_sick = 0
    if not hr_df.empty:
        tmp = hr_df.copy()
        tmp["end"] = pd.to_datetime(tmp["end_date"], errors="coerce").fillna(pd.to_datetime(tmp["start_date"]))
        tmp["start"] = pd.to_datetime(tmp["start_date"], errors="coerce")
        tmp["days"] = (tmp["end"] - tmp["start"]).dt.days.clip(lower=0) + 1
        hr_days_vac = int(tmp.loc[tmp["event_type"] == HREventType.vacation.value, "days"].sum())
        hr_days_sick = int(tmp.loc[tmp["event_type"] == HREventType.sick_leave.value, "days"].sum())

    fig4_desc_parts = [
        "Описание: столбцы отражают количество событий команды по месяцам с разбиением по типам.<br/>",
    ]
    if hr_df.empty:
        fig4_desc_parts.append("&bull; Событий команды в периоде нет.<br/>")
    else:
        tmpm = hr_df.copy()
        tmpm["month"] = pd.to_datetime(tmpm["start_date"]).dt.to_period("M").astype(str)
        by_m = tmpm.groupby("month", as_index=False).size().sort_values("size", ascending=False)
        if not by_m.empty:
            best_m = by_m.iloc[0]
            fig4_desc_parts.append(f"&bull; Максимум событий: <b>{str(best_m['month'])}</b> — <b>{int(best_m['size'])}</b><br/>")
        if hr_counts:
            top_type = max(hr_counts.items(), key=lambda kv: kv[1])
            fig4_desc_parts.append(f"&bull; Наиболее частый тип: <b>{top_type[0]}</b> — <b>{int(top_type[1])}</b><br/>")
        fig4_desc_parts.append(f"&bull; Дни отпуска/больничных: <b>{hr_days_vac}</b>/<b>{hr_days_sick}</b><br/>")
    fig4_desc = "".join(fig4_desc_parts)

    desc_hr_parts = [
        "Ключевые выводы:<br/>",
        f"&bull; Событий в периоде: <b>{hr_total}</b><br/>",
        f"&bull; Затронуто инженеров/специалистов: <b>{hr_employees}</b><br/>",
    ]
    if hr_counts:
        desc_hr_parts.append(
            "&bull; Разбивка по типам: "
            + ", ".join([f"{k}: <b>{v}</b>" for k, v in hr_counts.items()])
            + "<br/>"
        )
    desc_hr_parts.append(f"&bull; Суммарные дни отпуска: <b>{hr_days_vac}</b><br/>")
    desc_hr_parts.append(f"&bull; Суммарные дни больничных: <b>{hr_days_sick}</b><br/>")
    desc_hr = "".join(desc_hr_parts)

    # ----------------------------
    # Technical documents analytics
    # ----------------------------
    doc_total = int(len(doc_df)) if not doc_df.empty else 0
    doc_signed = int((doc_df["status"] == DocumentStatus.signed.value).sum()) if not doc_df.empty else 0
    sign_rate = (doc_signed / doc_total * 100.0) if doc_total else 0.0
    doc_counts = doc_df["status"].value_counts().to_dict() if not doc_df.empty else {}

    avg_sign_hours = None
    pending_over_7d = 0
    if not doc_df.empty:
        df = doc_df.copy()
        df["uploaded_at"] = pd.to_datetime(df["uploaded_at"], errors="coerce", utc=True)
        df["signed_at"] = pd.to_datetime(df["signed_at"], errors="coerce", utc=True)
        signed = df[df["status"] == DocumentStatus.signed.value].dropna(subset=["signed_at", "uploaded_at"])
        if not signed.empty:
            delta_h = (signed["signed_at"] - signed["uploaded_at"]).dt.total_seconds() / 3600.0
            avg_sign_hours = float(delta_h.mean())

        now = pd.Timestamp.now(tz="UTC")
        pending = df[df["status"] != DocumentStatus.signed.value].dropna(subset=["uploaded_at"])
        if not pending.empty:
            pending_over_7d = int(((now - pending["uploaded_at"]) > pd.Timedelta(days=7)).fillna(False).sum())

    fig5_desc_parts = [
        "Описание: диаграмма показывает распределение технических документов по статусам на момент формирования отчёта.<br/>",
    ]
    if doc_total == 0:
        fig5_desc_parts.append("&bull; Технических документов нет — распределение не рассчитывается.<br/>")
    else:
        fig5_desc_parts.append(f"&bull; Подписано: <b>{doc_signed}</b> из <b>{doc_total}</b> (доля <b>{sign_rate:.1f}%</b>)<br/>")
        if doc_counts:
            top_status = max(doc_counts.items(), key=lambda kv: kv[1])
            fig5_desc_parts.append(f"&bull; Доминирующий статус: <b>{top_status[0]}</b> — <b>{int(top_status[1])}</b><br/>")
        fig5_desc_parts.append(f"&bull; В ожидании более 7 дней: <b>{pending_over_7d}</b><br/>")
        if avg_sign_hours is not None:
            fig5_desc_parts.append(f"&bull; Среднее время до подписи: <b>{avg_sign_hours:.1f} ч</b><br/>")
    fig5_desc = "".join(fig5_desc_parts)

    fig8_desc_parts = [
        "Описание: пончиковая диаграмма показывает доли документов по статусам (в процентах от общего числа).<br/>",
        f"&bull; Технических документов всего: <b>{doc_total}</b><br/>",
        f"&bull; Подписано: <b>{doc_signed}</b> (доля <b>{sign_rate:.1f}%</b>)<br/>",
    ]
    if doc_counts:
        top_status = max(doc_counts.items(), key=lambda kv: kv[1])
        fig8_desc_parts.append(f"&bull; Доминирующий статус: <b>{top_status[0]}</b> — <b>{int(top_status[1])}</b><br/>")
    fig8_desc = "".join(fig8_desc_parts)

    desc_docs_parts = [
        "Ключевые выводы:<br/>",
        f"&bull; Технических документов всего: <b>{doc_total}</b><br/>",
        f"&bull; Подписано: <b>{doc_signed}</b> (доля <b>{sign_rate:.1f}%</b>)<br/>",
    ]
    if doc_counts:
        desc_docs_parts.append(
            "&bull; Разбивка по статусам: "
            + ", ".join([f"{k}: <b>{v}</b>" for k, v in doc_counts.items()])
            + "<br/>"
        )
    if avg_sign_hours is not None:
        desc_docs_parts.append(f"&bull; Среднее время до подписи: <b>{avg_sign_hours:.1f} ч</b><br/>")
    desc_docs_parts.append(f"&bull; В ожидании более 7 дней: <b>{pending_over_7d}</b><br/>")
    desc_docs = "".join(desc_docs_parts)

    sections = [
        ReportSection(
            title="Испытания и поставки СВЧ-компонентов",
            description=desc_sales,
            tables=[
                ReportTable(caption="Топ-5 СВЧ-компонентов по объёму работ", rows=top_prod_rows),
                ReportTable(caption="Топ-5 категорий по объёму работ", rows=top_cat_rows),
                ReportTable(caption="Объём работ, усл. ед. по стендам/участкам", rows=store_rows),
            ],
            figures=[
                ReportFigure(caption="Объём работ по дням.", png_bytes=png1, description=fig1_desc),
                ReportFigure(caption="Топ СВЧ-компонентов по объёму работ.", png_bytes=png2, description=fig2_desc),
                ReportFigure(caption="Доля объёма работ по категориям (пончиковая).", png_bytes=png3, description=fig3_desc),
                ReportFigure(caption="Распределение дневного объёма работ по стендам/участкам (боксплот).", png_bytes=png6, description=fig6_desc),
                ReportFigure(caption="Нормо-стоимость vs Количество образцов (диаграмма рассеивания).", png_bytes=png7, description=fig7_desc),
            ],
        ),
        ReportSection(
            title="События инженерной команды",
            description=desc_hr,
            figures=[
                ReportFigure(caption="События инженерной команды по месяцам.", png_bytes=png4, description=fig4_desc),
            ],
        ),
        ReportSection(
            title="Технические документы (регистрация/подписание)",
            description=desc_docs,
            figures=[
                ReportFigure(caption="Доля статусов технических документов (пончиковая).", png_bytes=png8, description=fig8_desc),
                ReportFigure(caption="Статусы технических документов (в абсолютных значениях).", png_bytes=png5, description=fig5_desc),
            ],
        ),
    ]

    if st.button("Сформировать PDF", type="primary"):
        try:
            pdf_bytes = build_pdf_report(
                app_title=settings.app_name,
                period_from=period_from,
                period_to=period_to,
                sections=sections,
                generated_at=datetime.utcnow(),
            )
            st.success("PDF сформирован.")
            st.download_button(
                label="Скачать отчёт PDF",
                data=pdf_bytes,
                file_name=f"report_{period_from.isoformat()}_{period_to.isoformat()}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            logger.exception("pdf generation failed")
            st.error(f"Ошибка формирования PDF: {e}")

# ----------------------------
# Main navigation
# ----------------------------
st.title(settings.app_name)

with st.sidebar:
    st.header("Навигация")
    page = st.radio(
        "Раздел",
        options=[
            "Дашборд",
            "СВЧ-компоненты",
            "Испытания и поставки",
            "События команды",
            "Документы",
            "PDF отчёт",
        ],
        index=0,
    )

    st.divider()
    st.subheader("Период анализа")
    default_to = date.today()
    default_from = default_to - timedelta(days=30)
    period_from = st.date_input("С", value=default_from)
    period_to = st.date_input("По", value=default_to)

    if period_from > period_to:
        st.error("Некорректный период: дата 'С' больше даты 'По'.")


if period_from <= period_to:
    if page == "Дашборд":
        ui_dashboard(period_from, period_to)
    elif page == "СВЧ-компоненты":
        ui_products()
    elif page == "Испытания и поставки":
        ui_sales(period_from, period_to)
    elif page == "События команды":
        ui_hr_events(period_from, period_to)
    elif page == "Документы":
        ui_documents()
    elif page == "PDF отчёт":
        ui_pdf_export(period_from, period_to)
else:
    st.stop()