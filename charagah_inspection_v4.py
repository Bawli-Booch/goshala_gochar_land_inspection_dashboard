# charagah_inspection_v7.py
"""
🐄 Goshala Inspection Dashboard — Final Integrated Version
Features:
- Unified column renaming for Google Sheet & Baseline data
- Auto date/time extraction from "Created At"
- GPS Location parsing (lat/lon)
- Overview comparison (required vs actual vs remaining)
- Photo + Map tabs (ready for enhancement)
"""

import os
import re
from io import BytesIO
from datetime import datetime, date

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import folium
from streamlit_folium import st_folium

import requests
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# --- Hide all Streamlit UI and Cloud branding ---
hide_streamlit_branding = """
    <style>
    /* Hide Streamlit main header and footer */
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}

    /* Hide possible Streamlit Cloud floating buttons */
    [data-testid="stStatusWidget"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecorationContainer"] {display: none !important;}
    .stAppDeployButton {display: none !important;}
    button[data-testid="manage-app-button"] {display: none !important;}
    div[class*="_link_"] {display: none !important;}
    div[title="Manage app"] {display: none !important;}
    div[data-testid="stActionButton"] {display: none !important;}
    
    /* 👇 Key trick: globally hide any Streamlit Cloud bottom-right floating button */
    [class*="st-emotion-cache"] button[title*="Manage"], 
    [class*="st-emotion-cache"] button[title*="View"],
    [class*="st-emotion-cache"] a[href*="streamlit.app"],
    [class*="st-emotion-cache"] svg[xmlns*="http"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Hide Streamlit Cloud overlay container completely */
    div[style*="position: fixed"][style*="right: 0px"][style*="bottom: 0px"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }
    </style>

    <script>
    // In case Streamlit Cloud injects after render — try removing again
    const hideCloudButton = () => {
        const elems = document.querySelectorAll('button[title*="Manage"], button[title*="View"], a[href*="streamlit.app"], div[class*="_link_"]');
        elems.forEach(el => el.style.display = "none");
    };
    setInterval(hideCloudButton, 1500);
    </script>
"""
st.markdown(hide_streamlit_branding, unsafe_allow_html=True)

#remove top padding
st.set_page_config(page_title="गोशाला चरागाह निरीक्षण Dashboard V7 - final", layout="wide")
st.markdown("""
    <style>
        div.block-container { padding-top: 0rem !important; }
        section[data-testid="stTabs"] { margin-top: 0px !important; }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# CONFIG
# ----------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1K0KxYzI7td53UmLu_5ZeK9_FDk1UoD0h0IpUYTg1mmY/edit?usp=sharing"
GOOGLE_DRIVE_FOLDER_ID = "1SO-p_yU7ARjEsMIcEqu7m2T8Dh2Bt4BJ"
BASELINE_PATH = "baseline_static_data.xlsx"

# ----------------------------
# LOAD CREDENTIALS
# ----------------------------
try:
    gcp_creds = st.secrets["gcp_service_account"]
except Exception:
    st.error("❌ Missing Google service account credentials in st.secrets['gcp_service_account'].")
    st.stop()

# ============================================================
# 🌿 GREEN THEME UI SETUP (Cyber Dashboard Style)
# ============================================================

# ============================================================
# 🌿 GREEN THEME UI (Cyber Dashboard Style)
# ============================================================


st.markdown("""
<style>
/* --- GENERAL PAGE --- */
body, .main {
    background-color: #f6faf6;
    font-family: 'Inter', sans-serif;
}
section[data-testid="stSidebar"] {
    background-color: #14532D;
    color: white;
}
h1, h2, h3, h4, h5 {
    color: #166534 !important;
    font-weight: 700;
    text-align: center !important;
    margin-top: -2rem;
    margin-bottom: -2rem;
}

.block-container {
    padding-top: 0.5rem;
    padding-bottom: -2rem;
}
            

/* --- TABS --- */
            
div[data-baseweb="tab-list"] {
    background-color: #E7F8E7;
    border-radius: 10px 10px 0 0;
    padding: -16px 10px;
    width: 100%;   
    display: flex;          
}
div[data-baseweb="tab-list"] button {
    flex-grow: 1;         /* Makes all buttons grow equally */
    text-align: center;   /* Centers text inside the expanded buttons */
    margin-right: 0;      /* Remove the button margin for a cleaner look */

    background-color: transparent;
    border: none;
    color: #166534;
    font-weight: 600;
    padding: 8px 20px;
    margin-right: 8px;
    border-radius: 8px 8px 0 0;
    transition: all 0.3s ease;
}
div[data-baseweb="tab-list"] button:hover {
    background-color: #22C55E20;
}
div[data-baseweb="tab-list"] button[aria-selected="true"] {
    background-color: #15803D !important;
    color: white !important;
}

/* ----- map css ----- */
.mode-selector {
    display: flex;
    justify-content: center;
    gap: 1rem;
    margin: 15px 0 25px 0;
}
.mode-button {
    background-color: #E8F5E9;
    border: 2px solid #166534;
    color: #166534;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
}
.mode-button:hover {
    background-color: #166534;
    color: white;
}
.mode-button.active {
    background-color: #166534;
    color: white;
}


/* --- CARD CONTAINERS --- */
.card {
    background-color: white;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
    margin-bottom: 1.5rem;
}

/* --- TABLE STYLING --- */
[data-testid="stDataFrame"] table {
    border-collapse: collapse !important;
    border-radius: 10px;
}
thead tr th {
    background-color: #D1FAE5 !important;
    color: #14532D !important;
    font-weight: 600 !important;
    text-align: center !important;
}
tbody tr td {
    text-align: center !important;
    vertical-align: middle !important;
}

/* --- METRICS --- */
div[data-testid="stMetricValue"] {
    color: #15803D !important;
    font-weight: bold;
}
            
/* footer section */
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #E7F8E7; /* Match your tab color */
    color: #166534; /* Match your text color */
    text-align: center;
    padding: 10px 0; /* Add some padding for height */
    z-index: 100; /* Ensure it's on top of other content */
}
.section-divider {
    border-top: 1px solid #ddd;
    margin-top: 20px;
    margin-bottom: 10px;
}

/* All unvisited links will be green */
a:link {
  color: #166534;
}

/* Visited links will also be green to ensure consistency */
a:visited {
  color: #166534;
}

/* Links will turn a darker green when the mouse hovers over them */
a:hover {
  color: #166534;
}

/* Links will turn an even darker green when being clicked */
a:active {
  color: #166534;
}
                        

                        
</style>
<div class='section-divider'></div>
<div class='footer'>
    <a href="https://devdev.clappia.com/app/YRX813600"  title="निरीक्षण फॉर्म के लिए यहाँ क्लिक करें" target="_blank" class='footer'>
        © CDO Office Shahjahanpur · गोशाला गोचर भूमि निरीक्षण Dashboard
    </a>
