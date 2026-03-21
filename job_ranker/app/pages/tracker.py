# app/pages/tracker.py
"""
Job Tracker + Recruiter Contacts — combined pipeline dashboard.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_HERE = Path(__file__).resolve()
TRACKER_DIR = _HERE.parents[2] / "users"
ROOT = _HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_ranker.app.db import get_ui_db  # noqa: E402
from job_ranker.app.tracking import (  # noqa: E402
    load_job_tracking,
    upsert_job_tracking,
)

st.set_page_config(layout="wide", page_title="Job Tracker")

# ── constants ─────────────────────────────────────────────────────────────────
TARGET_LPA = 70

STATUS_ORDER = [
    "Offer Received", "Negotiating", "Interview Scheduled",
    "Phone Screen", "Applied", "Rejected", "Not Applied",
]

STATUS_COLORS = {
    "Offer Received":      "#22c55e",
    "Negotiating":         "#86efac",
    "Interview Scheduled": "#3b82f6",
    "Phone Screen":        "#93c5fd",
    "Applied":             "#f59e0b",
    "Rejected":            "#ef4444",
    "Not Applied":         "#94a3b8",
    "":                    "#94a3b8",
}

PRIORITY_ORDER = ["🔥 P1 - Apply Today", "⚡ P2 - Apply This Week", "📋 P3 - Low Priority"]
GMAIL_SUBJECT = "Application for {role} at {company}"
GMAIL_BODY_PLAIN = """\
Hi {name},

I came across the {role} position at {company} and wanted to reach out directly.

Job posting: {job_url}

I'm a senior ML/AI engineer with 7+ years of experience building production ML systems \
— ranging from large-scale feature platforms to LLM pipelines and recommendation engines. \
I believe my background is a strong fit for this role and would love to explore the opportunity further.

Would you be open to a quick chat or could you point me to the right person on the team?

Thank you for your time!

