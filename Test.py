import streamlit as st
import pandas as pd
import datetime
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
    dict(st.secrets["gcp_service_account"]),
    scopes=scope
)
client = gspread.authorize(creds)
sheet  = client.open("Task_Tracker").worksheet("Log")

# ── CONSTANTS ───────────────────────────────────────────────
USERS         = ["MQ", "Samo", "Bashe"]
TASKS         = ["10 YouTube Comment Replies", "Market Research"]
TASKS_PER_DAY = len(TASKS)
COLS          = ["Timestamp", "User", "Date"] + TASKS + ["Role", "Action"]

# ensure header
if not sheet.get_all_values():
    sheet.append_row(COLS)

# ── HELPERS ─────────────────────────────────────────────────
def load_logs():
    data = sheet.get_all_records()
    df   = pd.DataFrame(data)

    # make sure every column exists
    for c in COLS:
        if c not in df:
            df[c] = None

    if not df.empty:
        # parse everything as real datetime
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Date"]      = pd.to_datetime(df["Date"],      errors="coerce")

        # fill any missing Date with the normalized Timestamp
        mask = df["Date"].isna() & df["Timestamp"].notna()
        df.loc[mask, "Date"] = df.loc[mask, "Timestamp"].dt.normalize()

        # convert task flags into booleans
        for t in TASKS:
            df[t] = df[t].astype(str).str.lower().isin(["true","1","yes"])

    return df

def save_log(user, date, status):
    df = load_logs()
    d  = pd.to_datetime(date)

    # drop existing for that user+date
    if not df.empty:
        df = df[~((df.User==user) & (df.Date.dt.date==d.date()))]

    row = [
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user,
        d.strftime("%Y-%m-%d"),
        *status,
        "User",
        "Log Updated",
    ]
    df = pd.concat([df, pd.DataFrame([row], columns=COLS)], ignore_index=True)

    # write back
    sheet.clear()
    sheet.update([df.columns.tolist()] + df.astype(str).values.tolist())

def fotmob(progress):
    return round(min(progress/10, 10), 1)

def streak(user_df):
    if user_df.empty:
        return 0
    uniq = user_df.sort_values("Date").drop_duplicates("Date")
    s, prev, best = 0, None, 0
    for _, r in uniq.iterrows():
        if all(r[t] for t in TASKS):
            if prev and (r.Date.date()-prev).days==1:
                s += 1
            else:
                s = 1
            prev = r.Date.date()
            best = max(best, s)
    return best

# ── SIDEBAR FILTER ─────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Settings")
    sel_year  = st.number_input("Year",  value=datetime.date.today().year, step=1)
    sel_month = st.number_input("Month", 1,12, value=datetime.date.today().month, step=1)

    logs_all = load_logs()
    if not logs_all.empty:
        st.download_button(
            "💾 Download CSV",
            data=logs_all.to_csv(index=False).encode("utf-8"),
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
    st.error("⛔ Backdating is locked. Enable unlock to choose another date.")

for u in USERS:
    st.markdown(f"### {u}")
    c1,c2,c3 = st.columns([2,2,1])
    s1 = c1.checkbox(TASKS[0], key=f"{u}_0_{sel_date}")
    s2 = c2.checkbox(TASKS[1], key=f"{u}_1_{sel_date}")
    if c3.button("Save", key=f"btn_{u}_{sel_date}"):
        save_log(u, sel_date, [s1,s2])
        st.success(f"✅ Logged for {u}")

# ── DASHBOARD ──────────────────────────────────────────────
st.subheader(f"📈 Dashboard ({sel_month}/{sel_year})")
logs = load_logs()

# drop any rows where Date truly could not parse
logs = logs.dropna(subset=["Date"])

# now safe to do .dt.year / .dt.month
mth = logs[
    (logs.Date.dt.year == sel_year) &
    (logs.Date.dt.month== sel_month)
]

if mth.empty:
    st.info("No logs for this month.")
else:
    first_day = mth.Date.min().date()
    days      = (today_date - first_day).days + 1
    max_tasks = days * TASKS_PER_DAY

    rows = []
    for u in USERS:
        udf    = mth[mth.User==u]
        done   = int(udf[TASKS].sum().sum()) if not udf.empty else 0
        done   = min(done, max_tasks)
        missed = max(max_tasks - done, 0)
        prog   = (done/max_tasks)*100 if max_tasks else 0
        rows.append({
            "User":       u,
            "Tasks Done": done,
            "Remaining":  missed,
            "Streak":     f"🔥 {streak(udf)}-day",
            "Rating":     fotmob(prog),
        })

    summary_df = pd.DataFrame(rows).set_index("User")
    st.table(summary_df)

    # two clean charts
    cA, cB = st.columns(2)
    with cA:
        fig = px.bar(
            summary_df.reset_index(),
            x="Rating", y="User",
            orientation="h",
            color="Rating",
            color_continuous_scale=[[0,"red"],[0.6,"yellow"],[1,"green"]],
            range_color=[0,10],
            title="🏆 Leaderboard"
        )
        st.plotly_chart(fig, use_container_width=True)
    with cB:
        fig2 = px.bar(
            summary_df.reset_index().melt(
                id_vars="User",
                value_vars=["Tasks Done","Remaining"]
            ),
            x="value", y="User",
            color="variable",
            barmode="group",
            title="✅ Done vs ❌ Remaining"
        )
        st.plotly_chart(fig2, use_container_width=True)
