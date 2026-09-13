import os
import json
import time
import uuid
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Student Rotation Planner", layout="wide")

# --- DATA PERSISTENCE SETUP ---
DATA_DIR = "data"
TASKS_FILE = os.path.join(DATA_DIR, "tasks.csv")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)

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

# --- LOAD CONFIG & SESSION STATE ---
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        st.session_state.classes = config.get("classes", DEFAULT_CLASSES)
        st.session_state.colors = config.get("colors", DEFAULT_COLORS)
        st.session_state.timetable = config.get("timetable", DEFAULT_TIMETABLE)
        st.session_state.rooms = config.get("rooms", DEFAULT_ROOMS)
        st.session_state.blocked_periods = config.get("blocked_periods", {})
        st.session_state.daily_notes = config.get("daily_notes", {})
        st.session_state.grades = config.get("grades", {})
        st.session_state.grade_weights = config.get("grade_weights", {})
else:
    st.session_state.classes = DEFAULT_CLASSES
    st.session_state.colors = DEFAULT_COLORS
    st.session_state.timetable = DEFAULT_TIMETABLE
    st.session_state.rooms = DEFAULT_ROOMS
    st.session_state.blocked_periods = {}
    st.session_state.daily_notes = {}
    st.session_state.grades = {}
    st.session_state.grade_weights = {}

if "tasks" not in st.session_state:
    if os.path.exists(TASKS_FILE):
        st.session_state.tasks = pd.read_csv(TASKS_FILE)
        if "id" not in st.session_state.tasks.columns:
            st.session_state.tasks["id"] = [str(uuid.uuid4()) for _ in range(len(st.session_state.tasks))]
        st.session_state.tasks["Due Date"] = pd.to_datetime(st.session_state.tasks["Due Date"]).dt.date
    else:
        st.session_state.tasks = pd.DataFrame(columns=["id", "Title", "Class", "Type", "Due Date", "Status"])

if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "classes": st.session_state.classes,
            "colors": st.session_state.colors,
            "timetable": st.session_state.timetable,
            "rooms": st.session_state.rooms,
            "blocked_periods": st.session_state.blocked_periods,
            "daily_notes": st.session_state.daily_notes,
            "grades": st.session_state.get("grades", {}),
            "grade_weights": st.session_state.get("grade_weights", {})
        }, f, indent=4)

def save_tasks():
    st.session_state.tasks.to_csv(TASKS_FILE, index=False)

def toggle_block(block_key):
    current = st.session_state.blocked_periods.get(block_key, False)
    st.session_state.blocked_periods[block_key] = not current
    save_config()

# --- SCHEDULED BREAKS & END DATE DEFINITION ---
def d_range(start_date, end_date):
    curr = start_date
    dates = set()
    while curr <= end_date:
        dates.add(curr)
        curr += timedelta(days=1)
    return dates

SCHOOL_BREAKS = set()
SCHOOL_BREAKS.add(date(2026, 10, 9))
SCHOOL_BREAKS.add(date(2026, 10, 12))
SCHOOL_BREAKS.update(d_range(date(2026, 11, 23), date(2026, 11, 30)))
SCHOOL_BREAKS.update(d_range(date(2026, 12, 21), date(2027, 1, 1)))
SCHOOL_BREAKS.update(d_range(date(2027, 2, 12), date(2027, 2, 16)))
SCHOOL_BREAKS.update(d_range(date(2027, 3, 15), date(2027, 3, 29)))

