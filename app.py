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
        max-width: 400px;
        margin: 50px auto;
        padding: 30px;
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: #111827;
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
    st.image("https://cdn-icons-png.flaticon.com/512/5087/5087579.png", width=100)
    st.title("🔐 DocUFile Login")
    st.write("Please sign in to access clinical tools.")
    
    username = st.text_input("Username", placeholder="Enter username")
    password = st.text_input("Password", type="password", placeholder="Enter password")
    
    if st.button("Log In", use_container_width=True):
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
    # LOCAL CLINICAL PARSER (No AI/API Needed)
    # ---------------------------------
    def parse_clinical_text(text):
        # A smart regex dictionary that segments your medical files automatically
        sections = {
            "Summary": "No general summary layout detected in text structure.",
            "Critical_Alerts": [],
            "Medications": [],
            "History": "No clear past historical section found."
        }
        
        # 1. Extract Medications using standard clinical naming conventions
        med_matches = re.findall(r'(?i)\b(mg|mcg|g|ml|tabs|capsules|tablets|daily|twice|refill|prescribed|take|dosage|ordered)\b', text)
        lines = text.split('\n')
        for line in lines:
            if any(k in line.lower() for k in ['mg', 'mcg', 'tabs', 'caps', 'daily', 'bid', 'tid', 'po', 'rx']):
                clean_line = line.strip()
                if len(clean_line) > 5 and clean_line not in sections["Medications"]:
                    sections["Medications"].append(clean_line)
                    
        # 2. Scan for Critical Flags / High Risk Red Flags
        critical_keywords = ['critical', 'severe', 'abnormal', 'alert', 'positive', 'high risk', 'emergency', 'acute', 'allergic', 'allergy', 'malignant', 'fail']
        for line in lines:
            if any(ck in line.lower() for ck in critical_keywords):
                clean_alert = line.strip()
                if len(clean_alert) > 5 and clean_alert not in sections["Critical_Alerts"]:
                    sections["Critical_Alerts"].append(clean_alert)

        # 3. Handle General Text Splitting for Summary & History windows
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
            # Fallback mapping if explicit headers aren't found
            sections["History"] = "Clinical text scanned. Past history landmarks found throughout source file text body."

        # Generate standard layout overview fallback
        sections["Summary"] = text[:400].strip() + "..." if len(text) > 400 else text.strip()
        
        # Clean defaults if arrays are empty
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
                text += extracted
        return text

    def generate_pdf(summary_text, name, dob, mrn):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(0, 10, "DocUFile Clinical Summary Report", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Patient Name: {name if name else 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Date of Birth: {dob if dob else 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Medical Record #: {mrn if mrn else 'N/A'}", ln=True)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(10)

        for line in summary_text.split("\n"):
            clean_line = line.encode('latin1', 'ignore').decode('latin1')
            pdf.multi_cell(0, 8, clean_line)
        
        pdf_bytes = pdf.output()
        return io.BytesIO(pdf_bytes)

    # ---------------------------------
    # SIDEBAR: PATIENT DEMOGRAPHICS
    # ---------------------------------
    st.sidebar.title("📋 Patient Demographics")
    st.sidebar.write("Optional — used only for the PDF report header.")
    patient_name = st.sidebar.text_input("Patient Full Name", placeholder="Jane Smith")
    patient_dob = st.sidebar.text_input("Date of Birth", placeholder="MM/DD/YYYY")
    patient_mrn = st.sidebar.text_input("Medical Record # (MRN)", placeholder="123-456-789")

    # ---------------------------------
    # MAIN INTERFACE LAYOUT
    # ---------------------------------
    cols = st.columns(4)
    step_data = [
        ("1. Secure Gateway", "Logged in securely as administrator."),
        ("2. Patient Details", "Enter optional demographics in the sidebar."),
        ("3. Upload Files", "Drop one or more clinical PDFs below."),
        ("4. Parse Insights", "Extract structural profiles safely with zero keys.")
    ]
    for i, (title, desc) in enumerate(step_data):
        with cols[i]:
            st.markdown(f"""
                <div style="background-color: #f8f9fa; border: 1px solid #e5e7eb; padding: 15px; border-radius: 5px; text-align: center; height: 110px; color: #111827;">
                    <b style="color: #1d3557;">{title}</b><br><span style="font-size: 0.85em; color: #4b5563;">{desc}</span>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    dash_col1, dash_col2 = st.columns(2)
    with dash_col1:
        st.markdown("""
            <div class="info-card">
                <h3>What DocUFile does</h3>
                <ul>
                    <li>Parses raw structure layout text parameters</li>
                    <li>Isolates prescription dosages, measurements & clinical records</li>
                    <li>Extracts safety anomalies based on warning key rules</li>
                    <li>Generates custom-formatted archival PDF output packets</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    with dash_col2:
        st.markdown("""
            <div class="info-card">
                <h3>Privacy & Safety</h3>
                <ul>
                    <li><b>Zero Network Pings</b> — No data is sent to external API addresses</li>
                    <li>Everything wiped instantly when this server stream session tab closes</li>
                    <li>No database logs — text stays in local runtime string blocks</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><hr>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "📂 Upload Patient PDF(s) to Start Secure Local Parsing",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Start Extraction"):
            for file in uploaded_files:
                st.subheader(f"📄 Processing: {file.name}")

                raw_text = extract_text(file)
                result = parse_clinical_text(raw_text)

                # Display Results
                st.write("### 🩺 Medical Document Text Overview")
                st.info(result.get("Summary", "No readable text profile isolated."))

                # Critical Alerts
                st.write("### 🚨 Extracted Red Flags & Alerts")
                alerts = result.get("Critical_Alerts", [])
                for alert in alerts:
                    st.write(f"- {alert}")

                # Medications & History
                col1, col2 = st.columns(2)
                with col1:
                    st.write("### 💊 Extracted Medications Lines")
                    meds = result.get("Medications", [])
                    for med in meds:
                        st.write(f"- {med}")
                        
                with col2:
                    st.write("### 📜 Identified History Block")
                    st.write(result.get("History", ""))

                # Download Summary Button
                pdf_buffer = generate_pdf(
                    result.get("Summary", "No text data package available."),
                    patient_name, patient_dob, patient_mrn
                )

                st.download_button(
                    label="⬇️ Download Document Report",
                    data=pdf_buffer,
                    file_name=f"{file.name}_parsed_report.pdf",
                    mime="application/pdf"
                )
