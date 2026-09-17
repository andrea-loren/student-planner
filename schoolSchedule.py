import os
import json
import time
import uuid
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection

# MUST be the first Streamlit command to expand layout back to full width
st.set_page_config(
    page_title="Student Rotation Planner",
    page_icon="🎓",
    layout="wide"
)

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- GOOGLE SHEETS DATA HELPERS ---
def load_sheet_data(worksheet_name):
    try:
        return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception:
        return pd.DataFrame()

def save_sheet_data(worksheet_name, df):
    # Ensure all data values are clean strings to prevent JSON payload formatting errors
    clean_df = df.astype(str)
    
    # Clear the worksheet first so existing dimensions don't cause write conflicts
    try:
        conn.clear(worksheet=worksheet_name)
    except Exception:
        pass
        
    conn.update(worksheet=worksheet_name, data=clean_df)
    st.cache_data.clear()

# --- DEFAULT DEFAULTS ---
DEFAULT_CLASSES = [
    "Advanced Calculus AB", "Honors English", "Advanced Biology", 
    "Advanced Computer Science", "Advanced French", "Philosophy", 
    "Free Period", "Advanced Photography", "Kairos", 
    "College Counseling", "X-Period", "Extracurricular / Other"
]

DEFAULT_COLORS = {
    "Advanced Calculus AB": "#FFADAD",
    "Honors English": "#FFD6A5",
    "Advanced Biology": "#CAFFBF",
    "Advanced Computer Science": "#9BF6FF",
    "Advanced French": "#A0C4FF",
    "Philosophy": "#BDB2FF",
    "Free Period": "#E5E5E5",
    "Advanced Photography": "#FFC6FF",
    "Kairos": "#FFFFFC",
    "College Counseling": "#D0F4DE",
    "X-Period": "#E4C1F9",
    "Extracurricular / Other": "#FFD1DC"
}

DEFAULT_WEIGHTS = {
    "daily": 10.0,
    "formative": 20.0,
    "evaluative": 70.0
}

DEFAULT_TIMETABLE = {
    "08:00 - 08:56": ["Honors English", "Advanced Calculus AB", "Advanced Biology", "Advanced French", "Free Period", "Free Period"],
    "09:00 - 09:56": ["Advanced Calculus AB", "Honors English", "Philosophy", "Free Period", "Advanced Computer Science", "Free Period"],
    "10:00 - 10:56": ["X-Period", "Advanced French", "Advanced Computer Science", "X-Period", "Philosophy", "Advanced French"],
    "11:00 - 11:56": ["College Counseling", "Advanced Computer Science", "Advanced Photography", "Free Period", "Advanced Calculus AB", "Free Period"],
    "12:00 - 12:56": ["Advanced Computer Science", "Free Period", "Kairos", "Advanced Biology", "Advanced Biology", "Advanced Computer Science"],
    "13:00 - 13:56": ["Free Period", "Free Period", "Honors English", "Advanced Calculus AB", "Free Period", "Advanced Biology"],
    "14:00 - 14:56": ["Advanced French", "Advanced Biology", "Advanced Calculus AB", "Philosophy", "Advanced Photography", "Honors English"]
}

DEFAULT_ROOMS = {
    "08:00 - 08:56": ["322", "C-07", "322", "322", "TBD", "TBD"],
    "09:00 - 09:56": ["322", "322", "101", "TBD", "C-07", "TBD"],
    "10:00 - 10:56": ["Auditorium", "322", "C-07", "Auditorium", "101", "322"],
    "11:00 - 11:56": ["104", "C-07", "Art Room", "TBD", "322", "TBD"],
    "12:00 - 12:56": ["C-07", "TBD", "Chapel", "322", "322", "C-07"],
    "13:00 - 13:56": ["TBD", "TBD", "322", "322", "TBD", "322"],
    "14:00 - 14:56": ["322", "322", "322", "101", "Art Room", "322"]
}

DEFAULT_SCHOOL_START = "2026-09-10"
DEFAULT_SCHOOL_END = "2027-06-04"
DEFAULT_CYCLE_DAYS = 6
DEFAULT_CUSTOM_BREAKS = [
    "2026-10-09", "2026-10-12",
    "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27",
    "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-25", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01",
    "2027-02-12", "2027-02-13", "2027-02-14", "2027-02-15", "2027-02-16",
    "2027-03-15", "2027-03-16", "2027-03-17", "2027-03-18", "2027-03-19", "2027-03-22", "2027-03-23", "2027-03-24", "2027-03-25", "2027-03-26"
]