ANCHOR_DATE = date(2026, 9, 10)
SCHOOL_END_DATE = date(2027, 6, 4)

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
        
    return ((school_days - 1) % 6) + 1

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

    # Inject global button styling so free period buttons match class cards exactly
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

    # ROW 2: Classes & Room Numbers (Pixel-Perfect Alignment & Edit Dialog)
    
    # Dialog for editing free periods cleanly without breaking block styling
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
                if c_day:
                    class_name = schedule[c_day - 1]
                    room_no = st.session_state.rooms.get(period_time, [""]*6)[c_day - 1]
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

                    # Button styled cleanly using native Streamlit full-width layout
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

                # Sort: Pending items top, Completed items bottom
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
    
    # 0. CLASS NAME MANAGER
    st.subheader("1. Class List Manager")
    with st.expander("✏️ Rename, Add, or Delete Classes"):
        st.markdown("**Rename Existing Classes:**")
        updated_classes = list(st.session_state.classes)
        for i, c_name in enumerate(st.session_state.classes):
            c1, c2 = st.columns([0.8, 0.2])
            new_name = c1.text_input(f"Class #{i+1}", value=c_name, key=f"rename_{i}")
            if c2.button("Delete", key=f"del_class_{i}"):
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
    st.subheader("3. Edit 6-Day Rotation Class Grid")
    
    schedule_data = []
    for period, days in st.session_state.timetable.items():
        schedule_data.append({"Time": period, **{f"Day {i+1}": days[i] for i in range(6)}})
    
    sched_df = pd.DataFrame(schedule_data)
    edited_df = st.data_editor(
        sched_df,
        column_config={
            f"Day {i+1}": st.column_config.SelectboxColumn(options=st.session_state.classes)
            for i in range(6)
        },
        use_container_width=True,
        hide_index=True,
        key="sched_editor"
    )

    if st.button("Save Schedule Changes"):
        new_tt = {}
        for _, row in edited_df.iterrows():
            p_name = row["Time"]
            new_tt[p_name] = [row[f"Day {i+1}"] for i in range(6)]
        st.session_state.timetable = new_tt
        save_config()
        st.success("Timetable updated successfully!")

    st.markdown("---")
    st.subheader("4. Edit Classroom Locations (Room Numbers)")
    
    room_data = []
    for period, rooms in st.session_state.rooms.items():
        room_data.append({"Time": period, **{f"Day {i+1}": rooms[i] for i in range(6)}})
    
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
            new_rooms[p_name] = [str(row[f"Day {i+1}"]) for i in range(6)]
        st.session_state.rooms = new_rooms
        save_config()
        st.success("Classroom locations saved!")

