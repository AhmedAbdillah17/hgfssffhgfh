import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime as dt

# ---------------------
# CONFIG
# ---------------------
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

# Define tasks and users
TASKS = ["10 YouTube Comment Replies", "Market Research"]  # Add more tasks if needed
TASKS_PER_DAY = len(TASKS)
USERS = ["MQ", "Samo", "Bashe"]

# ---------------------
# GOOGLE SHEETS AUTH (SECURE)
credentials = dict(st.secrets["gcp_service_account"])
credentials["private_key"] = credentials["private_key"].replace("\\n", "\n").strip()  # ✅ Ensure proper PEM format

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
client = gspread.authorize(creds)

# Sheet names
SHEET_NAME = "Task_Tracker"
AUDIT_SHEET_NAME = "Task_Audit"

# Main sheet
sheet = client.open(SHEET_NAME).sheet1

# Audit sheet
try:
    audit_sheet = client.open(SHEET_NAME).worksheet(AUDIT_SHEET_NAME)
except:
    audit_sheet = client.open(SHEET_NAME).add_worksheet(title=AUDIT_SHEET_NAME, rows="1000", cols="4")
    audit_sheet.append_row(["User", "Selected Date", "Timestamp", "Action"])

# Ensure main sheet header exists
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["User", "Date"] + [f"Task{i+1}" for i in range(TASKS_PER_DAY)] + ["Timestamp"])

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_log(user, date, tasks_done):
    timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [user, str(date)] + tasks_done + [timestamp]
    sheet.append_row(row)
    audit_sheet.append_row([user, str(date), timestamp, "Log Added"])

def delete_log(row_index, user, date):
    sheet.delete_rows(row_index)
    timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    audit_sheet.append_row([user, date, timestamp, "Log Deleted"])

# ---------------------
# SIDEBAR SETTINGS
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12, value=datetime.date.today().month, step=1)

    # Download full logs
    logs_df_all = load_logs()
    if not logs_df_all.empty:
        st.download_button(
            label="💾 Export All Logs (CSV)",
            data=logs_df_all.to_csv(index=False).encode('utf-8'),
            file_name="task_logs.csv",
            mime="text/csv"
        )

# ---------------------
# TASK ENTRY SECTION
# ---------------------
st.markdown("<h1 style='text-align:center;'>📊 Task Tracker</h1>", unsafe_allow_html=True)
st.subheader("✅ Log Tasks")

# Date restriction: only today or yesterday
selected_date = st.date_input("Select Date", value=datetime.date.today())
today = datetime.date.today()
if selected_date < (today - datetime.timedelta(days=1)):
    st.error("❌ You can only log for today or yesterday.")
    st.stop()

for user in USERS:
    st.markdown(f"**{user}**")
    cols = st.columns([2]*TASKS_PER_DAY + [1])
    task_values = [cols[i].checkbox(TASKS[i], key=f"{user}_task{i}") for i in range(TASKS_PER_DAY)]

    if cols[-1].button("Save", key=f"save_{user}"):
        logs_df = load_logs()
        if not logs_df.empty and any((logs_df["User"] == user) & (logs_df["Date"] == str(selected_date))):
            st.warning(f"⚠ {user} already logged for {selected_date}")
        else:
            save_log(user, selected_date, task_values)
            st.success(f"✅ Logged for {user} on {selected_date}")
            st.experimental_rerun()

# ---------------------
# DASHBOARD
# ---------------------
st.markdown(f"## 📈 Dashboard ({selected_month}/{selected_year})")
logs_df = load_logs()

if logs_df.empty:
    st.info("No logs yet. Start logging tasks!")
else:
    logs_df["Date"] = pd.to_datetime(logs_df["Date"])
    logs_df = logs_df[(logs_df["Date"].dt.year == selected_year) & (logs_df["Date"].dt.month == selected_month)]

    if logs_df.empty:
        st.warning("No data for this month.")
    else:
        start_date = logs_df["Date"].min().date()
        days_in_range = (today - start_date).days + 1

        summary = []
        for user in USERS:
            user_logs = logs_df[logs_df["User"] == user]
            completed = sum(user_logs.iloc[:, 2:2+TASKS_PER_DAY].astype(bool).sum(axis=1))

            missed_tasks = (days_in_range * TASKS_PER_DAY) - completed
            progress = (completed / (days_in_range * TASKS_PER_DAY)) * 100 if days_in_range > 0 else 0
            progress = min(progress, 100)

            days_100 = sum(user_logs.iloc[:, 2:2+TASKS_PER_DAY].all(axis=1))

            streak = 0
            current_streak = 0
            for d in pd.date_range(start_date, today):
                log = user_logs[user_logs["Date"] == d.date()]
                if not log.empty and log.iloc[:, 2:2+TASKS_PER_DAY].all(axis=1).any():
                    current_streak += 1
                    streak = max(streak, current_streak)
                else:
                    current_streak = 0

            inactive_warning = "⚠ Inactive" if missed_tasks >= 4 else ""

            summary.append({
                "User": user,
                "Days 100%": days_100,
                "Streak": streak,
                "Tasks Done": completed,
                "Missed": missed_tasks,
                "Progress %": round(progress, 1),
                "Rating": round(progress / 10, 1),
                "Status": inactive_warning
            })

        summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
        summary_df.index = range(1, len(summary_df) + 1)

        def color_rating(val):
            color = "green" if val >= 7 else "orange" if val >= 4 else "red"
            return f"background-color: {color}; color: white;"

        st.dataframe(summary_df.style.applymap(color_rating, subset=["Rating"]), use_container_width=True)

        # Charts
        col1, col2 = st.columns([2, 2])
        with col1:
            fig_bar = px.bar(summary_df, x="Progress %", y="User", orientation="h",
                             title="Leaderboard by Progress %", color="Progress %", color_continuous_scale="Blues")
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.markdown("### 🍩 Completed vs Missed per User")
            for user in USERS:
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
# LOG MANAGEMENT
# ---------------------
st.markdown("### 🗑 Manage Logs")
full_logs = load_logs()
if full_logs.empty:
    st.write("No logs to show.")
else:
    options = [f"{i+2}. {row['User']} - {row['Date']}" for i, row in full_logs.iterrows()]
    row_to_delete = st.selectbox("Choose log:", options=options)
    if st.button("Delete Selected Entry"):
        index_to_delete = int(row_to_delete.split(".")[0])
        user = full_logs.iloc[index_to_delete-2]["User"]
        date = full_logs.iloc[index_to_delete-2]["Date"]
        delete_log(index_to_delete, user, date)
        st.success("✅ Entry deleted successfully!")
        st.experimental_rerun()
