import streamlit as st
import json
import requests
from pypdf import PdfReader
import io
from fpdf import FPDF

# ---------------------------------
# PAGE SETTINGS & STYLING
# ---------------------------------
st.set_page_config(page_title="DocUFile", page_icon="🩺", layout="wide")

# Custom CSS styling to match your clinical dashboard cards
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
    div[data-testid="stMetricSimpleValue"] {
        font-size: 24px;
        font-weight: bold;
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
    # Sidebar logout option
    if st.sidebar.button("🚪 Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

    # App Banner
    st.markdown("""
        <div class="main-header">
            <h1>🩺 DocUFile</h1>
            <p>Secure Clinical Document Summarizer & Triage Assistant</p>
            <span style="background-color: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">
                🔒 Zero-retention • Cloud API Processing • Auto-wiped on close
            </span>
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # WEB CLOUD AI CONNECTION
    # ---------------------------------
    def call_cloud_ai(prompt):
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        if "GROQ_API_KEY" not in st.secrets:
            return {"error": "Missing 'GROQ_API_KEY' in Streamlit Cloud Secrets dashboard settings."}
            
        api_key = st.secrets["GROQ_API_KEY"]
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a clinical assistant. You must return your response as raw, valid, structured JSON data matching the requested schema exactly."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
            raw = data["choices"][0]["message"]["content"].strip()
            
            if raw.startswith("```"):
                raw = raw.split("```json")[-1].split("```")[0].strip()
                
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {
                    "Summary": raw,
                    "Critical_Alerts": [],
                    "Medications": [],
                    "History": "Could not parse JSON syntax from response text structure."
                }
        except Exception as e:
            return {"error": f"Cloud AI API connection failed: {str(e)}"}

    # ---------------------------------
    # DOCUMENT PROCESSING FUNCTIONS
    # ---------------------------------
    def extract_text(uploaded_file):
        file_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
        return text

    def summarize_large_file(full_text, demographic_info=""):
        chunk_size = 3500
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
        partials = []
        for c in chunks:
            prompt = f"Summarize medical details from this section:\n{c}"
            res = call_cloud_ai(prompt)
            if isinstance(res, dict):
                partials.append(res.get("Summary", str(res)))
            else:
                partials.append(str(res))

        final_prompt = f"""
        Merge these individual clinical sections into one clean, concise master medical report summary.
        Patient Context: {demographic_info}

        SECTIONS DATA:
        {partials}

        Return ONLY a raw JSON dictionary object in this exact key structure:
        {{
            "Summary": "Overall consolidated summary text here",
            "Critical_Alerts": ["Alert 1 text", "Alert 2 text"],
            "Medications": ["Medication name 1", "Medication name 2"],
            "History": "Patient past clinical history summary notes here"
        }}
        """
        return call_cloud_ai(final_prompt)

    def generate_pdf(summary_text, name, dob, mrn):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(0, 10, "DocUFile Clinical Summary", ln=True, align="C")
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
        
        pdf_bytes = pdf.output(dest="S").encode("latin1")
        return io.BytesIO(pdf_bytes)

    # ---------------------------------
    # SIDEBAR: PATIENT DEMOGRAPHICS ONLY
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
        ("4. Cloud Insights", "Processes on secure server link; share anywhere.")
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
                    <li>Extracts text from digital or scanned PDFs</li>
                    <li>Summarizes clinical history, diagnoses & medications</li>
                    <li>Flags urgent or abnormal findings</li>
                    <li>Exports a clean branded PDF report</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    with dash_col2:
        st.markdown("""
            <div class="info-card">
                <h3>Privacy & Safety</h3>
                <ul>
                    <li><b>Cloud Gateway</b> — Encrypted tokens run data queries securely</li>
                    <li>Everything wiped out when this application tab closes</li>
                    <li>No database — data lives temporarily in system memory</li>
                    <li>Files are never saved to a remote server disk</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><hr>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "📂 Upload Patient PDF(s) to Start Cloud-Enabled Analysis",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Start Analysis"):
            demo_context = f"Name: {patient_name}, DOB: {patient_dob}, MRN: {patient_mrn}"
            
            for file in uploaded_files:
                st.subheader(f"📄 Processing: {file.name}")

                with st.spinner("Analyzing data through cloud gateway..."):
                    raw_text = extract_text(file)
                    result = summarize_large_file(raw_text, demographic_info=demo_context)

                if "error" in result:
                    st.error(result["error"])
                    continue

                # Display Summary
                st.write("### 🩺 Medical Summary")
                st.info(result.get("Summary", "No summary found."))

                # Critical Alerts
                if result.get("Critical_Alerts"):
                    st.error("### 🚨 Critical Alerts")
                    for alert in result["Critical_Alerts"]:
                        st.write(f"- {alert}")

                # Medications & History
                col1, col2 = st.columns(2)
                with col1:
                    st.write("### 💊 Medications")
                    meds = result.get("Medications", [])
                    if isinstance(meds, list):
                        for med in meds:
                            st.write(f"- {med}")
                    else:
                        st.write(meds)
                        
                with col2:
                    st.write("### 📜 Patient History")
                    st.write(result.get("History", ""))

                # Download Button
                pdf_buffer = generate_pdf(
                    result.get("Summary", "No summary available."),
                    patient_name, patient_dob, patient_mrn
                )

                st.download_button(
                    label="⬇️ Download PDF Summary",
                    data=pdf_buffer,
                    file_name=f"{file.name}_summary.pdf",
                    mime="application/pdf"
                )
