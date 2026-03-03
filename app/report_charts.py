from __future__ import annotations

"""Генерация статических PNG-графиков для PDF.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as _fm  # noqa: E402


def _setup_ru_fonts() -> None:

    try:
        font_dir = Path(__file__).resolve().parent / "assets" / "fonts"
        regular = font_dir / "DejaVuSans.ttf"
        bold = font_dir / "DejaVuSans-Bold.ttf"
        if regular.exists():
            _fm.fontManager.addfont(str(regular))
        if bold.exists():
            _fm.fontManager.addfont(str(bold))

        matplotlib.rcParams["font.family"] = "DejaVu Sans"
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


_setup_ru_fonts()


def _png_bytes(fig: plt.Figure, dpi: int = 160) -> bytes:
    bio = BytesIO()
    fig.savefig(bio, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return bio.getvalue()


def _empty_plot(title: str) -> bytes:
    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    ax.set_title(title)
    ax.text(0.5, 0.5, "Нет данных", ha="center", va="center", fontsize=12)
    ax.set_axis_off()
    return _png_bytes(fig)


def png_revenue_by_day(sales_df: pd.DataFrame) -> bytes:
    if sales_df.empty:
        return _empty_plot("Выручка по дням")

    by_day = (
        sales_df.groupby("sale_date", as_index=False)["revenue"].sum().sort_values("sale_date")
    )
    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    ax.plot(by_day["sale_date"], by_day["revenue"], marker="o")
    ax.set_title("Выручка по дням")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Выручка")
    fig.autofmt_xdate(rotation=25)
    ax.grid(True, alpha=0.25)
    return _png_bytes(fig)


def png_top_products(sales_df: pd.DataFrame, top_n: int = 10) -> bytes:
    if sales_df.empty:
        return _empty_plot(f"Топ-{top_n} товаров по выручке")

    by_prod = (
        sales_df.groupby("product_name", as_index=False)["revenue"].sum().sort_values("revenue")
    )
    by_prod = by_prod.tail(top_n)

    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ax.barh(by_prod["product_name"], by_prod["revenue"])
    ax.set_title(f"Топ-{top_n} товаров по выручке")
    ax.set_xlabel("Выручка")
    ax.set_ylabel("Товар")
    ax.grid(True, axis="x", alpha=0.25)
    return _png_bytes(fig)


def png_revenue_share_by_category(sales_df: pd.DataFrame, max_categories: int = 8) -> bytes:

    if sales_df.empty:
        return _empty_plot("Доля выручки по категориям")

    by_cat = (
        sales_df.groupby("category", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    if len(by_cat) > max_categories:
        top = by_cat.head(max_categories)
        other_sum = float(by_cat.iloc[max_categories:]["revenue"].sum())
        by_cat = pd.concat(
            [top, pd.DataFrame([{"category": "Прочее", "revenue": other_sum}])],
            ignore_index=True,
        )

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    wedges, texts, autotexts = ax.pie(
        by_cat["revenue"],
        labels=by_cat["category"],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"width": 0.45, "edgecolor": "white"},
    )
    ax.set_title("Доля выручки по категориям")
    ax.axis("equal")
    return _png_bytes(fig)


def png_hr_events_by_month(hr_df: pd.DataFrame) -> bytes:
    if hr_df.empty:
        return _empty_plot("HR события по месяцам")

    df = hr_df.copy()
    df["month"] = pd.to_datetime(df["start_date"]).dt.to_period("M").astype(str)
    pivot = (
        df.pivot_table(index="month", columns="event_type", values="id", aggfunc="count", fill_value=0)
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(7.8, 4.0))
    bottom = None
    for col in pivot.columns:
        if bottom is None:
            ax.bar(pivot.index, pivot[col], label=str(col))
            bottom = pivot[col].values
        else:
            ax.bar(pivot.index, pivot[col], bottom=bottom, label=str(col))
            bottom = bottom + pivot[col].values
    ax.set_title("HR события по месяцам")
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Количество")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate(rotation=25)
    return _png_bytes(fig)


def png_documents_status(doc_df: pd.DataFrame) -> bytes:
    if doc_df.empty:
        return _empty_plot("Статусы документов")

    by = doc_df.groupby("status", as_index=False).size().sort_values("size", ascending=False)
    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    ax.bar(by["status"], by["size"])
    ax.set_title("Статусы документов")
    ax.set_xlabel("Статус")
    ax.set_ylabel("Количество")
    ax.grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate(rotation=15)
    return _png_bytes(fig)


def png_revenue_boxplot_by_store(sales_df: pd.DataFrame, max_stores: int = 8) -> bytes:

    if sales_df.empty:
        return _empty_plot("Распределение дневной выручки по точкам")

    by = (
        sales_df.groupby(["store", "sale_date"], as_index=False)["revenue"]
        .sum()
        .dropna(subset=["store", "sale_date"])
    )
    if by.empty:
        return _empty_plot("Распределение дневной выручки по точкам")

    top_stores = (
        by.groupby("store")["revenue"].sum().sort_values(ascending=False).head(max_stores).index.tolist()
    )
    by = by[by["store"].isin(top_stores)]
    by = by.sort_values("store")

    stores = sorted(by["store"].unique().tolist())
    data = [by.loc[by["store"] == s, "revenue"].astype(float).values for s in stores]

    fig, ax = plt.subplots(figsize=(7.8, 4.0))
    ax.boxplot(
        data,
        labels=stores,
        showmeans=True,
        meanline=True,
    )
    ax.set_title("Распределение дневной выручки по точкам")
    ax.set_xlabel("Точка")
    ax.set_ylabel("Дневная выручка")
    ax.grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate(rotation=20)
    return _png_bytes(fig)


def png_scatter_price_qty(sales_df: pd.DataFrame, max_points: int = 1500) -> bytes:

    if sales_df.empty:
        return _empty_plot("Цена vs Количество")

    df = sales_df.dropna(subset=["unit_price", "qty"]).copy()
    if df.empty:
        return _empty_plot("Цена vs Количество")

    df = df[(df["unit_price"] > 0) & (df["qty"] > 0)]
    if df.empty:
        return _empty_plot("Цена vs Количество")

    if len(df) > max_points:
        df = df.sample(n=max_points, random_state=42)

    fig, ax = plt.subplots(figsize=(7.8, 4.0))
    ax.scatter(df["unit_price"].astype(float), df["qty"].astype(float), alpha=0.55)
    ax.set_title("Цена vs Количество (строки продаж)")
    ax.set_xlabel("Цена за единицу")
    ax.set_ylabel("Количество")
    ax.grid(True, alpha=0.25)
    return _png_bytes(fig)


def png_documents_donut_status(doc_df: pd.DataFrame) -> bytes:

    if doc_df.empty:
        return _empty_plot("Доля статусов документов")

    by = doc_df.groupby("status", as_index=False).size().sort_values("size", ascending=False)
    if by.empty:
        return _empty_plot("Доля статусов документов")

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.pie(
        by["size"],
        labels=by["status"],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"width": 0.45, "edgecolor": "white"},
    )
    ax.set_title("Доля статусов документов")
    ax.axis("equal")
    return _png_bytes(fig)
