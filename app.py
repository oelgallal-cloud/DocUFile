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
            <p>Targeted Clinical Extraction & Urgent Diagnostics Parser</p>
            <span style="background-color: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">
                🔒 Zero API Keys • Bullet Point Summarization • Focus on Diagnostics
            </span>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # TARGETED DIAGNOSTICS PARSER
    # ---------------------------------
    def parse_clinical_text(text):
        # 1. Clean weird PDF line breaks to form proper continuous sentences
        clean_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text) 
        # 2. Split the massive text block into individual grammatical sentences
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)

        urgent_bullets = []
        diag_bullets = []

        urgent_keywords = ['acute', 'severe', 'critical', 'emergency', 'urgent', 'abnormal', 'malignant', 'life-threatening', 'stat', 'immediate']
        diag_keywords = ['diagnosis', 'diagnoses', 'assessment', 'impression', 'condition', 'icd', 'syndrome', 'disease', 'disorder', 'pathology']

        for sentence in sentences:
            s_lower = sentence.lower()
            clean_s = sentence.strip()
            
            # Skip tiny fragments that aren't real sentences
            if len(clean_s) < 15: 
                continue

            # Prioritize urgent flags first
            if any(k in s_lower for k in urgent_keywords):
                if clean_s not in urgent_bullets:
                    urgent_bullets.append(clean_s)
            
            # Then look for standard clinical diagnoses
            elif any(k in s_lower for k in diag_keywords):
                if clean_s not in diag_bullets:
                    diag_bullets.append(clean_s)

        # Fallbacks if none are found
        if not urgent_bullets:
            urgent_bullets.append("No explicit urgency or critical severity keywords flagged in the text.")
        if not diag_bullets:
            diag_bullets.append("No standard clinical diagnosis or assessment terminology detected.")

        return {
            "Urgent": urgent_bullets,
            "Diagnoses": diag_bullets
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

    def generate_pdf(urgent_list, diag_list, name, dob, mrn):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        
        styles = getSampleStyleSheet()
        Normal = styles['Normal']
        Heading2 = styles['Heading2']
        TitleStyle = styles['Title']
        
        # Create a clean bullet point style with proper indentation
        BulletStyle = ParagraphStyle(
            'Bullet',
            parent=Normal,
            leftIndent=20,
            firstLineIndent=-15,
            spaceAfter=8,
            leading=14
        )

        def safe_text(raw_text):
            clean = html.escape(str(raw_text))
            clean = re.sub(r'([^\s]{70})', r'\1 ', clean)
            return clean

        story = []

        # Header
        story.append(Paragraph("DocUFile Master Clinical Report", TitleStyle))
        story.append(Spacer(1, 12))
        
        # Patient Info
        story.append(Paragraph(f"<b>Patient Name:</b> {safe_text(name) if name else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Date of Birth:</b> {safe_text(dob) if dob else 'N/A'}", Normal))
        story.append(Paragraph(f"<b>Medical Record #:</b> {safe_text(mrn) if mrn else 'N/A'}", Normal))
        story.append(Spacer(1, 15))

        # --- URGENT SECTION ---
        story.append(Paragraph("<font color='red'><b>Urgent & Critical Findings:</b></font>", Heading2))
        story.append(Spacer(1, 5))
        for item in urgent_list:
            story.append(Paragraph(f"• {safe_text(item)}", BulletStyle))
        story.append(Spacer(1, 15))

        # --- DIAGNOSIS SECTION ---
        story.append(Paragraph("<b>Clinical Diagnoses & Assessments:</b>", Heading2))
        story.append(Spacer(1, 5))
        for item in diag_list:
            story.append(Paragraph(f"• {safe_text(item)}", BulletStyle))
        
        # Build document
        doc.build(story)
        buffer.seek(0)
        return buffer

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
            st.info(f"Scanning {len(uploaded_files)} document(s) for clinical diagnostics...")
            
            with st.spinner("Extracting targeted sentences into bullet points..."):
                raw_text = extract_text_from_multiple(uploaded_files)
                result = parse_clinical_text(raw_text)

            # Display a preview on screen
            st.write("### 🚨 Urgent Findings Preview (Top 5)")
            for alert in result["Urgent"][:5]:
                st.write(f"- {alert}")
                
            st.write("### 🩺 Diagnoses Preview (Top 5)")
            for diag in result["Diagnoses"][:5]:
                st.write(f"- {diag}")

            st.success("Targeted extraction complete! Click below to download the bulleted PDF report.")

            # Generate the bullet-point PDF
            pdf_buffer = generate_pdf(
                urgent_list=result["Urgent"],
                diag_list=result["Diagnoses"],
                name=patient_name, 
                dob=patient_dob, 
                mrn=patient_mrn
            )

            st.download_button(
                label="⬇️ Download Targeted Diagnostics Report",
                data=pdf_buffer,
                file_name="DocUFile_Diagnostics_Report.pdf",
                mime="application/pdf"
            )