# --- LOAD CONFIG & SESSION STATE FROM GOOGLE SHEETS ---
config_df = load_sheet_data("Config")
config = {}
if not config_df.empty and "Key" in config_df.columns and "Value" in config_df.columns:
    for _, row in config_df.iterrows():
        try:
            config[row["Key"]] = json.loads(row["Value"])
        except Exception:
            config[row["Key"]] = row["Value"]

if "classes" not in st.session_state:
    st.session_state.classes = config.get("classes", DEFAULT_CLASSES)
    st.session_state.colors = config.get("colors", DEFAULT_COLORS)
    st.session_state.timetable = config.get("timetable", DEFAULT_TIMETABLE)
    st.session_state.rooms = config.get("rooms", DEFAULT_ROOMS)
    st.session_state.blocked_periods = config.get("blocked_periods", {})
    st.session_state.daily_notes = config.get("daily_notes", {})
    st.session_state.grades = config.get("grades", {})
    st.session_state.grade_weights = config.get("grade_weights", {})
    st.session_state.graded_classes = config.get("graded_classes", [c for c in st.session_state.classes if c not in ["Advanced Photography", "Free Period", "Kairos", "College Counseling", "X-Period", "Extracurricular / Other"]])
    st.session_state.school_start_date = config.get("school_start_date", DEFAULT_SCHOOL_START)
    st.session_state.school_end_date = config.get("school_end_date", DEFAULT_SCHOOL_END)
    st.session_state.cycle_days_count = config.get("cycle_days_count", DEFAULT_CYCLE_DAYS)
    st.session_state.custom_breaks = config.get("custom_breaks", DEFAULT_CUSTOM_BREAKS)

# Load tasks dataframe from Google Sheets
tasks_df_raw = load_sheet_data("Tasks")
if "tasks" not in st.session_state:
    if not tasks_df_raw.empty and "Due Date" in tasks_df_raw.columns:
        st.session_state.tasks = tasks_df_raw.copy()
        if "id" not in st.session_state.tasks.columns:
            st.session_state.tasks["id"] = [str(uuid.uuid4()) for _ in range(len(st.session_state.tasks))]
        st.session_state.tasks["Due Date"] = pd.to_datetime(st.session_state.tasks["Due Date"]).dt.date
    else:
        st.session_state.tasks = pd.DataFrame(columns=["id", "Title", "Class", "Type", "Due Date", "Status"])

if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0

def save_config():
    data_dict = {
        "classes": st.session_state.classes,
        "colors": st.session_state.colors,
        "timetable": st.session_state.timetable,
        "rooms": st.session_state.rooms,
        "blocked_periods": st.session_state.blocked_periods,
        "daily_notes": st.session_state.daily_notes,
        "grades": st.session_state.get("grades", {}),
        "grade_weights": st.session_state.get("grade_weights", {}),
        "graded_classes": st.session_state.get("graded_classes", []),
        "school_start_date": st.session_state.school_start_date,
        "school_end_date": st.session_state.school_end_date,
        "cycle_days_count": st.session_state.cycle_days_count,
        "custom_breaks": st.session_state.custom_breaks
    }
    
    config_rows = [{"Key": k, "Value": json.dumps(v)} for k, v in data_dict.items()]
    new_config_df = pd.DataFrame(config_rows)
    save_sheet_data("Config", new_config_df)

def save_tasks():
    tasks_to_save = st.session_state.tasks.copy()
    if not tasks_to_save.empty and "Due Date" in tasks_to_save.columns:
        tasks_to_save["Due Date"] = tasks_to_save["Due Date"].astype(str)
    save_sheet_data("Tasks", tasks_to_save)

def parse_date(d_str):
    if isinstance(d_str, date):
        return d_str
    return datetime.strptime(d_str, "%Y-%m-%d").date()

# Dynamic academic calendar resolution
ANCHOR_DATE = parse_date(st.session_state.school_start_date)
SCHOOL_END_DATE = parse_date(st.session_state.school_end_date)
CYCLE_DAYS = int(st.session_state.cycle_days_count)
SCHOOL_BREAKS = {parse_date(b) for b in st.session_state.custom_breaks}

def is_school_day(check_date):
    if check_date.weekday() >= 5:
        return False
    if check_date in SCHOOL_BREAKS:
        return False
    if check_date > SCHOOL_END_DATE:
        return False
    return True

def get_cycle_day(target_date):
    if target_date < ANCHOR_DATE or target_date > SCHOOL_END_DATE:
        return None
    if not is_school_day(target_date):
        return None
    
    current = ANCHOR_DATE
    school_days = 0
    while current <= target_date:
        if is_school_day(current):
            school_days += 1
        current += timedelta(days=1)
        
    return ((school_days - 1) % CYCLE_DAYS) + 1

