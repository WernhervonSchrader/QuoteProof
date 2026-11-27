"""Generic read-only SQL adapter for any ERP whose data tier speaks SQL.

Built for the common Mittelstand case: a three-tier ERP whose application
layer is unknown or closed, but whose database (MS SQL Server, Oracle,
PostgreSQL, MySQL/MariaDB, DB2, …) can be read through a DB-API 2.0 driver.

The profile supplies, per lookup, one parameterised SELECT and a column map.
Nothing about the ERP's schema lives in code. Placeholders are written as
``:name`` in the profile and translated to whatever the driver expects.

Safety, enforced at load time and fail-closed:
- only a single ``SELECT`` or ``WITH`` statement; no ``;``, no comments;
- no write, DDL or execution keywords anywhere in the statement;
- values are always bound as parameters, never formatted into the SQL;
- the connection string comes from an environment variable, never the profile.
Use a read-only database user or read-only views as the second line of defence.
"""

from __future__ import annotations

import importlib
import os
import re
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterator

from pydantic import BaseModel, Field

from ..models import ERPCustomer, ERPItem
from .base import ERPUnavailable


class SQLConfigError(ValueError):
    pass


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"exec|execute|call|into|replace|upsert|attach|detach|pragma|copy|lock)\b",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"(?<![:\w]):([A-Za-z_][A-Za-z0-9_]*)")
_TRUTHY = {"1", "true", "t", "yes", "y", "j", "ja", "x", "wahr"}

ITEM_FIELDS = (
    "sku",
    "description",
    "list_price",
    "cost_floor",
    "currency",
    "controlled_goods",
    "export_classification",
    "blocked_for_sale",
)
CUSTOMER_FIELDS = ("customer_id", "name", "country", "blocked", "credit_hold")


class QuerySpec(BaseModel):
    sql: str
    columns: dict[str, str] = Field(default_factory=dict)


def check_read_only(sql: str) -> str:
    statement = sql.strip()
    if not statement:
        raise SQLConfigError("Empty query.")
    if ";" in statement or "--" in statement or "/*" in statement:
        raise SQLConfigError("Queries must be one statement without ';' or comments.")
    if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
        raise SQLConfigError("Only SELECT or WITH queries are allowed.")
    hit = _FORBIDDEN.search(statement)
    if hit:
        raise SQLConfigError(f"Keyword '{hit.group(1)}' is not allowed in a read-only query.")
    return statement


def translate_placeholders(sql: str, paramstyle: str, params: dict[str, Any]) -> tuple[str, Any]:
    """Turn ``:name`` placeholders into the driver's paramstyle (PEP 249)."""

    names = _PLACEHOLDER.findall(sql)
    missing = [name for name in names if name not in params]
    if missing:
        raise SQLConfigError(f"Query uses undefined parameter(s): {', '.join(sorted(set(missing)))}")
    if paramstyle == "named":
        return sql, {name: params[name] for name in names}
    if paramstyle in {"format", "pyformat"}:
        sql = sql.replace("%", "%%")
    if paramstyle == "pyformat":
        return _PLACEHOLDER.sub(lambda m: f"%({m.group(1)})s", sql), {
            name: params[name] for name in names
        }
    ordered = [params[name] for name in names]
    if paramstyle == "qmark":
        return _PLACEHOLDER.sub("?", sql), ordered
    if paramstyle == "format":
        return _PLACEHOLDER.sub("%s", sql), ordered
    if paramstyle == "numeric":
        counter = iter(range(1, len(names) + 1))
        return _PLACEHOLDER.sub(lambda _m: f":{next(counter)}", sql), ordered
    raise SQLConfigError(f"Unsupported paramstyle '{paramstyle}'.")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ERPUnavailable(f"ERP returned a non-numeric value: {value!r}") from exc


