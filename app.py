import streamlit as st
import openai
import pandas as pd
from pypdf import PdfReader
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json
from gtts import gTTS
import os

# Konfigurasi Halaman
st.set_page_config(
    page_title="AI Video Interviewer - Pro", page_icon="🤖", layout="wide"
)

# Fungsi untuk memutar suara AI
def putar_suara_ai(teks):
    tts = gTTS(text=teks, lang="id", slow=False)
    audio_file = "pertanyaan_ai.mp3"
    tts.save(audio_file)
    st.audio(audio_file, format="audio/mp3", autoplay=True)

# Fungsi untuk memanggil Groq Client
def get_groq_client():
    groq_api_key = st.secrets.get("GROQ_API_KEY", "MASUKKAN_KEY_DI_SECRETS")
    return openai.OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

# Fungsi simpan ke Google Sheets
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
    except Exception as e:
        st.error(f"Gagal simpan ke Sheet: {e}")
        return False

# Inisialisasi state
if "step" not in st.session_state: st.session_state.step = 0
if "answers" not in st.session_state: st.session_state.answers = []
if "cv_uploaded" not in st.session_state: st.session_state.cv_uploaded = False

st.title("🤖 AI Interview Assistant (Suara & CV)")
role = st.sidebar.text_input("Posisi yang Dilamar", value="Administrative Staff (Admin)")

if not st.session_state.cv_uploaded:
    nama_input = st.text_input("Nama Lengkap Kandidat")
    uploaded_file = st.file_uploader("Unggah CV (PDF)", type=["pdf"])
    
    if st.button("Mulai Wawancara"):
        if nama_input and uploaded_file:
            st.session_state.nama_kandidat = nama_input
            reader = PdfReader(uploaded_file)
            cv_text = "".join([p.extract_text() for p in reader.pages])
            
            client = get_groq_client()
            prompt = f"Buat 3 pertanyaan wawancara untuk posisi {role} berdasarkan CV: {cv_text}. Berikan hanya pertanyaannya saja."
            
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            st.session_state.generated_questions = [q.strip() for q in resp.choices[0].message.content.split("\n") if q.strip()]
            st.session_state.cv_uploaded = True
            st.rerun()
else:
    current_questions = st.session_state.generated_questions
    if st.session_state.step < len(current_questions):
        q = current_questions[st.session_state.step]
        st.subheader(f"Pertanyaan {st.session_state.step + 1}")
        st.markdown(f"> **{q}**")
        
        # Panggil fungsi suara
        putar_suara_ai(q)
        
        with st.form("jawab"):
            ans = st.text_area("Jawaban Anda:")
            if st.form_submit_button("Kirim & Lanjut"):
                st.session_state.answers.append({"q": q, "a": ans})
                st.session_state.step += 1
                st.rerun()
    else:
        st.success("Wawancara Selesai!")
        # ... (Logika evaluasi dan simpan ke sheets seperti sebelumnya) ...
        if st.button("Reset"):
            st.session_state.clear()
            st.rerun()