# --- HEADER & TABS ---
st.title("🎓 Student Rotation Planner")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📅 Weekly Schedule", 
    "📝 Tasks & Assessments", 
    "⏱️ Pomodoro Timer", 
    "⚙️ Customize Schedule & Colors",
    "📊 Grade Calculator"
])

# --- TAB 1: WEEKLY CALENDAR VIEW ---
with tab1:
    st.header("Weekly Overview")
    
    col_prev, col_curr, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("⬅️ Previous Week"):
            st.session_state.week_offset -= 1
            st.rerun()
    with col_curr:
        if st.button("🔄 Current Week"):
            st.session_state.week_offset = 0
            st.rerun()
    with col_next:
        if st.button("Next Week ➡️"):
            st.session_state.week_offset += 1
            st.rerun()

    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state.week_offset)
    week_days = [monday + timedelta(days=i) for i in range(5)]
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    st.markdown("---")

    # ROW 1: Headers & Tasks
    task_cols = st.columns(5)
    for idx, d in enumerate(week_days):
        c_day = get_cycle_day(d)
        day_tasks = st.session_state.tasks[st.session_state.tasks["Due Date"] == d]
        pending_day_tasks = day_tasks[day_tasks["Status"] != "Completed"]
        
        with task_cols[idx]:
            st.markdown(f"### {day_names[idx]} ({d.strftime('%m/%d')})")
            
            if d < ANCHOR_DATE:
                st.caption("🌴 **Pre-School Year**")
            elif d > SCHOOL_END_DATE:
                st.caption("☀️ **Summer Break**")
            elif d in SCHOOL_BREAKS:
                st.caption("🎉 **School Break**")
            elif c_day:
                st.caption(f"**Cycle Day {c_day}**")
            else:
                st.caption("**Weekend**")
            
            st.markdown("#### 📌 Due Today")
            if not pending_day_tasks.empty:
                for _, task in pending_day_tasks.iterrows():
                    color = st.session_state.colors.get(task["Class"], "#EEEEEE")
                    badge_type = "🚨 Exam" if task["Type"] == "Assessment" else "📌 Task"
                    st.markdown(
                        f"<div style='background-color:{color}; padding:6px; border-radius:5px; margin-bottom:6px; font-size:12px; color:#121212; border:1px solid #ccc;'>"
                        f"<b>{badge_type}:</b> {task['Title']}<br><small>{task['Class']}</small>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.caption("Nothing due")

    st.markdown("---")

    # Inject CSS to make popover buttons look identical to class cards
    st.markdown("""
        <style>
        div[data-testid="stPopover"] > button {
            width: 100% !important;
            background-color: #E5E5E5 !important;
            color: #121212 !important;
            border: 1px solid #ddd !important;
            border-radius: 5px !important;
            padding: 6px !important;
            margin-bottom: 6px !important;
            font-size: 12px !important;
            font-weight: bold !important;
            text-align: center !important;
            box-shadow: none !important;
            min-height: 48px !important;
        }
        div[data-testid="stPopover"] > button:hover {
            border-color: #999 !important;
            background-color: #DCDCDC !important;
        }
        div[data-testid="stPopover"] > button p {
            font-size: 12px !important;
            font-weight: bold !important;
            margin: 0 !important;
            line-height: 1.2 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # ROW 2: Classes & Room Numbers
    @st.dialog("Edit Free Period Activity")
    def edit_free_period_modal(block_key, period_time):
        is_blocked = st.session_state.blocked_periods.get(block_key, False)
        custom_note = st.session_state.daily_notes.get(f"free_note_{block_key}", "")

        st.write(f"**Period:** {period_time}")

        new_blocked = st.toggle("Mark as Busy / Meeting", value=is_blocked, key=f"dlg_tog_{block_key}")
        new_note = st.text_input("What are you doing during this time?", value=custom_note, placeholder="e.g., SAT Prep, Math Tutoring", key=f"dlg_inp_{block_key}")

        if st.button("Save Changes", type="primary", use_container_width=True):
            st.session_state.blocked_periods[block_key] = new_blocked
            st.session_state.daily_notes[f"free_note_{block_key}"] = new_note
            save_config()
            st.rerun()

    class_cols = st.columns(5)
    for idx, d in enumerate(week_days):
        c_day = get_cycle_day(d)
        date_str = d.strftime("%Y-%m-%d")

        with class_cols[idx]:
            st.markdown("#### 🗓️ Classes")
            for period_time, schedule in st.session_state.timetable.items():
                if c_day and (c_day - 1) < len(schedule):
                    class_name = schedule[c_day - 1]
                    rooms_list = st.session_state.rooms.get(period_time, [""] * CYCLE_DAYS)
                    room_no = rooms_list[c_day - 1] if (c_day - 1) < len(rooms_list) else ""
                    bg_color = st.session_state.colors.get(class_name, "#FFFFFF")
                else:
                    class_name = "No School"
                    room_no = ""
                    bg_color = "#F0F0F0"

                block_key = f"{date_str}_{period_time}"
                is_blocked = st.session_state.blocked_periods.get(block_key, False)
                custom_note = st.session_state.daily_notes.get(f"free_note_{block_key}", "")
                period_label = f"{period_time} | {room_no}" if room_no and room_no != "TBD" else period_time

                if class_name == "Free Period" and c_day:
                    if is_blocked:
                        status_display = f"🚫 {custom_note}" if custom_note else "🚫 Meeting / Busy"
                        card_color = "#757575"
                        text_color = "#FFFFFF"
                    else:
                        status_display = f"🟢 {custom_note}" if custom_note else "🟢 Free Period"
                        card_color = bg_color
                        text_color = "#121212"

                    btn_text = f"{status_display}"
                    if st.button(btn_text, key=f"btn_fp_{block_key}", use_container_width=True):
                        edit_free_period_modal(block_key, period_time)

                else:
                    display_text = "🚫 Blocked / Busy" if is_blocked else class_name
                    card_color = "#757575" if is_blocked else bg_color
                    text_color = "#FFFFFF" if is_blocked else "#121212"
                    st.markdown(
                        f"<div style='background-color:{card_color}; color:{text_color}; padding:6px; border-radius:5px; margin-bottom:6px; text-align:center; font-size:12px; font-weight:bold; border:1px solid #ddd;'>"
                        f"<small style='font-weight:normal; font-size:10px;'>{period_label}</small><br>{display_text}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    
    # ROW 3: Daily Notes
    st.subheader("💡 Daily Reminders & Special Schedule Notes")
    note_cols = st.columns(5)
    
    for idx, d in enumerate(week_days):
        date_str = d.strftime("%Y-%m-%d")
        saved_notes = st.session_state.daily_notes.get(date_str, [""])
        if not isinstance(saved_notes, list):
            saved_notes = [saved_notes] if saved_notes else [""]
            
        if len(saved_notes) == 0 or saved_notes[-1].strip() != "":
            saved_notes.append("")

        with note_cols[idx]:
            st.markdown(f"**{day_names[idx]} Notes**")
            updated_day_notes = []
            
            for note_idx, note_val in enumerate(saved_notes):
                note_key = f"note_{date_str}_{note_idx}"
                entry = st.text_area(
                    label=f"Reminder {note_idx + 1}",
                    value=note_val,
                    key=note_key,
                    placeholder="e.g., Leader meeting, Mass schedule",
                    height=68,
                    label_visibility="collapsed"
                )
                if entry.strip() != "":
                    updated_day_notes.append(entry)

            if updated_day_notes != [n for n in saved_notes if n.strip() != ""]:
                st.session_state.daily_notes[date_str] = updated_day_notes
                save_config()
                st.rerun()

# --- TAB 2: TASKS & ASSESSMENTS ---
with tab2:
    st.header("Tasks & Assessments Manager")
    
    with st.expander("➕ Add New Task or Exam"):
        with st.form("add_task_form"):
            title = st.text_input("Title (e.g., SAT Prep, Essay Draft, Club Deadline)")
            subject = st.selectbox("Category / Class", st.session_state.classes)
            task_type = st.selectbox("Type", ["Homework", "Assessment", "Extracurricular / Personal"])
            due_date = st.date_input("Due Date", date.today())
            
            if st.form_submit_button("Save Item"):
                if title:
                    new_item = pd.DataFrame([{
                        "id": str(uuid.uuid4()),
                        "Title": title,
                        "Class": subject,
                        "Type": task_type,
                        "Due Date": due_date,
                        "Status": "Pending"
                    }])
                    st.session_state.tasks = pd.concat([st.session_state.tasks, new_item], ignore_index=True)
                    save_tasks()
                    st.success(f"Added {task_type}: {title}")
                    st.rerun()

    col_sort, col_filter = st.columns(2)
    with col_sort:
        sort_by = st.radio("Sort View By:", ["Due Next", "Class"], horizontal=True)
    with col_filter:
        filter_cls = st.selectbox("Filter by Category:", ["All"] + st.session_state.classes)

    df = st.session_state.tasks.copy()
    if not df.empty:
        df["Due Date"] = pd.to_datetime(df["Due Date"])
        
        if filter_cls != "All":
            df = df[df["Class"] == filter_cls]
            
        col_hw, col_assess, col_extra = st.columns(3)
        
        def render_task_list(task_type, container, header_title):
            with container:
                st.subheader(header_title)
                filtered = df[df["Type"] == task_type].copy()
                
                if filtered.empty:
                    st.info("No items in this list!")
                    return

                filtered["is_completed"] = filtered["Status"] == "Completed"
                if sort_by == "Due Next":
                    filtered = filtered.sort_values(by=["is_completed", "Due Date"], ascending=[True, True])
                else:
                    filtered = filtered.sort_values(by=["is_completed", "Class"], ascending=[True, True])

                for idx, row in filtered.iterrows():
                    cols = st.columns([0.15, 0.5, 0.25, 0.1])
                    task_id = row["id"]
                    
                    is_done = row["Status"] == "Completed"
                    checked = cols[0].checkbox("", value=is_done, key=f"task_{task_id}")
                    
                    if checked != is_done:
                        st.session_state.tasks.loc[st.session_state.tasks["id"] == task_id, "Status"] = "Completed" if checked else "Pending"
                        save_tasks()
                        st.rerun()

                    title_str = f"~~{row['Title']}~~" if checked else f"**{row['Title']}**"
                    cols[1].markdown(f"{title_str} <br><small>{row['Class']}</small>", unsafe_allow_html=True)
                    cols[2].caption(row["Due Date"].strftime("%Y-%m-%d"))
                    
                    if cols[3].button("🗑️", key=f"del_{task_id}"):
                        st.session_state.tasks = st.session_state.tasks[st.session_state.tasks["id"] != task_id].reset_index(drop=True)
                        save_tasks()
                        st.rerun()

        render_task_list("Homework", col_hw, "📚 Homework & To-Dos")
        render_task_list("Assessment", col_assess, "🚨 Assessments & Exams")
        render_task_list("Extracurricular / Personal", col_extra, "🏆 Extracurricular")

# --- TAB 3: POMODORO TIMER ---
with tab3:
    st.header("⏱️ Pomodoro Focus Timer")
    st.caption("Standard focus timer with pause, resume, and reset capabilities.")

    if "timer_running" not in st.session_state:
        st.session_state.timer_running = False
    if "timer_seconds" not in st.session_state:
        st.session_state.timer_seconds = 25 * 60
    if "timer_mode" not in st.session_state:
        st.session_state.timer_mode = "Work Focus (25 min)"

    col_mode, col_timer = st.columns([1, 2])

    with col_mode:
        selected_mode = st.radio(
            "Select Session Mode:",
            ["Work Focus (25 min)", "Short Break (5 min)"],
            index=0 if st.session_state.timer_mode == "Work Focus (25 min)" else 1
        )

        if selected_mode != st.session_state.timer_mode:
            st.session_state.timer_mode = selected_mode
            st.session_state.timer_running = False
            st.session_state.timer_seconds = 25 * 60 if "Work" in selected_mode else 5 * 60
            st.rerun()

        st.markdown("---")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.session_state.timer_running:
                if st.button("⏸️ Pause", use_container_width=True):
                    st.session_state.timer_running = False
                    st.rerun()
            else:
                if st.button("▶️ Start / Resume", use_container_width=True):
                    st.session_state.timer_running = True
                    st.rerun()

        with col_btn2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.timer_running = False
                st.session_state.timer_seconds = 25 * 60 if "Work" in selected_mode else 5 * 60
                st.rerun()

    with col_timer:
        timer_placeholder = st.empty()

        mins, secs = divmod(st.session_state.timer_seconds, 60)
        border_color = "#1E88E5" if st.session_state.timer_running else "#888888"
        
        timer_placeholder.markdown(
            f"<div style='font-size: 72px; font-weight: bold; text-align: center; color: {border_color}; padding: 20px; border: 3px solid {border_color}; border-radius: 10px;'>"
            f"{mins:02d}:{secs:02d}"
            f"</div>",
            unsafe_allow_html=True
        )

        if st.session_state.timer_running and st.session_state.timer_seconds > 0:
            time.sleep(1)
            st.session_state.timer_seconds -= 1
            st.rerun()
        elif st.session_state.timer_running and st.session_state.timer_seconds == 0:
            st.session_state.timer_running = False
            timer_placeholder.markdown(
                f"<div style='font-size: 48px; font-weight: bold; text-align: center; color: #4CAF50; padding: 20px; border: 3px solid #4CAF50; border-radius: 10px;'>"
                f"🎉 Session Complete!"
                f"</div>",
                unsafe_allow_html=True
            )
            st.balloons()

# --- TAB 4: CUSTOMIZE SCHEDULE ---
with tab4:
    st.header("Schedule, Rooms & Color Configuration")

    # 0. ACADEMIC CALENDAR & CYCLE CONFIGURATION
    st.subheader("🗓️ Academic Calendar & Cycle Setup")
    with st.expander("📅 Set School Year Dates, Cycle Length & Holidays", expanded=True):
        cal_col1, cal_col2, cal_col3 = st.columns(3)
        
        cur_start = parse_date(st.session_state.school_start_date)
        cur_end = parse_date(st.session_state.school_end_date)
        
        new_start = cal_col1.date_input("Start of School Year", value=cur_start)
        new_end = cal_col2.date_input("End of School Year", value=cur_end)
        new_cycle_days = cal_col3.number_input("Days in Cycle", min_value=1, max_value=14, value=int(st.session_state.cycle_days_count))

        st.markdown("**Block Off Holidays & Breaks:**")
        
        selected_break_days = st.date_input(
            "Select dates to add to Blocked School Breaks",
            value=[],
            key="break_picker"
        )
        
        if st.button("➕ Add Selected Break Date(s)"):
            if isinstance(selected_break_days, list):
                dates_to_add = [d.strftime("%Y-%m-%d") for d in selected_break_days]
            else:
                dates_to_add = [selected_break_days.strftime("%Y-%m-%d")]
                
            updated_breaks = list(set(st.session_state.custom_breaks + dates_to_add))
            st.session_state.custom_breaks = sorted(updated_breaks)
            save_config()
            st.success("Added break dates!")
            st.rerun()

        st.markdown("**Current Blocked Holidays / Breaks:**")
        breaks_df = pd.DataFrame({"Date": st.session_state.custom_breaks})
        
        c_del_b, c_view_b = st.columns([0.4, 0.6])
        with c_del_b:
            remove_dates = st.multiselect("Select dates to remove:", st.session_state.custom_breaks)
            if st.button("🗑️ Remove Selected Breaks"):
                st.session_state.custom_breaks = [b for b in st.session_state.custom_breaks if b not in remove_dates]
                save_config()
                st.success("Removed selected break dates!")
                st.rerun()

        if st.button("💾 Save Academic Calendar Settings", type="primary"):
            st.session_state.school_start_date = new_start.strftime("%Y-%m-%d")
            st.session_state.school_end_date = new_end.strftime("%Y-%m-%d")
            st.session_state.cycle_days_count = int(new_cycle_days)
            save_config()
            st.success("Academic Calendar Settings Saved!")
            st.rerun()

    st.markdown("---")

    # 1. CLASS NAME MANAGER
    st.subheader("1. Class List Manager")
    with st.expander("✏️ Rename, Add, or Delete Classes"):
        st.markdown("**Rename Existing Classes:**")
        updated_classes = list(st.session_state.classes)
        
        for i, c_name in enumerate(st.session_state.classes):
            c1, c2 = st.columns([0.8, 0.2], vertical_alignment="bottom")
            new_name = c1.text_input(f"Class #{i+1}", value=c_name, key=f"rename_{i}")
            if c2.button("Delete", key=f"del_class_{i}", use_container_width=True):
                updated_classes.pop(i)
                st.session_state.classes = updated_classes
                save_config()
                st.rerun()
            else:
                updated_classes[i] = new_name

        st.markdown("---")
        new_class_input = st.text_input("Add New Class Name:", placeholder="e.g. AP Physics")
        if st.button("➕ Add Class"):
            if new_class_input and new_class_input not in updated_classes:
                updated_classes.append(new_class_input)
                st.session_state.classes = updated_classes
                save_config()
                st.rerun()

        if st.button("Save Class List Updates"):
            st.session_state.classes = updated_classes
            save_config()
            st.success("Class names updated successfully!")
            st.rerun()

    st.markdown("---")
    st.subheader("2. Subject Color Palette")
    color_cols = st.columns(3)
    for idx, cls in enumerate(st.session_state.classes):
        with color_cols[idx % 3]:
            st.session_state.colors[cls] = st.color_picker(
                f"{cls}", 
                st.session_state.colors.get(cls, "#FFFFFF")
            )
    
    if st.button("Save Palette"):
        save_config()
        st.success("Colors updated!")

    st.markdown("---")
    st.subheader(f"3. Edit {CYCLE_DAYS}-Day Rotation Class Grid")
    
    schedule_data = []
    for period, days in st.session_state.timetable.items():
        adjusted_days = (days + ["Free Period"] * CYCLE_DAYS)[:CYCLE_DAYS]
        schedule_data.append({"Time": period, **{f"Day {i+1}": adjusted_days[i] for i in range(CYCLE_DAYS)}})
    
    sched_df = pd.DataFrame(schedule_data)
    edited_df = st.data_editor(
        sched_df,
        column_config={
            f"Day {i+1}": st.column_config.SelectboxColumn(options=st.session_state.classes)
            for i in range(CYCLE_DAYS)
        },
        use_container_width=True,
        hide_index=True,
        key="sched_editor"
    )

    if st.button("Save Schedule Changes"):
        new_tt = {}
        for _, row in edited_df.iterrows():
            p_name = row["Time"]
            new_tt[p_name] = [row[f"Day {i+1}"] for i in range(CYCLE_DAYS)]
        st.session_state.timetable = new_tt
        save_config()
        st.success("Timetable updated successfully!")

    st.markdown("---")
    st.subheader("4. Edit Classroom Locations (Room Numbers)")
    
    room_data = []
    for period, rooms in st.session_state.rooms.items():
        adjusted_rooms = (rooms + ["TBD"] * CYCLE_DAYS)[:CYCLE_DAYS]
        room_data.append({"Time": period, **{f"Day {i+1}": adjusted_rooms[i] for i in range(CYCLE_DAYS)}})
    
    room_df = pd.DataFrame(room_data)
    edited_room_df = st.data_editor(
        room_df,
        use_container_width=True,
        hide_index=True,
        key="room_editor"
    )

    if st.button("Save Room Changes"):
        new_rooms = {}
        for _, row in edited_room_df.iterrows():
            p_name = row["Time"]
            new_rooms[p_name] = [str(row[f"Day {i+1}"]) for i in range(CYCLE_DAYS)]
        st.session_state.rooms = new_rooms
        save_config()
        st.success("Classroom locations saved!")

# --- TAB 5: GRADE CALCULATOR ---
with tab5:
    st.header("📊 Class Grade Calculator")

    with st.expander("⚙️ Manage Graded Classes List", expanded=False):
        st.write("Select which classes should be available in the Grade Calculator:")
        
        if "graded_classes" not in st.session_state:
            default_excluded = {
                "Advanced Photography", "Free Period", "Kairos", 
                "College Counseling", "X-Period", "Extracurricular / Other"
            }
            st.session_state.graded_classes = [c for c in st.session_state.classes if c not in default_excluded]

        updated_graded_classes = st.multiselect(
            "Graded Academic Classes:",
            options=st.session_state.classes,
            default=[c for c in st.session_state.graded_classes if c in st.session_state.classes],
            key="graded_classes_multiselect"
        )

        if updated_graded_classes != st.session_state.graded_classes:
            st.session_state.graded_classes = updated_graded_classes
            save_config()
            st.rerun()

    academic_classes = st.session_state.graded_classes

    if not academic_classes:
        st.info("No classes selected for grading. Use 'Manage Graded Classes List' above to add classes.")
    else:
        selected_class = st.selectbox("Select Academic Class:", academic_classes, key="grade_calc_subject_select")

        if selected_class:
            st.subheader(f"Grade Breakdown: {selected_class}")
            
            if selected_class not in st.session_state.grade_weights:
                st.session_state.grade_weights[selected_class] = DEFAULT_WEIGHTS.copy()
                
            class_weights = st.session_state.grade_weights[selected_class]

            with st.expander(f"⚙️ Customize Category Weights (%) for {selected_class}", expanded=False):
                w_col1, w_col2, w_col3 = st.columns(3)
                w_daily = w_col1.number_input("Daily Work Weight (%)", value=float(class_weights.get("daily", 10.0)), step=1.0, key=f"w_d_{selected_class}")
                w_form = w_col2.number_input("Formative Weight (%)", value=float(class_weights.get("formative", 20.0)), step=1.0, key=f"w_f_{selected_class}")
                w_eval = w_col3.number_input("Evaluative Weight (%)", value=float(class_weights.get("evaluative", 70.0)), step=1.0, key=f"w_e_{selected_class}")
                
                total_w = w_daily + w_form + w_eval
                if total_w != 100.0:
                    st.warning(f"⚠️ Total weight equals {total_w:.1f}%. (Should total 100%)")
                
                if st.button("Save Weights for Class", key=f"save_w_{selected_class}"):
                    st.session_state.grade_weights[selected_class] = {
                        "daily": w_daily,
                        "formative": w_form,
                        "evaluative": w_eval
                    }
                    save_config()
                    st.success("Weights updated successfully!")
                    st.rerun()

            if selected_class not in st.session_state.grades:
                st.session_state.grades[selected_class] = {
                    "daily": [],
                    "formative": [],
                    "evaluative": []
                }

            class_data = st.session_state.grades[selected_class]

            def calculate_avg(scores_list):
                valid_scores = []
                for item in scores_list:
                    val = item.get("score") if isinstance(item, dict) else item
                    try:
                        if str(val).strip() != "":
                            valid_scores.append(float(val))
                    except (ValueError, TypeError):
                        pass
                return sum(valid_scores) / len(valid_scores) if valid_scores else None

            col_daily, col_form, col_eval = st.columns(3)

            # 1. Daily Work Column
            with col_daily:
                st.markdown(f"### 📅 Daily ({w_daily:.0f}%)")
                daily_list = class_data.get("daily", [])
                updated_daily = []

                for i, score in enumerate(daily_list + [""]):
                    val = st.text_input(
                        f"Item #{i+1}", 
                        value=str(score), 
                        key=f"daily_in_{selected_class}_{i}",
                        placeholder="Score %"
                    )
                    if val.strip() != "":
                        updated_daily.append(val)

                if updated_daily != daily_list:
                    st.session_state.grades[selected_class]["daily"] = updated_daily
                    save_config()
                    st.rerun()

            # 2. Formative Column
            with col_form:
                st.markdown(f"### 📝 Formative ({w_form:.0f}%)")
                form_list = class_data.get("formative", [])
                updated_form = []

                for i, score in enumerate(form_list + [""]):
                    val = st.text_input(
                        f"Item #{i+1}", 
                        value=str(score), 
                        key=f"form_in_{selected_class}_{i}",
                        placeholder="Score %"
                    )
                    if val.strip() != "":
                        updated_form.append(val)

                if updated_form != form_list:
                    st.session_state.grades[selected_class]["formative"] = updated_form
                    save_config()
                    st.rerun()

            # 3. Evaluative Column
            with col_eval:
                st.markdown(f"### 🚨 Evaluative ({w_eval:.0f}%)")
                eval_list = class_data.get("evaluative", [])
                updated_eval = []

                eval_input_list = eval_list + [{"type": "Quiz", "score": ""}]

                for i, item in enumerate(eval_input_list):
                    if isinstance(item, dict):
                        item_type = item.get("type", "Quiz")
                        item_score = item.get("score", "")
                    else:
                        item_type = "Quiz"
                        item_score = str(item)

                    ec1, ec2 = st.columns([0.45, 0.55], vertical_alignment="bottom")
                    
                    e_type = ec1.selectbox(
                        f"Item #{i+1}",
                        ["Quiz", "Test", "Project", "Final"],
                        index=["Quiz", "Test", "Project", "Final"].index(item_type) if item_type in ["Quiz", "Test", "Project", "Final"] else 0,
                        key=f"eval_type_{selected_class}_{i}"
                    )
                    e_score = ec2.text_input(
                        f"Score #{i+1}",
                        value=str(item_score),
                        key=f"eval_score_{selected_class}_{i}",
                        placeholder="Score %",
                        label_visibility="hidden"
                    )

                    if e_score.strip() != "":
                        updated_eval.append({"type": e_type, "score": e_score})

                if updated_eval != eval_list:
                    st.session_state.grades[selected_class]["evaluative"] = updated_eval
                    save_config()
                    st.rerun()

            # --- GRADE OVERVIEW SUMMARY ---
            st.markdown("---")
            st.subheader("📈 Grade Overview")

            avg_daily = calculate_avg(st.session_state.grades[selected_class].get("daily", []))
            avg_form = calculate_avg(st.session_state.grades[selected_class].get("formative", []))
            avg_eval = calculate_avg(st.session_state.grades[selected_class].get("evaluative", []))

            g_col1, g_col2, g_col3, g_col4 = st.columns(4)

            g_col1.metric("Daily Avg", f"{avg_daily:.1f}%" if avg_daily is not None else "N/A")
            g_col2.metric("Formative Avg", f"{avg_form:.1f}%" if avg_form is not None else "N/A")
            g_col3.metric("Evaluative Avg", f"{avg_eval:.1f}%" if avg_eval is not None else "N/A")

            total_weight_used = 0.0
            weighted_sum = 0.0

            if avg_daily is not None:
                weighted_sum += avg_daily * (w_daily / 100.0)
                total_weight_used += (w_daily / 100.0)
            if avg_form is not None:
                weighted_sum += avg_form * (w_form / 100.0)
                total_weight_used += (w_form / 100.0)
            if avg_eval is not None:
                weighted_sum += avg_eval * (w_eval / 100.0)
                total_weight_used += (w_eval / 100.0)

            if total_weight_used > 0:
                final_grade = weighted_sum / total_weight_used
                g_col4.metric("Current Grade", f"{final_grade:.2f}%")
            else:
                g_col4.metric("Current Grade", "N/A")
