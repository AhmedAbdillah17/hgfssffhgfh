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
    if rating > 10: rating = 10
    return round(rating, 1)


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
selected_date = st.date_input("Select Date", value=datetime.date.today())

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
    start_date = logs_df_filtered["Date"].min().date()
    today = datetime.date.today()
    days_in_range = (today - start_date).days + 1

    summary = []
    for user in USERS:
        user_logs = logs_df_filtered[logs_df_filtered["User"] == user]
        completed = sum(user_logs[t].astype(bool).sum() for t in TASKS)
        missed = (days_in_range * TASKS_PER_DAY) - completed
        progress = min((completed / (days_in_range * TASKS_PER_DAY)) * 100, 100)
        summary.append({
            "User": user,
            "Tasks Done": completed,
            "Remaining": missed,
            "Progress %": round(progress, 1),
            "FotMob Rating": calculate_fotmob_rating(progress),
            "XP": completed * 10
        })

    summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
    st.dataframe(summary_df, use_container_width=True)

    # Charts
    col1, col2 = st.columns([2, 2])
    with col1:
        fig_bar = px.bar(summary_df, x="Progress %", y="User", orientation="h",
                         title="Leaderboard", color="Progress %", color_continuous_scale="Blues")
        st.plotly_chart(fig_bar, use_container_width=True)
    with col2:
        st.markdown("### 🍩 Completed vs Remaining per User")
        for user in USERS:
            u_data = next((item for item in summary if item["User"] == user), None)
            if u_data:
                comp = u_data["Tasks Done"]
                missed = u_data["Remaining"]
                if comp == 0 and missed == 0:
                    comp, missed = 0.01, 0.01
                fig = px.pie(values=[comp, missed], names=["Completed", "Remaining"],
                             hole=0.6, title=user,
                             color_discrete_map={"Completed": "#00CC96", "Remaining": "#EF553B"})
                fig.update_traces(textinfo="label+percent", sort=False)
                st.plotly_chart(fig, use_container_width=True)
