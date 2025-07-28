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
sheet = client.open(SHEET_NAME).worksheet("Log")  # Ensure "Log" sheet exists

# Ensure headers
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["Timestamp", "User", "Date", "Task1", "Task2", "Role", "Action"])

# ---------------------
# SETTINGS
# ---------------------
USERS = ["MQ", "Samo", "Bashe"]
ROLES = {u: "User" for u in USERS}
TASK_1 = "10 YouTube Comment Replies"
TASK_2 = "Market Research"
TASKS_PER_DAY = 2

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_log(user, date, t1, t2, action="Log Added"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role = ROLES.get(user, "User")
    sheet.append_row([timestamp, user, str(date), t1, t2, role, action])

# ---------------------
# SIDEBAR
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12, value=datetime.date.today().month, step=1)

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
st.subheader("✅ Log Tasks")
selected_date = st.date_input("Select Date", value=datetime.date.today())

for user in USERS:
    st.markdown(f"### {user}")
    col1, col2, col3 = st.columns([2, 2, 1])
    t1 = col1.checkbox(TASK_1, key=f"{user}_t1_{selected_date}")
    t2 = col2.checkbox(TASK_2, key=f"{user}_t2_{selected_date}")
    if col3.button("Save", key=f"save_{user}_{selected_date}"):
        save_log(user, selected_date, t1, t2)
        st.success(f"✅ Logged tasks for {user}")

# ---------------------
# DASHBOARD
# ---------------------
st.subheader(f"📈 Dashboard ({selected_month}/{selected_year})")
logs_df = load_logs()

if logs_df.empty:
    st.info("No logs yet.")
else:
    # Clean dates
    logs_df["Date"] = pd.to_datetime(logs_df["Date"], errors="coerce")
    logs_df = logs_df.dropna(subset=["Date"])

    # Filter for selected month/year
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
            completed = user_logs["Task1"].astype(bool).sum() + user_logs["Task2"].astype(bool).sum()
            missed = (days_in_range * TASKS_PER_DAY) - completed
            progress = min((completed / (days_in_range * TASKS_PER_DAY)) * 100, 100)
            days_100 = sum((row.Task1 and row.Task2) for _, row in user_logs.iterrows())
            summary.append({
                "User": user,
                "Days 100%": days_100,
                "Tasks Done": completed,
                "Remaining": missed,
                "Progress %": round(progress, 1),
                "Rating": round(progress / 10, 1),
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
