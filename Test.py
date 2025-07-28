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
# DARK MODE TOGGLE
# ---------------------
dark_mode = st.sidebar.checkbox("🌙 Dark Mode", value=False)
if dark_mode:
    st.markdown(
        """
        <style>
        body { background-color: #121212; color: white; }
        .stButton>button { background-color: #333333; color: white; border: 1px solid white; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ---------------------
# GOOGLE SHEETS AUTH
# ---------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = dict(st.secrets["gcp_service_account"])
creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "Task_Tracker"
sheet = client.open(SHEET_NAME).worksheet("Log")

# Ensure header exists
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["Timestamp", "User", "Date", "Task1", "Task2", "Role", "Action"])

# ---------------------
# USER & ROLE SETUP
# ---------------------
USERS = {
    "Ahmed": "Admin",
    "MQ": "User",
    "Samo": "User",
    "Bashe": "User"
}

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_log(user, date, t1, t2, action="Log Added"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role = USERS.get(user, "User")
    sheet.append_row([timestamp, user, str(date), t1, t2, role, action])

def delete_log(row_index, user):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.delete_rows(row_index)
    sheet.append_row([timestamp, user, "", "", "", USERS.get(user, "User"), "Log Deleted"])

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
        st.download_button(
            label="💾 Export All Logs (CSV)",
            data=logs_df_all.to_csv(index=False).encode('utf-8'),
            file_name="task_logs.csv",
            mime="text/csv"
        )

# ---------------------
# LOGIN
# ---------------------
st.title("✅ Task Tracker")
username = st.text_input("Enter your name (case-sensitive):")

if username not in USERS:
    st.warning("Please enter a valid username.")
    st.stop()

role = USERS[username]
st.success(f"Logged in as {username} ({role})")

# ---------------------
# TASK ENTRY SECTION
# ---------------------
TASK_1 = "10 YouTube Comment Replies"
TASK_2 = "Market Research"
TASKS_PER_DAY = 2

st.subheader("✅ Log Tasks")
selected_date = st.date_input("Select Date", value=datetime.date.today(),
                               min_value=datetime.date.today() - datetime.timedelta(days=1),
                               max_value=datetime.date.today())

logs_df = load_logs()
user_logs_today = logs_df[(logs_df["User"] == username) & (logs_df["Date"] == str(selected_date))]

if not user_logs_today.empty:
    st.info(f"You already logged for {selected_date}.")
else:
    col1, col2, col3 = st.columns([2, 2, 1])
    t1 = col1.checkbox(TASK_1)
    t2 = col2.checkbox(TASK_2)

    if col3.button("Save Log"):
        save_log(username, selected_date, t1, t2)
        st.success(f"✅ Logged tasks for {selected_date}")
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
        for user in USERS.keys():
            user_logs = logs_df_filtered[logs_df_filtered["User"] == user]
            completed = (user_logs["Task1"].astype(bool).sum() + user_logs["Task2"].astype(bool).sum())

            missed_tasks = (days_in_range * TASKS_PER_DAY) - completed
            progress = (completed / (days_in_range * TASKS_PER_DAY)) * 100 if days_in_range > 0 else 0
            progress = min(progress, 100)

            days_100 = sum((row.Task1 and row.Task2) for _, row in user_logs.iterrows())

            summary.append({
                "User": user,
                "Days 100%": days_100,
                "Tasks Done": completed,
                "Missed": missed_tasks,
                "Progress %": round(progress, 1),
                "Rating": round(progress / 10, 1)
            })

        summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
        summary_df.index = range(1, len(summary_df) + 1)

        st.dataframe(summary_df, use_container_width=True)

        col1, col2 = st.columns([2, 2])
        with col1:
            fig_bar = px.bar(summary_df, x="Progress %", y="User", orientation="h",
                             title="Leaderboard", color="Progress %", color_continuous_scale="Blues")
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.markdown("### 🍩 Completed vs Missed per User")
            for user in USERS.keys():
                u_data = next((item for item in summary if item["User"] == user), None)
                if u_data:
                    comp = u_data["Tasks Done"]
                    missed = u_data["Missed"]
                    if comp == 0 and missed == 0:
                        comp, missed = 0.01, 0.01
                    fig = px.pie(values=[comp, missed], names=["Completed", "Missed"],
                                 hole=0.6, title=user,
                                 color_discrete_map={"Completed": "#00CC96", "Missed": "#EF553B"})
                    fig.update_traces(textinfo="label+percent", sort=False)
                    st.plotly_chart(fig, use_container_width=True)

# ---------------------
# ADMIN: MANAGE LOGS
# ---------------------
if role == "Admin":
    st.markdown("### 🗑 Manage Logs")
    full_logs = load_logs()
    if full_logs.empty:
        st.write("No logs to show.")
    else:
        options = [f"{i+2}. {row['User']} - {row['Date']} ({row['Action']})" for i, row in full_logs.iterrows()]
        row_to_delete = st.selectbox("Choose log:", options=options)
        if st.button("Delete Selected Entry"):
            index_to_delete = int(row_to_delete.split(".")[0])
            delete_log(index_to_delete, username)
            st.success("✅ Entry deleted successfully! Refresh to update view.")