def _to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in _TRUTHY


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class SQLAdapter:
    """Reads customers and items from any DB-API 2.0 database."""

    def __init__(
        self,
        queries: dict[str, QuerySpec],
        driver: str = "pyodbc",
        connection_env: str = "QUOTEPROOF_ERP_DSN",
        connect: Callable[[], Any] | None = None,
        paramstyle: str | None = None,
        label: str = "sql",
    ) -> None:
        if "item" not in queries:
            raise SQLConfigError("The SQL adapter needs at least an 'item' query.")
        for name, spec in queries.items():
            check_read_only(spec.sql)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", driver):
            raise SQLConfigError(f"Invalid driver module name '{driver}'.")
        self.queries = queries
        self.driver = driver
        self.connection_env = connection_env
        self._connect = connect
        self._paramstyle = paramstyle
        self.adapter_id = f"{label}:{driver}"

    @classmethod
    def from_options(cls, options: dict[str, Any], connect: Callable[[], Any] | None = None) -> "SQLAdapter":
        raw_queries = options.get("queries") or {}
        queries = {name: QuerySpec(**spec) for name, spec in raw_queries.items()}
        return cls(
            queries=queries,
            driver=options.get("driver", "pyodbc"),
            connection_env=options.get("connection_env", "QUOTEPROOF_ERP_DSN"),
            connect=connect,
            paramstyle=options.get("paramstyle"),
            label=options.get("label", "sql"),
        )

    def _module(self):
        try:
            return importlib.import_module(self.driver)
        except ImportError as exc:
            raise ERPUnavailable(f"Database driver '{self.driver}' is not installed.") from exc

    @contextmanager
    def _connection(self) -> Iterator[tuple[Any, str]]:
        if self._connect is not None:
            conn = self._connect()
            paramstyle = self._paramstyle or "qmark"
        else:
            module = self._module()
            dsn = os.getenv(self.connection_env)
            if not dsn:
                raise ERPUnavailable(f"Environment variable {self.connection_env} is not set.")
            try:
                conn = module.connect(dsn)
            except Exception as exc:  # noqa: BLE001 - never leak the DSN
                raise ERPUnavailable(f"Could not connect via {self.driver}.") from exc
            paramstyle = self._paramstyle or getattr(module, "paramstyle", "qmark")
        try:
            yield conn, paramstyle
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _rows(self, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        spec = self.queries.get(name)
        if spec is None:
            return []
        with self._connection() as (conn, paramstyle):
            sql, bound = translate_placeholders(spec.sql, paramstyle, params)
            cursor = conn.cursor()
            try:
                cursor.execute(sql, bound)
                columns = [column[0] for column in cursor.description or []]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except Exception as exc:  # noqa: BLE001
                raise ERPUnavailable(f"Query '{name}' failed.") from exc
            finally:
                cursor.close()

    def _source(self, name: str, key: str) -> str:
        return f"{self.adapter_id} query '{name}' key={key}"

    @staticmethod
    def _pick(row: dict[str, Any], columns: dict[str, str], field: str) -> Any:
        column = columns.get(field, field)
        if column in row:
            return row[column]
        lowered = {key.casefold(): value for key, value in row.items()}
        return lowered.get(column.casefold())

    def items(self, skus: list[str]) -> dict[str, ERPItem]:
        spec = self.queries["item"]
        found: dict[str, ERPItem] = {}
        for sku in skus:
            rows = self._rows("item", {"sku": sku})
            if len(rows) > 1:
                raise ERPUnavailable(f"Item query returned {len(rows)} rows for one SKU.")
            if not rows:
                continue
            row, cols = rows[0], spec.columns
            found[sku] = ERPItem(
                sku=_to_text(self._pick(row, cols, "sku")) or sku,
                description=_to_text(self._pick(row, cols, "description")),
                list_price=_to_decimal(self._pick(row, cols, "list_price")),
                cost_floor=_to_decimal(self._pick(row, cols, "cost_floor")),
                currency=_to_text(self._pick(row, cols, "currency")),
                controlled_goods=_to_bool(self._pick(row, cols, "controlled_goods")),
                export_classification=_to_text(self._pick(row, cols, "export_classification")),
                blocked_for_sale=bool(_to_bool(self._pick(row, cols, "blocked_for_sale"))),
                source=self._source("item", sku),
            )
        return found

    def customer(self, customer_id: str | None, name: str | None) -> ERPCustomer | None:
        if customer_id and "customer_by_id" in self.queries:
            query, params, key = "customer_by_id", {"customer_id": customer_id}, customer_id
        elif name and "customer_by_name" in self.queries:
            query, params, key = "customer_by_name", {"name": name}, name
        else:
            return None
        rows = self._rows(query, params)
        if not rows:
            return None
        if len(rows) > 1:
            raise ERPUnavailable(f"Customer lookup '{query}' is ambiguous ({len(rows)} rows).")
        row, cols = rows[0], self.queries[query].columns
        return ERPCustomer(
            customer_id=_to_text(self._pick(row, cols, "customer_id")),
            name=_to_text(self._pick(row, cols, "name")) or (name or ""),
            country=_to_text(self._pick(row, cols, "country")),
            blocked=bool(_to_bool(self._pick(row, cols, "blocked"))),
            credit_hold=bool(_to_bool(self._pick(row, cols, "credit_hold"))),
            source=self._source(query, key),
        )

    def customer_names(self) -> list[str]:
        if "customer_names" not in self.queries:
            return []
        cols = self.queries["customer_names"].columns
        return [
            text
            for row in self._rows("customer_names", {})
            if (text := _to_text(self._pick(row, cols, "name")))
        ]