--
Example Candidate
(+91) 7020901969  |  examplecandidate@gmail.com
GitHub    https://github.com/examplecandidate
LinkedIn  https://linkedin.com/in/examplecandidate
Portfolio https://examplecandidate.github.io\
"""


# ── helpers ───────────────────────────────────────────────────────────────────
def _best_job_url(indeed: str, board: str) -> str:
    if board.strip():
        return board.strip()
    return indeed.strip()


def load_tracker(user: str) -> pd.DataFrame:
    path = TRACKER_DIR / user / "job_tracker.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str).fillna("")
    df["Status"] = df["Status"].str.strip().where(df["Status"].str.strip() != "", "Not Applied")
    df["System Score"]  = pd.to_numeric(df["System Score"],  errors="coerce")
    df["Resume Match %"] = pd.to_numeric(df["Resume Match %"], errors="coerce")
    df["Offer LPA"]     = pd.to_numeric(df["Offer LPA"],     errors="coerce")
    df["Indeed URL"] = df.apply(
        lambda r: _best_job_url(r["Indeed URL"], r["Company Board URL"]),
        axis=1,
    )
    return df


def extract_hyperlink(cell: str) -> tuple[str, str]:
    m = re.match(r'=HYPERLINK\("([^"]+)","([^"]+)"\)', cell.strip())
    return (m.group(2), m.group(1)) if m else (cell, "")


def _norm_company(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _norm_title(s: str) -> str:
    t = re.sub(r"\b(senior|sr|lead|staff|junior|jr)\b", "", s.lower())
    return re.sub(r"[^a-z0-9\s]", "", t).strip()


def _derive_group(location: str) -> str:
    loc = (location or "").lower()
    if any(k in loc for k in ["pune", "remote"]):
        return "Pune/Remote"
    if any(k in loc for k in ["ka", "karnataka", "bangalore", "bengaluru"]):
        return "Bangalore"
    return "Remote"


def hex_to_rgba(hex_color: str, alpha: float = 0.35) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _parse_date(val):
    if not val or pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def gmail_url(to: str, subject: str, body: str) -> str:
    import urllib.parse
    return "https://mail.google.com/mail/?" + urllib.parse.urlencode(
        {"view": "cm", "fs": "1", "to": to, "su": subject, "body": body}
    )


# ── recruiter helpers ─────────────────────────────────────────────────────────
def _parse_guessed(raw) -> list[str]:
    if pd.isna(raw) or not raw:
        return []
    return [e.strip() for e in str(raw).split("|") if e.strip()]


def _best_email(row) -> tuple[str, bool]:
    """Return (email, is_confirmed)."""
    e = (row.get("email") or "").strip()
    if e:
        return e, True
    g = _parse_guessed(row.get("guessed_emails"))
    return (g[0], False) if g else ("", False)


@st.cache_data(ttl=60)
def load_recruiter_lookup() -> dict[str, list[dict]]:
    """Return {norm_company: [recruiter_dict, ...]} ordered best-confidence-first."""
    try:
        rec_df = get_ui_db().execute("""
            SELECT company, name, title, email, guessed_emails, linkedin_url,
                   confidence, job_title
            FROM recruiters
            ORDER BY
                CASE confidence WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END
        """).df()
    except Exception:
        return {}
    lookup: dict[str, list[dict]] = {}
    for _, r in rec_df.iterrows():
        key = _norm_company(str(r.get("company") or ""))
        email, confirmed = _best_email(r)
        entry = {
            "name":      (r.get("name") or "").strip(),
            "email":     email,
            "confirmed": confirmed,
            "linkedin":  (r.get("linkedin_url") or "").strip(),
            "job_title": (r.get("job_title") or "").strip(),
            "conf":      (r.get("confidence") or "").strip(),
        }
        lookup.setdefault(key, []).append(entry)
    return lookup


def _primary_recruiter(company: str) -> dict:
    """Best (first) recruiter for a company, or empty dict."""
    return (rec_lookup.get(_norm_company(company)) or [{}])[0]


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 SignalRank")
    st.caption("AI-powered job discovery")
    st.divider()
    users = [p.name for p in TRACKER_DIR.iterdir() if p.is_dir()]
    user = st.selectbox("User", users, index=users.index("example") if "example" in users else 0)
    st.divider()
    st.markdown("**Navigate**")
    st.page_link("pages/dashboard.py", label="📊 Dashboard")
    st.page_link("pages/tracker.py",   label="📋 Job Tracker")
    st.page_link("pages/all_jobs.py",  label="🗂 All Jobs")
    st.divider()
    st.markdown(f"**Target:** {TARGET_LPA} LPA")
    sidebar_offers = st.empty()

# ── load tracker data ─────────────────────────────────────────────────────────
df = load_tracker(user)
if df.empty:
    st.error("No tracker file found.")
    st.stop()

def job_id(row: pd.Series) -> str:
    return f"{row['Company'].strip().lower()}|{row['Title'].strip().lower()}"

db_state = load_job_tracking(user)
df["_job_id"] = df.apply(job_id, axis=1)
df["Applied"]        = df["_job_id"].map(lambda jid: db_state.get(jid, {}).get("applied", False))
df["Status"]         = df["_job_id"].map(lambda jid: db_state.get(jid, {}).get("status", "Not Applied"))
df["Date Applied"]   = df["_job_id"].map(lambda jid: db_state.get(jid, {}).get("date_applied", ""))
df["Interview Date"] = df["_job_id"].map(lambda jid: db_state.get(jid, {}).get("interview_date", ""))
for idx, row in df.iterrows():
    db_lpa = db_state.get(row["_job_id"], {}).get("offer_lpa")
    if db_lpa is not None:
        df.at[idx, "Offer LPA"] = db_lpa

for _, orow in df[df["Offer LPA"].notna()].iterrows():
    jid = orow["_job_id"]
    if jid not in db_state:
        upsert_job_tracking(jid, user, applied=True, status="Offer Received",
                            notes=f"Offer: {int(orow['Offer LPA'])} LPA",
                            offer_lpa=float(orow["Offer LPA"]))
        df.loc[df["_job_id"] == jid, ["Applied", "Status"]] = [True, "Offer Received"]

# ── header ────────────────────────────────────────────────────────────────────
st.title("📋 Job Tracker")
offers_df = df[df["Offer LPA"].notna()]
best_offer = int(offers_df["Offer LPA"].max()) if not offers_df.empty else 0
offer_summary = ", ".join(f"{r['Company']} {int(r['Offer LPA'])}L" for _, r in offers_df.iterrows())
st.caption(f"Tracking {len(df)} roles · Target: **{TARGET_LPA} LPA** · Offers: {offer_summary or 'none'}")

with sidebar_offers.container():
    st.markdown("**Offers in Hand:**")
    if offers_df.empty:
        st.caption("No offers yet")
    else:
        for _, r in offers_df.iterrows():
            lpa = int(r["Offer LPA"])
            pct = lpa / TARGET_LPA
            color = "#22c55e" if lpa >= 50 else "#f59e0b"
            st.markdown(f"<span style='color:{color}'>●</span> **{r['Company']}** — {lpa} LPA", unsafe_allow_html=True)
            st.progress(pct, text=f"{pct*100:.0f}% of {TARGET_LPA}L target")

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Roles",      len(df))
c2.metric("P1 – Apply Today", (df["Priority"].str.contains("P1")).sum())
c3.metric("P2 – This Week",   (df["Priority"].str.contains("P2")).sum())
c4.metric("Offers in Hand",   len(offers_df), delta=f"+{len(offers_df)}")
c5.metric("Best Offer",       f"{best_offer} LPA")
c6.metric("Gap to Target",    f"{TARGET_LPA - best_offer} LPA",
          delta=f"-{TARGET_LPA - best_offer}" if best_offer < TARGET_LPA else "0",
          delta_color="inverse")

st.divider()

# ── Offers highlight ──────────────────────────────────────────────────────────
st.subheader("🎯 Offers in Hand")
offer_cols = st.columns(len(offers_df) + 1)
for i, (_, row) in enumerate(offers_df.iterrows()):
    lpa = int(row["Offer LPA"])
    pct = round(lpa / TARGET_LPA * 100)
    color = "#22c55e" if lpa >= 45 else "#f59e0b"
    offer_cols[i].markdown(f"""
