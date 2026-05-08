from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Any

from django.conf import settings
from django.http import Http404


HIDDEN_TABLES = {"reuse_notes"}

STUDY_TABLE_ORDER = [
    "exam_intents",
    "paragraph_roles",
    "logic_relations",
    "grammar_items",
    "vocab_keywords",
    "vocab_collocations",
]

TABLE_LABELS = {
    "passages": "入試英文",
    "exam_intents": "出題意図",
    "paragraph_roles": "段落構成",
    "logic_relations": "論理関係",
    "grammar_items": "文法分析",
    "vocab_keywords": "重要語彙",
    "vocab_collocations": "語句・コロケーション",
}

COLUMN_LABELS = {
    "id": "ID",
    "passage_id": "英文ID",
    "source_exam": "大学入試名",
    "year": "年度",
    "level_tag": "レベル",
    "topic": "テーマ",
    "text_type": "英文タイプ",
    "word_count": "語数",
    "meta_json": "メタ情報",
    "passage_en": "英文",
    "passage_jp": "日本語訳",
    "why_this_text": "出題意図",
    "likely_types_json": "想定設問",
    "p_index": "段落",
    "role": "役割",
    "summary_en": "要約（英語）",
    "summary_jp": "要約（日本語）",
    "type": "関係",
    "from_p": "前段落",
    "to_p": "後段落",
    "note": "説明",
    "span_en": "英文箇所",
    "tag_json": "文法タグ",
    "explanation_jp": "解説",
    "difficulty": "難度",
    "word": "単語",
    "level": "レベル",
    "note_jp": "メモ",
    "expr": "表現",
}


@dataclass(frozen=True)
class ColumnInfo:
    cid: int
    name: str
    type: str
    not_null: bool
    default: Any
    pk: int


@dataclass(frozen=True)
class TableInfo:
    name: str
    type: str
    columns: list[ColumnInfo]
    row_count: int
    primary_key: str | None


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.SQLITE_BROWSER_DB)
    connection.row_factory = sqlite3.Row
    return connection


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_names(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = connection.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY CASE WHEN name = 'passages' THEN 0 ELSE 1 END, name
        """
    ).fetchall()
    return [(row["name"], row["type"]) for row in rows if row["name"] not in HIDDEN_TABLES]


def table_label(name: str) -> str:
    return TABLE_LABELS.get(name, name)


def column_label(name: str) -> str:
    return COLUMN_LABELS.get(name, name)


def get_tables() -> list[TableInfo]:
    with connect() as connection:
        return [_read_table_info(connection, name, table_type) for name, table_type in _table_names(connection)]


def get_table_info(table: str) -> TableInfo:
    with connect() as connection:
        known = dict(_table_names(connection))
        if table not in known:
            raise Http404("Table not found.")
        return _read_table_info(connection, table, known[table])


def _read_table_info(connection: sqlite3.Connection, table: str, table_type: str) -> TableInfo:
    columns = [
        ColumnInfo(
            cid=row[0],
            name=row[1],
            type=row[2] or "",
            not_null=bool(row[3]),
            default=row[4],
            pk=row[5],
        )
        for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})")
    ]
    row_count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()[0]
    primary_key = next((column.name for column in sorted(columns, key=lambda item: item.pk) if column.pk), None)
    return TableInfo(table, table_type, columns, row_count, primary_key)


def require_table(table: str) -> TableInfo:
    return get_table_info(table)


def _query_terms(query: str) -> list[str]:
    return [term for term in query.split() if term]


def _search_clause(columns: list[ColumnInfo], query: str) -> tuple[str, list[str]]:
    terms = _query_terms(query)
    if not terms:
        return "", []

    searchable = [column.name for column in columns]
    where_groups = []
    params = []
    for term in terms:
        column_clauses = [f"CAST({quote_identifier(column)} AS TEXT) LIKE ? COLLATE NOCASE" for column in searchable]
        where_groups.append("(" + " OR ".join(column_clauses) + ")")
        params.extend([f"%{term}%"] * len(searchable))
    return " WHERE " + " AND ".join(where_groups), params


def _append_passage_filters(
    where_sql: str,
    params: list[Any],
    level_tag: str = "",
    word_min: int | None = None,
    word_max: int | None = None,
) -> tuple[str, list[Any]]:
    clauses = []
    if level_tag:
        clauses.append("level_tag = ?")
        params.append(level_tag)
    if word_min is not None:
        clauses.append("word_count >= ?")
        params.append(word_min)
    if word_max is not None:
        clauses.append("word_count <= ?")
        params.append(word_max)

    if not clauses:
        return where_sql, params
    prefix = " WHERE " if not where_sql else " AND "
    return where_sql + prefix + " AND ".join(clauses), params


def list_rows(
    table: str,
    query: str = "",
    page: int = 1,
    per_page: int = 25,
    sort: str | None = None,
    direction: str = "asc",
    level_tag: str = "",
    word_min: int | None = None,
    word_max: int | None = None,
) -> dict[str, Any]:
    info = require_table(table)
    column_names = [column.name for column in info.columns]
    if sort not in column_names:
        sort = info.primary_key or column_names[0]
    direction = "desc" if direction == "desc" else "asc"
    page = max(page, 1)
    per_page = min(max(per_page, 10), 100)

    where_sql, params = _search_clause(info.columns, query.strip())
    if table == "passages":
        where_sql, params = _append_passage_filters(where_sql, params, level_tag, word_min, word_max)
    order_sql = f" ORDER BY {quote_identifier(sort)} {direction.upper()}"

    with connect() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}{where_sql}",
            params,
        ).fetchone()[0]
        page_count = max((total + per_page - 1) // per_page, 1)
        page = min(page, page_count)
        offset = (page - 1) * per_page
        rows = connection.execute(
            f"""
            SELECT *
            FROM {quote_identifier(table)}
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, per_page, offset],
        ).fetchall()

    return {
        "info": info,
        "rows": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "page_count": page_count,
        "sort": sort,
        "direction": direction,
    }


