import streamlit as st
import json
import requests
import PyPDF2
import io
import numpy as np
from pdf2image import convert_from_bytes
import easyocr
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
            st.rer
