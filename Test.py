import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------
# CONFIG
# ---------------------
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

# ---------------------
# DARK MODE
# ---------------------
dark_mode = st.sidebar.checkbox("🌙 Dark Mode", value=False)
if dark_mode:
    st.markdown("""
        <style>
        body { background-color: #121212; color: white; }
        .stButton>button { background-color: #333; color: white; border: 1px solid white; }
        </style>
    """, unsafe_allow_html=True)

# ---------------------
# GOOGLE SHEETS AUTH
# ---------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = dict(st.secrets["gcp_service_account"])
creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "Task_Tracker"
sheet = client.open(SHEET_NAME).worksheet("Log")

# Ensure header
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["Timestamp", "User", "Date", "Task1", "Task2", "Role", "Action"])

# ---------------------
# USERS & TASKS
# ---------------------
USERS = ["MQ", "Samo", "Bashe"]
TASK_1 = "10 YouTube Comment Replies"
TASK_2 = "Market Research"
TASKS_PER_DAY = 2

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    df = pd.DataFrame(sheet.get_all_records())
    return df if not df.empty else pd.DataFrame(columns=["Timestamp", "User", "Date", "Task1", "Task2", "Role", "Action"])

def save_log(user, date, t1, t2):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role = "User"
    sheet.append_row([timestamp, user, str(date), t1, t2, role, "Log Added"])

# ---------------------
# SIDEBAR SETTINGS
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12, value=datetime.date.today().month, step=1)

    st.markdown("---")
    logs_df_all = load_logs()
    if not logs_df_all.empty:
        st.download_button("💾 Download Data", logs_df_all.to_csv(index=False).encode('utf-8'), "task_logs.csv", "text/csv")

# ---------------------
# MAIN TITLE
# ---------------------
st.title("📊 Task Tracker")
selected_date = st.date_input("Select Date", value=datetime.date.today())

# ---------------------
# TASK ENTRY (Multi-User)
# ---------------------
st.subheader("✅ Log Tasks")

for user in USERS:
    st.write(f"### {user}")
    col1, col2, col3 = st.columns([2, 2, 1])
    t1 = col1.checkbox(TASK_1, key=f"{user}_t1")
    t2 = col2.checkbox(TASK_2, key=f"{user}_t2")
    if col3.button("Save", key=f"{user}_save"):
        save_log(user, selected_date, t1, t2)
        st.success(f"✅ Saved for {user}")
        if t1 and t2:
            st.balloons()

# ---------------------
# DASHBOARD
# ---------------------
st.markdown(f"## 📈 Dashboard ({selected_month}/{selected_year})")
logs_df = load_logs()

if logs_df.empty:
    st.info("No logs yet.")
else:
    logs_df["Date"] = pd.to_datetime(logs_df["Date"], errors="coerce")
    logs_df = logs_df.dropna(subset=["Date"])
    logs_df_filtered = logs_df[(logs_df["Date"].dt.year == selected_year) & (logs_df["Date"].dt.month == selected_month)]

    if logs_df_filtered.empty:
        st.warning("No data for this month.")
    else:
        start_date = logs_df_filtered["Date"].min().date()
        today = datetime.date.today()
        days_in_range = (today - start_date).days + 1

        summary = []
        for user in USERS:
            user_logs = logs_df_filtered[logs_df_filtered["User"] == user]
            completed = (user_logs["Task1"].astype(bool).sum() + user_logs["Task2"].astype(bool).sum())
            missed = (days_in_range * TASKS_PER_DAY) - completed
            progress = (completed / (days_in_range * TASKS_PER_DAY)) * 100 if days_in_range > 0 else 0
            days_100 = sum((row.Task1 and row.Task2) for _, row in user_logs.iterrows())
            summary.append({"User": user, "Days 100%": days_100, "Tasks Done": completed, "Remaining": missed, "Progress %": round(progress, 1), "Rating": round(progress / 10, 1), "XP": completed * 10})

        summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
        st.dataframe(summary_df, use_container_width=True)

        col1, col2 = st.columns([2, 2])
        with col1:
            st.plotly_chart(px.bar(summary_df, x="Progress %", y="User", orientation="h", title="Leaderboard", color="Progress %", color_continuous_scale="Blues"), use_container_width=True)
        with col2:
            st.markdown("### 🍩 Completed vs Remaining per User")
            for user in USERS:
                u = next((item for item in summary if item["User"] == user), None)
                if u:
                    st.plotly_chart(px.pie(values=[u["Tasks Done"], u["Remaining"]], names=["Completed", "Remaining"], hole=0.6, title=user), use_container_width=True)
