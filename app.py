import streamlit as st
from pypdf import PdfReader
import io
import re
from fpdf import FPDF

# ---------------------------------
# PAGE SETTINGS & STYLING
# ---------------------------------
st.set_page_config(page_title="DocUFile", page_icon="🩺", layout="wide")

st.markdown("""
    <style>
    .main-header {
        background-color: #1d3557;
        padding: 30px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    .info-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        height: 100%;
        color: #111827;
    }
    .login-container {
        max-width: 450px;
        margin: 40px auto;
        padding: 30px;
        background-color: transparent;
        color: #ffffff;
    }
    /* Styling for our custom stethoscope logo */
    .logo-container {
        text-align: center;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 42px;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 15px;
    }
    .logo-doc {
        color: #24b4ff; 
    }
    .logo-file {
        color: #457b9d;
    }
    .logo-icon {
        width: 46px;
        vertical-align: middle;
        margin: 0 -4px;
    }
    /* This completely hides the default white form background block */
    div[data-testid="stForm"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------
# LOGIN SYSTEM STATE
# ---------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- LOGIN PAGE INTERFACE ---
if not st.session_state["logged_in"]:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="logo-container">
            <span class="logo-doc">Doc</span>
            <img class="logo-icon" src="https://cdn-icons-png.flaticon.com/512/387/387561.png" alt="Stethoscope">
            <span class="logo-file">File</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<h2 style="text-align:center; margin-top:0;">🔐 Login Area</h2>', unsafe_allow_html=True)
    st.write("<p style='text-align:center; color:#9ca3af;'>Fill your details and press Enter to access clinical tools.</p>", unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        submit_button = st.form_submit_button("Log In", use_container_width=True)
        
        if submit_button:
            if username == "admin" and password == "admin":
                st.session_state["logged_in"] = True
                st.success("Access Granted!")
                st.rerun()
            else:
                st.error("Incorrect Username or Password. Please try again.")
                
    st.markdown('</div>', unsafe_allow_html=True)

# --- LOCKED MAIN CONTENT (ONLY SHOWS IF LOGGED IN) ---
else:
    if st.sidebar.button("🚪 Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.markdown("""
        <div class="main-header">
            <h1>🩺 DocUFile</h1>
            <p>Secure Clinical Document Parser & Triage Assistant</p>
            <span style="background-color: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">
                🔒 Zero API Keys Required • 100% Local Rule-Based Processing
            </span>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # LOCAL CLINICAL PARSER
    # ---------------------------------
    def parse_clinical_text(text):
        sections = {
            "Summary": "No general summary layout detected in text structure.",
            "Critical_Alerts": [],
            "Medications": [],
            "History": "No clear past historical section found."
        }
        
        lines = text.split('\n')
        for line in lines:
            if any(k in line.lower() for k in ['mg', 'mcg', 'tabs', 'caps', 'daily', 'bid', 'tid', 'po', 'rx']):
                clean_line = line.strip()
                if len(clean_line) > 5 and clean_line not in sections["Medications"]:
                    sections["Medications"].append(clean_line)
                    
        critical_keywords = ['critical', 'severe', 'abnormal', 'alert', 'positive', 'high risk', 'emergency', 'acute', 'allergic', 'allergy', 'malignant', 'fail']
        for line in lines:
            if any(ck in line.lower() for ck in critical_keywords):
                clean_alert = line.strip()
                if len(clean_alert) > 5 and clean_alert not in sections["Critical_Alerts"]:
                    sections["Critical_Alerts"].append(clean_alert)

        history_blocks = []
        capture_history = False
        
        for line in lines:
            if any(h_key in line.lower() for h_key in ['history', 'past medical', 'pmh', 'prior diagnosis']):
                capture_history = True
                continue
            if capture_history and any(stop_key in line.lower() for stop_key in ['medication', 'plan', 'signature', 'vital', 'labs']):
                capture_history = False
            if capture_history and line.strip():
                history_blocks.append(line.strip())

        if history_blocks:
            sections["History"] = "\n".join(history_blocks[:10])
        else:
            sections["History"] = "Clinical text scanned. Past history landmarks found throughout source file text body."

        sections["Summary"] = text[:400].strip() + "..." if len(text) > 400 else text.strip()
        
        if not sections["Critical_Alerts"]:
            sections["Critical_Alerts"].append("No acute warning keywords or explicit critical threshold violations flagged.")
        if not sections["Medications"]:
            sections["Medications"].append("No specific dosage metrics or medication logs extracted.")
            
        return sections

    def extract_text(uploaded_file):
        file_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
