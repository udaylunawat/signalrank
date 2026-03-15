# app/pages/recruiters.py
"""
Recruiters Dashboard — Browse, search, and manage recruiter contacts.
"""

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from job_ranker.app.db import get_ui_db
from job_ranker.app.tracking import load_tracking, set_tracking

st.set_page_config(layout="wide", page_title="Recruiters")
st.title("🤝 Recruiter Contacts")

db = get_ui_db()

# ── Ensure table exists ──────────────────────────────────────────────────────
db.execute("""
    CREATE TABLE IF NOT EXISTS recruiters (
        id             TEXT PRIMARY KEY,
        company        TEXT,
        name           TEXT,
        title          TEXT,
        email          TEXT,
        guessed_emails TEXT,
        linkedin_url   TEXT,
        domain         TEXT,
        source         TEXT,
        confidence     TEXT,
        job_url        TEXT,
        job_title      TEXT,
        job_score      DOUBLE,
        found_at       TIMESTAMP
    )
""")

# ── Load data ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_recruiters():
    try:
        df = db.execute("""
            SELECT
                id, company, name, title, email,
                guessed_emails, linkedin_url, domain,
                source, confidence, job_url, job_title,
                job_score, found_at
            FROM recruiters
            ORDER BY
                CASE confidence
                    WHEN 'high'   THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low'    THEN 3
                    ELSE 4
                END,
                job_score DESC NULLS LAST,
                found_at DESC NULLS LAST
        """).df()
        return df
    except Exception:
        return pd.DataFrame()

df = load_recruiters()

if df.empty:
    st.info("No recruiter contacts yet. Run `job-ranker find-recruiter --csv <path>` to populate.")
    st.stop()

# ── Load tracking state into session (re-fetched from SQLite each page load) ─
ids = df["id"].dropna().tolist()
st.session_state["tracking_map"] = load_tracking(ids)

# ── Metrics row ──────────────────────────────────────────────────────────────
total       = len(df)
has_email   = df["email"].notna() & (df["email"] != "")
has_li      = df["linkedin_url"].notna() & (df["linkedin_url"] != "")
has_guessed = df["guessed_emails"].notna() & (df["guessed_emails"] != "")
high_conf   = (df["confidence"] == "high").sum()
companies   = df["company"].nunique()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Contacts",     total)
c2.metric("Companies",          companies)
c3.metric("High Confidence",    int(high_conf))
c4.metric("Have LinkedIn",      int(has_li.sum()))
c5.metric("Have Direct Email",  int(has_email.sum()))
c6.metric("Have Guessed Email", int(has_guessed.sum()))

st.divider()

# ── Filters ──────────────────────────────────────────────────────────────────
col_search, col_conf, col_source, col_email = st.columns([3, 1.5, 1.5, 1.5])

search_q = col_search.text_input("🔍 Search (name, company, title)", "")
conf_filter = col_conf.multiselect(
    "Confidence", ["high", "medium", "low", "none"],
    default=["high", "medium"],
)
source_filter = col_source.multiselect(
    "Source", df["source"].dropna().unique().tolist(),
    default=df["source"].dropna().unique().tolist(),
)
email_only = col_email.checkbox("Has any email", value=False)

# Apply filters
mask = pd.Series([True] * len(df), index=df.index)

if search_q:
    q = search_q.lower()
    mask &= (
        df["name"].fillna("").str.lower().str.contains(q, na=False) |
        df["company"].fillna("").str.lower().str.contains(q, na=False) |
        df["title"].fillna("").str.lower().str.contains(q, na=False)
    )
if conf_filter:
    mask &= df["confidence"].isin(conf_filter)
if source_filter:
    mask &= df["source"].isin(source_filter)
if email_only:
    mask &= (has_email | has_guessed)

filtered = df[mask].copy()

st.caption(f"Showing {len(filtered)} of {total} contacts")

# ── Table ────────────────────────────────────────────────────────────────────