</div>
""", unsafe_allow_html=True)


# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
@st.cache_data
def load_google_sheet(sheet_url: str, _creds_json: dict) -> pd.DataFrame:
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive.readonly"]
    credentials = Credentials.from_service_account_info(_creds_json, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(sheet_url)
    ws = sh.get_worksheet(0)
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    header = rows[0]
    data = rows[1:]
    df = pd.DataFrame(data, columns=header)
    df.columns = df.columns.str.strip()


    return df


from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

@st.cache_data
def fetch_drive_photos(folder_id: str, _creds_json: dict) -> pd.DataFrame:
    """Fetch photos from Google Drive and generate valid public URLs."""
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(_creds_json, scopes=scopes)
    service = build("drive", "v3", credentials=credentials)

    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    resp = service.files().list(q=query, fields="files(id, name, webViewLink, webContentLink)").execute()
    files = resp.get("files", [])

    drive_photos = []
    for f in files:
        file_id = f["id"]
        file_name = f["name"]

        # ✅ Ensure sharing permission "anyoneWithLink"
        try:
            service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
                fields="id"
            ).execute()
        except Exception:
            pass  # Ignore if already public

        # ✅ Generate real public link (guaranteed accessible)
        public_url = f"https://drive.google.com/uc?id={file_id}"

        drive_photos.append({
            "file_name": file_name,
            "public_url": public_url
        })

    return pd.DataFrame(drive_photos)




import re
import requests
from io import BytesIO
from PIL import Image

# --- Convert Drive URLs to direct-download form ---
def convert_drive_url(url: str):
    """Convert various Google Drive link formats to direct-download form."""
    if not isinstance(url, str) or not url:
        return None
    if "drive.google.com" in url:
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=view"
        match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=view"
    return url

def extract_filename_from_url(url: str):
    """Extracts the image filename (e.g. IMG-20251027_0347.jpeg) from any URL."""
    if not isinstance(url, str) or not url:
        return None
    match = re.search(r"(IMG-[\d_]+[a-z0-9]+\.jpe?g)", url, re.IGNORECASE)
    return match.group(1) if match else None


# --- Robust downloader for any image URL ---
@st.cache_data(show_spinner=False)
def get_image_bytes(url: str):
    """Download image bytes safely, following redirects and checking MIME."""
    if not isinstance(url, str) or not url:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        # Only accept real image responses
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
            return resp.content
        return None
    except Exception:
        return None


def parse_gps_column(df, col):
    """Parse GPS column formatted like '27.8921216,79.9309824'."""
    def parse_val(v):
        try:
            s = str(v).replace("(", "").replace(")", "").replace(" ", "")
            a, b = s.split(",")
            return float(a), float(b)
        except Exception:
            return np.nan, np.nan
    lat, lon = zip(*df[col].map(parse_val))
    df["latitude"] = lat
    df["longitude"] = lon
    return df


def normalize_quality(val):
    if pd.isna(val): return "not_inspected"
    s = str(val).lower().strip()
    if s in ["1", "good", "5", "उत्कृष्ट"]: return "good"
    if s in ["2", "3", "4", "bad", "खराब"]: return "bad"
    return "not_inspected"


    # ==========================================================
# 🧹 Clean & Deduplicate Google Sheet Data
# ==========================================================

def remove_duplicates(df_raw):
    # Ensure datetime
    if "created_at" in df_raw.columns:
        df_raw["created_at"] = pd.to_datetime(df_raw["created_at"], errors="coerce")

    # Create a date-only column
    #df_raw["created_date"] = df_raw["created_at"].dt.date

    # Sort so newest submissions appear first
    df_raw = df_raw.sort_values(by="created_at", ascending=False)

    # Drop duplicate submissions for the same village in the same block on the same day
    if {"block", "village"} <= set(df_raw.columns):
        df_raw = df_raw.drop_duplicates(subset=["block", "village", "created_date"], keep="first")
    else:
        # fallback if block not present
        df_raw = df_raw.drop_duplicates(subset=["village", "created_date"], keep="first")

    # Remove helper column
    #df_raw = df_raw.drop(columns=["created_date"], errors="ignore")

    # Summary info
    # st.info(f"✅ Cleaned data: {len(df_raw)} unique (latest) submissions per village per day.")

    return df_raw
# ----------------------------
# LOAD GOOGLE SHEET + RENAME
# ----------------------------
#st.set_page_config(page_title="Goshala Dashboard", layout="wide")
st.title("🐄 गोशाला चरागाह निरीक्षण Dashboard")
st.markdown("---")


with st.spinner("Loading Google Sheet..."):
    df_raw = load_google_sheet(GOOGLE_SHEET_URL, gcp_creds)
    


if df_raw.empty:
    st.error("⚠️ Google Sheet returned no data.")
    st.stop()

# 🏷️ Rename Google Sheet columns
COLUMN_RENAME_MAP = {
    "Created At": "created_at",
    "तहसील": "tehsil",
    "विकास खंड": "block",
    "गांव": "village",
    "भूमि गाटा संख्या": "plot_gata_number",
    "क्षेत्रफल ( हे)": "plot_area",
    "बुवाई की गई भूमि": "reported_cultivation",
    "GPS Location": "plot_gps_location",
    "अधिकारी का नाम": "officer_name",
    "अधिकारी पद": "officer_designation",
    "अभिकारी मोबाइल नंबर": "officer_contact",
    "गोशाला का नाम": "goshala_name",
    "कुल बुवाई पाई गई क्षेत्रफल( हे में)": "area_actual_cultivated",
    "फसल की गुणवत्ता": "crop_quality",
    "सेल्फी ले": "photo_selfie",
    "फसल की फोटो": "photo_field",
    "Date": "date",
    "Time": "time",
    "GPS Location inspection": "gps_inspection",
}


df_raw.columns = df_raw.columns.str.strip()
df_raw = df_raw.rename(columns=COLUMN_RENAME_MAP)

# Extract date/time
if "created_at" in df_raw.columns:
    #st.markdown("created_at column found")
    df_raw["created_at"] = pd.to_datetime(df_raw["created_at"], errors="coerce")
    df_raw["created_date"] = df_raw["created_at"].dt.date
    df_raw["created_time"] = df_raw["created_at"].dt.time
    #st.markdown(f"created_at: {df_raw["created_date"]}")

# Parse GPS coordinates
if "plot_gps_location" in df_raw.columns:
    df_raw = parse_gps_column(df_raw, "gps_inspection")

#remove duplicate entrues fo the same day - village + block filter
df_raw = remove_duplicates(df_raw)
    

st.sidebar.success(f"✅ Loaded {len(df_raw)} records from Google Sheet")

# ----------------------------
# BASELINE LOADING + RENAME
# ----------------------------
def rename_baseline_columns(df_base: pd.DataFrame) -> pd.DataFrame:
    BASELINE_RENAME_MAP = {
        "तहसील": "tehsil",
        "विकास खंड": "block",
        "गांव": "village",
        "भूमि गाटा संख्या": "plot_gata_number",
        "क्षेत्रफल ( हे)": "plot_area",
        "बुवाई की गई भूमि": "reported_cultivation",
        "GPS Location": "plot_gps_location",
    }
    if df_base.empty:
        return df_base
    df_base.columns = df_base.columns.str.strip()
    df_base = df_base.rename(columns=BASELINE_RENAME_MAP)
    return df_base


with st.spinner("Loading baseline reference data..."):
    if os.path.exists(BASELINE_PATH):
        try:
            df_base = pd.read_excel(BASELINE_PATH)
            df_base = rename_baseline_columns(df_base)
            st.sidebar.success(f"📘 Baseline loaded: {len(df_base)} rows")
        except Exception as e:
            st.sidebar.error(f"❌ Baseline load error: {e}")
            df_base = pd.DataFrame()
    else:
        st.sidebar.warning("⚠️ Baseline file not found.")
        df_base = pd.DataFrame()



# ----------------------------
# MAIN DASHBOARD
# ----------------------------
tab1, tab2 = st.tabs(["1️⃣ Last Inspection", "2️⃣ Progress Monitoring"])

# ----------------------------
# TAB 1 — LAST INSPECTION
# ----------------------------
with tab1:
    #st.header("📅 Last Inspection Overview")
    #st.markdown("<h2 '>📅 Last Inspection Overview</h2>", unsafe_allow_html=True)
    #st.markdown(f"{df_raw.columns}")
    if "created_date" in df_raw.columns and df_raw["created_date"].notna().any():
        # ================================
        # 📅 Date Range Selector (Styled Full-Width)
        # ================================

        # ================================
        # ================================
        # 📅 Simple Date Range Selector (40/60 Layout)
        # ================================
        from datetime import date

        # Ensure proper date parsing
        df_raw["created_date"] = pd.to_datetime(df_raw["created_date"], errors="coerce")
        min_date = df_raw["created_date"].min()
        max_date = df_raw["created_date"].max()
        min_date = min_date.date() if hasattr(min_date, "date") else min_date
        max_date = max_date.date() if hasattr(max_date, "date") else max_date

        # Create a two-column layout: 40% title, 60% date input
        col1, col2 = st.columns([0.4, 0.6])

        with col1:
            st.markdown(
                "<h5 style='text-align:right; margin-top:2rem;'>📅 Select date range of inspection</h5>",
                unsafe_allow_html=True
            )

        with col2:
            start, end = st.date_input(
                label="",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="date_selector"
            )

        # Filter dataframe based on selected date range
        df_last = df_raw[
            (df_raw["created_date"] >= pd.to_datetime(start))
            & (df_raw["created_date"] <= pd.to_datetime(end))
        ]

    else:
        st.markdown("no created_date column found so no date selector")
        df_last = df_raw.copy()

    


    #df_last["crop_quality"] = df_last["crop_quality"].apply(normalize_quality)
    df_last["plot_area"] = pd.to_numeric(df_last["plot_area"], errors="coerce")

    sub_overview, sub_area, sub_map, sub_photo  = st.tabs(["Overview", "Area", "Map", "Photo"])




    # --- Overview ---
    # --- Overview ---
 #   with sub_overview:
#        st.subheader("📊 Block-wise Inspection Overview")
    with sub_overview:
        #st.markdown('<div class="card">', unsafe_allow_html=True)
        #st.subheader("📊 Block-wise Inspection Overview")
        #st.markdown("<h3 >📊 Block-wise Inspection Overview</h3>", unsafe_allow_html=True)

        
        #st.markdown('</div>', unsafe_allow_html=True)

        #st.markdown("---")
        if "block" in df_last.columns:
            # Prepare baseline (required) and actual (submitted) counts
            base_counts = (
                df_base.groupby("block").size().rename("required").reset_index()
                if "block" in df_base.columns else pd.DataFrame(columns=["block", "required"])
            )
            actual_counts = df_last.groupby("block").size().rename("submitted").reset_index()

            # Merge both
            merged = pd.merge(base_counts, actual_counts, on="block", how="outer").fillna(0)
            merged["required"] = merged["required"].astype(int)
            merged["submitted"] = merged["submitted"].astype(int)
            merged["remaining"] = (merged["required"] - merged["submitted"]).clip(lower=0)
            merged["inspection_%"] = (merged["submitted"] / merged["required"].replace(0, np.nan) * 100).round(1)

            # --- SUMMARY KPIs ---
            total_required = merged["required"].sum()
            total_submitted = merged["submitted"].sum()
            total_remaining = merged["remaining"].sum()
            percent_done = (total_submitted / total_required * 100) if total_required > 0 else 0

                
            #2 main columns for data and pie chart
            col1, col2 = st.columns(2)
            with col1:
                # --- Summary KPIs (Styled Table) ---

                summary_df = pd.DataFrame({
                    "Metric": ["Required (Total)", "Submitted", "Remaining", "% Completed"],
                    "Value": [
                        f"{int(total_required):,}",
                        f"{int(total_submitted):,}",
                        f"{int(total_remaining):,}",
                        f"{percent_done:.1f}%",
                    ]
                })

                # Apply custom colors using HTML
                def color_metric(row):
                    if "Remaining" in row["Metric"]:
                        color = "red"
                    elif "Submitted" in row["Metric"] :
                        color = "green"
                    elif "Required" in row["Metric"]:
                        color = "#007BFF"  # blue
                    else:
                        color = "black"
                    return f"<tr><td style='text-align:center;font-size:40px; font-weight:bold;'>{row['Metric']}</td>" \
                        f"<td style='text-align:center;color:{color}; font-size:48px; font-weight:bold;'>{row['Value']}</td></tr>"

                # Build HTML table
                html_table = (
                    "<table style='width:100%;border-collapse:collapse;'>"
                    "<thead><tr style='background-color:#f2f2f2;'>"
                    "<th style='text-align:center;'></th><th style='text-align:center;'></th>"
                    "</tr></thead><tbody>"
                    + "".join(summary_df.apply(color_metric, axis=1))
                    + "</tbody></table>"
                )

                st.markdown(html_table, unsafe_allow_html=True)

            with col2:
                # --- Pie Chart of Completion ---
                pie_df = pd.DataFrame({
                    "Status": ["Completed", "Pending"],
                    "Count": [total_submitted, total_remaining]
                })
                fig_pie = px.pie(
                    pie_df,
                    names="Status",
                    values="Count",
                    title="Overall Inspection Completion %",
                    color="Status",
                    color_discrete_map={"Completed": "green", "Pending": "red"},
                )
                fig_pie.update_layout(
                    autosize=True,
                    margin=dict(l=20, r=20, t=40, b=20)
                )

                # ✅ Updated Streamlit Plotly call
                st.plotly_chart(
                    fig_pie,
                    config={"displayModeBar": False, "responsive": True},
                    use_container_width=True,
                )


            st.markdown("---")
            # --- Bar Chart (block-wise progress) ---
            fig_bar = px.bar(
                merged.melt(
                    id_vars="block",
                    value_vars=["required", "submitted", "remaining"],
                    var_name="Status",
                    value_name="Count"
                ),
                x="block",
                y="Count",
                color="Status",
                color_discrete_map={
                    "required": "blue",
                    "submitted": "green",
                    "remaining": "red"
                },
                barmode="group",
                text="Count",
                title="Block-wise Required vs Submitted vs Remaining"
            )

            fig_bar.update_traces(
                texttemplate="%{text}",
                textposition="outside"
            )

            # ✅ Modern Streamlit Plotly call
            st.plotly_chart(
                fig_bar,
                config={"displayModeBar": False, "responsive": True},
                use_container_width=True,
                key="block_required_vs_submitted"
            )

            # --- Add total row ---
            total_row = pd.DataFrame([{
                "block": "TOTAL",
                "required": total_required,
                "submitted": total_submitted,
                "remaining": total_remaining,
                "inspection_%": round(percent_done, 1)
            }])
            merged = pd.concat([merged, total_row], ignore_index=True)

            # --- Improve Table UI ---
            def style_table(df):
                styled = (
                    df.style
                    .set_properties(**{
                        "text-align": "center",
                        "border-color": "lightgray"
                    })
                    .set_table_styles([
                        {"selector": "th", "props": [("text-align", "center"), ("background-color", "#f5f5f5")]}
                    ])
                    .format({"inspection_%": "{:.1f}%"})
                )
                return styled
            
            #table section
            st.markdown("---")
            st.markdown("### 📋 Block-wise Inspection Table")
            st.dataframe(merged.sort_values(by="inspection_%", ascending=False), use_container_width=True)

            #village wise details
            st.markdown("---")
            # --- Inspected vs Remaining charagah list ---
            st.markdown("### 🏡 Detailed Village-wise Status")

            if all(col in df_last.columns for col in ["village", "block", "plot_area", "latitude", "longitude"]):
                inspected = df_last[["village", "block", "plot_area", "latitude", "longitude"]].copy()
                inspected["status"] = "Inspected"

                baseline_villages = df_base[["village", "block", "plot_area", "plot_gps_location"]] if "village" in df_base.columns else pd.DataFrame()

                if not baseline_villages.empty:
                    # find remaining (villages present in baseline but not inspected)
                    inspected_villages = inspected["village"].dropna().unique().tolist()
                    remaining = baseline_villages[~baseline_villages["village"].isin(inspected_villages)].copy()
                    remaining["status"] = "Not Inspected"

                    combined = pd.concat([inspected, remaining], ignore_index=True, sort=False)
                    combined = combined.fillna("")
                    st.dataframe(combined)

                    # Excel download for full village list
                    out_villages = BytesIO()
                    with pd.ExcelWriter(out_villages, engine="openpyxl") as w:
                        combined.to_excel(w, index=False, sheet_name="charagah_status")
                    st.download_button(
                        "📥 Download Village-wise Details",
                        out_villages.getvalue(),
                        "village_inspection_details.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Baseline villages not available for comparison.")
            else:
                st.warning("Village / Area / GPS data missing in Sheet.")
            
            
            #download link
            st.markdown("---")
            # --- Table Excel Download ---
            out_summary = BytesIO()
            with pd.ExcelWriter(out_summary, engine="openpyxl") as w:
                merged.to_excel(w, index=False, sheet_name="block_summary")
            st.download_button(
                "📥 Download Block Summary Table",
                out_summary.getvalue(),
                "block_summary_table.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.warning("Column 'block' not found in the dataset.")





    # --- Area ---
    # --- Area Subtab ---
    with sub_area:
        #st.subheader("🌾 Area and Production Analysis (Block-wise)")
        st.markdown("<h3 >🌾 Area and Production Analysis (Block-wise)</h3>", unsafe_allow_html=True)


        
        # 🔹 Use only inspected entries
        df_inspected = df_last[df_last["crop_quality"].notna()].copy()
        df_inspected = df_inspected[df_inspected["crop_quality"].astype(str).str.strip() != ""]

        if df_inspected.empty:
            st.warning("No inspected data available to display.")
            st.stop()

        # Convert numeric columns
        df_inspected["plot_area"] = pd.to_numeric(df_inspected["plot_area"], errors="coerce")
        df_inspected["area_actual_cultivated"] = pd.to_numeric(df_inspected["area_actual_cultivated"], errors="coerce")
        df_inspected["crop_quality"] = pd.to_numeric(df_inspected["crop_quality"], errors="coerce")

        # Compute % cultivated per row
        df_inspected["area_cultivated_%"] = (df_inspected["area_actual_cultivated"] / df_inspected["plot_area"] * 100).clip(0, 100)

        # --- Block-wise Aggregates ---
        block_agg = df_inspected.groupby("block").agg(
            total_plot_area=("plot_area", "sum"),
            total_cultivated=("area_actual_cultivated", "sum"),
            avg_quality=("crop_quality", "mean"),
            inspected_count=("village", "count")
        ).reset_index()

        # % cultivated
        block_agg["cultivated_%"] = (block_agg["total_cultivated"] / block_agg["total_plot_area"] * 100).round(0)
        # Quality % normalized to 0–100 (assuming max 5)
        block_agg["quality_%"] = (block_agg["avg_quality"] / 5 * 100).round(0)
        # Production expected = cultivated% * quality% / 100
        block_agg["production_%"] = (block_agg["cultivated_%"] * block_agg["quality_%"] / 100).round(0)

        # --- Aggregated Totals ---
        total_cultivated = block_agg["total_cultivated"].sum()
        total_area = block_agg["total_plot_area"].sum()
        total_quality = block_agg["avg_quality"].mean()
        #total_production = (block_agg["production_%"].mean())
        total_production = ( total_cultivated / total_area ) * (total_quality / 5 ) * 100

        st.markdown("---")
        # --- PIE CHARTS (Aggregate Overview) ---
        st.markdown("### 📊 Overall Aggregation")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            fig1 = px.pie(
                names=["Cultivated", "Uncultivated"],
                values=[total_cultivated, total_area - total_cultivated],
                title="Total Area Cultivated (%)",
                color_discrete_sequence=["green", "lightgray"]
            )

            # ✅ Modern, warning-free Streamlit call
            st.plotly_chart(
                fig1,
                config={"displayModeBar": False, "responsive": True},
                use_container_width=True,
                key="total_area_cultivated_pie"
            )

        with col2:
            fig2 = px.pie(
                names=["Good Quality", " "],
                values=[total_quality * 20, 100 - (total_quality * 20)],
                title="Average Quality (%)",
                color_discrete_sequence=["#00CC96", "#E3755A"]
            )

            st.plotly_chart(
                fig2,
                config={"displayModeBar": False, "responsive": True},
                use_container_width=True,
                key="average_quality_pie"
            )

        with col3:
            fig3 = px.pie(
                names=["Expected Production", "Remaining"],
                values=[total_production, 100 - total_production],
                title="Total Production Expected (%)",
                color_discrete_sequence=["lightgray", "#FA0B9A"]
            )

            st.plotly_chart(
                fig3,
                config={"displayModeBar": False, "responsive": True},
                use_container_width=True,
                key="total_production_expected_pie"
            )

        with col4:
            # Reuse total inspection data from overview
            if "block" in df_last.columns:
                base_counts = df_base.groupby("block").size().sum() if "block" in df_base.columns else 0
                actual_counts = df_last.groupby("block").size().sum()
                remaining_counts = base_counts - actual_counts if base_counts > 0 else 0
                pie_inspect = pd.DataFrame({
                    "Status": ["Inspected", "Pending"],
                    "Count": [actual_counts, remaining_counts]
                })
                fig4 = px.pie(
                    pie_inspect,
                    names="Status",
                    values="Count",
                    title="Inspection Completion (%)",
                    color="Status",
                    color_discrete_map={"Inspected": "green", "Pending": "red"}
                )

                st.plotly_chart(
                    fig4,
                    config={"displayModeBar": False, "responsive": True},
                    use_container_width=True,
                    key="inspection_completion_pie"
                )

        st.markdown("---")

        # =========================================================
        # 1️⃣ % OF TOTAL AREA CULTIVATED (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🌱 % of Total Area Cultivated (Block-wise)")

        fig_cult = px.bar(
            block_agg,
            x="block",
            y="cultivated_%",
            color="cultivated_%",
            color_continuous_scale=["#2fd973", "#66c2a4", "#238b45", "#09682f"],
            title="% of Total Area Cultivated per Block",
            text="cultivated_%"
        )
        fig_cult.update_traces(texttemplate="%{text}%", textposition="outside")

        st.plotly_chart(
            fig_cult,
            config={"displayModeBar": False, "responsive": True},
            use_container_width=True,
            key="total_area_cultivated_bar"
        )
        st.markdown("---")
        st.dataframe(block_agg[["block", "total_plot_area", "total_cultivated", "cultivated_%"]].sort_values(by="cultivated_%", ascending=False))

        # Excel download
        out_cult = BytesIO()
        with pd.ExcelWriter(out_cult, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="area_cultivated")
        st.download_button("📥 Download Cultivated Area Data", out_cult.getvalue(), "blockwise_cultivated_area.xlsx")
        st.markdown("---")

        # =========================================================
        # 2️⃣ QUALITY OF CULTIVATED AREA (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🌾 Quality of Cultivated Area (Block-wise)")

        fig_qual = px.bar(
            block_agg,
            x="block",
            y="quality_%",
            color="quality_%",
            color_continuous_scale=["#5DD6F5", "#1ee7f9", "#466ff7", "#0639F0"],
            title="Average Crop Quality per Block",
            text="quality_%"
        )
        fig_qual.update_traces(texttemplate="%{text}%", textposition="outside")

        st.plotly_chart(
            fig_qual,
            config={"displayModeBar": False, "responsive": True},
            use_container_width=True,
            key="average_crop_quality_bar"
        )
        st.markdown("---")
        st.dataframe(block_agg[["block", "avg_quality", "quality_%"]].sort_values(by="quality_%", ascending=False))

        out_quality = BytesIO()
        with pd.ExcelWriter(out_quality, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="quality")
        st.download_button("📥 Download Quality Data", out_quality.getvalue(), "blockwise_quality_data.xlsx")

        st.markdown("---")

        # =========================================================
        # 3️⃣ TOTAL PRODUCTION EXPECTED (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🧮 Total Production Expected (Block-wise)")

        fig_prod = px.bar(
            block_agg,
            x="block",
            y="production_%",
            color="production_%",
            color_continuous_scale="Oranges",
            title="Expected Production (Cultivation × Quality)",
            text="production_%"
        )
        fig_prod.update_traces(texttemplate="%{text}%", textposition="outside")

        st.plotly_chart(
            fig_prod,
            config={"displayModeBar": False, "responsive": True},
            use_container_width=True,
            key="expected_production_bar"
        )
        st.markdown("---")
        st.dataframe(block_agg[["block", "production_%"]].sort_values(by="production_%", ascending=False))

        out_prod = BytesIO()
        with pd.ExcelWriter(out_prod, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="production")
        st.download_button("📥 Download Production Data", out_prod.getvalue(), "blockwise_production_data.xlsx")

    # --- Map ---
    # --- MAP SUBTAB ---
    # --- MAP SUBTAB ---
    with sub_map:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        if {"latitude", "longitude"} <= set(df_last.columns):
            dfm = df_last.dropna(subset=["latitude", "longitude"]).copy()

            if dfm.empty:
                st.warning("⚠️ No valid GPS coordinates available for mapping.")
            else:
                # --- Numeric Cleanup ---
                dfm["plot_area"] = pd.to_numeric(dfm.get("plot_area", 0), errors="coerce").fillna(0)
                dfm["area_actual_cultivated"] = pd.to_numeric(dfm.get("area_actual_cultivated", 0), errors="coerce").fillna(0)
                dfm["crop_quality"] = pd.to_numeric(dfm.get("crop_quality", 0), errors="coerce").fillna(0)

                # --- Derived Metrics ---
                dfm["area_%"] = (dfm["area_actual_cultivated"] / dfm["plot_area"] * 100).replace([np.inf, -np.inf], np.nan).fillna(0)
                dfm["production_%"] = (dfm["area_%"] * (dfm["crop_quality"] / 5)).fillna(0)

                
                # -----------------------------
                # ================================
                # 🎛️ MAP MODE SELECTION (Green Tab Buttons)
                # ================================
                # ================================
                # 🎛️ MAP MODE SELECTION (Green Tab Buttons - Fully Functional)
                # ================================

                modes = [
                    "Inspection Status",
                    "Area under Cultivation (%)",
                    "Quality of Cultivation (1–5)",
                    "Expected Production (%)"
                ]

                # --- Remember selected mode in session ---
                if "map_mode" not in st.session_state:
                    st.session_state.map_mode = modes[0]

                # --- Custom CSS styling ---
                st.markdown("""
                <style>
                .mode-tabs {
                    display: flex;
                    justify-content: center;
                    flex-wrap: wrap;
                    gap: 12px;
                    margin-bottom: 18px;
                    margin-top: -30px;
                }
                div[data-testid="stButton"] > button {
                    border-radius: 10px !important;
                    padding: -30px 18px !important;
                    border: 2px solid #15803D !important;
                    background-color: #E8F5E9 !important;
                    color: #166534 !important;
                    font-weight: 600 !important;
                    transition: all 0.2s ease;
                }
                div[data-testid="stButton"] > button:hover {
                    background-color: #bbf7d0 !important;
                }
                div[data-testid="stButton"].active > button {
                    background-color: #166534 !important;
                    color: white !important;
                    border-color: #166534 !important;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                }
                </style>
                """, unsafe_allow_html=True)

                # --- Render as Streamlit buttons in columns ---
                cols = st.columns(len(modes))
                for i, m in enumerate(modes):
                    with cols[i]:
                        # Highlight active one
                        container_class = "active" if st.session_state.map_mode == m else ""
                        st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
                        if st.button(m, key=f"mode_{i}"):
                            st.session_state.map_mode = m
                        st.markdown("</div>", unsafe_allow_html=True)

                # --- Selected mode ---
                map_mode = st.session_state.map_mode


                # ================================
                # 🏷️ Dynamic Map Title (Matches Theme)
                # ================================
                map_titles = {
                    "Inspection Status": "🗺️ Inspection Status Map",
                    "Area under Cultivation (%)": "🌾 Cultivation Coverage Map",
                    "Quality of Cultivation (1–5)": "📈 Crop Quality Map",
                    "Expected Production (%)": "📊 Expected Production Map"
                }

                map_subtitles = {
                    "Inspection Status": "Color-coded by inspecting officer type (BDO, CVO, Secretary, etc.)",
                    "Area under Cultivation (%)": "Based on the ratio of actual cultivated area to total land area",
                    "Quality of Cultivation (1–5)": "Derived from average crop condition ratings (1–5 scale)",
                    "Expected Production (%)": "Calculated as Area% × Quality Score"
                }

                # --- Styled title ---
                st.markdown(f"""
                <div style='text-align:center; margin-top:0px; margin-bottom:0px;'>
                    <h4 style='color:#166534; font-weight:700; margin-bottom:0px;'>{map_titles.get(map_mode, '🗺️ Map View')}</h4>
                    <p style='color:#4b5563; font-size:15px;'>{map_subtitles.get(map_mode, '')}</p>
                </div>
                """, unsafe_allow_html=True)


                # ================================
                # 🧭 HOVER TEXT BUILDER
                # ================================
                def make_hover_text(row):
                    parts = [f"<b>📍 Block:</b> {row['block']}", f"<b>Village:</b> {row['village']}"]
                    if row.get("officer_name"):
                        parts.append(f"<b>Officer:</b> {row['officer_name']} ({row.get('officer_designation','')})")
                    parts.append(f"<b>Plot Area:</b> {row['plot_area']:.2f} ha")
                    parts.append(f"<b>Area Cultivated:</b> {row['area_actual_cultivated']:.2f} ha")
                    parts.append(f"<b>Area %:</b> {row['area_%']:.1f}%")
                    parts.append(f"<b>Quality:</b> {row['crop_quality']:.1f}")
                    parts.append(f"<b>Production %:</b> {row['production_%']:.1f}%")
                    if row.get("created_at"):
                        parts.append(f"<b>Date:</b> {str(row['created_at']).split(' ')[0]}")
                    return "<br>".join(parts)

                dfm["hover_text"] = dfm.apply(make_hover_text, axis=1)

                # ================================
                # 🎨 COLOR LOGIC
                # ================================
                def get_color(row):
                    if map_mode == "Inspection Status":
                        d = str(row.get("officer_designation", "")).upper()
                        if not d or d == "NAN":
                            return "black"
                        elif "BDO" in d:
                            return "blue"
                        elif "CVO" in d:
                            return "green"
                        elif "सचिव" in d or "SEC" in d:
                            return "red"
                        else:
                            return "gray"
                    elif map_mode == "Area under Cultivation (%)":
                        v = row["area_%"]
                        return "red" if v < 50 else "blue" if v < 80 else "green"
                    elif map_mode == "Quality of Cultivation (1–5)":
                        q = row["crop_quality"]
                        return "red" if q <= 2 else "blue" if q <= 4 else "green"
                    elif map_mode == "Expected Production (%)":
                        p = row["production_%"]
                        return "red" if p < 50 else "blue" if p < 80 else "green"
                    return "gray"

                dfm["color"] = dfm.apply(get_color, axis=1)

                # ================================
                # 🗺️ BUILD PLOTLY MAP
                # ================================
                import plotly.graph_objects as go

                # Define color mapping for current mode
                if map_mode == "Inspection Status":
                    color_map = {
                        "Not Done": "black",
                        "BDO": "blue",
                        "CVO": "green",
                        "सचिव": "red"
                    }

                    def classify(row):
                        d = str(row.get("officer_designation", "")).upper()
                        if not d or d == "NAN":
                            return "Not Done"
                        elif "BDO" in d:
                            return "BDO"
                        elif "CVO" in d:
                            return "CVO"
                        elif "सचिव" in d or "SEC" in d:
                            return "सचिव"
                        return "Other"

                    dfm["category"] = dfm.apply(classify, axis=1)

                elif map_mode == "Area under Cultivation (%)":
                    color_map = {"< 50%": "red", "50–80%": "blue", "> 80%": "green"}

                    def classify(row):
                        val = row["area_%"]
                        if val < 50:
                            return "< 50%"
                        elif val < 80:
                            return "50–80%"
                        else:
                            return "> 80%"

                    dfm["category"] = dfm.apply(classify, axis=1)

                elif map_mode == "Quality of Cultivation (1–5)":
                    color_map = {"<= 2": "red", "<= 4": "blue", "> 4": "green"}

                    def classify(row):
                        q = row["crop_quality"]
                        if q <= 2:
                            return "<= 2"
                        elif q <= 4:
                            return "<= 4"
                        else:
                            return "> 4"

                    dfm["category"] = dfm.apply(classify, axis=1)

                else:  # Expected Production
                    color_map = {"< 50%": "red", "< 80%": "blue", "> 80%": "green"}

                    def classify(row):
                        p = row["production_%"]
                        if p < 50:
                            return "< 50%"
                        elif p < 80:
                            return "< 80%"
                        else:
                            return "> 80%"

                    dfm["category"] = dfm.apply(classify, axis=1)

                # --- Build figure with multiple traces (one per category) ---
                fig = go.Figure()

                # --- Center and Zoom Control ---
                if not dfm.empty:
                    center_lat = dfm["latitude"].mean()
                    center_lon = dfm["longitude"].mean()
                else:
                    center_lat, center_lon = 27.5, 80.5  # fallback (UP region default)

                fig.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lat=center_lat, lon=center_lon),
                        zoom=9
                    )
                )


                for label, color in color_map.items():
                    df_cat = dfm[dfm["category"] == label]
                    if not df_cat.empty:
                        fig.add_trace(go.Scattermapbox(
                            lat=df_cat["latitude"],
                            lon=df_cat["longitude"],
                            mode="markers",
                            marker=dict(size=22, color=color, opacity=0.85),
                            text=df_cat["hover_text"],
                            hovertemplate="%{text}<extra></extra>",
                            name=label
                        ))

                # --- Layout & Legend ---
                fig.update_layout(
                    mapbox_style="open-street-map",
                    margin={"r": 0, "t": 0, "l": 0, "b": 0},
                    legend_title_text="Click to Toggle Layers",
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=0.9,
                        xanchor="left",
                        x=0.8,
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="#15803D",
                        borderwidth=1,
                        font=dict(size=13, color="#166534")
                    ),
                    legend_itemclick="toggle",
                    legend_itemdoubleclick="toggleothers",
                    height=650,
                    
                )


                # ================================
                # 🧭 HTML BORDER + ZOOM BUTTONS
                # ================================
                from streamlit.components.v1 import html as st_html

                zoom_html = f"""
                <div style="position: relative; border:4px solid #15803D; border-radius:12px; overflow:hidden; background:#fff; box-shadow:0 2px 6px rgba(0,0,0,0.1);">

                <div id="plotly-map" style="height:650px; width:100%;">
                    {fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='plotly-map')}
                </div>

                <div style="position:absolute;top:20px;left:20px;display:flex;flex-direction:column;gap:8px;z-index:999;">
                    <button id="zoom-in" style="background:white;border:2px solid #15803D;color:#15803D;font-size:22px;border-radius:6px;width:44px;height:44px;cursor:pointer;">+</button>
                    <button id="zoom-out" style="background:white;border:2px solid #15803D;color:#15803D;font-size:26px;border-radius:6px;width:44px;height:44px;cursor:pointer;">−</button>
                </div>

                <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    const mapDiv = document.getElementById('plotly-map');
                    if (!mapDiv) return;
                    function getZoom() {{
                        const layout = mapDiv._fullLayout || {{}};
                        return layout.mapbox?.zoom || 9;
                    }}
                    function zoom(delta) {{
                        const newZoom = getZoom() + delta;
                        Plotly.relayout(mapDiv, {{'mapbox.zoom': newZoom}});
                    }}
                    document.getElementById('zoom-in').addEventListener('click', () => zoom(+0.5));
                    document.getElementById('zoom-out').addEventListener('click', () => zoom(-0.5));
                }});
                </script>
                </div>
                """

                st_html(zoom_html, height=700)

                # ================================
                # 📋 DATA TABLE BELOW MAP
                # ================================
                st.markdown("---")
                st.markdown("#### 📋 Data Used in Map Visualization")
                display_cols = [
                    "block", "village", "officer_name", "officer_designation",
                    "plot_area", "area_actual_cultivated", "area_%", "crop_quality",
                    "production_%", "latitude", "longitude"
                ]
                display_cols = [c for c in display_cols if c in dfm.columns]

                st.dataframe(
                    dfm[display_cols].round(2).style.set_properties(**{
                        'text-align': 'center',
                        'vertical-align': 'middle'
                    }),
                    use_container_width=True
                )

                out_map = BytesIO()
                with pd.ExcelWriter(out_map, engine="openpyxl") as w:
                    dfm[display_cols].to_excel(w, index=False, sheet_name="map_data")
                st.download_button(
                    "📥 Download Map Data (Excel)",
                    out_map.getvalue(),
                    "inspection_map_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        else:
            st.warning("⚠️ No GPS columns ('latitude', 'longitude') found in dataset.")

        st.markdown('</div>', unsafe_allow_html=True)



    # --- PHOTO SUBTAB ---
    # --- PHOTO SUBTAB ---
    # --- PHOTO SUBTAB ---
    # --- PHOTO SUBTAB ---
    with sub_photo:
        import re, json, requests, html
        from io import BytesIO
        from PIL import Image
        from streamlit.components.v1 import html as st_html

        #st.markdown("<h3 style='text-align:center; color:#2E7D32;'>📸 Photo Analytics — From Submission Data</h3>", unsafe_allow_html=True)
        #st.markdown("---")

        # ================================================================
        # 1️⃣ Extract filenames from URLs
        # ================================================================
        def extract_filename_from_url(url):
            if not isinstance(url, str) or not url:
                return None
            m = re.search(r"(IMG-[\d_]+[a-zA-Z0-9]+\.jpe?g)", url)
            return m.group(1) if m else None

        df_last["photo_selfie_name"] = df_last["photo_selfie"].apply(extract_filename_from_url)
        df_last["photo_field_name"] = df_last["photo_field"].apply(extract_filename_from_url)

        # ================================================================
        # 2️⃣ Load Google Drive photos and normalize URLs
        # ================================================================
        drive_folder_id = "1SO-p_yU7ARjEsMIcEqu7m2T8Dh2Bt4BJ"
        try:
            df_drive = fetch_drive_photos(folder_id=drive_folder_id, _creds_json=st.secrets["gcp_service_account"])
            #st.success(f"✅ Loaded {len(df_drive)} photos from Google Drive.")
        except Exception as e:
            st.error(f"❌ Failed to load Drive photos: {e}")
            df_drive = pd.DataFrame(columns=["file_name", "public_url"])

        drive_map = dict(zip(df_drive["file_name"], df_drive["public_url"]))
        df_last["photo_selfie_url"] = df_last["photo_selfie_name"].map(drive_map)
        df_last["photo_field_url"] = df_last["photo_field_name"].map(drive_map)

        def normalize_drive_url(url):
            if not isinstance(url, str) or not url:
                return None
            m = re.search(r"(?:id=|/d/|uc\\?id=|download\\?id=)([a-zA-Z0-9_-]{15,})", url)
            if not m:
                return url
            file_id = m.group(1)
            return f"https://drive.usercontent.google.com/download?id={file_id}"

        for col in ["photo_selfie_url", "photo_field_url"]:
            df_last[col] = df_last[col].apply(normalize_drive_url)

        # ================================================================
        # 3️⃣ Debug Table
        # ================================================================
        #st.markdown("### 🧩 Debug: Sample Mapped URLs")
        #st.dataframe(df_last[["village", "block", "photo_selfie_url", "photo_field_url"]].head(10))

        # ================================================================
        # 4️⃣ Function to render gallery (iframe-safe)
        # ================================================================
        import base64

        def render_gallery(photo_urls, captions, gallery_id="gallery1"):
            """Renders image gallery with base64 inline encoding (Streamlit-safe)."""
            if not photo_urls:
                st.warning("⚠️ No photos to display.")
                return

            # Fetch and encode images as base64
            encoded_photos = []
            for i, url in enumerate(photo_urls):
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
                        img_b64 = base64.b64encode(resp.content).decode("utf-8")
                        mime = resp.headers.get("Content-Type", "image/jpeg")
                        encoded_photos.append(f"data:{mime};base64,{img_b64}")
                    else:
                        st.write(f"⚠️ Skipped non-image or failed URL: {url}")
                except Exception as e:
                    st.write(f"❌ Error fetching {url}: {e}")

            if not encoded_photos:
                st.warning("⚠️ No valid image data after download.")
                return

            photo_json = json.dumps(encoded_photos)
            caption_json = json.dumps(captions)

            gallery_html = f"""
            <html>
            <head>
            <meta charset="utf-8">
            <style>
            body {{
                font-family: Arial;
                background-color: #f9f9f9;
                margin: 0;
                padding: 10px;
            }}
            .gallery {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 10px;
            }}
            .gallery img {{
                width: 100%;
                border-radius: 10px;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                transition: transform 0.2s ease;
            }}
            .gallery img:hover {{ transform: scale(1.05); }}
            .modal {{
                display: none;
                position: fixed;
                z-index: 9999;
                left: 0; top: 0;
                width: 100%; height: 100%;
                background-color: rgba(0,0,0,0.95);
                text-align: center;
            }}
            .modal img {{
                max-width: 95%;
                max-height: 80vh;
                border-radius: 10px;
                margin-top: 50px;
            }}
            .caption {{
                color: white;
                font-size: 18px;
                margin-top: 10px;
            }}
            .close, .prev, .next {{
                position: absolute;
                color: white;
                font-size: 36px;
                font-weight: bold;
                cursor: pointer;
            }}
            .close {{ top: 20px; right: 40px; }}
            .prev {{ top: 50%; left: 40px; transform: translateY(-50%); }}
            .next {{ top: 50%; right: 40px; transform: translateY(-50%); }}
            </style>
            </head>
            <body>

            <div class="gallery" style="margin-bottom:0; padding-bottom:0;">
                {"".join([
                    f"<img src='{html.escape(u)}' alt='{html.escape(c)}' onclick='openModal({i})' "
                    f"style='display:block; margin:0; padding:0;'/>"
                    for i,(u,c) in enumerate(zip(encoded_photos,captions))
                ])}
            </div>

            <div id="modal" class="modal">
                <span class="close" onclick="closeModal()">&times;</span>
                <span class="prev" onclick="prevImage()">&#10094;</span>
                <span class="next" onclick="nextImage()">&#10095;</span>
                <img id="modal-img">
                <div class="caption" id="modal-caption"></div>
            </div>

            <script>
            const photos = {photo_json};
            const captions = {caption_json};
            let currentIndex = 0;

            function openModal(i) {{
                currentIndex = i;
                document.getElementById("modal").style.display = "block";
                document.getElementById("modal-img").src = photos[i];
                document.getElementById("modal-caption").innerText = captions[i];
            }}
            function closeModal() {{
                document.getElementById("modal").style.display = "none";
            }}
            function nextImage() {{
                currentIndex = (currentIndex + 1) % photos.length;
                openModal(currentIndex);
            }}
            function prevImage() {{
                currentIndex = (currentIndex - 1 + photos.length) % photos.length;
                openModal(currentIndex);
            }}
            </script>
            </body>
            </html>
            """

            st_html(gallery_html, height=650, scrolling=True)

        # ================================================================
        # 5️⃣ Block Tabs + Village Galleries
        # ================================================================
        blocks = sorted(df_last["block"].dropna().unique())
        if not blocks:
            st.warning("⚠️ No block data available.")
        else:
            #st.markdown("### 🏢 Select Block to View Photos")
            block_tabs = st.tabs(blocks)

            for b_i, block in enumerate(blocks):
                with block_tabs[b_i]:
                    df_block = df_last[df_last["block"] == block].copy()

                    # --- Block Gallery ---
                    st.markdown(f"#### 🏞️ {block} Block All Inspection Photos")

                    # Melt to combine selfie + field photos while keeping village info
                    df_block_long = (
                        df_block.melt(
                            id_vars=["village", "block", "date"],
                            value_vars=["photo_selfie_url", "photo_field_url"],
                            var_name="photo_type",
                            value_name="url"
                        )
                        .dropna(subset=["url"])
                        .reset_index(drop=True)
                    )

                    # Extract unique URLs and create matching captions (village - block - date)
                    block_photos = df_block_long["url"].unique().tolist()
                    block_captions = [
                        f"{row['village']} - {row['block']} - {row['date'] if 'date' in row else ''}"
                        for _, row in df_block_long.iterrows()
                        if row["url"] in block_photos
                    ]

                    # Render gallery using base64-safe display
                    render_gallery(block_photos, block_captions, gallery_id=f"block_{block}")

                    st.markdown("---")

                    # --- Village Galleries ---
                    villages = sorted(df_block["village"].dropna().unique())
                    for v in villages:
                        st.markdown(f"#### 📍 Village: {v}")
                        df_v = df_block[df_block["village"] == v].copy()

                        photos, captions = [], []
                        for c in ["photo_selfie_url", "photo_field_url"]:
                            for u in df_v[c].dropna().unique():
                                photos.append(u)
                                captions.append(f"{v} - {block} - {df_v['date'].iloc[0] if 'date' in df_v else ''}")

                        if photos:
                            render_gallery(photos, captions, gallery_id=f"{v}_{block}")
                        else:
                            st.warning("⚠️ No photos found for this village.")


# ----------------------------
# TAB 2 — Progress Monitoring (Placeholder)
# ----------------------------
with tab2:
    st.info("Progress Monitoring enhancements will use these renamed fields and baseline for comparison.")




# ------------------- END -------------------
