import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------
# CONFIG
# ---------------------
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

TASK_1 = "10 YouTube Comment Replies"
TASK_2 = "Market Research"
TASKS_PER_DAY = 2
USERS = ["MQ", "Samo", "Bashe"]

# ---------------------
# GOOGLE SHEETS AUTH
# ---------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

SHEET_NAME = "Task_Tracker"
sheet = client.open(SHEET_NAME).sheet1

# Ensure header exists
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["User", "Date", "Task1", "Task2", "Timestamp"])

# ---------------------
# FUNCTIONS
# ---------------------
def load_logs():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_log(user, date, t1, t2):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([user, str(date), t1, t2, timestamp])

def delete_log(row_index):
    sheet.delete_rows(row_index)

def get_inactivity_warnings(df):
    warnings = []
    today = datetime.date.today()
    for user in USERS:
        user_logs = df[df["User"] == user]
        if user_logs.empty or user_logs["Date"].max() < pd.Timestamp(today - pd.Timedelta(days=2)):
            warnings.append(f"⚠ {user} inactive for 2+ days!")
    return warnings

# ---------------------
# SIDEBAR SETTINGS
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")
    role = st.radio("Select Role", ["User", "Admin"])
    dark_mode = st.toggle("🌙 Dark Mode", value=False)
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12, value=datetime.date.today().month, step=1)

    # Export logs (Admin only)
    if role == "Admin":
        logs_df_all = load_logs()
        if not logs_df_all.empty:
            st.download_button(
                label="💾 Export All Logs (CSV)",
                data=logs_df_all.to_csv(index=False).encode('utf-8'),
                file_name="task_logs.csv",
                mime="text/csv"
            )

# Apply dark mode styling
if dark_mode:
    st.markdown("""
        <style>
        body {background-color: #1e1e1e; color: white;}
        .stButton>button {background-color: #333; color: white;}
        </style>
    """, unsafe_allow_html=True)

# ---------------------
# TASK ENTRY SECTION (User)
# ---------------------
if role == "User":
    st.markdown("<h1 style='text-align:center;'>📊 Task Tracker</h1>", unsafe_allow_html=True)
    st.subheader("✅ Log Tasks")

    selected_date = st.date_input("Select Date", value=datetime.date.today())

    # Lock dates (only today & yesterday allowed)
    if selected_date < datetime.date.today() - datetime.timedelta(days=1) or selected_date > datetime.date.today():
        st.error("❌ You can only log tasks for today or yesterday!")
    else:
        for user in USERS:
            st.markdown(f"**{user}**")
            col1, col2, col3 = st.columns([2, 2, 1])
            t1 = col1.checkbox(TASK_1, key=f"{user}_t1")
            t2 = col2.checkbox(TASK_2, key=f"{user}_t2")

            if col3.button(f"Save", key=f"save_{user}"):
                logs_df = load_logs()
                if not logs_df.empty and any((logs_df["User"] == user) & (logs_df["Date"] == str(selected_date))):
                    st.warning(f"⚠ {user} already logged for {selected_date}")
                else:
                    save_log(user, selected_date, t1, t2)
                    st.success(f"✅ Logged for {user} on {selected_date}")
                    if t1 and t2:
                        st.balloons()

# ---------------------
# DASHBOARD (Admin)
# ---------------------
if role == "Admin":
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
            today = datetime.date.today()
            days_in_range = (today - start_date).days + 1

            summary = []
            for user in USERS:
                user_logs = logs_df[logs_df["User"] == user]
                completed = (user_logs["Task1"].astype(bool).sum() + user_logs["Task2"].astype(bool).sum())

                missed_tasks = (days_in_range * TASKS_PER_DAY) - completed
                progress = (completed / (days_in_range * TASKS_PER_DAY)) * 100 if days_in_range > 0 else 0
                progress = min(progress, 100)

                days_100 = sum((row.Task1 and row.Task2) for _, row in user_logs.iterrows())

                # Calculate streak
                streak = 0
                current_streak = 0
                for d in pd.date_range(start_date, today):
                    log = user_logs[user_logs["Date"] == d.date()]
                    if not log.empty and log.iloc[0]["Task1"] and log.iloc[0]["Task2"]:
                        current_streak += 1
                        streak = max(streak, current_streak)
                    else:
                        current_streak = 0

                summary.append({
                    "User": user,
                    "Days 100%": days_100,
                    "Streak": streak,
                    "Tasks Done": completed,
                    "Missed": missed_tasks,
                    "Progress %": round(progress, 1),
                    "Rating": round(progress / 10, 1)
                })

            summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
            summary_df.index = range(1, len(summary_df) + 1)

            def color_rating(val):
                color = "green" if val >= 7 else "orange" if val >= 4 else "red"
                return f"background-color: {color}; color: white;"

            st.dataframe(summary_df.style.applymap(color_rating, subset=["Rating"]), use_container_width=True)

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

            # Inactivity warnings
            st.markdown("### ⚠ Inactivity Alerts")
            inactivity_msgs = get_inactivity_warnings(logs_df)
            if inactivity_msgs:
                for msg in inactivity_msgs:
                    st.warning(msg)
            else:
                st.success("✅ All users active!")

# ---------------------
# LOG MANAGEMENT (Admin)
# ---------------------
if role == "Admin":
    st.markdown("### 🗑 Manage Logs")
    full_logs = load_logs()
    if full_logs.empty:
        st.write("No logs to show.")
    else:
        options = [f"{i+2}. {row['User']} - {row['Date']}" for i, row in full_logs.iterrows()]
        row_to_delete = st.selectbox("Choose log:", options=options)
        if st.button("Delete Selected Entry"):
            index_to_delete = int(row_to_delete.split(".")[0])  # Actual row in sheet
            delete_log(index_to_delete)
            st.success("✅ Entry deleted successfully! Refresh to update view.")
