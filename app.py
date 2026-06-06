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
                🔒 Zero API Keys Required • 100% Local Processing • Multi-File Batch Ready
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
        
        text = re.sub(r'\n\s*\n', '\n\n', text)
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
            sections["History"] = "\n".join(history_blocks[:25]) 
        else:
            sections["History"] = "Clinical text scanned. Past history landmarks found throughout source file text body."

        # Expanded to 20,000 chars to comfortably hold data from multiple aggregated PDFs
        summary_limit = 20000 
        sections["Summary"] = text[:summary_limit].strip() + ("\n\n...[End of extraction reach]" if len(text) > summary_limit else "")
        
        if not sections["Critical_Alerts"]:
            sections["Critical_Alerts"].append("No acute warning keywords or explicit critical threshold violations flagged.")
        if not sections["Medications"]:
            sections["Medications"].append("No specific dosage metrics or medication logs extracted.")
            
        return sections

    def extract_text_from_multiple(uploaded_files_list):
        combined_text = ""
        for file in uploaded_files_list:
            combined_text += f"\n\n{'='*40}\n📄 SOURCE FILE: {file.name}\n{'='*40}\n\n"
            file_bytes = file.read()
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    combined_text += extracted + "\n"
        return combined_text

    def generate_pdf(summary_text, alerts, meds, history, name, dob, mrn):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # INDESTRUCTIBLE SANITIZER: Forces spaces so FPDF never runs out of horizontal room
        def safe_text(raw_text):
            # 1. Clean weird hidden PDF formatting blocks
            clean = str(raw_text).replace('\t', ' ').replace('\xa0', ' ')
            # 2. Force Latin-1 encoding so weird symbols don't crash the engine
            clean = clean.encode('latin1', 'ignore').decode('latin1')
            # 3. Mathematically force a space every 60 continuous non-space characters
            clean = re.sub(r'([^\s]{60})', r'\1 ', clean)
            return clean

        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(0, 10, "DocUFile Master Clinical Report", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Patient Name: {safe_text(name) if name else 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Date of Birth: {safe_text(dob) if dob else 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Medical Record #: {safe_text(mrn) if mrn else 'N/A'}", ln=True)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(10)

        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "Aggregated Critical Alerts & Red Flags:", ln=True)
        pdf.set_font("Arial", size=11)
        for alert in alerts:
            pdf.multi_cell(0, 6, f"- {safe_text(alert)}")
        pdf.ln(5)

        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "Aggregated Medications:", ln=True)
        pdf.set_font("Arial", size=11)
        for med in meds[:25]: 
            pdf.multi_cell(0, 6, f"- {safe_text(med)}")
        pdf.ln(5)

        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "Combined Text Extraction (All Files):", ln=True)
        pdf.set_font("Arial", size=11)
        
        for line in summary_text.split("\n"):
            if line.strip():
                pdf.multi_cell(0, 6, safe_text(line))
                pdf.ln(2)
        
        pdf_bytes = pdf.output()
        return io.BytesIO(pdf_bytes)

    # ---------------------------------
    # SIDEBAR & MAIN INTERFACE
    # ---------------------------------
    st.sidebar.title("📋 Patient Demographics")
    st.sidebar.write("Optional — used only for the PDF report header.")
    patient_name = st.sidebar.text_input("Patient Full Name", placeholder="Jane Smith")
    patient_dob = st.sidebar.text_input("Date of Birth", placeholder="MM/DD/YYYY")
    patient_mrn = st.sidebar.text_input("Medical Record # (MRN)", placeholder="123-456-789")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "📂 Upload Patient PDF(s) [Up to 300MB supported]",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Process All Files Together"):
            st.info(f"Merging {len(uploaded_files)} document(s) into a master file...")
            
            with st.spinner("Extracting and analyzing batch data..."):
                raw_text = extract_text_from_multiple(uploaded_files)
                result = parse_clinical_text(raw_text)

            st.write("### 🚨 Master Extracted Red Flags")
            alerts = result.get("Critical_Alerts", [])
            for alert in alerts:
                st.write(f"- {alert}")

            st.write("### 🩺 Master Document Ready")
            st.success("Batch successfully parsed! Click below to download the compiled multi-page PDF report.")

            pdf_buffer = generate_pdf(
                summary_text=result.get("Summary", ""),
                alerts=result.get("Critical_Alerts", []),
                meds=result.get("Medications", []),
                history=result.get("History", ""),
                name=patient_name, 
                dob=patient_dob, 
                mrn=patient_mrn
            )

            st.download_button(
                label="⬇️ Download Master PDF Report",
                data=pdf_buffer,
                file_name="DocUFile_Master_Report.pdf",
                mime="application/pdf"
            )
