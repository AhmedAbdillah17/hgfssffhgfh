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
ROLES = {u: "User" for u in USERS}
TASKS = ["10 YouTube Comment Replies", "Market Research"]
TASKS_PER_DAY = len(TASKS)
REQUIRED_COLUMNS = ["Timestamp", "User", "Date"] + TASKS + ["Role", "Action"]

# Ensure headers
if len(sheet.get_all_values()) == 0:
    sheet.append_row(REQUIRED_COLUMNS)

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    """Load logs and normalize datatypes."""
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
    """Overwrite or insert entry for a specific user and date."""
    logs = load_logs()
    date = pd.to_datetime(date)

    # Remove existing log for same user/date
    if not logs.empty:
        logs = logs[~((logs["User"] == user) & (logs["Date"].dt.date == date.date()))]

    # Add new entry
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role = ROLES.get(user, "User")
    row_values = [timestamp, user, date.strftime("%Y-%m-%d")] + task_status + [role, action]

    new_row = pd.DataFrame([row_values], columns=REQUIRED_COLUMNS)
    logs = pd.concat([logs, new_row], ignore_index=True)

    # Update Google Sheet
    sheet.clear()
    sheet.update([logs.columns.tolist()] + logs.astype(str).values.tolist())


def get_filtered_logs(year, month):
    logs_df = load_logs()
    if logs_df.empty:
        return logs_df
    logs_df = logs_df.dropna(subset=["Date"])
    return logs_df[(logs_df["Date"].dt.year == year) & (logs_df["Date"].dt.month == month)]


def calculate_fotmob_rating(progress):
    """Convert progress (0-100%) to FotMob-style rating (0-10)."""
    rating = (progress / 10)  # Scale
    return round(min(rating, 10), 1)


def calculate_streak(user_logs):
    """Calculate Duolingo-style streak (consecutive days with full completion)."""
    if user_logs.empty:
        return 0
    user_logs = user_logs.sort_values(by="Date")
    streak = 0
    max_streak = 0
    previous_date = None
    for _, row in user_logs.iterrows():
        if all(row[t] for t in TASKS):  # Full day completion
            if previous_date and (row["Date"].date() - previous_date).days == 1:
                streak += 1
            else:
                streak = 1
            previous_date = row["Date"].date()
            max_streak = max(max_streak, streak)
        else:
            previous_date = None
            streak = 0
    return max_streak


# ---------------------
# SIDEBAR FILTERS
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12,
                                     value=datetime.date.today().month, step=1)

    logs_df_all = load_logs()
    if not logs_df_all.empty:
        st.download_button(
            label="💾 Download Data",
            data=logs_df_all.to_csv(index=False).encode('utf-8'),
            file_name="task_logs.csv",
            mime="text/csv"
        )

# ---------------------
# LOG TASKS
# ---------------------
st.title("📊 Task Tracker")
st.subheader("✅ Log Today's Tasks")

today_date = datetime.date.today()

# Restrict logging to today's date
selected_date = today_date
st.info(f"Logging is allowed for today only: **{today_date}**")

for user in USERS:
    st.markdown(f"### {user}")
    col1, col2, col3 = st.columns([2, 2, 1])
    task_status = []
    for i, task in enumerate(TASKS):
        task_status.append(col1.checkbox(task, key=f"{user}_{i}_{selected_date}")) if i == 0 else task_status.append(
            col2.checkbox(task, key=f"{user}_{i}_{selected_date}"))
    if col3.button("Save", key=f"save_{user}_{selected_date}"):
        save_log(user, selected_date, task_status)
        st.success(f"✅ Log updated for {user}")

# ---------------------
# DASHBOARD
# ---------------------
st.subheader(f"📈 Dashboard ({selected_month}/{selected_year})")
logs_df_filtered = get_filtered_logs(selected_year, selected_month)

if logs_df_filtered.empty:
    st.info("No logs yet for this month.")
else:
    summary = []
    for user in USERS:
        user_logs = logs_df_filtered[logs_df_filtered["User"] == user].copy()
        if user_logs.empty:
            completed, missed, streak, rating = 0, 0, 0, 0
        else:
            # Only count missed after user's first activity
            first_activity = user_logs["Date"].min().date()
            today = datetime.date.today()
            active_days = (today - first_activity).days + 1
            completed = sum(user_logs[t].astype(bool).sum() for t in TASKS)
            missed = max((active_days * TASKS_PER_DAY) - completed, 0)
            progress = (completed / (active_days * TASKS_PER_DAY)) * 100 if active_days > 0 else 0
            rating = calculate_fotmob_rating(progress)
            streak = calculate_streak(user_logs)

        summary.append({
            "User": user,
            "Tasks Done": completed,
            "Remaining": missed,
            "Streak": f"🔥 {streak}-day" if streak > 0 else "🔥 0-day",
            "Rating": rating
        })

    summary_df = pd.DataFrame(summary).sort_values(by="Rating", ascending=False)
    st.dataframe(summary_df, use_container_width=True)

    # ---------------------
    # VISUALS
    # ---------------------
    col1, col2 = st.columns([2, 2])
    with col1:
        # Leaderboard by Rating (FotMob-style colours)
        fig_rating = px.bar(summary_df, x="Rating", y="User", orientation="h",
                            title="Leaderboard (Rating)",
                            color="Rating",
                            color_continuous_scale=[[0, "red"], [0.6, "yellow"], [1, "green"]],
                            range_color=[0, 10])
        st.plotly_chart(fig_rating, use_container_width=True)

    with col2:
        # Completed vs Remaining (Grouped Bar)
        fig_tasks = px.bar(summary_df.melt(id_vars="User", value_vars=["Tasks Done", "Remaining"]),
                           x="value", y="User", color="variable",
                           barmode="group",
                           title="Tasks Done vs Remaining")
        st.plotly_chart(fig_tasks, use_container_width=True)
