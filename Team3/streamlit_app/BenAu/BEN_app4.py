import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px

# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(page_title="App4 — SG Job Market Insights", layout="wide")
st.title("🇸🇬 App4 — Singapore Job Market Insights")
st.caption("Detail distributions (sampled) + Heatmap (DB-aggregated) • No SQL Views")

# --------------------------------------------------
# Config
# --------------------------------------------------
DB_PATH = "/home/auyan/SGJobData-Visualization-Assignment/Team3/data/raw/SGJobData.db"
T_BASE = "jobs_base"
T_CAT  = "jobs_categories"
T_ENR  = "jobs_enriched"
T_RAW  = "jobs_raw"   # only used if status not present in base/enriched

# --------------------------------------------------
# DuckDB helpers
# --------------------------------------------------
@st.cache_resource
def get_con():
    return duckdb.connect(DB_PATH, read_only=True)

def run_df(sql: str, params=None) -> pd.DataFrame:
    con = get_con()
    if params is not None:
        # params should be a list/tuple in positional order
        return con.execute(sql, params).df()
    return con.execute(sql).df()


@st.cache_data(ttl=1800)
def get_table_cols(table: str) -> list[str]:
    df = run_df(f"PRAGMA table_info('{table}')")
    return df["name"].tolist()

def pick_first(cols: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None

def to_list_safe(v) -> list:
    if v is None:
        return []
    try:
        if pd.isna(v):
            return []
    except Exception:
        pass
    if isinstance(v, (list, tuple)):
        out = list(v)
    else:
        try:
            out = list(v)
        except Exception:
            out = []
    return [x for x in out if x is not None and str(x).strip() != ""]

def default_primary_category(all_categories, preferred="Banking and Finance"):
    return [preferred] if preferred in all_categories else all_categories

def sql_try_double(expr: str) -> str:
    return f"try_cast({expr} AS DOUBLE)"

# --------------------------------------------------
# Detect schema
# --------------------------------------------------
@st.cache_data(ttl=1800)
def build_plan():
    cols_b = get_table_cols(T_BASE)
    cols_c = get_table_cols(T_CAT)
    cols_e = get_table_cols(T_ENR)
    try:
        cols_r = get_table_cols(T_RAW)
    except Exception:
        cols_r = []

    key_candidates = ["metadata_jobPostId", "job_post_id", "jobPostId", "job_id", "metadata_job_post_id"]

    b_key = pick_first(cols_b, key_candidates)
    c_key = pick_first(cols_c, key_candidates)
    e_key = pick_first(cols_e, key_candidates)
    r_key = pick_first(cols_r, key_candidates) if cols_r else None

    if not b_key:
        raise RuntimeError(f"Cannot find join key in {T_BASE}. Tried: {key_candidates}")

    # base
    b_title   = pick_first(cols_b, ["title"])
    b_company = pick_first(cols_b, ["postedCompany_name", "company_name", "posted_company_name"])
    b_emp     = pick_first(cols_b, ["employmentTypes", "employment_type"])
    b_level   = pick_first(cols_b, ["positionLevels", "position_level"])
    b_sal_min = pick_first(cols_b, ["salary_minimum", "salary_min"])
    b_sal_max = pick_first(cols_b, ["salary_maximum", "salary_max"])
    b_status  = pick_first(cols_b, ["status_jobStatus", "status_job_status", "jobStatus", "job_status"])

    # categories (assumed clean)
    c_primary = pick_first(cols_c, ["primary_category", "primaryCategory", "category", "category_name"])

    # enriched
    e_avg     = pick_first(cols_e, ["avg_salary", "average_salary", "salary_mid", "salary_midpoint"])
    e_emp     = pick_first(cols_e, ["employment_type", "employmentTypes"])
    e_level   = pick_first(cols_e, ["position_level", "positionLevels"])
    e_primary = pick_first(cols_e, ["primary_category"])
    e_sal_min = pick_first(cols_e, ["salary_min", "salary_minimum"])
    e_sal_max = pick_first(cols_e, ["salary_max", "salary_maximum"])
    e_status  = pick_first(cols_e, ["status_jobStatus", "status_job_status", "jobStatus", "job_status"])

    # raw fallback status
    r_status = pick_first(cols_r, ["status_jobStatus", "status_job_status", "jobStatus", "job_status"]) if cols_r else None

    return dict(
        b_key=b_key, c_key=c_key, e_key=e_key, r_key=r_key,
        b_title=b_title, b_company=b_company, b_emp=b_emp, b_level=b_level,
        b_sal_min=b_sal_min, b_sal_max=b_sal_max, b_status=b_status,
        c_primary=c_primary,
        e_avg=e_avg, e_emp=e_emp, e_level=e_level, e_primary=e_primary,
        e_sal_min=e_sal_min, e_sal_max=e_sal_max, e_status=e_status,
        r_status=r_status,
    )

def build_salary_mid_expr(plan: dict) -> str:
    pieces = []
    if plan["e_key"] and plan["e_avg"]:
        pieces.append(sql_try_double(f"e.{plan['e_avg']}"))

    min_expr = None
    max_expr = None

    if plan["e_key"] and plan["e_sal_min"]:
        min_expr = sql_try_double(f"e.{plan['e_sal_min']}")
    elif plan["b_sal_min"]:
        min_expr = sql_try_double(f"b.{plan['b_sal_min']}")

    if plan["e_key"] and plan["e_sal_max"]:
        max_expr = sql_try_double(f"e.{plan['e_sal_max']}")
    elif plan["b_sal_max"]:
        max_expr = sql_try_double(f"b.{plan['b_sal_max']}")

    if min_expr and max_expr:
        pieces.append(f"(({min_expr} + {max_expr}) / 2.0)")
        pieces.append(min_expr)
        pieces.append(max_expr)
    elif min_expr:
        pieces.append(min_expr)
    elif max_expr:
        pieces.append(max_expr)

    return "NULL::DOUBLE" if not pieces else "coalesce(" + ", ".join(pieces) + ")"

def build_status_group_expr(status_expr: str) -> str:
    return f"""
    CASE
      WHEN {status_expr} IS NULL THEN NULL
      WHEN lower({status_expr}) IN ('re-open','reopen','re-opened','reopened') THEN 'Open'
      WHEN lower({status_expr}) = 'open' THEN 'Open'
      WHEN lower({status_expr}) = 'closed' THEN 'Closed'
      ELSE {status_expr}
    END
    """

def joined_cte_sql(plan: dict) -> str:
    join_enr = f"LEFT JOIN {T_ENR} e ON b.{plan['b_key']} = e.{plan['e_key']}" if plan["e_key"] else ""
    join_cat = f"LEFT JOIN {T_CAT} c ON b.{plan['b_key']} = c.{plan['c_key']}" if plan["c_key"] else ""

    # join raw only if needed for status
    join_raw = ""
    if not plan["b_status"] and not (plan["e_key"] and plan["e_status"]):
        if plan["r_key"] and plan["r_status"]:
            join_raw = f"LEFT JOIN {T_RAW} r ON b.{plan['b_key']} = r.{plan['r_key']}"

    salary_mid_expr = build_salary_mid_expr(plan)
    pos_expr = f"e.{plan['e_level']}" if (plan["e_key"] and plan["e_level"]) else f"b.{plan['b_level']}"
    emp_expr = f"e.{plan['e_emp']}" if (plan["e_key"] and plan["e_emp"]) else f"b.{plan['b_emp']}"

    if plan["c_primary"]:
        primary_expr = f"c.{plan['c_primary']}"
    elif plan["e_key"] and plan["e_primary"]:
        primary_expr = f"e.{plan['e_primary']}"
    else:
        primary_expr = "NULL"

    if plan["b_status"]:
        status_expr = f"b.{plan['b_status']}"
    elif plan["e_key"] and plan["e_status"]:
        status_expr = f"e.{plan['e_status']}"
    elif plan["r_status"]:
        status_expr = f"r.{plan['r_status']}"
    else:
        status_expr = "NULL"

    status_group_expr = build_status_group_expr(status_expr)

    return f"""
    WITH joined AS (
      SELECT
        b.{plan['b_key']} AS job_post_id,
        {('b.' + plan['b_title']) if plan['b_title'] else 'NULL'} AS title,
        {('b.' + plan['b_company']) if plan['b_company'] else 'NULL'} AS company_name,
        {salary_mid_expr} AS salary_mid,
        {pos_expr} AS position_level,
        {emp_expr} AS employment_type,
        {primary_expr} AS primary_category,
        {status_group_expr} AS status_group
      FROM {T_BASE} b
      {join_enr}
      {join_cat}
      {join_raw}
    )
    """

# --------------------------------------------------
# Filters
# --------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=True)
def load_filter_values():
    plan = build_plan()

    pos_col = plan["b_level"] or plan["e_level"]
    emp_col = plan["b_emp"] or plan["e_emp"]
    if not pos_col or not emp_col:
        raise RuntimeError("Missing position level / employment type columns.")

    df_pe = run_df(
        f"""
        SELECT
          array_agg(DISTINCT {pos_col} ORDER BY {pos_col}) AS position_levels,
          array_agg(DISTINCT {emp_col} ORDER BY {emp_col}) AS employment_types
        FROM {T_BASE}
        """
    )

    position_levels, employment_types = [], []
    if not df_pe.empty:
        row = df_pe.iloc[0]
        position_levels = to_list_safe(row.get("position_levels"))
        employment_types = to_list_safe(row.get("employment_types"))

    categories = []
    if plan["c_primary"]:
        df_c = run_df(
            f"""
            SELECT array_agg(DISTINCT {plan['c_primary']} ORDER BY {plan['c_primary']}) AS categories
            FROM {T_CAT}
            """
        )
        if not df_c.empty:
            categories = to_list_safe(df_c.iloc[0].get("categories"))

    return dict(
        position_levels=position_levels,
        employment_types=employment_types,
        categories=categories,
        statuses=["Open", "Closed"],
    )

# --------------------------------------------------
# Detail sample + Heatmap agg (filters ONLY reference joined columns)
# --------------------------------------------------

def build_where_and_params(levels, cats, emps, status_groups):
    where = []
    params = []

    if levels:
        where.append("position_level = ANY(?)")
        params.append(levels)

    if cats:
        where.append("primary_category = ANY(?)")
        params.append(cats)

    if emps:
        where.append("employment_type = ANY(?)")
        params.append(emps)

    if status_groups:
        where.append("status_group = ANY(?)")
        params.append(status_groups)

    where_sql = " AND ".join(where) if where else "1=1"
    return where_sql, params




@st.cache_data(ttl=300, show_spinner=True)
def load_detail_sample(levels, cats, emps, status_groups, max_rows, debug_sql=False):
    plan = build_plan()
    joined_sql = joined_cte_sql(plan)

    where_sql, params = build_where_and_params(levels, cats, emps, status_groups)

    sql = f"""
    {joined_sql}
    , filtered AS (
      SELECT *
      FROM joined
      WHERE {where_sql}
        AND salary_mid IS NOT NULL
        AND position_level IS NOT NULL
        AND employment_type IS NOT NULL
    )
    SELECT *
    FROM filtered
    USING SAMPLE {int(max_rows)} ROWS
    """

    if debug_sql:
        return pd.DataFrame({"sql":[sql], "params":[str(params)]})

    return run_df(sql, params)


@st.cache_data(ttl=300, show_spinner=True)
def load_heatmap_agg(levels, cats, emps, status_groups, salary_cap_pct, nbinsy, debug_sql=False):
    plan = build_plan()
    joined_sql = joined_cte_sql(plan)

    where_sql, where_params = build_where_and_params(levels, cats, emps, status_groups)

    # --- 1) compute cap (percentile) ---
    cap_sql = f"""
    {joined_sql}
    SELECT quantile_cont(salary_mid, ?) AS cap
    FROM joined
    WHERE {where_sql}
      AND salary_mid IS NOT NULL
      AND position_level IS NOT NULL
    """
    cap_params = [float(salary_cap_pct)] + where_params

    if debug_sql:
        return pd.DataFrame({"sql":[cap_sql], "params":[str(cap_params)]})

    cap_df = run_df(cap_sql, cap_params)
    cap_val = cap_df.iloc[0]["cap"] if (not cap_df.empty) else None

    if cap_val is None or pd.isna(cap_val) or float(cap_val) <= 0:
        return pd.DataFrame(columns=["position_level", "bin_start", "cnt", "cap", "bin_size"])

    # --- 2) binning ---
    nbinsy = int(nbinsy)
    bin_size = max(float(cap_val) / nbinsy, 1.0)

    agg_sql = f"""
    {joined_sql}
    , filtered AS (
      SELECT *
      FROM joined
      WHERE {where_sql}
        AND salary_mid IS NOT NULL
        AND position_level IS NOT NULL
    ),
    capped AS (
      SELECT
        position_level,
        least(salary_mid, ?) AS salary_mid_capped
      FROM filtered
    )
    SELECT
      position_level,
      floor(salary_mid_capped / ?) * ? AS bin_start,
      count(*) AS cnt
    FROM capped
    GROUP BY 1, 2
    ORDER BY 1, 2
    """

    # Order of params must match the ? placeholders:
    # least(..., ?) -> cap_val
    # floor(... / ?) -> bin_size
    # * ? -> bin_size again
    agg_params = where_params + [float(cap_val), float(bin_size), float(bin_size)]

    out = run_df(agg_sql, agg_params)
    out["cap"] = float(cap_val)
    out["bin_size"] = float(bin_size)
    return out


# --------------------------------------------------
# Sidebar UI
# --------------------------------------------------
filters = load_filter_values()

with st.sidebar:
    st.header("🎛 Filters")

    if st.button("🧹 Clear cache"):
        st.cache_data.clear()
        st.success("Cache cleared. Re-run will rebuild queries.")

    show_sql = st.toggle("Show SQL (debug)", value=False)

    sel_levels = st.multiselect("Position Level", filters["position_levels"], default=filters["position_levels"])
    sel_cats = st.multiselect("Primary Category", filters["categories"],
                              default=default_primary_category(filters["categories"], "Banking and Finance"))
    sel_emp = st.multiselect("Employment Type", filters["employment_types"], default=[])
    sel_status = st.multiselect("Status", filters["statuses"], default=["Open"], help="Re-open is grouped under Open.")

    st.divider()
    st.subheader("⚡ Guardrails")
    max_detail_rows = st.slider("Max rows (detail sample)", 20_000, 300_000, 120_000, 20_000)
    salary_cap_pct = st.slider("Salary cap (percentile)", 0.80, 0.99, 0.95, 0.01)
    heatmap_bins = st.slider("Heatmap bins (Y)", 10, 120, 50, 5)

# --------------------------------------------------
# Debug SQL output if requested
# --------------------------------------------------
if show_sql:
    st.subheader("SQL Debug")
    st.dataframe(load_detail_sample(sel_levels, sel_cats, sel_emp, sel_status, max_detail_rows, debug_sql=True))
    st.dataframe(load_heatmap_agg(sel_levels, sel_cats, sel_emp, sel_status, salary_cap_pct, heatmap_bins, debug_sql=True))
    st.stop()

# --------------------------------------------------
# Load data
# --------------------------------------------------
detail_df = load_detail_sample(sel_levels, sel_cats, sel_emp, sel_status, max_detail_rows)
heat_df = load_heatmap_agg(sel_levels, sel_cats, sel_emp, sel_status, salary_cap_pct, heatmap_bins)

# --------------------------------------------------
# Violin + Box
# --------------------------------------------------
st.subheader("📦 Salary Distributions")
if detail_df.empty:
    st.info("No detail rows for current filters (sampled).")
else:
    cap_detail = detail_df["salary_mid"].quantile(salary_cap_pct)
    detail_df["salary_mid_capped"] = detail_df["salary_mid"].clip(upper=cap_detail)

    st.markdown("### 🎻 Violin: Salary by Position Level")
    fig_v = px.violin(detail_df, x="position_level", y="salary_mid_capped", box=True, points=False)
    fig_v.update_layout(height=520)
    st.plotly_chart(fig_v, use_container_width=True)

    st.divider()

    st.markdown("### 📦 Box & Whisker: Salary by Position Level")
    fig_b = px.box(detail_df, x="position_level", y="salary_mid_capped", points=False)
    fig_b.update_layout(height=520)
    st.plotly_chart(fig_b, use_container_width=True)

## --------------------------------------------------
# Heatmap + totals
# --------------------------------------------------
st.divider()
st.subheader("🔥 Heatmap: Position Level vs Salary (Binned)")

if heat_df.empty:
    st.info("No heatmap data for current filters.")
else:
    # --- pick dimension column (prefer position_level, fallback to employment_type) ---
    dim_col = "position_level" if "position_level" in heat_df.columns else "employment_type"
    if dim_col != "position_level":
        st.warning(
            "Heatmap is still using employment_type because heat_df does not contain position_level. "
            "To truly switch, ensure load_heatmap_agg returns position_level."
        )

    bin_size = float(heat_df["bin_size"].iloc[0])
    cap_val = float(heat_df["cap"].iloc[0])

    heat_df = heat_df.copy()
    heat_df["bin_end"] = heat_df["bin_start"] + bin_size
    heat_df["salary_bin"] = heat_df.apply(
        lambda r: f"{r['bin_start']:,.0f}–{min(r['bin_end'], cap_val):,.0f}",
        axis=1
    )

    # --- order dimension by total count (descending) ---
    dim_order = (
        heat_df.groupby(dim_col)["cnt"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    # --- order salary bins by bin_start (ascending) ---
    bin_order = (
        heat_df.sort_values("bin_start")["salary_bin"]
        .drop_duplicates()
        .tolist()
    )

    heat_df[dim_col] = pd.Categorical(heat_df[dim_col], categories=dim_order, ordered=True)
    heat_df["salary_bin"] = pd.Categorical(heat_df["salary_bin"], categories=bin_order, ordered=True)

    # --- heatmap plot ---
    fig_h = px.density_heatmap(
        heat_df,
        x=dim_col,
        y="salary_bin",
        z="cnt",
        histfunc="sum"
    )
    fig_h.update_layout(height=620)
    st.plotly_chart(fig_h, use_container_width=True)

    # --- totals table ---
    st.markdown(f"### 📊 Total Job Count by {dim_col.replace('_', ' ').title()} (Heatmap Basis)")
    totals_df = (
        heat_df.groupby(dim_col, observed=True)["cnt"]
        .sum()
        .reset_index(name="job_count")
        .sort_values("job_count", ascending=False)
    )

    grand_total = int(totals_df["job_count"].sum()) if not totals_df.empty else 0
    if grand_total > 0:
        totals_df["percentage"] = (totals_df["job_count"] / grand_total * 100).round(1)
    else:
        totals_df["percentage"] = 0.0

    total_row = {dim_col: "TOTAL", "job_count": grand_total, "percentage": 100.0 if grand_total > 0 else 0.0}
    totals_df = pd.concat([totals_df, pd.DataFrame([total_row])], ignore_index=True)

    st.dataframe(totals_df, use_container_width=True, hide_index=True)
