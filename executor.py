# executor.py
import duckdb
import pandas as pd
from schema import QuerySpec, Filter, SortSpec, TimeSpec

def _quarter_of_date(d: pd.Timestamp) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year} Q{q}"

def _prev_quarter(qstr: str) -> str:
    year, q = qstr.split()
    year = int(year)
    qn = int(q.replace("Q",""))
    if qn == 1:
        return f"{year-1} Q4"
    return f"{year} Q{qn-1}"

def _resolve_time_filter(df: pd.DataFrame, time: TimeSpec):
    min_date = df["Date"].min()
    max_date = df["Date"].max()
    note = f"Data range: {min_date.date()} ~ {max_date.date()}"

    if time.type == "none":
        return None, note

    if time.type == "year":
        return Filter(field="Year", op="=", value=int(time.value)), note + f"; Year={time.value}"

    if time.type == "quarter":
        return Filter(field="Quarter", op="=", value=str(time.value)), note + f"; Quarter={time.value}"

    if time.type == "month":
        return Filter(field="Month", op="=", value=str(time.value)), note + f"; Month={time.value}"

    if time.type == "date_between":
        start, end = time.value
        return Filter(field="Date", op="between", value=[start, end]), note + f"; Date between {start} and {end}"

    if time.type == "last_quarter":
        max_q = _quarter_of_date(max_date)
        last_q = _prev_quarter(max_q)
        return Filter(field="Quarter", op="=", value=last_q), note + f"; last_quarter based on max_date={max_date.date()} -> {last_q}"

    if time.type == "last_month":
        last_month = (max_date.to_period("M") - 1).strftime("%YM%m")  # e.g. 2023M07
        return Filter(field="Month", op="=", value=last_month), note + f"; last_month based on max_date={max_date.date()} -> {last_month}"

    raise ValueError(f"Unsupported time type: {time.type}")

def _sql_quote_ident(col: str) -> str:
    # duckdb SQL identifier quoting
    return f'"{col}"'

def _filter_to_sql(f: Filter, params: list):
    col = _sql_quote_ident(f.field)
    if f.op == "=":
        params.append(f.value)
        return f"{col} = ?"
    if f.op == "!=":
        params.append(f.value)
        return f"{col} != ?"
    if f.op == "in":
        vals = list(f.value)
        placeholders = ",".join(["?"] * len(vals))
        params.extend(vals)
        return f"{col} IN ({placeholders})"
    if f.op == "between":
        start, end = f.value
        params.extend([start, end])
        return f"{col} BETWEEN ? AND ?"
    raise ValueError(f"Unsupported op: {f.op}")

def execute_query(df: pd.DataFrame, spec: QuerySpec):
    con = duckdb.connect()
    con.register("md", df)

    time_filter, note = _resolve_time_filter(df, spec.time)
    filters = list(spec.filters)
    if time_filter:
        # Remove old rules with identical field names
        filters = [x for x in filters if x.field != time_filter.field]
        filters.append(time_filter)

    params = []
    where_sql = ""
    if filters:
        parts = [_filter_to_sql(f, params) for f in filters]
        where_sql = "WHERE " + " AND ".join(parts)

    # Select Metrics（Profit：SUM(Revenue) - SUM(Cost)）
    select_exprs = []

    if "Revenue" in spec.metrics or "Profit" in spec.metrics:
        select_exprs.append("SUM(Revenue) AS Revenue")
    if "Cost" in spec.metrics or "Profit" in spec.metrics:
        select_exprs.append("SUM(Cost) AS Cost")
    if "Profit" in spec.metrics:
        select_exprs.append("(SUM(Revenue) - SUM(Cost)) AS Profit")

    # group by
    gb = spec.group_by or []
    gb_select = [f"{_sql_quote_ident(c)} AS {_sql_quote_ident(c)}" for c in gb]
    group_sql = ""
    if gb:
        group_cols = ", ".join([_sql_quote_ident(c) for c in gb])
        group_sql = f"GROUP BY {group_cols}"

    select_sql = ", ".join(gb_select + select_exprs)

    base_sql = f"""
    SELECT {select_sql}
    FROM md
    {where_sql}
    {group_sql}
    """

    # sort
    order_sql = ""
    if spec.sort:
        s = spec.sort[0]
        order_sql = f'ORDER BY "{s.by}" {s.dir.upper()}'

    # limit
    limit_sql = f"LIMIT {int(spec.limit)}" if spec.limit else ""

    final_sql = " ".join([base_sql, order_sql, limit_sql]).strip()
    out = con.execute(final_sql, params).df()

    # Scenario A: Handling single_value output patterns (e.g., asking “Total revenue”)
    if spec.output == "single_value":
        # 1. Security Check: If SQL finds no rows
        if len(out) == 0:
            return None, note, final_sql
        
        # 2. Get the value of the first metric
        col = spec.metrics[0]
        val = out[col].iloc[0]
        
        # 3. Core fix: Check if SQL returns NULL (NAN)
        if pd.isna(val):
            return None, note, final_sql
        
        return float(val), note, final_sql

    # Situation B: Handling Trend Pattern
    if spec.output == "trend" and gb:
        time_cols = [c for c in gb if c in ["Date","Month","Week","Quarter","Year"]]
        if time_cols:
            out = out.sort_values(time_cols)

    # Scenario C: By default, return the entire table (DataFrame)
    return out, note, final_sql
