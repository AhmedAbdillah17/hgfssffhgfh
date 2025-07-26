import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import json

# ---------------------
# CONFIG
# ---------------------
st.set_page_config(page_title="Task Tracker", page_icon="✅", layout="wide")

TASK_1 = "10 YouTube Comment Replies"
TASK_2 = "Market Research"
TASKS_PER_DAY = 2

# Initialize session state
if "data" not in st.session_state:
    st.session_state.data = {
        "go_live": None,
        "logs": [],
        "users": ["MQ", "Samo", "Bashe"]
    }

# ---------------------
# SIDEBAR SETTINGS
# ---------------------
with st.sidebar:
    st.subheader("⚙️ Settings")

    # Go Live button
    if st.button("🚀 Go Live"):
        st.session_state.data["go_live"] = datetime.date.today()
        st.success(f"Tracking started on {st.session_state.data['go_live']}")

    # Year & Month selection for dashboard
    selected_year = st.number_input("Select Year", value=datetime.date.today().year, step=1)
    selected_month = st.number_input("Select Month", min_value=1, max_value=12,
                                     value=datetime.date.today().month, step=1)

    st.markdown("---")
    # Save & Restore
    st.download_button(
        "💾 Download Data",
        data=json.dumps(st.session_state.data, default=str),
        file_name="task_data.json",
        mime="application/json"
    )
    uploaded_file = st.file_uploader("Upload Data", type="json")
    if uploaded_file:
        st.session_state.data = json.load(uploaded_file)
        st.success("✅ Data restored successfully!")

# ---------------------
# TASK ENTRY SECTION
# ---------------------
st.markdown("<h1 style='text-align:center;'>📊 Task Tracker</h1>", unsafe_allow_html=True)
st.subheader("✅ Log Tasks")

# Select date for logging
selected_date = st.date_input("Select Date", value=datetime.date.today())

for user in st.session_state.data["users"]:
    st.markdown(f"**{user}**")
    col1, col2, col3 = st.columns([2, 2, 1])
    t1 = col1.checkbox(TASK_1, key=f"{user}_t1")
    t2 = col2.checkbox(TASK_2, key=f"{user}_t2")

    if col3.button(f"Save", key=f"save_{user}"):
        # Prevent multiple logs on same day
        if any(log["user"] == user and log["date"] == str(selected_date) for log in st.session_state.data["logs"]):
            st.warning(f"⚠ {user} already logged for {selected_date}")
        else:
            st.session_state.data["logs"].append({
                "user": user,
                "date": str(selected_date),
                "task1": t1,
                "task2": t2
            })
            st.success(f"✅ Logged for {user} on {selected_date}")
            if t1 and t2:
                st.balloons()

# ---------------------
# DASHBOARD
# ---------------------
st.markdown(f"## 📈 Dashboard ({selected_month}/{selected_year})")

logs_df = pd.DataFrame(st.session_state.data["logs"])

if logs_df.empty:
    st.info("No logs yet. Start logging tasks!")
else:
    # Convert to datetime
    logs_df["date"] = pd.to_datetime(logs_df["date"])

    # Filter for selected month & year
    logs_df = logs_df[(logs_df["date"].dt.year == selected_year) &
                      (logs_df["date"].dt.month == selected_month)]

    if logs_df.empty:
        st.warning("No data for this month.")
    else:
        start_date = st.session_state.data["go_live"] or logs_df["date"].min().date()
        today = datetime.date.today()
        days_in_range = (today - start_date).days + 1
        expected_tasks = days_in_range * TASKS_PER_DAY

        summary = []
        for user in st.session_state.data["users"]:
            user_logs = logs_df[logs_df["user"] == user]
            completed = ((user_logs["task1"] == True).sum() + (user_logs["task2"] == True).sum())
            missed = max(expected_tasks - completed, 0)  # ✅ Missed tasks
            progress = min((completed / expected_tasks) * 100 if expected_tasks > 0 else 0, 100)
            days_100 = sum((row.task1 and row.task2) for _, row in user_logs.iterrows())

            # ✅ FIXED Streak calculation
            streak = 0
            current_streak = 0
            for d in pd.date_range(start_date, today):
                log = user_logs[user_logs["date"] == d.date()]
                if not log.empty and log.iloc[0]["task1"] and log.iloc[0]["task2"]:
                    current_streak += 1
                    streak = max(streak, current_streak)
                else:
                    current_streak = 0

            rating = round(progress / 10, 1)

            summary.append({
                "User": user,
                "Days 100%": days_100,
                "Streak": streak,
                "Tasks Done": completed,
                "Missed": missed,
                "Progress %": round(progress, 1),
                "Rating": rating
            })

        summary_df = pd.DataFrame(summary).sort_values(by="Progress %", ascending=False)
        summary_df.index = range(1, len(summary_df) + 1)

        # ✅ Apply color to Rating column
        def color_rating(val):
            if val >= 8:
                return 'background-color: #28a745; color: white;'
            elif val >= 5:
                return 'background-color: #ffc107; color: black;'
            else:
                return 'background-color: #dc3545; color: white;'

        st.dataframe(summary_df.style.format({
            "Progress %": "{:.1f}",
            "Rating": "{:.1f}"
        }).applymap(color_rating, subset=['Rating']),
            use_container_width=True)

        # ✅ Charts
        col1, col2 = st.columns([2, 2])
        with col1:
            fig_bar = px.bar(summary_df, x="Progress %", y="User", orientation="h",
                             title="Leaderboard by Progress %", color="Progress %", color_continuous_scale="Blues")
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.markdown("### 🍩 Completed vs Missed per User")
            for user in st.session_state.data["users"]:
                u_data = next((item for item in summary if item["User"] == user), None)
                if u_data:
                    comp = u_data["Tasks Done"]
                    missed_val = u_data["Missed"]
                    if comp == 0 and missed_val == 0:
                        comp, missed_val = 0.01, 0.01
                    fig = px.pie(
                        values=[comp, missed_val],
                        names=["Completed", "Missed"],
                        hole=0.6,
                        title=user,
                        color_discrete_map={"Completed": "#00CC96", "Missed": "#EF553B"}
                    )
                    fig.update_traces(textinfo="label+percent", sort=False)
                    st.plotly_chart(fig, use_container_width=True)