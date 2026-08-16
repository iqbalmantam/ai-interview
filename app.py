import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import openai
from pypdf import PdfReader
import streamlit as st
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(
    page_title="AI Interviewer", page_icon="🤖", layout="wide"
)

# Custom CSS
st.markdown(
    """
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Fungsi Groq & Google Sheets
def get_groq_client():
  groq_api_key = st.secrets.get("GROQ_API_KEY", "")
  return openai.OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

def simpan_ke_googlesheet(nama, posisi, skor, rekomendasi, evaluasi):
  try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Data_Hasil_Wawancara_AI").sheet1
    waktu = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([waktu, nama, posisi, skor, rekomendasi, evaluasi])
    return True
  except Exception: return False

def ambil_data_googlesheet():
  try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Data_Hasil_Wawancara_AI").sheet1
    return pd.DataFrame(sheet.get_all_records())
  except Exception: return pd.DataFrame()

# State
if "step" not in st.session_state: st.session_state.step = 0
if "answers" not in st.session_state: st.session_state.answers = []
if "cv_uploaded" not in st.session_state: st.session_state.cv_uploaded = False

tab_kandidat, tab_admin = st.tabs(["📝 Portal Kandidat", "🔐 Dashboard Admin"])

with tab_admin:
  st.title("🔐 Dashboard Admin")
  password = st.text_input("Password Admin", type="password")
  if password == "2273":
    df = ambil_data_googlesheet()
    if not df.empty:
      st.dataframe(df, use_container_width=True)
      pilihan = st.selectbox("Pilih Kandidat", (df["Nama Kandidat"] + " - " + df["Timestamp"]))
      idx = (df["Nama Kandidat"] + " - " + df["Timestamp"]).tolist().index(pilihan)
      st.info(df.iloc[idx]["Detail Evaluasi"])
    else: st.info("Belum ada data.")

with tab_kandidat:
  st.title("🤖 AI Interview Assistant")
  role = st.selectbox("Posisi:", ["Administrative Staff (Admin)", "Operations Supervisor", "Software Engineer (Full Stack)", "Product Manager", "Data Analyst"])
  
  if not st.session_state.cv_uploaded:
    nama = st.text_input("Nama Lengkap:")
    file = st.file_uploader("Upload CV (PDF):", type=["pdf"])
    if st.button("Mulai Wawancara"):
      if nama and file:
        st.session_state.nama_kandidat = nama
        cv_text = "".join([p.extract_text() for p in PdfReader(file).pages])
        client = get_groq_client()
        
        # AI menentukan jumlah pertanyaan otomatis (3-10)
        prompt = f"""
        Anda adalah expert recruiter. Baca CV berikut untuk posisi {role}.
        Tentukan jumlah pertanyaan yang tepat (minimal 3, maksimal 10) berdasarkan kedalaman pengalaman di CV.
        Output HANYA daftar pertanyaan saja, dipisahkan oleh baris baru.
        CV: {cv_text}
        """
        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
        st.session_state.generated_questions = [q.strip() for q in resp.choices[0].message.content.split("\n") if q.strip()]
        st.session_state.cv_uploaded = True
        st.rerun()
  else:
    q_list = st.session_state.generated_questions
    if st.session_state.step < len(q_list):
      st.subheader(f"Pertanyaan {st.session_state.step + 1} dari {len(q_list)}")
      st.markdown(f"> **{q_list[st.session_state.step]}**")
      with st.form("jawab"):
        ans = st.text_area("Jawaban:")
        if st.form_submit_button("Kirim & Lanjut"):
          st.session_state.answers.append({"q": q_list[st.session_state.step], "a": ans})
          st.session_state.step += 1
          st.rerun()
    else:
      if not st.session_state.get("saved", False):
        with st.spinner("Menyimpan..."):
          transkrip = "\n".join([f"Q: {i['q']}\nA: {i['a']}" for i in st.session_state.answers])
          resp = get_groq_client().chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": f"Evaluasi transkrip ini: {transkrip}"}])
          simpan_ke_googlesheet(st.session_state.nama_kandidat, role, "Selesai", "Review", resp.choices[0].message.content)
          st.session_state.saved = True
      st.success("Wawancara Selesai!")
      if st.button("Sesi Baru"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Developed by iqbalmantam</p>", unsafe_allow_html=True)
