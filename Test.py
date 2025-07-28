import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------
# PAGE CONFIG
# ---------------------
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

# ---------------------
# GOOGLE SHEETS AUTH
# ---------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = dict(st.secrets["gcp_service_account"])
creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "Task_Tracker"
sheet = client.open(SHEET_NAME).worksheet("Log")

# ---------------------
# SETTINGS
# ---------------------
USERS = ["MQ", "Samo", "Bashe"]
TASKS = ["10 YouTube Comment Replies", "Market Research"]
TASKS_PER_DAY = len(TASKS)
REQUIRED_COLUMNS = ["Timestamp", "User", "Date"] + TASKS + ["Role", "Action"]
GRACE_DAYS = 2  # Global grace period for missed calculation

# Ensure headers exist
if len(sheet.get_all_values()) == 0:
    sheet.append_row(REQUIRED_COLUMNS)

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for t in TASKS:
            df[t] = df[t].astype(str).str.lower().isin(["true", "1", "yes"])
    return df

def save_log(user, date, task_status, action="Log Updated"):
    logs = load_logs()
    date = pd.to_datetime(date)
    if not logs.empty:
        logs = logs[~((logs["User"] == user) & (logs["Date"].dt.date == date.date()))]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_values = [timestamp, user, date.strftime("%Y-%m-%d")] + task_status + ["User", action]
    new_row = pd.DataFrame([row_values], columns=REQUIRED_COLUMNS)
    logs = pd.concat([logs, new_row], ignore_index=True)
    sheet.clear()
    sheet.update([logs.columns.tolist()] + logs.astype(str).values.tolist())

def calculate_fotmob_rating(progress):
    return round(min(progress / 10, 10), 1)

def calculate_streak(user_logs):
    if user_logs.empty:
        return 0
    user_logs = user_logs.sort_values(by="Date").drop_duplicates(subset="Date")
    streak = 0
    max_streak = 0
    prev = None
    for _, row in user_logs.iterrows():
        if all(row[t] for t in TASKS):
            if prev and (row["Date"].date() - prev).days == 1:
                streak += 1
            else:
                streak = 1
            prev = row["Date"].date()
            max_streak = max(max_streak, streak)
    return max_streak

def color_for_rating(val):
    return '#28a745' if val >= 7 else '#ffc107' if val >= 4 else '#dc3545'

# ---------------------
# SIDEBAR FILTER
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12,
                                     value=datetime.date.today().month, step=1)

    logs_df_all = load_logs()
    if not logs_df_all.empty:
        st.download_button("💾 Download Data",
                           data=logs_df_all.to_csv(index=False).encode('utf-8'),
                           file_name="task_logs.csv", mime="text/csv")

# ---------------------
# LOG TASKS
# ---------------------
st.title("📊 Task Tracker")
st.subheader("✅ Log Tasks")

unlock = st.checkbox("🔓 Unlock Backfill Mode", value=False)
today = datetime.date.today()
selected_date = st.date_input("Select Date", value=today, min_value=today if not unlock else None)

if not unlock and selected_date != today:
    st.error("Backdating is locked. Enable unlock to choose another date.")

for user in USERS:
    st.markdown(f"### {user}")
    col1, col2, col3 = st.columns([2, 2, 1])
    task_status = [col1.checkbox(TASKS[0], key=f"{user}_0_{selected_date}"),
                   col2.checkbox(TASKS[1], key=f"{user}_1_{selected_date}")]
    if col3.button("Save", key=f"save_{user}_{selected_date}"):
        save_log(user, selected_date, task_status)
        st.success(f"✅ Log updated for {user}")

# ---------------------
# DASHBOARD
# ---------------------
st.subheader(f"📈 Dashboard ({selected_month}/{selected_year})")
logs_df_filtered = logs_df_all[(logs_df_all["Date"].dt.year == selected_year) &
                                (logs_df_all["Date"].dt.month == selected_month)]

if logs_df_filtered.empty:
    st.info("No logs yet for this month.")
else:
    summary = []
    global_first_log = logs_df_all["Date"].min().date() if not logs_df_all.empty else today

    for user in USERS:
        user_logs = logs_df_filtered[logs_df_filtered["User"] == user].copy()
        if user_logs.empty:
            completed, missed, rating, streak = 0, 0, 0, 0
        else:
            active_days = max((today - global_first_log).days + 1 - GRACE_DAYS, 1)
            completed = int(user_logs[TASKS].sum(axis=1).sum())
            theoretical_max = active_days * TASKS_PER_DAY
            completed = min(completed, theoretical_max)
            missed = max(theoretical_max - completed, 0)
            progress = (completed / theoretical_max) * 100 if theoretical_max > 0 else 0
            rating = calculate_fotmob_rating(progress)
            streak = calculate_streak(user_logs)
        summary.append({"User": user, "Tasks Done": completed, "Remaining": missed,
                        "Streak": f"🔥 {streak}-day", "Rating": rating})

    summary_df = pd.DataFrame(summary).sort_values(by="Rating", ascending=False)

    # KPIs
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("🏆 Best Performer", summary_df.iloc[0]["User"])
    col_kpi2.metric("📊 Avg Rating", f"{summary_df['Rating'].mean():.1f}")
    col_kpi3.metric("✅ Total Done", int(summary_df["Tasks Done"].sum()))
    col_kpi4.metric("❌ Total Missed", int(summary_df["Remaining"].sum()))

    # Custom HTML Table
    table_html = """
    <style>
        table {width:100%; border-collapse: collapse; margin-top:10px;}
        th, td {padding:10px; text-align:center; border-bottom:1px solid #444;}
        th {background:#222; color:#fff;}
    </style>
    <table>
        <tr>
            <th>User</th><th>Tasks Done</th><th>Remaining</th><th>Streak</th><th>Rating</th>
        </tr>
    """
    for _, row in summary_df.iterrows():
        color = color_for_rating(row["Rating"])
        table_html += f"""
        <tr>
            <td>{row['User']}</td>
            <td>{row['Tasks Done']}</td>
            <td>{row['Remaining']}</td>
            <td>{row['Streak']}</td>
            <td style="background:{color};color:white;font-weight:bold;">{row['Rating']:.1f}</td>
        </tr>
        """
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # Charts
    col1, col2 = st.columns([2, 2])
    with col1:
        st.plotly_chart(px.bar(summary_df, x="Rating", y="User", orientation="h",
                               title="Leaderboard (Rating)", color="Rating",
                               color_continuous_scale=[[0, "red"], [0.6, "yellow"], [1, "green"]],
                               range_color=[0, 10]), use_container_width=True)
    with col2:
        st.plotly_chart(px.bar(summary_df.melt(id_vars="User", value_vars=["Tasks Done", "Remaining"]),
                               x="value", y="User", color="variable", barmode="group",
                               title="Tasks Done vs Remaining"), use_container_width=True)

    # Daily Trend
    daily_df = logs_df_filtered.copy()
    daily_df["Day"] = daily_df["Date"].dt.date
    daily_df["Completed Tasks"] = daily_df[TASKS].sum(axis=1)
    trend_df = daily_df.groupby(["Day", "User"])["Completed Tasks"].sum().reset_index()
    st.plotly_chart(px.line(trend_df, x="Day", y="Completed Tasks", color="User",
                             title="📈 Daily Task Completion Trend", markers=True), use_container_width=True)

    # Task Distribution Pie
    total_tasks = {t: logs_df_filtered[t].sum() for t in TASKS}
    st.plotly_chart(px.pie(names=list(total_tasks.keys()), values=list(total_tasks.values()),
                           title="📊 Task Distribution"), use_container_width=True)