def make_li_link(url):
    if pd.isna(url) or not url:
        return ""
    return f"[LinkedIn]({url})"

def fmt_score(v):
    if pd.isna(v):
        return ""
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)

def conf_badge(v):
    badges = {"high": "🟢", "medium": "🟡", "low": "🔴", "none": "⚪"}
    return f"{badges.get(v, '⚪')} {v}"

tracking_map = st.session_state.get("tracking_map", {})

display = filtered[[
    "id",  # temporary — dropped before render
    "company", "name", "title", "confidence",
    "email", "guessed_emails", "linkedin_url",
    "source", "job_title", "job_score",
]].copy()

# Build tracking columns from the id column directly
display["Applied"]   = display["id"].map(
    lambda rid: "✅" if tracking_map.get(rid, {}).get("applied") else "—"
)
display["Connected"] = display["id"].map(
    lambda rid: "✅" if tracking_map.get(rid, {}).get("connected") else "—"
)

# Drop id before rename/render
display = display.drop(columns=["id"])

display["confidence"]    = display["confidence"].apply(conf_badge)
display["linkedin_url"]  = display["linkedin_url"].apply(make_li_link)
display["job_score"]     = display["job_score"].apply(fmt_score)
display.columns = [
    "Company", "Name", "Title", "Confidence",
    "Direct Email", "Guessed Emails", "LinkedIn",
    "Source", "Job Title", "Job Score",
    "Applied", "Connected",
]

st.dataframe(
    display,
    use_container_width=True,
    height=min(600, 50 + 35 * len(display)),
    column_config={
        "LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="→ Profile"),
    },
)

# ── Per-company expandable view ───────────────────────────────────────────────
st.divider()
st.subheader("By Company")

for company, grp in filtered.groupby("company", sort=False):
    score = grp["job_score"].dropna().max()
    score_str = f"  ·  score {score:.2f}" if pd.notna(score) else ""
    high_n = (grp["confidence"] == "high").sum()
    badge = "🟢" if high_n > 0 else "🟡"
    label = f"{badge} **{company}**{score_str}  ·  {len(grp)} contact(s)"

    with st.expander(label, expanded=False):
        for _, row in grp.iterrows():
            rid = row.get("id") or ""
            tracking = st.session_state["tracking_map"].get(rid, {})

            cols = st.columns([2, 3, 2, 2, 2, 1.5, 1.5])
            cols[0].write(f"**{row.get('name') or '—'}**")
            cols[1].caption(row.get("title") or "")

            email = row.get("email") or ""
            guessed = row.get("guessed_emails") or ""
            if email:
                cols[2].code(email)
            elif guessed:
                for ge in guessed.split("|")[:3]:
                    cols[2].caption(f"~ {ge}")

            li = row.get("linkedin_url") or ""
            if li:
                cols[3].markdown(f"[→ LinkedIn]({li})")

            cols[4].caption(f"{row.get('source', '')}, {row.get('confidence', '')}")

            # Tracking checkboxes — unique keys required by Streamlit
            applied_val = cols[5].checkbox(
                "Applied", value=bool(tracking.get("applied")), key=f"applied_{rid}"
            )
            connected_val = cols[6].checkbox(
                "Connected", value=bool(tracking.get("connected")), key=f"connected_{rid}"
            )

            # Write to SQLite on change; update session state to avoid re-read
            if rid and (
                applied_val != bool(tracking.get("applied"))
                or connected_val != bool(tracking.get("connected"))
            ):
                set_tracking(rid, applied=applied_val, connected=connected_val)
                st.session_state["tracking_map"][rid] = {
                    "applied": applied_val,
                    "connected": connected_val,
                    "notes": tracking.get("notes", ""),
                    "updated_at": "",
                }

# ── Export ───────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Export")

csv_data = filtered.to_csv(index=False).encode("utf-8")
ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
st.download_button(
    "⬇️ Download filtered contacts (CSV)",
    data=csv_data,
    file_name=f"recruiters_{ts}.csv",
    mime="text/csv",
)
