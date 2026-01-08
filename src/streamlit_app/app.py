import streamlit as st
import os
import logging
from pathlib import Path
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)
from garth.exc import GarthHTTPError
import dotenv

# Load environment variables from override file if present
dotenv.load_dotenv("override-default-vars.env", override=True)

# Configuration
TOKEN_DIR = os.getenv("TOKEN_DIR", "~/.garminconnect")
TOKEN_DIR = os.path.expanduser(TOKEN_DIR)
GARMINCONNECT_IS_CN = os.getenv("GARMINCONNECT_IS_CN", "False").lower() in ['true', 't', 'yes', '1']

# Ensure token directory exists
Path(TOKEN_DIR).mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Page configuration
st.set_page_config(
    page_title="Garmin Connect Authentication",
    page_icon="🏃",
    layout="centered"
)

# Custom CSS for better aesthetics
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        padding: 0.75rem;
        border-radius: 8px;
        border: none;
        font-size: 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #45a049;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        color: #155724;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        color: #721c24;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 8px;
        color: #0c5460;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.title("🏃 Garmin Connect Authentication")
st.markdown("---")

# Check if already authenticated
token_files_exist = Path(TOKEN_DIR).exists() and any(Path(TOKEN_DIR).iterdir())

if token_files_exist:
    st.markdown('<div class="info-box">✅ Authentication tokens found! The collector should be able to run automatically.</div>', unsafe_allow_html=True)
    st.info(f"**Token directory:** `{TOKEN_DIR}`")
    
    if st.button("🔄 Re-authenticate (Clear existing tokens)"):
        try:
            for file in Path(TOKEN_DIR).iterdir():
                file.unlink()
            st.success("Tokens cleared. Please log in again.")
            st.rerun()
        except Exception as e:
            st.error(f"Error clearing tokens: {str(e)}")
else:
    st.markdown('<div class="info-box">🔐 Please log in with your Garmin Connect credentials.</div>', unsafe_allow_html=True)

st.markdown("---")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'needs_mfa' not in st.session_state:
    st.session_state.needs_mfa = False
if 'garmin_obj' not in st.session_state:
    st.session_state.garmin_obj = None
if 'mfa_data' not in st.session_state:
    st.session_state.mfa_data = None

# Login form
if not st.session_state.authenticated and not token_files_exist:
    with st.form("login_form"):
        st.subheader("Login Credentials")
        email = st.text_input("Email", placeholder="your.email@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if GARMINCONNECT_IS_CN:
            st.info("🇨🇳 China region (garmin.cn) is enabled")
        
        submit_button = st.form_submit_button("🔑 Login")
        
        if submit_button:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                try:
                    with st.spinner("Authenticating..."):
                        garmin = Garmin(
                            email=email,
                            password=password,
                            is_cn=GARMINCONNECT_IS_CN,
                            return_on_mfa=True
                        )
                        result1, result2 = garmin.login()
                        
                        if result1 == "needs_mfa":
                            st.session_state.needs_mfa = True
                            st.session_state.garmin_obj = garmin
                            st.session_state.mfa_data = result2
                            st.rerun()
                        else:
                            # Login successful without MFA
                            garmin.garth.dump(TOKEN_DIR)
                            st.session_state.authenticated = True
                            logging.info(f"Authentication successful! Tokens saved to {TOKEN_DIR}")
                            st.rerun()
                            
                except GarminConnectAuthenticationError as e:
                    st.markdown(f'<div class="error-box">❌ Authentication failed: {str(e)}</div>', unsafe_allow_html=True)
                    logging.error(f"Authentication error: {str(e)}")
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error: {str(e)}</div>', unsafe_allow_html=True)
                    logging.error(f"Unexpected error: {str(e)}")

# MFA form
if st.session_state.needs_mfa and not st.session_state.authenticated:
    st.markdown('<div class="info-box">📱 Multi-Factor Authentication required</div>', unsafe_allow_html=True)
    
    with st.form("mfa_form"):
        st.subheader("Enter MFA Code")
        mfa_code = st.text_input("MFA Code", placeholder="Enter the code from your email or SMS")
        
        submit_mfa = st.form_submit_button("✅ Verify MFA Code")
        
        if submit_mfa:
            if not mfa_code:
                st.error("Please enter the MFA code.")
            else:
                try:
                    with st.spinner("Verifying MFA code..."):
                        garmin = st.session_state.garmin_obj
                        garmin.resume_login(st.session_state.mfa_data, mfa_code)
                        garmin.garth.dump(TOKEN_DIR)
                        
                        st.session_state.authenticated = True
                        st.session_state.needs_mfa = False
                        logging.info(f"MFA verification successful! Tokens saved to {TOKEN_DIR}")
                        st.rerun()
                        
                except GarminConnectAuthenticationError as e:
                    st.markdown(f'<div class="error-box">❌ MFA verification failed: {str(e)}</div>', unsafe_allow_html=True)
                    logging.error(f"MFA error: {str(e)}")
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error: {str(e)}</div>', unsafe_allow_html=True)
                    logging.error(f"Unexpected error: {str(e)}")

# Success message
if st.session_state.authenticated or token_files_exist:
    st.markdown('<div class="success-box">✅ Authentication successful!</div>', unsafe_allow_html=True)
    st.success(f"Tokens have been saved to: `{TOKEN_DIR}`")
    st.info("The Garmin collector service can now run automatically using these tokens.")
    
    st.markdown("---")
    st.markdown("### Next Steps")
    st.markdown("""
    1. The authentication tokens are stored in the shared volume
    2. The `garmin-fetch-data` service will use these tokens automatically
    3. You can close this page - tokens will persist
    4. Re-run this app if you need to re-authenticate
    """)