<div style="background:{color}22;border:2px solid {color};border-radius:12px;padding:16px;text-align:center;">
<div style="font-size:1.4em;font-weight:700">{row['Company']}</div>
<div style="font-size:2em;font-weight:900;color:{color}">{lpa} LPA</div>
<div style="color:#888">{pct}% of target</div>
<div style="font-size:0.85em;margin-top:6px">{row['Title']}</div>
</div>""", unsafe_allow_html=True)
with offer_cols[-1]:
    st.markdown(f"""
<div style="background:#3b82f622;border:2px dashed #3b82f6;border-radius:12px;padding:16px;text-align:center;">
<div style="font-size:1.4em;font-weight:700">Target</div>
<div style="font-size:2em;font-weight:900;color:#3b82f6">{TARGET_LPA} LPA</div>
<div style="color:#888">100%</div>
<div style="font-size:0.85em;margin-top:6px">+{TARGET_LPA - best_offer} LPA to go</div>
</div>""", unsafe_allow_html=True)

st.divider()

# ── Sankey ────────────────────────────────────────────────────────────────────
st.subheader("🔀 Application Pipeline")

node_labels = ["All Roles", "P1 Today", "P2 Week", "P3 Low"] + STATUS_ORDER
node_idx    = {label: i for i, label in enumerate(node_labels)}
node_colors = (
    ["#64748b", "#ef4444", "#f59e0b", "#94a3b8"]
    + [STATUS_COLORS.get(s, "#94a3b8") for s in STATUS_ORDER]
)
priority_map = {
    "🔥 P1 - Apply Today":    "P1 Today",
    "⚡ P2 - Apply This Week": "P2 Week",
    "📋 P3 - Low Priority":    "P3 Low",
}

sources, targets, values, link_colors = [], [], [], []
for p_label, node_name in priority_map.items():
    cnt = (df["Priority"] == p_label).sum()
    if cnt:
        sources.append(node_idx["All Roles"])
        targets.append(node_idx[node_name])
        values.append(cnt)
        link_colors.append("rgba(100,116,139,0.3)")

for p_label, node_name in priority_map.items():
    grp = df[df["Priority"] == p_label]
    for status in STATUS_ORDER:
        cnt = (grp["Status"] == status).sum()
        if cnt:
            sources.append(node_idx[node_name])
            targets.append(node_idx[status])
            values.append(cnt)
            link_colors.append(hex_to_rgba(STATUS_COLORS.get(status, "#94a3b8")))

fig_sankey = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(pad=20, thickness=24, line=dict(color="rgba(0,0,0,0.1)", width=0.5),
              label=node_labels, color=node_colors,
              hovertemplate="%{label}: %{value}<extra></extra>"),
    link=dict(source=sources, target=targets, value=values, color=link_colors,
              hovertemplate="%{source.label} → %{target.label}: %{value}<extra></extra>"),
))
fig_sankey.update_layout(height=440, margin=dict(l=0, r=0, t=20, b=0),
                         paper_bgcolor="rgba(0,0,0,0)", font=dict(size=13))
st.plotly_chart(fig_sankey, use_container_width=True)

st.divider()

# ── Analytics ─────────────────────────────────────────────────────────────────
st.subheader("📊 Analytics")
ch1, ch2, ch3 = st.columns(3)
with ch1:
    st.markdown("**By Group / Location**")
    st.bar_chart(df.groupby("Group").size().reset_index(name="Count"), x="Group", y="Count", horizontal=True)
with ch2:
    st.markdown("**By Priority**")
    pri = df.groupby("Priority").size().reset_index(name="Count")
    pri["Priority"] = pri["Priority"].str.replace(r"[^\w\s-]", "", regex=True).str.strip()
    st.bar_chart(pri, x="Priority", y="Count", horizontal=True)
with ch3:
    st.markdown("**Score Distribution**")
    score_data = df["System Score"].dropna()
    if not score_data.empty:
        bins = [70, 75, 80, 85, 90, 95, 101]
        labels = ["70-75", "75-80", "80-85", "85-90", "90-95", "95+"]
        hist = (pd.cut(score_data, bins=bins, labels=labels, include_lowest=True)
                .value_counts().reindex(labels, fill_value=0).reset_index())
        hist.columns = ["Score Range", "Count"]
        st.bar_chart(hist, x="Score Range", y="Count")

st.divider()

# ── Salary progress ───────────────────────────────────────────────────────────
st.subheader("💰 Salary Progress")
sal1, sal2 = st.columns([2, 1])
with sal1:
    bar_data = offers_df[["Company", "Offer LPA"]].dropna().copy()
    bar_data["Offer LPA"] = bar_data["Offer LPA"].astype(int)
    fig_sal = go.Figure()
    fig_sal.add_trace(go.Bar(
        name="Offer LPA", x=bar_data["Company"], y=bar_data["Offer LPA"],
        marker_color=["#22c55e" if v >= 45 else "#f59e0b" for v in bar_data["Offer LPA"]],
        text=[f"{v} LPA" for v in bar_data["Offer LPA"]], textposition="outside",
    ))
    fig_sal.add_hline(y=TARGET_LPA, line_dash="dash", line_color="#3b82f6",
                      annotation_text=f"Target {TARGET_LPA} LPA", annotation_position="top right")
    fig_sal.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(range=[0, TARGET_LPA + 15], gridcolor="rgba(100,100,100,0.15)"),
                          showlegend=False)
    st.plotly_chart(fig_sal, use_container_width=True)
with sal2:
    for _, row in offers_df.iterrows():
        lpa = int(row["Offer LPA"])
        pct = lpa / TARGET_LPA
        st.markdown(f"**{row['Company']}** — {lpa} LPA")
        st.progress(pct, text=f"{pct*100:.0f}% of target")

st.divider()

# ── Import from pipeline ──────────────────────────────────────────────────────
with st.expander("📥 Import Top Jobs from Latest Run"):
    imp1, imp2, imp3 = st.columns(3)
    top_n           = imp1.number_input("Top N jobs", min_value=5, max_value=100, value=20, step=5)
    score_threshold = imp2.slider("Min score", min_value=60, max_value=95, value=80)
    sel_loc_groups  = imp3.multiselect("Location groups", ["Pune/Remote", "Bangalore", "All"], default=["All"])

    if st.button("Import", key="pipeline_import_btn"):
        try:
            con = get_ui_db()
            run_row = con.execute(
                "SELECT run_id FROM runs WHERE user = ? AND status = 'success' ORDER BY finished_at DESC LIMIT 1",
                [user],
            ).fetchone()
            if not run_row:
                st.warning("No successful runs found.")
            else:
                run_id_import = run_row[0]
                rows = con.execute(
                    "SELECT payload, final_score FROM run_results WHERE run_id = ? ORDER BY final_score DESC LIMIT 200",
                    [run_id_import],
                ).fetchall()
                existing_keys = {(_norm_company(r["Company"]), _norm_title(r["Title"])) for _, r in df.iterrows()}
                tracker_cols  = df.columns.tolist()
                new_rows = []
                for payload_str, final_score in rows:
                    if final_score < score_threshold:
                        continue
                    p     = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    group = _derive_group(str(p.get("location") or ""))
                    if "All" not in sel_loc_groups and group not in sel_loc_groups:
                        continue
                    ck = (_norm_company(str(p.get("company") or "")), _norm_title(str(p.get("title") or "")))
                    if ck in existing_keys:
                        continue
                    job_url = str(p.get("job_url") or "")
                    job_url_direct = str(p.get("job_url_direct") or "")
                    company_board  = job_url_direct if job_url_direct and job_url_direct != job_url else ""
                    row_dict = {c: "" for c in tracker_cols}
                    row_dict.update({
                        "Priority": "⚡ P2 - Apply This Week", "Group": group,
                        "Company": str(p.get("company") or ""), "Title": str(p.get("title") or ""),
                        "Location": str(p.get("location") or ""),
                        "System Score": round(float(final_score), 1),
                        "Resume Match %": round(float(p.get("skill_overlap") or 0) * 100),
                        "Status": "", "Indeed URL": job_url, "Company Board URL": company_board,
                        "Notes": f"Imported run {run_id_import[:8]}, tier={p.get('company_tier', '')}",
                    })
                    new_rows.append(row_dict)
                    existing_keys.add(ck)
                    if len(new_rows) >= int(top_n):
                        break
                if not new_rows:
                    st.info("No new jobs to import.")
                else:
                    st.write(f"**{len(new_rows)} new job(s) to import:**")
                    st.dataframe(
                        pd.DataFrame(new_rows)[["Priority", "Group", "Company", "Title", "Location", "System Score"]],
                        hide_index=True, use_container_width=True,
                    )
                    if st.button("Confirm & Add to Tracker", key="pipeline_import_confirm"):
                        tracker_path = TRACKER_DIR / user / "job_tracker.csv"
                        combined = pd.concat([pd.read_csv(tracker_path, dtype=str).fillna(""),
                                              pd.DataFrame(new_rows)], ignore_index=True)
                        combined.to_csv(tracker_path, index=False)
                        st.success(f"Added {len(new_rows)} jobs to tracker")
                        st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

st.divider()

# ── All Roles table ───────────────────────────────────────────────────────────
st.subheader("📋 All Roles")
st.caption("Edit **Applied** and **Status** inline — changes auto-save to the tracking DB.")

fc1, fc2, fc3 = st.columns(3)
sel_priority = fc1.multiselect("Priority", PRIORITY_ORDER, default=PRIORITY_ORDER)
sel_status   = fc2.multiselect("Status", STATUS_ORDER, default=STATUS_ORDER)
all_groups   = sorted(df["Group"].unique().tolist())
sel_group    = fc3.multiselect("Group", all_groups, default=all_groups)

filt = df[
    df["Priority"].isin(sel_priority) &
    df["Status"].isin(sel_status) &
    df["Group"].isin(sel_group)
].copy()

filt[["Recruiter", "Recruiter URL"]] = filt["Referral Contact"].apply(
    lambda x: pd.Series(extract_hyperlink(x))
)

# ── Merge recruiter DB data by company ───────────────────────────────────────
rec_lookup = load_recruiter_lookup()

display = filt[[
    "_job_id", "Priority", "Group", "Company", "Title", "Location",
    "System Score", "Resume Match %", "Applied", "Status",
    "Date Applied", "Interview Date", "Offer LPA",
    "Indeed URL", "Recruiter", "Recruiter URL", "Notes",
]].rename(columns={
    "System Score": "Score", "Resume Match %": "Match %",
    "Indeed URL": "Apply", "Recruiter URL": "Recruiter LinkedIn",
})
display["Priority"]       = display["Priority"].str.extract(r"(P\d)")
display["Date Applied"]   = display["Date Applied"].apply(_parse_date)
display["Interview Date"] = display["Interview Date"].apply(_parse_date)
display["Offer LPA"]      = pd.to_numeric(display["Offer LPA"], errors="coerce")


def _all_names_label(company: str) -> str:
    recs = rec_lookup.get(_norm_company(company), [])
    names = [r.get("name") or "" for r in recs if r.get("name")]
    return ", ".join(names) if names else ""


def _rec_linkedin_all(company: str, csv_url: str, csv_name: str) -> str:
    r = _primary_recruiter(company)
    url = r.get("linkedin", "") or csv_url
    if not url:
        return ""
    label = _all_names_label(company) or r.get("name", "") or csv_name
    return f"{url}#{label}"


def _rec_gmail_link(company: str, job_title: str, job_url: str) -> str:
    r = _primary_recruiter(company)
    email = r.get("email", "")
    if not email:
        return ""
    name = r.get("name") or "there"
    role = job_title or r.get("job_title") or "open role"
    url = gmail_url(
        email,
        GMAIL_SUBJECT.format(role=role, company=company),
        GMAIL_BODY_PLAIN.format(name=name, role=role, company=company, job_url=job_url or "—"),
    )
    label = _all_names_label(company) or name
    return f"{url}#{label}"


display["Recruiter LinkedIn"] = display.apply(
    lambda r: _rec_linkedin_all(r["Company"], r["Recruiter LinkedIn"], r["Recruiter"]), axis=1
)
display["Recruiter Gmail"] = display.apply(
    lambda r: _rec_gmail_link(r["Company"], r["Title"], r["Apply"]), axis=1
)
display = display.drop(columns=["Recruiter"])

edited = st.data_editor(
    display,
    hide_index=True,
    use_container_width=True,
    column_config={
        "_job_id":            None,
        "Apply":              st.column_config.LinkColumn("Apply",           display_text="Apply ↗"),
        "Recruiter LinkedIn": st.column_config.LinkColumn("Recruiters",      display_text=r"#(.+)$"),
        "Recruiter Gmail":    st.column_config.LinkColumn("Email Recruiter", display_text=r"#(.+)$"),
        "Score":              st.column_config.NumberColumn("Score",   format="%.1f"),
        "Match %":            st.column_config.NumberColumn("Match %", format="%d%%"),
        "Offer LPA":          st.column_config.NumberColumn("Offer LPA", min_value=0, max_value=500, step=1, format="%d LPA"),
        "Applied":            st.column_config.CheckboxColumn("Applied",  default=False),
        "Status":             st.column_config.SelectboxColumn("Status",  options=STATUS_ORDER, required=True),
        "Date Applied":       st.column_config.DateColumn("Date Applied"),
        "Interview Date":     st.column_config.DateColumn("Interview Date"),
    },
    disabled=["Priority", "Group", "Company", "Title", "Location",
              "Score", "Match %", "Apply", "Recruiter LinkedIn", "Recruiter Gmail"],
    height=600,
    key="job_tracker_editor",
)

if edited is not None:
    current_db = load_job_tracking(user)
    changed = 0
    for _, erow in edited.iterrows():
        jid = erow["_job_id"]
        orig = current_db.get(jid, {})
        new_applied   = bool(erow["Applied"])
        new_status    = str(erow["Status"])
        if new_applied and new_status == "Not Applied":
            new_status = "Applied"
        elif not new_applied and new_status == "Applied":
            new_status = "Not Applied"
        new_date      = str(erow["Date Applied"])   if erow["Date Applied"]   is not None else ""
        new_interview = str(erow["Interview Date"]) if erow["Interview Date"] is not None else ""
        new_notes     = str(erow.get("Notes", ""))
        new_offer     = float(erow["Offer LPA"]) if pd.notna(erow.get("Offer LPA")) else None
        if (orig.get("applied") != new_applied or orig.get("status") != new_status
                or orig.get("date_applied") != new_date or orig.get("interview_date") != new_interview
                or orig.get("offer_lpa") != new_offer):
            upsert_job_tracking(jid, user, new_applied, new_status, new_date, new_interview, new_notes, offer_lpa=new_offer)
            changed += 1
    if changed:
        st.toast(f"Saved {changed} change(s)", icon="✅")
        st.session_state.pop("job_tracker_editor", None)
        st.rerun()

st.caption(f"Showing {len(filt)} / {len(df)} roles · DB: `{Path.home() / '.job_ranker' / 'tracking.db'}`")

st.divider()

# ── Recruiter Contacts ────────────────────────────────────────────────────────
st.subheader("👤 Recruiter Contacts")

_visible_companies = filt["Company"].dropna().unique().tolist()
_rec_rows = []
for _company in sorted(_visible_companies):
    for _rec in rec_lookup.get(_norm_company(_company), []):
        _rec_rows.append({
            "Company":    _company,
            "Name":       _rec.get("name") or "",
            "Title":      _rec.get("job_title") or "",
            "LinkedIn":   _rec.get("linkedin") or "",
            "Email":      _rec.get("email") or "",
            "Confidence": _rec.get("conf") or "",
        })

if _rec_rows:
    _rec_df = pd.DataFrame(_rec_rows)
    st.caption(f"{len(_rec_df)} recruiter contact(s) across {_rec_df['Company'].nunique()} companies")
    _rec_filter = st.multiselect(
        "Filter by company", sorted(_rec_df["Company"].unique()), key="rec_company_filter"
    )
    if _rec_filter:
        _rec_df = _rec_df[_rec_df["Company"].isin(_rec_filter)]
    st.dataframe(
        _rec_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="Profile ↗"),
            "Email":    st.column_config.TextColumn("Email"),
        },
        height=min(40 + len(_rec_df) * 35, 500),
    )
else:
    st.info("No recruiter contacts found yet. Run `job-ranker find-recruiter --csv job_ranker/users/example/job_tracker.csv --top 33` to populate.")

st.divider()

# ── Email Composer (disabled) ─────────────────────────────────────────────────
# st.subheader("✉ Email Composer")
st.caption(
    "Select a company and role · Pick a recruiter · Preview the formatted email · Open in Gmail"
)

# comp_companies = sorted(filt["Company"].dropna().unique().tolist())
# ec1, ec2 = st.columns([2, 2])
# sel_company = ec1.selectbox("Company", comp_companies, key="comp_company")
# ... (email composer disabled — use the Recruiter Contacts table above)
