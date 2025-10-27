# app.py
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

# ----------------------------
# CONFIG
# ----------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1K0KxYzI7td53UmLu_5ZeK9_FDk1UoD0h0IpUYTg1mmY/edit?usp=sharing"
GOOGLE_DRIVE_FOLDER_ID = "1SO-p_yU7ARjEsMIcEqu7m2T8Dh2Bt4BJ"
BASELINE_PATH = "baseline_static_data.XLSX"

# ----------------------------
# LOAD CREDENTIALS
# ----------------------------
try:
    gcp_creds = st.secrets["gcp_service_account"]
except Exception:
    st.error("❌ Missing Google service account credentials in st.secrets['gcp_service_account'].")
    st.stop()

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
    df_raw["created_date"] = df_raw["created_at"].dt.date

    # Sort so newest submissions appear first
    df_raw = df_raw.sort_values(by="created_at", ascending=False)

    # Drop duplicate submissions for the same village in the same block on the same day
    if {"block", "village"} <= set(df_raw.columns):
        df_raw = df_raw.drop_duplicates(subset=["block", "village", "created_date"], keep="first")
    else:
        # fallback if block not present
        df_raw = df_raw.drop_duplicates(subset=["village", "created_date"], keep="first")

    # Remove helper column
    df_raw = df_raw.drop(columns=["created_date"], errors="ignore")

    # Summary info
    st.info(f"✅ Cleaned data: {len(df_raw)} unique (latest) submissions per village per day.")

    return df_raw
