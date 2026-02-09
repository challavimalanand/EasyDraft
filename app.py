import streamlit as st
import os
import tempfile
import hashlib  
from datetime import date
from docx import Document

from utils import (
    load_states, load_courts, load_cases, load_benches,
    load_python_module, replace_placeholders,
    get_court_name_for_bench
)

# ---------------- HARDCODED USERS (Username: Plain Password) ----------------
USERS = {
    "admin": "admin12345",      # password: "admin12345"
    "chetluru": "chetluru09",   # password: "chetluru09"
    "ramana": "ramana61",       # password: "ramana61"
    "ravikiran": "ravi$5269",       # password: "ramana61"
}

# ---------------- LOGIN FUNCTIONS ----------------
def check_login(username, password):
    """Check if username exists and password matches"""
    if username in USERS:
        # Direct plain text comparison
        return USERS[username] == password
    return False

def login_page():
    """Display login form"""
    st.title("⚖️ EasyDraft - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    st.markdown("---")
    st.caption("Developed by Challa Vimalanand, Advocate & Patent Agent")

# ---------------- PATHS ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, "modules")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# ---------------- SESSION INIT ----------------
def init_session():
    defaults = {
        "logged_in": False,          # NEW: Track login status
        "username": "",              # NEW: Store username
        "selected_state": "",
        "selected_court": "",
        "selected_case": "",
        "selected_bench": "",
        "form_version": 0,     # 🔑 UI reset key
        "entries": {},
        "current_template": None,
        "bench_court_name": "",
        "autofill_mode": False
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

# ---------------- MAIN APP ----------------
def main():
    st.set_page_config(
        page_title="EasyDraft – Legal Document Generator",
        layout="wide",
        page_icon="⚖️"
    )

    init_session()

    # NEW: Check login status
    if not st.session_state.logged_in:
        login_page()
        return  # Stop here if not logged in

    st.title("⚖️ EasyDraft – Legal Document Generator")

        # -------- SIDEBAR --------
    with st.sidebar:
        st.header("Court Selection")

        states = load_states()
        state = st.selectbox("State", states, key="state_sel")
        st.session_state.selected_state = state

        courts = load_courts(state)
        court = st.selectbox("Court", courts, key="court_sel")
        st.session_state.selected_court = court

        benches = load_benches(state, court)
        bench = ""
        if benches:
            bench = st.selectbox("Bench", [""] + benches, key="bench_sel")
        st.session_state.selected_bench = bench

        cases = load_cases(state, court)
        case = st.selectbox("Case Type", cases, key="case_sel")
        st.session_state.selected_case = case

        st.markdown("---")

        # Get bench value for button logic
        current_bench = st.session_state.get("selected_bench", "")
        
        # COURT NAME BUTTON - ALWAYS VISIBLE
        fill_disabled = not current_bench
        if st.button("🏛️ Fill Court Name", 
                    disabled=fill_disabled,
                    use_container_width=True,
                    help="Select a bench first" if fill_disabled else "Fill court name from selected bench"):
            if current_bench:  # Double check
                bench_court_name = get_court_name_for_bench(state, court, current_bench)
                if bench_court_name:
                    st.session_state.bench_court_name = bench_court_name
                    st.session_state.form_version += 1
                    st.rerun()

        # ACTION BUTTONS
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Reset Form", use_container_width=True):
                # Clear specific form-related states
                keys_to_clear = [
                    "autofill_mode", 
                    "bench_court_name",
                    "selected_bench",  # Clear this too
                    "state_sel",
                    "court_sel", 
                    "bench_sel",
                    "case_sel"
                ]
                
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.session_state.form_version += 1
                st.rerun()
        
        with col2:
            if st.button("🧪 Auto Fill", use_container_width=True):
                st.session_state.autofill_mode = True
                st.session_state.form_version += 1
                st.rerun()

        st.markdown("---")

        # USER INFO & LOGOUT - ALWAYS VISIBLE
        st.caption(f"Logged in as: **{st.session_state.username}**")
        
        if st.button("🚪 Logout", use_container_width=True):
            # Clear all session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


    # -------- FORM LOAD --------
    if not (state and court and case):
        st.info("Select State, Court, and Case to continue.")
        return

    mod_path = os.path.join(MODULES_DIR, state, court, f"{case}.py")
    mod = load_python_module(mod_path)

    template_path = os.path.join(TEMPLATES_DIR, state, court, f"{case}.docx")
    st.session_state.current_template = template_path

    # Bench-based court name
    is_high = "high" in court.lower()
    bench_court_name = ""
    if is_high and bench:
        bench_court_name = get_court_name_for_bench(state, court, bench)
    st.session_state.bench_court_name = bench_court_name

    # -------- FORM UI --------
    st.subheader("Document Details")

    with st.form(
        key=f"draft_form_{st.session_state.form_version}",
        clear_on_submit=False
    ):
        entries = {}

        for key, label in mod.FIELDS:
            default = ""

            # 1. If it's court_name AND we have a bench court name stored, use it
            if key == "court_name" and st.session_state.get("bench_court_name"):
                default = st.session_state.bench_court_name
            
            # 2. If auto-fill mode is ON, fill with test text
            elif st.session_state.autofill_mode:
                default = "This is a test Run"
                
                # Except for year field
                if key == "year":
                    default = str(date.today().year)
                # And if we also have bench court name, use it for court_name
                elif key == "court_name" and st.session_state.get("bench_court_name"):
                    default = st.session_state.bench_court_name
            
            # 3. Normal/default values
            else:
                if key == "year":
                    default = str(date.today().year)

            widget_key = f"field_{key}_{st.session_state.form_version}"

            # ✅ ALL FIELDS AS TEXT AREA
            entries[key] = st.text_area(
                label=label,
                value=default,
                key=widget_key,
                height=90
            )

        submitted = st.form_submit_button("📄 Generate Document", type="primary")

    # -------- GENERATE DOC --------
    if submitted:
        # VALIDATION: Check all fields are filled
        empty_fields = []
        data = {}
        
        for key, value in entries.items():
            clean_value = (value or "").strip()
            data[key] = clean_value
            
            # Skip validation for "year" field (auto-filled)
            if key == "year":
                continue
                
            # Check if field is empty
            if not clean_value:
                # Find the field label for better error message
                field_label = key  # default to key name
                for field_key, label in mod.FIELDS:
                    if field_key == key:
                        field_label = label
                        break
                empty_fields.append(field_label)
        
        # If any required fields are empty, show error and STOP
        if empty_fields:
            st.error("❌ **Please fill all required fields:**")
            for field in empty_fields:
                st.write(f"• {field}")
            st.warning("All fields must be completed before generating document.")
            
            # Show the download button as DISABLED
            st.button(
                "⬇️ Download Word Document (Disabled - Fill All Fields)",
                disabled=True,
                help="Complete all fields to enable download"
            )
            
            # Don't generate document
            return  # Exit the function early
        
        # ✅ ALL FIELDS FILLED - Generate document
        doc = Document(st.session_state.current_template)
        replace_placeholders(doc, data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            st.download_button(
                "⬇️ Download Word Document",
                data=f.read(),
                file_name=f"{case}_{date.today().strftime('%Y%m%d')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        os.unlink(tmp_path)
        st.success("✅ Document generated successfully!")

        # Clear autofill after successful submit
        st.session_state.autofill_mode = False



# ---------------- RUN ----------------
if __name__ == "__main__":
    main()