# --- TAB 5: GRADE CALCULATOR ---
with tab5:
    st.header("📊 Class Grade Calculator")

    EXCLUDED_CLASSES = {
        "Advanced Photography", "Free Period", "Kairos", 
        "College Counseling", "X-Period", "Extracurricular / Other"
    }
    academic_classes = [c for c in st.session_state.classes if c not in EXCLUDED_CLASSES]

    selected_class = st.selectbox("Select Academic Class:", academic_classes)

    if selected_class:
        st.subheader(f"Grade Breakdown: {selected_class}")
        
        # Load or set default weightings for this class
        class_weights = st.session_state.grade_weights.get(selected_class, DEFAULT_WEIGHTS.copy())
        
        with st.expander("⚙️ Customize Category Weights (%) for " + selected_class, expanded=True):
            w_col1, w_col2, w_col3 = st.columns(3)
            w_daily = w_col1.number_input("Daily Work Weight (%)", value=float(class_weights.get("daily", 10.0)), step=1.0)
            w_form = w_col2.number_input("Formative Weight (%)", value=float(class_weights.get("formative", 20.0)), step=1.0)
            w_eval = w_col3.number_input("Evaluative Weight (%)", value=float(class_weights.get("evaluative", 70.0)), step=1.0)
            
            total_w = w_daily + w_form + w_eval
            if total_w != 100.0:
                st.warning(f"⚠️ Total weight equals {total_w:.1f}%. (It should ideally equal 100%)")
            
            st.session_state.grade_weights[selected_class] = {
                "daily": w_daily,
                "formative": w_form,
                "evaluative": w_eval
            }

        if selected_class not in st.session_state.grades:
            st.session_state.grades[selected_class] = {
                "daily": [""],
                "formative": [""],
                "evaluative": [{"type": "Quiz", "score": ""}]
            }

        class_data = st.session_state.grades[selected_class]

        col_daily, col_form, col_eval = st.columns(3)

        # 1. Daily Grades
        with col_daily:
            st.markdown(f"### 📅 Daily Work ({w_daily:.0f}%)")
            daily_list = class_data.get("daily", [""])
            if not daily_list or daily_list[-1] != "":
                daily_list.append("")
            
            updated_daily = []
            for i, score in enumerate(daily_list):
                val = st.text_input(
                    f"Daily #{i+1}", 
                    value=str(score) if score != "" else "", 
                    key=f"daily_{selected_class}_{i}",
                    placeholder="e.g. 95"
                )
                if val.strip() != "":
                    try:
                        updated_daily.append(float(val))
                    except ValueError:
                        st.error("Enter a number")
            
            class_data["daily"] = updated_daily

        # 2. Formative Grades
        with col_form:
            st.markdown(f"### 📝 Formative / HW ({w_form:.0f}%)")
            form_list = class_data.get("formative", [""])
            if not form_list or form_list[-1] != "":
                form_list.append("")
            
            updated_form = []
            for i, score in enumerate(form_list):
                val = st.text_input(
                    f"HW/Formative #{i+1}", 
                    value=str(score) if score != "" else "", 
                    key=f"form_{selected_class}_{i}",
                    placeholder="e.g. 88"
                )
                if val.strip() != "":
                    try:
                        updated_form.append(float(val))
                    except ValueError:
                        st.error("Enter a number")

            class_data["formative"] = updated_form

        # 3. Evaluative Grades
        with col_eval:
            st.markdown(f"### 🚨 Evaluative ({w_eval:.0f}%)")
            st.caption("Tests weight 2x compared to Quizzes")
            
            eval_list = class_data.get("evaluative", [{"type": "Quiz", "score": ""}])
            if not eval_list or eval_list[-1]["score"] != "":
                eval_list.append({"type": "Quiz", "score": ""})

            updated_eval = []
            for i, item in enumerate(eval_list):
                c_type, c_score = st.columns([0.4, 0.6])
                
                e_type = c_type.selectbox(
                    "Type", 
                    ["Quiz", "Test"], 
                    index=0 if item.get("type", "Quiz") == "Quiz" else 1,
                    key=f"eval_type_{selected_class}_{i}",
                    label_visibility="collapsed"
                )
                
                e_val = c_score.text_input(
                    f"Eval #{i+1}", 
                    value=str(item["score"]) if item["score"] != "" else "", 
                    key=f"eval_score_{selected_class}_{i}",
                    placeholder="Grade",
                    label_visibility="collapsed"
                )
                
                if e_val.strip() != "":
                    try:
                        updated_eval.append({"type": e_type, "score": float(e_val)})
                    except ValueError:
                        st.error("Enter a number")

            class_data["evaluative"] = updated_eval

        st.session_state.grades[selected_class] = class_data
        save_config()

        st.markdown("---")
        
        daily_scores = [s for s in class_data["daily"] if isinstance(s, (int, float))]
        daily_avg = sum(daily_scores) / len(daily_scores) if daily_scores else None

        form_scores = [s for s in class_data["formative"] if isinstance(s, (int, float))]
        form_avg = sum(form_scores) / len(form_scores) if form_scores else None

        eval_items = [e for e in class_data["evaluative"] if isinstance(e.get("score"), (int, float))]
        
        total_eval_points = 0
        total_eval_weight = 0
        for e in eval_items:
            w = 2.0 if e["type"] == "Test" else 1.0
            total_eval_points += e["score"] * w
            total_eval_weight += w

        eval_avg = total_eval_points / total_eval_weight if total_eval_weight > 0 else None

        weighted_sum = 0
        total_applied_weight = 0

        if daily_avg is not None:
            weighted_sum += daily_avg * (w_daily / 100.0)
            total_applied_weight += (w_daily / 100.0)
            
        if form_avg is not None:
            weighted_sum += form_avg * (w_form / 100.0)
            total_applied_weight += (w_form / 100.0)
            
        if eval_avg is not None:
            weighted_sum += eval_avg * (w_eval / 100.0)
            total_applied_weight += (w_eval / 100.0)

        final_grade = (weighted_sum / total_applied_weight) if total_applied_weight > 0 else None

        def get_letter_grade(pct):
            if pct is None: return "N/A"
            if pct >= 93: return "A"
            if pct >= 90: return "A-"
            if pct >= 87: return "B+"
            if pct >= 83: return "B"
            if pct >= 80: return "B-"
            if pct >= 77: return "C+"
            if pct >= 73: return "C"
            if pct >= 70: return "C-"
            if pct >= 60: return "D"
            return "F"

        st.subheader("📈 Summary Breakdown")
        m1, m2, m3, m4 = st.columns(4)
        
        m1.metric(f"Daily Avg ({w_daily:.0f}%)", f"{daily_avg:.1f}%" if daily_avg is not None else "No grades")
        m2.metric(f"Formative Avg ({w_form:.0f}%)", f"{form_avg:.1f}%" if form_avg is not None else "No grades")
        m3.metric(f"Evaluative Avg ({w_eval:.0f}%)", f"{eval_avg:.1f}%" if eval_avg is not None else "No grades")
        
        if final_grade is not None:
            letter = get_letter_grade(final_grade)
            m4.metric("Overall Class Grade", f"{final_grade:.2f}% ({letter})")
        else:
            m4.metric("Overall Class Grade", "Enter grades above")