# ----------------------------
# LOAD GOOGLE SHEET + RENAME
# ----------------------------
st.set_page_config(page_title="Goshala Dashboard", layout="wide")
st.title("🐄 Goshala Inspection Dashboard")

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
    df_raw["created_at"] = pd.to_datetime(df_raw["created_at"], errors="coerce")
    df_raw["created_date"] = df_raw["created_at"].dt.date
    df_raw["created_time"] = df_raw["created_at"].dt.time

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
    st.header("📅 Last Inspection Overview")

    if "created_date" in df_raw.columns and df_raw["created_date"].notna().any():
        min_date, max_date = df_raw["created_date"].min(), df_raw["created_date"].max()
        start, end = st.date_input("Select date range", (min_date, max_date))
        df_last = df_raw[(df_raw["created_date"] >= start) & (df_raw["created_date"] <= end)]
    else:
        df_last = df_raw.copy()

    


    #df_last["crop_quality"] = df_last["crop_quality"].apply(normalize_quality)
    df_last["plot_area"] = pd.to_numeric(df_last["plot_area"], errors="coerce")

    sub_overview, sub_area, sub_map, sub_photo  = st.tabs(["Overview", "Area", "Map", "Photo"])




    # --- Overview ---
    # --- Overview ---
    with sub_overview:
        st.subheader("📊 Block-wise Inspection Overview")
        st.markdown("---")
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
                st.plotly_chart(fig_pie, use_container_width=True, key="Overall Inspection Completion %")


            st.markdown("---")
            # --- Bar Chart (block-wise progress) ---
            fig_bar = px.bar(
                merged.melt(id_vars="block", value_vars=["required", "submitted", "remaining"],
                            var_name="Status", value_name="Count"),
                x="block", y="Count", color="Status",
                color_discrete_map={"required": "blue", "submitted": "green", "remaining": "red"},
                barmode="group", text="Count",
                title="Block-wise Required vs Submitted vs Remaining"
            )
            fig_bar.update_traces(texttemplate="%{text}", textposition="outside")
            st.plotly_chart(fig_bar, use_container_width=True, key="Block-wise Required vs Submitted vs Remaining")

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
        st.subheader("🌾 Area and Production Analysis (Block-wise)")


        
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
            st.plotly_chart(fig1, use_container_width=True, key="Total Area Cultivated (%)")

        with col2:
            fig2 = px.pie(
                names=["Good Quality", " "],
                values=[total_quality * 20, 100 - (total_quality * 20)],
                title="Average Quality (%)",
                color_discrete_sequence=["#00CC96", "#E3755A"]
            )
            st.plotly_chart(fig2, use_container_width=True, key="Average Quality (%)")

        with col3:
            fig3 = px.pie(
                names=["Expected Production", "Remaining"],
                values=[total_production, 100 - total_production],
                title="Total Production Expected (%)",
                color_discrete_sequence=["lightgray", "#FA0B9A"]
            )
            st.plotly_chart(fig3, use_container_width=True, key="Total Production Expected (%)")

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
                st.plotly_chart(fig4, use_container_width=True, key="Inspection Completion (%")

        st.markdown("---")

        # =========================================================
        # 1️⃣ % OF TOTAL AREA CULTIVATED (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🌱 % of Total Area Cultivated (Block-wise)")

        fig_cult = px.bar(
            block_agg, x="block", y="cultivated_%",
            color="cultivated_%", 
            
            color_continuous_scale=["#2fd973", "#66c2a4", "#238b45", "#09682f"],
            title="% of Total Area Cultivated per Block", text="cultivated_%"
        )
        fig_cult.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig_cult, use_container_width=True, key=" percentage of Total Area Cultivated per Block")

        st.dataframe(block_agg[["block", "total_plot_area", "total_cultivated", "cultivated_%"]].sort_values(by="cultivated_%", ascending=False))

        # Excel download
        out_cult = BytesIO()
        with pd.ExcelWriter(out_cult, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="area_cultivated")
        st.download_button("📥 Download Cultivated Area Data", out_cult.getvalue(), "blockwise_cultivated_area.xlsx")

        # =========================================================
        # 2️⃣ QUALITY OF CULTIVATED AREA (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🌾 Quality of Cultivated Area (Block-wise)")

        fig_qual = px.bar(
            block_agg, x="block", y="quality_%",
            color="quality_%", 
            color_continuous_scale=["#5DD6F5", "#1ee7f9", "#466ff7", "#0639F0"],
            title="Average Crop Quality per Block", text="quality_%"
        )
        fig_qual.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig_qual, use_container_width=True, key="Average Crop Quality per Block")

        st.dataframe(block_agg[["block", "avg_quality", "quality_%"]].sort_values(by="quality_%", ascending=False))

        out_quality = BytesIO()
        with pd.ExcelWriter(out_quality, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="quality")
        st.download_button("📥 Download Quality Data", out_quality.getvalue(), "blockwise_quality_data.xlsx")

        # =========================================================
        # 3️⃣ TOTAL PRODUCTION EXPECTED (BLOCK-WISE)
        # =========================================================
        st.markdown("## 🧮 Total Production Expected (Block-wise)")

        fig_prod = px.bar(
            block_agg, x="block", y="production_%",
            color="production_%", color_continuous_scale="Oranges",
            title="Expected Production (Cultivation × Quality)", text="production_%"
        )
        fig_prod.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig_prod, use_container_width=True, key="Expected Production (Cultivation × Quality)")

        st.dataframe(block_agg[["block", "production_%"]].sort_values(by="production_%", ascending=False))

        out_prod = BytesIO()
        with pd.ExcelWriter(out_prod, engine="openpyxl") as w:
            block_agg.to_excel(w, index=False, sheet_name="production")
        st.download_button("📥 Download Production Data", out_prod.getvalue(), "blockwise_production_data.xlsx")

    # --- Map ---
    # --- MAP SUBTAB ---
    with sub_map:
        st.subheader("🗺️ Inspection Map with Mode Options")

        if {"latitude", "longitude"} <= set(df_last.columns):
            dfm = df_last.dropna(subset=["latitude", "longitude"]).copy()

            if dfm.empty:
                st.warning("⚠️ No valid GPS coordinates available for mapping.")
            else:
                # --- Compute required metrics for mapping ---
                dfm["plot_area"] = pd.to_numeric(dfm.get("plot_area", 0), errors="coerce").fillna(0)
                dfm["area_actual_cultivated"] = pd.to_numeric(dfm.get("area_actual_cultivated", 0), errors="coerce").fillna(0)
                dfm["crop_quality"] = pd.to_numeric(dfm.get("crop_quality", 0), errors="coerce").fillna(0)

                # Derived metrics
                dfm["area_%"] = (dfm["area_actual_cultivated"] / dfm["plot_area"] * 100).replace([np.inf, -np.inf], np.nan).fillna(0)
                dfm["production_%"] = (dfm["area_%"] * (dfm["crop_quality"] / 5 ) ).fillna(0)

                # --- Map Center (Safe) ---
                lat_mean = dfm["latitude"].mean(skipna=True)
                lon_mean = dfm["longitude"].mean(skipna=True)
                if pd.isna(lat_mean) or pd.isna(lon_mean):
                    lat_mean, lon_mean = 27.5, 80.5  # fallback
                m = folium.Map(location=[lat_mean, lon_mean], zoom_start=11)

                # --- Map Mode Selection ---
                st.markdown("### 🗺️ Select Map View Mode")
                mode = st.radio(
                    "Select visualization type:",
                    [
                        "Inspection Status",
                        "Area under Cultivation (%)",
                        "Quality of Cultivation (1–5)",
                        "Expected Production (%)"
                    ],
                    horizontal=True
                )

                # --- Helper: Color logic for each mode ---
                def get_color(row):
                    if mode == "Inspection Status":
                        desig = str(row.get("officer_designation", "")).strip()
                        if not desig or desig == "nan":
                            return "black"
                        elif "BDO" in desig.upper():
                            return "blue"
                        elif "CVO" in desig.upper():
                            return "green"
                        elif "सचिव" in desig or "SEC" in desig.upper():
                            return "red"
                        else:
                            return "gray"

                    elif mode == "Area under Cultivation (%)":
                        val = row["area_%"]
                        if val < 50:
                            return "red"
                        elif val < 80:
                            return "blue"
                        else:
                            return "green"

                    elif mode == "Quality of Cultivation (1–5)":
                        val = row["crop_quality"]
                        if val <= 2:
                            return "red"
                        elif val <= 4:
                            return "blue"
                        else:
                            return "green"

                    elif mode == "Expected Production (%)":
                        val = row["production_%"]
                        if val < 50:
                            return "red"
                        elif val < 80:
                            return "blue"
                        else:
                            return "green"

                    return "gray"

                # --- Add Markers to Map ---
                for _, r in dfm.iterrows():
                    color = get_color(r)
                    popup_text = (
                        f"<b>Block:</b> {r.get('block','')}<br>"
                        f"<b>Village:</b> {r.get('village','')}<br>"
                        f"<b>Officer:</b> {r.get('officer_name','')} ({r.get('officer_designation','')})<br>"
                        f"<b>Area Cultivated %:</b> {r.get('area_%',0):.1f}%<br>"
                        f"<b>Quality:</b> {r.get('crop_quality',0):.1f}<br>"
                        f"<b>Production %:</b> {r.get('production_%',0):.1f}%"
                    )

                    folium.CircleMarker(
                        location=[r["latitude"], r["longitude"]],
                        radius=6,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.9,
                        popup=folium.Popup(popup_text, max_width=250)
                    ).add_to(m)

                st_folium(m, width=1000, height=600)

                # --- Data Table for plotted points ---
                st.markdown("### 📋 Data Used in Map Visualization")

                display_cols = [
                    "block", "village", "officer_name", "officer_designation",
                    "plot_area", "area_actual_cultivated", "area_%", "crop_quality",
                    "production_%", "latitude", "longitude"
                ]
                display_cols = [c for c in display_cols if c in dfm.columns]

                table_df = dfm[display_cols].copy().round(2)
                st.dataframe(table_df, use_container_width=True)

                # --- Download Button for Map Data ---
                out_map = BytesIO()
                with pd.ExcelWriter(out_map, engine="openpyxl") as w:
                    table_df.to_excel(w, index=False, sheet_name="map_data")
                st.download_button(
                    "📥 Download Map Data (Excel)",
                    out_map.getvalue(),
                    "inspection_map_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning("No GPS columns ('latitude', 'longitude') found in dataset.")



    # --- Photo ---
    # --- PHOTO SUBTAB ---
    # --- PHOTO SUBTAB ---
    with sub_photo:
        st.subheader("📸 Photo Analytics — From Submission Data")

        # ================================================================
        # 1️⃣ Extract Filenames from Clappia URLs
        # ================================================================
        import re

        def extract_filename_from_url(url):
            """Extract image filename (e.g., IMG-20251026_2218ik0da.jpeg) from any URL."""
            if not isinstance(url, str) or not url:
                return None
            match = re.search(r"(IMG-[\d_]+[a-zA-Z0-9]+\.jpe?g)", url)
            return match.group(1) if match else None

        df_last["photo_selfie_name"] = df_last["photo_selfie"].apply(extract_filename_from_url)
        df_last["photo_field_name"] = df_last["photo_field"].apply(extract_filename_from_url)

        # ================================================================
        # 2️⃣ Load Drive Photos & Match by Filename
        # ================================================================
        drive_folder_id = "1SO-p_yU7ARjEsMIcEqu7m2T8Dh2Bt4BJ"  # your folder ID
        try:
            df_drive = fetch_drive_photos(folder_id=drive_folder_id, _creds_json=st.secrets["gcp_service_account"])
            st.success(f"✅ Loaded {len(df_drive)} photos from Google Drive.")
        except Exception as e:
            st.error(f"❌ Failed to load Drive photos: {e}")
            df_drive = pd.DataFrame(columns=["file_name", "public_url"])

        # Map Drive filenames to public URLs
        drive_map = dict(zip(df_drive["file_name"], df_drive["public_url"]))
        df_last["photo_selfie_url"] = df_last["photo_selfie_name"].map(drive_map)
        df_last["photo_field_url"] = df_last["photo_field_name"].map(drive_map)

        # Debug preview
        with st.expander("🧪 Debug: Drive Matching Preview"):
            st.dataframe(df_last[["village", "photo_selfie_name", "photo_selfie_url",
                                "photo_field_name", "photo_field_url"]].head(10))

        # ================================================================
        # 3️⃣ Clean numeric fields for analysis
        # ================================================================
        df_last["plot_area"] = pd.to_numeric(df_last.get("plot_area", 0), errors="coerce").fillna(0)
        df_last["area_actual_cultivated"] = pd.to_numeric(df_last.get("area_actual_cultivated", 0), errors="coerce").fillna(0)
        df_last["crop_quality"] = pd.to_numeric(df_last.get("crop_quality", 0), errors="coerce").fillna(0)
        df_last["area_%"] = (df_last["area_actual_cultivated"] / df_last["plot_area"] * 100).clip(0, 100)

        # ================================================================
        # 4️⃣ Build Block Tabs
        # ================================================================
        blocks = sorted(df_last["block"].dropna().unique())
        if not blocks:
            st.warning("⚠️ No block data available.")
        else:
            st.markdown("### 🏢 Select a Block to View Photo & Metrics")
            block_tabs = st.tabs(blocks)

            for b_i, block in enumerate(blocks):
                with block_tabs[b_i]:
                    st.markdown(f"## 🏢 Block: {block}")
                    df_block = df_last[df_last["block"] == block].copy()

                    # --- Block Aggregates ---
                    total_area = df_block["plot_area"].sum()
                    total_cult = df_block["area_actual_cultivated"].sum()
                    avg_quality = df_block["crop_quality"].mean()
                    total_req = df_base[df_base["block"] == block].shape[0] if "block" in df_base.columns else 0
                    actual_done = df_block["village"].nunique()
                    remaining = max(total_req - actual_done, 0)

                    # --- Block Summary Charts ---
                    st.markdown("### 📊 Block Summary Charts")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        fig_q = px.pie(
                            names=["Avg Quality", "Remaining"],
                            values=[avg_quality * 20, 100 - (avg_quality * 20)],
                            title="Average Quality (%)",
                            color_discrete_sequence=["lightgray", "green"]
                        )
                        st.plotly_chart(fig_q, use_container_width=True, key=f"avg_quality_{block}")
                    with c2:
                        cultivated_pct = (total_cult / total_area * 100) if total_area > 0 else 0
                        fig_a = px.pie(
                            names=["Cultivated", "Uncultivated"],
                            values=[cultivated_pct, 100 - cultivated_pct],
                            title="Total Area Cultivated (%)",
                            color_discrete_sequence=["lightgray", "blue"]
                        )
                        st.plotly_chart(fig_a, use_container_width=True, key=f"area_cult_{block}")
                    with c3:
                        fig_i = px.pie(
                            names=["Inspected", "Pending"],
                            values=[actual_done, remaining],
                            title="Inspections Completed",
                            color_discrete_sequence=["lightgray", "red"]
                        )
                        st.plotly_chart(fig_i, use_container_width=True, key=f"inspect_done_{block}")

                    st.markdown("---")

                    # ================================================================
                    # 5️⃣ Village-Level Photo Display
                    # ================================================================
                    villages = sorted(df_block["village"].dropna().unique())
                    for v in villages:
                        st.markdown(f"### 📍 Village: {v}")
                        df_v = df_block[df_block["village"] == v].copy()

                        st.markdown("#### 🖼️ Photos")
                        cols = st.columns(4)
                        photo_urls = pd.concat([
                            df_v["photo_selfie_url"].dropna(),
                            df_v["photo_field_url"].dropna()
                        ]).unique()

                        if len(photo_urls) == 0:
                            st.warning("⚠️ No matching Drive photos found for this village.")
                        else:
                            for i, url in enumerate(photo_urls):
                                if isinstance(url, str) and url.startswith("http"):
                                    # --- Extract the file ID from any Google Drive link format ---
                                    file_id = None
                                    patterns = [
                                        r"id=([a-zA-Z0-9_-]+)",
                                        r"/d/([a-zA-Z0-9_-]+)",
                                        r"uc\?id=([a-zA-Z0-9_-]+)",
                                        r"download\?id=([a-zA-Z0-9_-]+)"
                                    ]
                                    for p in patterns:
                                        match = re.search(p, url)
                                        if match:
                                            file_id = match.group(1)
                                            break

                                    if file_id:
                                        # ✅ Use raw Googleusercontent link (always works inline)
                                        direct_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=view"

                                        image_html = f"""
                                            <div style='text-align:center; margin:8px;'>
                                                <img src="{direct_url}" 
                                                    style="width:100%; border-radius:12px; box-shadow:0 0 5px rgba(0,0,0,0.2);" 
                                                    alt="Photo" />
                                                <p style='font-size:12px; color:#444; margin-top:4px;'>
                                                    {os.path.basename(url)}
                                                </p>
                                            </div>
                                        """
                                        cols[i % 4].markdown(image_html, unsafe_allow_html=True)
                                    else:
                                        cols[i % 4].markdown(
                                            f"⚠️ <span style='color:red;'>No file ID found:</span> {url}",
                                            unsafe_allow_html=True
                                        )
                                else:
                                    cols[i % 4].markdown(
                                        f"⚠️ <span style='color:red;'>Invalid or missing image:</span> {url}",
                                        unsafe_allow_html=True
                                    )


                        # --- Village Summary ---
                        st.markdown("#### 📊 Village Summary")
                        colv1, colv2, colv3 = st.columns(3)
                        avg_quality_v = df_v["crop_quality"].mean()
                        area_pct_v = (df_v["area_actual_cultivated"].sum() / df_v["plot_area"].sum() * 100) if df_v["plot_area"].sum() > 0 else 0

                        with colv1:
                            fig_vq = px.pie(
                                names=["Quality", "Remaining"],
                                values=[avg_quality_v * 20, 100 - avg_quality_v * 20],
                                title="Avg Quality (%)",
                                color_discrete_sequence=["lightgray", "green"]
                            )
                            st.plotly_chart(fig_vq, use_container_width=True, key=f"fig_vq_{block}_{v}")
                        with colv2:
                            fig_va = px.pie(
                                names=["Cultivated", "Uncultivated"],
                                values=[area_pct_v, 100 - area_pct_v],
                                title="Avg Area Cultivated (%)",
                                color_discrete_sequence=["lightgray", "blue"]
                            )
                            st.plotly_chart(fig_va, use_container_width=True, key=f"fig_va_{block}_{v}")
                        with colv3:
                            fig_vi = px.pie(
                                names=["Inspected", "Pending"],
                                values=[1, 0],
                                title="Inspection Status",
                                color_discrete_sequence=["lightgray", "red"]
                            )
                            st.plotly_chart(fig_vi, use_container_width=True, key=f"fig_vi_{block}_{v}")

                        # --- Data Table + Download ---
                        st.markdown("#### 📋 Submission Data")
                        show_cols = [
                            "village", "block", "crop_quality", "area_actual_cultivated",
                            "plot_area", "area_%", "photo_selfie_name", "photo_field_name",
                            "photo_selfie_url", "photo_field_url"
                        ]
                        show_cols = [c for c in show_cols if c in df_v.columns]
                        st.dataframe(df_v[show_cols], use_container_width=True)

                        out_village = BytesIO()
                        with pd.ExcelWriter(out_village, engine="openpyxl") as w:
                            df_v.to_excel(w, index=False, sheet_name=f"{v}")
                        st.download_button(
                            f"📥 Download {v} Data",
                            out_village.getvalue(),
                            f"{block}_{v}_photos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    # --- Block Summary Table + Download ---
                    st.markdown("### 📋 Block Submission Summary")
                    st.dataframe(df_block[show_cols], use_container_width=True)

                    out_block = BytesIO()
                    with pd.ExcelWriter(out_block, engine="openpyxl") as w:
                        df_block.to_excel(w, index=False, sheet_name=f"{block}")
                    st.download_button(
                        f"📥 Download {block} Block Data",
                        out_block.getvalue(),
                        f"{block}_block_photo_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


# ----------------------------
# TAB 2 — Progress Monitoring (Placeholder)
# ----------------------------
with tab2:
    st.info("Progress Monitoring enhancements will use these renamed fields and baseline for comparison.")
