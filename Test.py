import streamlit as st
import pandas as pd
import datetime
import calendar
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

# ── GOOGLE SHEETS AUTH ──────────────────────────────────────
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_info(
    dict(st.secrets["gcp_service_account"]), scopes=scope
)
client = gspread.authorize(creds)
sheet  = client.open("Task_Tracker").worksheet("Log")

# ── CONSTANTS ───────────────────────────────────────────────
USERS         = ["MQ", "Samo", "Bashe"]
TASKS         = ["10 YouTube Comment Replies", "Market Research"]
TASKS_PER_DAY = len(TASKS)
COLS          = ["Timestamp", "User", "Date"] + TASKS + ["Role", "Action"]

# ── ENSURE HEADER ROW EXISTS ─────────────────────────────────
try:
    existing = sheet.get_all_values()
except gspread.exceptions.APIError:
    existing = []
if not existing:
    sheet.append_row(COLS)

# ── HELPERS ─────────────────────────────────────────────────
def load_logs() -> pd.DataFrame:
    """Fetch all rows, normalize types, fill missing Date from Timestamp."""
    df = pd.DataFrame(sheet.get_all_records())
    for c in COLS:
        if c not in df:
            df[c] = None

    if not df.empty:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Date"]      = pd.to_datetime(df["Date"],      errors="coerce")
        # any row where Date failed, backfill from Timestamp
        mask = df["Date"].isna() & df["Timestamp"].notna()
        df.loc[mask, "Date"] = df.loc[mask, "Timestamp"].dt.normalize()
        # boolify task columns
        for t in TASKS:
            df[t] = df[t].astype(str).str.lower().isin(["true", "1", "yes"])
    return df

def save_log(user: str, sel_date: datetime.date, status: list[bool]) -> None:
    """Insert or overwrite a single user/date combination."""
    df = load_logs()
    d  = pd.to_datetime(sel_date)
    # drop any existing for that user+date
    if not df.empty:
        df = df[~((df.User==user) & (df.Date.dt.date==d.date()))]

    new_row = [
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user,
        d.strftime("%Y-%m-%d"),
        *status,
        "User",
        "Log Updated"
    ]
    df = pd.concat([df, pd.DataFrame([new_row], columns=COLS)], ignore_index=True)

    # rewrite entire sheet in one go
    sheet.clear()
    sheet.update([df.columns.tolist()] + df.astype(str).values.tolist())

def fotmob_rating(percentage: float) -> float:
    """Scale 0–100% down to 0–10."""
    return round(min(percentage/10, 10), 1)

def compute_streak(user_df: pd.DataFrame) -> int:
    """Duolingo-style streak: consecutive full-task days."""
    if user_df.empty:
        return 0
    uniq = user_df.sort_values("Date").drop_duplicates("Date")
    best = 0
    cur  = 0
    prev = None
    for _, r in uniq.iterrows():
        if all(r[t] for t in TASKS):
            today = r.Date.date()
            if prev and (today - prev).days == 1:
                cur += 1
            else:
                cur = 1
            prev  = today
            best  = max(best, cur)
    return best

# ── SIDEBAR FILTER ─────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Settings")
    sel_year  = st.number_input("Year",  value=datetime.date.today().year, step=1)
    sel_month = st.number_input("Month", 1,12, value=datetime.date.today().month, step=1)

    full = load_logs()
    if not full.empty:
        st.download_button(
            "💾 Download CSV",
            data=full.to_csv(index=False).encode("utf-8"),
            file_name="task_logs.csv",
            mime="text/csv"
        )

# ── LOGGING UI ─────────────────────────────────────────────
st.title("📊 Task Tracker")
st.subheader("✅ Log Tasks")

unlock     = st.checkbox("🔓 Unlock Backfill Mode", value=False)
today_date = datetime.date.today()
min_date   = None if unlock else today_date
sel_date   = st.date_input("Select Date", value=today_date, min_value=min_date)

if not unlock and sel_date != today_date:
    st.error("⛔ Backdating locked. Toggle unlock to choose another date.")

for u in USERS:
    st.markdown(f"### {u}")
    c1,c2,c3 = st.columns([2,2,1])
    s1 = c1.checkbox(TASKS[0], key=f"{u}_0_{sel_date}")
    s2 = c2.checkbox(TASKS[1], key=f"{u}_1_{sel_date}")
    if c3.button("Save", key=f"save_{u}_{sel_date}"):
        save_log(u, sel_date, [s1, s2])
        st.success(f"✅ Logged for {u}")

# ── DASHBOARD ──────────────────────────────────────────────
st.subheader(f"📈 Dashboard ({sel_month}/{sel_year})")

logs = load_logs().dropna(subset=["Date"])
month_logs = logs[
    (logs.Date.dt.year  == sel_year) &
    (logs.Date.dt.month == sel_month)
]

if month_logs.empty:
    st.info("No logs for this month.")
else:
    # compute number of days we want to measure against:
    # if viewing current month, use today.day
    # otherwise use full days in that month
    if sel_year == today_date.year and sel_month == today_date.month:
        days_count = today_date.day
    else:
        days_count = calendar.monthrange(sel_year, sel_month)[1]

    max_tasks = days_count * TASKS_PER_DAY

    summary = []
    for u in USERS:
        udf    = month_logs[month_logs.User==u]
        done   = int(udf[TASKS].sum(axis=1).sum())  # total tasks checked
        done   = min(done, max_tasks)
        missed = max(max_tasks - done, 0)
        pct    = (done / max_tasks) * 100 if max_tasks else 0
        summary.append({
            "User":       u,
            "Tasks Done": done,
            "Remaining":  missed,
            "Streak":     f"🔥 {compute_streak(udf)}-day",
            "Rating":     fotmob_rating(pct),
        })

    df_summary = pd.DataFrame(summary).set_index("User")
    st.table(df_summary)

    # Charts
    cA, cB = st.columns(2)
    with cA:
        fig = px.bar(
            df_summary.reset_index(),
            x="Rating", y="User",
            orientation="h",
            color="Rating",
            color_continuous_scale=[[0,"red"],[0.6,"yellow"],[1,"green"]],
            range_color=[0,10],
            title="🏆 Leaderboard"
        )
        st.plotly_chart(fig, use_container_width=True)

    with cB:
        tidy = (
            df_summary
            .reset_index()
            .melt(id_vars="User", value_vars=["Tasks Done","Remaining"])
        )
        fig2 = px.bar(
            tidy,
            x="value", y="User",
            color="variable",
            barmode="group",
            title="✅ Done vs ❌ Remaining"
        )
        st.plotly_chart(fig2, use_container_width=True)
