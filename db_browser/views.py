from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse

from . import db


TECHNICAL_COLUMNS = {"id", "passage_id", "meta_json"}
SHORT_COLUMNS = {"year", "word_count", "p_index", "from_p", "to_p", "level", "difficulty", "type"}
LONG_COLUMNS = {
    "passage_en",
    "passage_jp",
    "why_this_text",
    "likely_types_json",
    "summary_en",
    "summary_jp",
    "span_en",
    "tag_json",
    "explanation_jp",
    "note",
    "note_jp",
    "expr",
}


def _int_param(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except ValueError:
        return default


def _optional_int_param(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _passage_url(passage_id: object) -> str:
    return reverse("db_browser:passage_detail", args=[passage_id])


def _passage_read_url(passage_id: object) -> str:
    return reverse("db_browser:passage_read", args=[passage_id])


def _row_url(table: str, pk: object) -> str:
    if table == "passages":
        return _passage_url(pk)
    return reverse("db_browser:row_detail", args=[table, pk])


def _passage_nav(active_passage_id: object | None = None) -> list[dict[str, object]]:
    active = str(active_passage_id) if active_passage_id is not None else ""
    return [
        {
            **row,
            "active": str(row["id"]) == active,
            "url": _passage_url(row["id"]),
        }
        for row in db.passage_nav_rows()
    ]


def _query_url(params: dict[str, object]) -> str:
    cleaned = {key: value for key, value in params.items() if value not in ("", None)}
    query_string = urlencode(cleaned)
    return reverse("db_browser:index") + ("?" + query_string if query_string else "")


def _attach_detail_urls(rows: list[dict[str, object]], table: str) -> list[dict[str, object]]:
    for row in rows:
        if row.get("pk") is not None:
            row["detail_url"] = _row_url(table, row["pk"])
    return rows


def _content_length(value: object) -> int:
    if value is None:
        return 0
    return len(" ".join(str(value).split()))


def _column_weight(column: object, rows: list[dict[str, object]]) -> float:
    label = db.column_label(column.name)
    lengths = [_content_length(row.get(column.name)) for row in rows]
    average = sum(min(length, 260) for length in lengths) / max(len(lengths), 1)
    longest = max([min(length, 320) for length in lengths], default=0)
    weight = max(len(label) * 2.2, average * 0.68 + longest * 0.32, 16)

    if column.name in SHORT_COLUMNS:
        weight = min(weight, 34)
    if column.name in LONG_COLUMNS:
        weight *= 1.35
    return min(max(weight, 16), 160)


def _display_columns(rows: list[dict[str, object]], columns: list[object]) -> list[dict[str, object]]:
    if not columns:
        return []

    weights = [_column_weight(column, rows) for column in columns]
    total = sum(weights) or 1
    widths = [max((weight / total) * 100, 7) for weight in weights]
    width_total = sum(widths) or 1

    return [
        {
            "info": column,
            "label": db.column_label(column.name),
            "width": f"{(width / width_total) * 100:.2f}%",
        }
        for column, width in zip(columns, widths)
    ]


def _passage_list_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    passages = []
    for row in rows:
        passages.append(
            {
                **row,
                "url": _passage_read_url(row["id"]),
                "read_url": _passage_read_url(row["id"]),
                "analysis_url": _passage_url(row["id"]),
                "preview": db.display_value(row.get("passage_en"), max_length=260)["preview"],
            }
        )
    return passages


def _section_rows(section: dict[str, object]) -> dict[str, object]:
    info = section["info"]
    display_columns = [column for column in info.columns if column.name not in TECHNICAL_COLUMNS]
    rows = db.prepared_rows(section["rows"], display_columns, info.primary_key)
    return {
        **section,
        "columns": _display_columns(section["rows"], display_columns),
        "rows": _attach_detail_urls(rows, section["name"]),
    }


def index(request):
    query = request.GET.get("q", "").strip()
    level_tag = request.GET.get("level_tag", "").strip()
    word_min = _optional_int_param(request.GET.get("word_min"))
    word_max = _optional_int_param(request.GET.get("word_max"))
    if word_min is not None and word_max is not None and word_min > word_max:
        word_min, word_max = word_max, word_min

    page = _int_param(request.GET.get("page"), 1)
    per_page = _int_param(request.GET.get("per_page"), settings.SQLITE_BROWSER_PAGE_SIZE)

    result = db.list_rows(
        "passages",
        query,
        page,
        per_page,
        sort="id",
        direction="asc",
        level_tag=level_tag,
        word_min=word_min,
        word_max=word_max,
    )
    passages = _passage_list_rows(result["rows"])
    page_count = result["page_count"]
    page = result["page"]
    base_params = {
        "q": query,
        "level_tag": level_tag,
        "word_min": word_min,
        "word_max": word_max,
        "per_page": per_page,
    }

    context = {
        "passage_nav": _passage_nav(),
        "query": query,
        "level_tag": level_tag,
        "level_tag_options": db.level_tag_options(),
        "word_min": word_min,
        "word_max": word_max,
        "passages": passages,
        "result": {**result, "page": page},
        "prev_url": _query_url({**base_params, "page": page - 1}) if page > 1 else "",
        "next_url": _query_url({**base_params, "page": page + 1}) if page < page_count else "",
        "page_sizes": [10, 25, 50, 100],
    }
    return render(request, "db_browser/index.html", context)


def global_search(request):
    query = request.GET.get("q", "").strip()
    results = db.global_search_rows(query)
    prepared_results = []
    for item in results:
        info = item["table"]
        columns = [column for column in info.columns if column.name not in TECHNICAL_COLUMNS]
        rows = db.prepared_rows(item["rows"], columns, info.primary_key)
        prepared_results.append(
            {
                **item,
                "label": db.table_label(info.name),
                "columns": _display_columns(item["rows"], columns),
                "rows": _attach_detail_urls(rows, info.name),
            }
        )

    return render(
        request,
        "db_browser/global_search.html",
        {
            "passage_nav": _passage_nav(),
            "query": query,
            "results": prepared_results,
        },
    )


def passage_detail(request, pk: str):
    return _render_passage_detail(request, pk)


def passage_read(request, pk: str):
    passage = db.get_row("passages", pk)
    return render(
        request,
        "db_browser/passage_read.html",
        {
            "passage_nav": _passage_nav(pk),
            "passage": passage,
            "back_url": _query_url({}),
            "analysis_url": _passage_url(pk),
        },
    )


def _render_passage_detail(request, pk: str):
    passage = db.get_row("passages", pk)
    sections = [_section_rows(section) for section in db.passage_sections(pk)]
    passage_fields = [
        {
            "name": db.column_label(column),
            "value": passage.get(column),
        }
        for column in ("source_exam", "year", "level_tag", "topic", "text_type", "word_count")
    ]

    return render(
        request,
        "db_browser/passage_detail.html",
        {
            "passage_nav": _passage_nav(pk),
            "passage": passage,
            "passage_fields": passage_fields,
            "sections": sections,
            "back_url": _query_url({}),
        },
    )


def row_detail(request, table: str, pk: str):
    info = db.require_table(table)
    row = db.get_row(table, pk)
    if table == "passages":
        return _render_passage_detail(request, pk)

    fields = [
        {
            "column": column,
            "label": db.column_label(column.name),
            "value": db.display_value(row.get(column.name), max_length=5000),
        }
        for column in info.columns
    ]
    related = []
    active_passage_id = row.get("passage_id")
    for name, item in db.related_rows(table, row).items():
        display_columns = [column for column in item["info"].columns if column.name not in TECHNICAL_COLUMNS]
        rows = db.prepared_rows(item["rows"], display_columns, item["info"].primary_key)
        related.append(
            {
                "name": name,
                "label": db.table_label(name),
                "info": item["info"],
                "total": item["total"],
                "columns": _display_columns(item["rows"], display_columns),
                "rows": _attach_detail_urls(rows, name),
            }
        )

    return render(
        request,
        "db_browser/detail.html",
        {
            "passage_nav": _passage_nav(active_passage_id),
            "active_table": table,
            "table_label": db.table_label(table),
            "info": info,
            "row": row,
            "pk": pk,
            "fields": fields,
            "related": related,
            "back_url": _passage_url(active_passage_id) if active_passage_id else _query_url({}),
        },
    )
