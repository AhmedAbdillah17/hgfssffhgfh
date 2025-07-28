import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

# ── GOOGLE SHEETS AUTH ──────────────────────────────────────
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = dict(st.secrets["gcp_service_account"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("Task_Tracker").worksheet("Log")

# ── SETTINGS ────────────────────────────────────────────────
USERS = ["MQ", "Samo", "Bashe"]
TASKS = ["10 YouTube Comment Replies", "Market Research"]
TASKS_PER_DAY = len(TASKS)
COLS = ["Timestamp", "User", "Date"] + TASKS + ["Role", "Action"]

# ensure header row
if not sheet.get_all_values():
    sheet.append_row(COLS)

# ── HELPERS ─────────────────────────────────────────────────
def load_logs():
    df = pd.DataFrame(sheet.get_all_records())
    for c in COLS:
        if c not in df: df[c] = None
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for t in TASKS:
            df[t] = df[t].astype(str).str.lower().isin(["true","1","yes"])
    return df

def save_log(user, date, status):
    df = load_logs()
    d = pd.to_datetime(date).date()
    # drop any existing for that user+date
    if not df.empty:
        df = df[~((df["User"]==user)&(df["Date"].dt.date==d))]
    row = [
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user,
        date.strftime("%Y-%m-%d"),
        *status,
        "User",
        "Log Updated"
    ]
    df = pd.concat([df, pd.DataFrame([row], columns=COLS)], ignore_index=True)
    sheet.clear()
    sheet.update([df.columns.tolist()]+df.astype(str).values.tolist())

def fotmob(progress):
    return round(min(progress/10,10),1)

def streak(df):
    if df.empty: return 0
    d = df.sort_values("Date").drop_duplicates("Date")
    s, prev = 0, None
    for _,r in d.iterrows():
        if all(r[t] for t in TASKS):
            if prev and (r["Date"].date()-prev).days==1:
                s+=1
            else:
                s=1
            prev = r["Date"].date()
    return s

# ── SIDEBAR FILTER ──────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Settings")
    year = st.number_input("Year", value=datetime.date.today().year, step=1)
    month = st.number_input("Month", 1,12, value=datetime.date.today().month, step=1)
    logs_all = load_logs()
    if not logs_all.empty:
        st.download_button("💾 Download CSV",
                           data=logs_all.to_csv(index=False).encode(),
                           file_name="task_logs.csv")

# ── TASK LOGGER ─────────────────────────────────────────────
st.title("📊 Task Tracker")
st.subheader("✅ Log Tasks")
unlock = st.checkbox("🔓 Unlock Backfill", False)
today = datetime.date.today()
sel_date = st.date_input("Select Date", today, min_value=(None if unlock else today))
if not unlock and sel_date!=today:
    st.error("Backdating locked – enable unlock to backfill.")

for u in USERS:
    st.markdown(f"### {u}")
    c1,c2,c3 = st.columns([2,2,1])
    s1 = c1.checkbox(TASKS[0], key=f"{u}_0_{sel_date}")
    s2 = c2.checkbox(TASKS[1], key=f"{u}_1_{sel_date}")
    if c3.button("Save", key=f"btn_{u}_{sel_date}"):
        save_log(u, sel_date, [s1,s2])
        st.success(f"✅ Saved for {u}")

# ── DASHBOARD ──────────────────────────────────────────────
st.subheader(f"📈 Dashboard ({month}/{year})")
logs = load_logs()
df = logs[(logs["Date"].dt.year==year)&(logs["Date"].dt.month==month)]
if df.empty:
    st.info("No logs this month.")
else:
    first = df["Date"].min().date()
    days_active = max((today-first).days+1,1)
    max_tasks = days_active*TASKS_PER_DAY

    summary = []
    for u in USERS:
        ulog = df[df["User"]==u]
        done = int(ulog[TASKS].sum().sum()) if not ulog.empty else 0
        done = min(done, max_tasks)
        remain = max_tasks - done
        prog = (done/max_tasks)*100 if max_tasks else 0
        rating = fotmob(prog)
        summary.append({
            "User":u,
            "Tasks Done":done,
            "Remaining":remain,
            "Streak":f"🔥 {streak(ulog)}-day",
            "Rating":rating
        })

    sum_df = pd.DataFrame(summary).set_index("User")
    st.table(sum_df)  # native Streamlit table

    # Charts below...
    colA,colB = st.columns(2)
    with colA:
        fig = px.bar(sum_df.reset_index(), x="Rating", y="User", orientation="h",
                     title="Leaderboard", color="Rating",
                     color_continuous_scale=[[0,"red"],[0.6,"yellow"],[1,"green"]], range_color=[0,10])
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig2 = px.bar(sum_df.reset_index().melt(id_vars="User", value_vars=["Tasks Done","Remaining"]),
                      x="value",y="User",color="variable",barmode="group",
                      title="Done vs Remaining")
        st.plotly_chart(fig2, use_container_width=True)