def level_tag_options() -> list[str]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT level_tag
            FROM passages
            WHERE level_tag IS NOT NULL AND TRIM(level_tag) != ''
            ORDER BY level_tag
            """
        ).fetchall()
    return [row["level_tag"] for row in rows]


def global_search_rows(query: str, limit_per_table: int = 8) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    results = []
    for table in get_tables():
        where_sql, params = _search_clause(table.columns, query)
        pk = table.primary_key or table.columns[0].name
        with connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {quote_identifier(table.name)}{where_sql}",
                params,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT *
                FROM {quote_identifier(table.name)}
                {where_sql}
                ORDER BY {quote_identifier(pk)} ASC
                LIMIT ?
                """,
                [*params, limit_per_table],
            ).fetchall()
        if total:
            results.append(
                {
                    "table": table,
                    "total": total,
                    "rows": [dict(row) for row in rows],
                }
            )
    return results


def get_row(table: str, pk: str) -> dict[str, Any]:
    info = require_table(table)
    if not info.primary_key:
        raise Http404("This table does not have a primary key.")
    with connect() as connection:
        row = connection.execute(
            f"""
            SELECT *
            FROM {quote_identifier(table)}
            WHERE {quote_identifier(info.primary_key)} = ?
            """,
            [pk],
        ).fetchone()
    if row is None:
        raise Http404("Row not found.")
    return dict(row)


def passage_nav_rows() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, source_exam, year, level_tag, topic
            FROM passages
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def passage_sections(passage_id: str | int) -> list[dict[str, Any]]:
    tables_by_name = {table.name: table for table in get_tables()}
    ordered_names = [
        name
        for name in STUDY_TABLE_ORDER
        if name in tables_by_name and any(column.name == "passage_id" for column in tables_by_name[name].columns)
    ]
    remaining_names = [
        table.name
        for table in get_tables()
        if table.name not in {"passages", *ordered_names}
        and any(column.name == "passage_id" for column in table.columns)
    ]

    sections = []
    for table_name in [*ordered_names, *remaining_names]:
        info = tables_by_name[table_name]
        order_columns = [
            column_name
            for column_name in ("p_index", "from_p", "to_p", info.primary_key or info.columns[0].name)
            if any(column.name == column_name for column in info.columns)
        ]
        order_sql = ", ".join(quote_identifier(column_name) for column_name in order_columns)
        with connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {quote_identifier(table_name)}
                WHERE passage_id = ?
                ORDER BY {order_sql}
                """,
                [passage_id],
            ).fetchall()
        sections.append(
            {
                "name": table_name,
                "label": table_label(table_name),
                "info": info,
                "rows": [dict(row) for row in rows],
                "total": len(rows),
            }
        )
    return sections


def related_rows(table: str, row: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    info = require_table(table)
    related: dict[str, Any] = {}

    if table == "passages" and "id" in row:
        passage_id = row["id"]
        for candidate in get_tables():
            if candidate.name == "passages":
                continue
            if any(column.name == "passage_id" for column in candidate.columns):
                with connect() as connection:
                    rows = connection.execute(
                        f"""
                        SELECT *
                        FROM {quote_identifier(candidate.name)}
                        WHERE passage_id = ?
                        ORDER BY {quote_identifier(candidate.primary_key or candidate.columns[0].name)} ASC
                        LIMIT ?
                        """,
                        [passage_id, limit],
                    ).fetchall()
                    total = connection.execute(
                        f"SELECT COUNT(*) FROM {quote_identifier(candidate.name)} WHERE passage_id = ?",
                        [passage_id],
                    ).fetchone()[0]
                related[candidate.name] = {
                    "info": candidate,
                    "rows": [dict(item) for item in rows],
                    "total": total,
                }
        return related

    if "passage_id" in row:
        with connect() as connection:
            passage = connection.execute(
                """
                SELECT id, source_exam, year, topic, level_tag, word_count
                FROM passages
                WHERE id = ?
                """,
                [row["passage_id"]],
            ).fetchone()
        if passage:
            related["passages"] = {
                "info": get_table_info("passages"),
                "rows": [dict(passage)],
                "total": 1,
            }
    return related


def display_value(value: Any, max_length: int = 120) -> dict[str, Any]:
    if value is None:
        return {"text": "NULL", "is_null": True, "is_json": False, "is_long": False}

    text = str(value)
    formatted = text
    is_json = False
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            formatted = json.dumps(json.loads(stripped), ensure_ascii=False, indent=2)
            is_json = True
        except json.JSONDecodeError:
            formatted = text

    compact = " ".join(text.split())
    is_long = len(compact) > max_length
    preview = compact[: max_length - 3] + "..." if is_long else compact
    return {
        "text": formatted,
        "preview": preview,
        "is_null": False,
        "is_json": is_json,
        "is_long": is_long or "\n" in formatted,
    }


def prepared_rows(
    rows: list[dict[str, Any]],
    columns: list[ColumnInfo],
    primary_key: str | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "raw": row,
            "pk": row.get(primary_key) if primary_key else row.get("id"),
            "cells": [
                {
                    "column": column,
                    "label": column_label(column.name),
                    "value": display_value(row.get(column.name)),
                }
                for column in columns
            ],
        }
        for row in rows
    ]
