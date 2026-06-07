import streamlit as st
from pypdf import PdfReader
import io
import re
import html
import pandas as pd
import hashlib
import time
import logging
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- OCR Dependencies ---
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ---------------------------------
# AUDIT LOGGING SETUP
# ---------------------------------
logger = logging.getLogger("DocUFile_Audit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("docufile_audit_trail.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# ---------------------------------
# PAGE SETTINGS & STYLING
# ---------------------------------
st.set_page_config(page_title="DocUFile Pro", page_icon="🩺", layout="wide")

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
    .logo-doc { color: #24b4ff; }
    .logo-file { color: #457b9d; }
    .logo-icon { width: 46px; vertical-align: middle; margin: 0 -4px; }
    div[data-testid="stForm"] { background-color: transparent !important; border: none !important; padding: 0 !important; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------
# SESSION TIMEOUT & STATE LOGIC
# ---------------------------------
TIMEOUT_SECONDS = 900 # 15 Minutes

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["last_active"] = time.time()

if st.session_state["logged_in"]:
    current_time = time.time()
    if current_time - st.session_state["last_active"] > TIMEOUT_SECONDS:
        logger.warning(f"TIMEOUT: Session expired for {st.session_state['username']} due to 15 minutes of inactivity.")
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.warning("🔒 Your session has expired due to 15 minutes of inactivity. Please log in again.")
    else:
        st.session_state["last_active"] = current_time

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
    
    st.markdown('<h2 style="text-align:center; margin-top:0;">🔐 Secure Access Area</h2>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        submit_button = st.form_submit_button("Log In", use_container_width=True)
        
        if submit_button:
            # Hash for "admin123"
            correct_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
            
            # SECRETS MANAGEMENT: Pulls from Streamlit Cloud Secrets, falls back to default if missing
            db_username = st.secrets.get("admin_username", "admin")
            db_hash = st.secrets.get("admin_hash", correct_hash)
            
            # Scramble the input password to check against the secure hash
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if username == db_username and input_hash == db_hash:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["last_active"] = time.time()
                logger.info(f"SUCCESS: Secure login by user '{username}'.")
                st.rerun()
            else:
                logger.warning(f"FAILED LOGIN: Invalid attempt for username '{username}'.")
                st.error("Incorrect Username or Password.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- LOCKED MAIN CONTENT ---
else:
    if st.sidebar.button("🚪 Log Out"):
        logger.info(f"LOGOUT: User '{st.session_state['username']}' manually logged out.")
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

    st.markdown("""
        <div class="main-header">
            <h1>🩺 DocUFile Pro</h1>
            <p>Advanced Clinical Parser with OCR, Date Mapping & EMR Export</p>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # CORE PROCESSING ENGINES
    # ---------------------------------
    def extract_text_with_ocr(uploaded_files_list):
        combined_text = ""
        for file in uploaded_files_list:
            file_bytes = file.read()
            reader = PdfReader(io.BytesIO(file_bytes))
            doc_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    doc_text += extracted + " "
            
            if len(doc_text.strip()) < 50 and OCR_AVAILABLE:
                with st.spinner(f"Dead scan detected in {file.name}. Booting OCR Vision Engine..."):
                    try:
                        images = convert_from_bytes(file_bytes)
                        for img in images:
                            doc_text += pytesseract.image_to_string(img) + " "
                    except Exception as e:
                        doc_text += f" [OCR Error: Could not read image based PDF] "
            
            combined_text += doc_text + " "
        return combined_text

    def parse_clinical_text(text):
        clean_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text) 
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)

        urgent_bullets, finding_bullets, med_bullets = set(), set(), set()

        urgent_keywords = ['acute', 'severe', 'critical', 'emergency', 'urgent', 'malignan', 'life-threatening', 'hemorrhage', 'infarct']
        diag_keywords = ['findings:', 'impression:', 'assessment:', 'evidence of', 'consistent with', 'diagnosed with', 'reveals', 'conclusion:']
        med_keywords = [' mg ', ' mcg ', ' ml ', ' tabs ', ' capsule', ' tablet', ' po ', ' daily ', ' bid ', ' tid ', ' qid ', ' prn ', 'dose', 'prescribed ']

        date_pattern = r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b'

        for sentence in sentences:
            s_lower = sentence.lower()
            clean_s = re.sub(r'\s+', ' ', sentence).strip()
            
            if len(clean_s) < 10 or len(clean_s) > 300: 
                continue

            found_dates = re.findall(date_pattern, clean_s, re.IGNORECASE)
            date_prefix = f"[{found_dates[0]}] - " if found_dates else ""
            timeline_string = date_prefix + clean_s

            if any(k in s_lower for k in med_keywords) and len(clean_s) < 150:
                med_bullets.add(timeline_string)
                continue 

            if any(k in s_lower for k in urgent_keywords):
                urgent_bullets.add(timeline_string)
            elif any(k in s_lower for k in diag_keywords):
                finding_bullets.add(timeline_string)

        return {
            "Urgent": list(urgent_bullets)[:25] if urgent_bullets else ["No explicit urgency keywords flagged."],
            "Diagnoses": list(finding_bullets)[:50] if finding_bullets else ["No standard clinical diagnosis terminology detected."],
            "Medications": list(med_bullets)[:60] if med_bullets else ["No structured medication or dosage data detected."]
        }

    # ---------------------------------
    # EXPORT GENERATORS (PDF & CSV)
    # ---------------------------------
    def generate_pdf(report_title, sections_dict, name, dob, mrn):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        Normal, Heading2, TitleStyle = styles['Normal'], styles['Heading2'], styles['Title']
        BulletStyle = ParagraphStyle('Bullet', parent=Normal, leftIndent=20, firstLineIndent=-15, spaceAfter=10, leading=14)

        def safe_text(raw_text):
            clean = html.escape(str(raw_text))
            return re.sub(r'([^\s]{70})', r'\1 ', clean)

        story = []
        story.append(Paragraph(report_title, TitleStyle))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>Patient Name:</b> {safe_text(name) if name else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Date of Birth:</b> {safe_text(dob) if dob else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Medical Record #:</b> {safe_text(mrn) if mrn else 'N/A'}", Normal))
        story.append(Spacer(1, 15))

        for section_title, item_list in sections_dict.items():
            color_tag = "<font color='red'>" if 'Urgent' in section_title else ""
            color_end = "</font>" if 'Urgent' in section_title else ""
            story.append(Paragraph(f"{color_tag}<b>{section_title}</b>{color_end}", Heading2))
            story.append(Spacer(1, 8))
            for item in item_list:
                story.append(Paragraph(f"• {safe_text(item)}", BulletStyle))
            story.append(Spacer(1, 15))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_csv(urgent, diagnoses, meds):
        max_len = max(len(urgent), len(diagnoses), len(meds))
        df = pd.DataFrame({
            "Urgent Findings": urgent + [""] * (max_len - len(urgent)),
            "Clinical Diagnoses": diagnoses + [""] * (max_len - len(diagnoses)),
            "Medications": meds + [""] * (max_len - len(meds))
        })
        return df.to_csv(index=False).encode('utf-8')

    # ---------------------------------
    # SIDEBAR & MAIN UI
    # ---------------------------------
    st.sidebar.title("📋 Patient Demographics")
    patient_name = st.sidebar.text_input("Patient Full Name", placeholder="Jane Smith")
    patient_dob = st.sidebar.text_input("Date of Birth", placeholder="MM/DD/YYYY")
    patient_mrn = st.sidebar.text_input("Medical Record # (MRN)", placeholder="123-456-789")

    uploaded_files = st.file_uploader("📂 Upload Patient PDF(s) [OCR Enabled]", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        if st.button("🚀 Process & Extract All Patient Data", use_container_width=True):
            # Record the action in the permanent audit trail
            logger.info(f"PROCESS: '{st.session_state['username']}' extracted {len(uploaded_files)} documents for MRN: {patient_mrn if patient_mrn else 'Unknown'}.")
            
            with st.spinner("Extracting text, mapping timelines, and removing duplicates..."):
                st.session_state["last_active"] = time.time() # Reset timeout clock
                raw_text = extract_text_with_ocr(uploaded_files)
                st.session_state["parsed_data"] = parse_clinical_text(raw_text)
            st.success("Extraction complete! Use the search bar or download reports below.")

    # --- LIVE SEARCH & FILTER DASHBOARD ---
    if "parsed_data" in st.session_state:
        result = st.session_state["parsed_data"]
        
        st.markdown("<hr>", unsafe_allow_html=True)
        search_query = st.text_input("🔍 Live Filter (Search by condition, date, or medication):", placeholder="e.g., 'Cardiac', '2023', 'Lisinopril'")
        
        def filter_list(data_list, query):
            if not query: return data_list
            return [item for item in data_list if query.lower() in item.lower()]

        f_urgent = filter_list(result["Urgent"], search_query)
        f_diag = filter_list(result["Diagnoses"], search_query)
        f_meds = filter_list(result["Medications"], search_query)

        findings_pdf = generate_pdf("DocUFile Findings", {"Urgent & Critical Findings:": f_urgent, "Clinical Findings & Assessments:": f_diag}, patient_name, patient_dob, patient_mrn)
        meds_pdf = generate_pdf("DocUFile Medication Record", {"Historical Prescriptions & Dosages:": f_meds}, patient_name, patient_dob, patient_mrn)
        csv_export = generate_csv(f_urgent, f_diag, f_meds)

        tab1, tab2, tab3 = st.tabs(["🩺 Findings Report", "💊 Medication Record", "📊 EMR CSV Export"])

        with tab1:
            st.write("### 🚨 Urgent Findings")
            for alert in f_urgent[:10]: st.write(f"- {alert}")
            st.write("### 🩺 Clinical Diagnoses")
            for diag in f_diag[:10]: st.write(f"- {diag}")
            st.download_button("⬇️ Download Findings PDF", data=findings_pdf, file_name="Findings_Report.pdf", mime="application/pdf")

        with tab2:
            st.write("### 💊 Historical Medications")
            for med in f_meds[:15]: st.write(f"- {med}")
            st.download_button("⬇️ Download Medications PDF", data=meds_pdf, file_name="Medication_Report.pdf", mime="application/pdf")

        with tab3:
            st.write("### 💾 Export to EMR")
            st.write("Download the structured data grid to easily copy/paste or import directly into your clinic's database.")
            st.download_button("⬇️ Download Excel/CSV Data", data=csv_export, file_name="DocUFile_EMR_Export.csv", mime="text/csv")
