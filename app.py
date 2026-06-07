import streamlit as st
from pypdf import PdfReader
import io
import re
import html
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
    /* Style for the tabs to make them look clickable and distinct */
    div[data-baseweb="tab-list"] {
        gap: 20px;
    }
    div[data-baseweb="tab"] {
        font-size: 1.1rem;
        font-weight: 600;
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

# --- LOCKED MAIN CONTENT ---
else:
    if st.sidebar.button("🚪 Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.markdown("""
        <div class="main-header">
            <h1>🩺 DocUFile</h1>
            <p>Targeted Clinical Extraction & Medication Parser</p>
            <span style="background-color: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">
                🔒 Zero API Keys • Strict Deduplication • Multi-Report Generation
            </span>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # DUAL-ENGINE PARSER (Findings + Meds)
    # ---------------------------------
    def parse_clinical_text(text):
        clean_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text) 
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)

        # 3 Dedicated Sets for strict deduplication
        urgent_bullets = set()
        finding_bullets = set()
        med_bullets = set()

        urgent_keywords = ['acute', 'severe', 'critical', 'emergency', 'urgent', 'malignan', 'life-threatening', 'hemorrhage', 'infarct']
        diag_keywords = ['findings:', 'impression:', 'assessment:', 'evidence of', 'consistent with', 'diagnosed with', 'reveals', 'conclusion:']
        # Precision keywords to isolate medication dosages and instructions
        med_keywords = [' mg ', ' mcg ', ' ml ', ' tabs ', ' capsule', ' tablet', ' po ', ' daily ', ' bid ', ' tid ', ' qid ', ' prn ', 'dose', 'prescribed ']

        for sentence in sentences:
            s_lower = sentence.lower()
            clean_s = re.sub(r'\s+', ' ', sentence).strip()
            
            # Skip noise
            if len(clean_s) < 10 or len(clean_s) > 300: 
                continue

            # 1. Meds isolation (meds are usually shorter instructions)
            if any(k in s_lower for k in med_keywords) and len(clean_s) < 150:
                med_bullets.add(clean_s)
                continue # If it's a med, don't add it to diagnoses

            # 2. Urgent isolation
            if any(k in s_lower for k in urgent_keywords):
                urgent_bullets.add(clean_s)
            
            # 3. Standard clinical findings isolation
            elif any(k in s_lower for k in diag_keywords):
                finding_bullets.add(clean_s)

        final_urgent = list(urgent_bullets)
        final_findings = list(finding_bullets)
        final_meds = list(med_bullets)

        if not final_urgent: final_urgent.append("No explicit urgency keywords flagged.")
        if not final_findings: final_findings.append("No standard clinical diagnosis terminology detected.")
        if not final_meds: final_meds.append("No structured medication or dosage data detected.")

        return {
            "Urgent": final_urgent[:25],
            "Diagnoses": final_findings[:50],
            "Medications": final_meds[:60] # Store up to 60 distinct historical meds
        }

    def extract_text_from_multiple(uploaded_files_list):
        combined_text = ""
        for file in uploaded_files_list:
            file_bytes = file.read()
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    combined_text += extracted + " "
        return combined_text

    # Dynamic PDF Generator that handles whichever report is requested
    def generate_pdf(report_title, sections_dict, name, dob, mrn):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        
        styles = getSampleStyleSheet()
        Normal = styles['Normal']
        Heading2 = styles['Heading2']
        TitleStyle = styles['Title']
        
        BulletStyle = ParagraphStyle(
            'Bullet', parent=Normal, leftIndent=20, firstLineIndent=-15, spaceAfter=10, leading=14
        )

        def safe_text(raw_text):
            clean = html.escape(str(raw_text))
            clean = re.sub(r'([^\s]{70})', r'\1 ', clean)
            return clean

        story = []

        # Header
        story.append(Paragraph(report_title, TitleStyle))
        story.append(Spacer(1, 12))
        
        # Patient Info
        story.append(Paragraph(f"<b>Patient Name:</b> {safe_text(name) if name else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Date of Birth:</b> {safe_text(dob) if dob else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Medical Record #:</b> {safe_text(mrn) if mrn else 'N/A'}", Normal))
        story.append(Spacer(1, 15))

        # Dynamically loop through the sections provided (Findings vs Meds)
        for section_title, item_list in sections_dict.items():
            # If the word 'Urgent' is in the title, color it red
            if 'Urgent' in section_title:
                story.append(Paragraph(f"<font color='red'><b>{section_title}</b></font>", Heading2))
            else:
                story.append(Paragraph(f"<b>{section_title}</b>", Heading2))
                
            story.append(Spacer(1, 8))
            for item in item_list:
                story.append(Paragraph(f"• {safe_text(item)}", BulletStyle))
            story.append(Spacer(1, 15))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    # ---------------------------------
    # SIDEBAR & MAIN INTERFACE
    # ---------------------------------
    st.sidebar.title("📋 Patient Demographics")
    st.sidebar.write("Optional — used only for the PDF report headers.")
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
        # One master button to read the heavy documents once
        if st.button("🚀 Process & Extract All Patient Data", use_container_width=True):
            st.info(f"Scanning {len(uploaded_files)} document(s). Removing duplicates and isolating records...")
            
            with st.spinner("Extracting Findings and Medications simultaneously..."):
                raw_text = extract_text_from_multiple(uploaded_files)
                result = parse_clinical_text(raw_text)

            st.success("Extraction complete! Select a tab below to view and download specific reports.")

            # --- DUAL TABS FOR SEPARATE REPORTS ---
            tab1, tab2 = st.tabs(["🩺 Clinical Findings Report", "💊 Historical Medication Report"])

            # TAB 1: FINDINGS
            with tab1:
                st.write("### 🚨 Urgent Findings Preview (Top 5)")
                for alert in result["Urgent"][:5]:
                    st.write(f"- {alert}")
                    
                st.write("### 🩺 Clinical Findings Preview (Top 5)")
                for diag in result["Diagnoses"][:5]:
                    st.write(f"- {diag}")

                # Build Findings PDF
                findings_pdf = generate_pdf(
                    report_title="DocUFile Concise Clinical Findings",
                    sections_dict={
                        "Urgent & Critical Findings:": result["Urgent"],
                        "Clinical Findings & Assessments:": result["Diagnoses"]
                    },
                    name=patient_name, dob=patient_dob, mrn=patient_mrn
                )

                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label="⬇️ Download Concise Findings Report (PDF)",
                    data=findings_pdf,
                    file_name="DocUFile_Findings_Report.pdf",
                    mime="application/pdf",
                    key="btn_findings"
                )

            # TAB 2: MEDICATIONS
            with tab2:
                st.write("### 💊 Extracted Medications Preview (Top 10)")
                st.write("*Note: History spanning years has been deduplicated into single distinct entries.*")
                for med in result["Medications"][:10]:
                    st.write(f"- {med}")

                # Build Medications PDF
                meds_pdf = generate_pdf(
                    report_title="DocUFile Historical Medication Record",
                    sections_dict={
                        "Deduplicated Historical Prescriptions & Dosages:": result["Medications"]
                    },
                    name=patient_name, dob=patient_dob, mrn=patient_mrn
                )

                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label="⬇️ Download Medication History Report (PDF)",
                    data=meds_pdf,
                    file_name="DocUFile_Medication_Report.pdf",
                    mime="application/pdf",
                    key="btn_meds"
                )
