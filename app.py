import streamlit as st
import openai
import pandas as pd
from pypdf import PdfReader
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json

# Konfigurasi Halaman
st.set_page_config(
    page_title="AI Video Interviewer - TestGorilla Style",
    page_icon="🤖",
    layout="wide"
)

# Sidebar untuk Konfigurasi
st.sidebar.header("⚙️ Konfigurasi Rekrutmen")
api_key = st.sidebar.text_input("Masukkan OpenAI API Key", type="password")

role = st.sidebar.selectbox(
    "Pilih Posisi yang Dilamar",
    [
        "Software Engineer (Full Stack)",
        "Product Manager",
        "Customer Success Specialist",
        "Data Analyst"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("Aplikasi ini membaca CV kandidat, menghasilkan pertanyaan wawancara khusus, dan menyimpan hasilnya ke Google Sheets.")

# Judul Utama
st.title("🤖 AI Interview Assistant (Berbasis CV)")
st.markdown(f"**Posisi Tujuan:** `{role}`")
st.markdown("---")

# Inisialisasi state sesi wawancara
if "step" not in st.session_state:
    st.session_state.step = 0
if "answers" not in st.session_state:
    st.session_state.answers = []
if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = []
if "cv_uploaded" not in st.session_state:
    st.session_state.cv_uploaded = False
if "saved_to_sheet" not in st.session_state:
    st.session_state.saved_to_sheet = False

# Fungsi untuk menyimpan ke Google Sheets via Streamlit Secrets
def simpan_ke_googlesheet(nama_kandidat, posisi, skor, rekomendasi, evaluasi):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Mengambil kredensial dari st.secrets (untuk Streamlit Cloud) atau file lokal
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            
        client = gspread.authorize(creds)
        
        # Sesuaikan dengan nama Google Sheet Anda
        sheet = client.open("Data_Hasil_Wawancara_AI").sheet1
        
        waktu_sekarang = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        baris_data = [
            waktu_sekarang,
            nama_kandidat,
            posisi,
            skor,
            rekomendasi,
            evaluasi
        ]
        sheet.append_row(baris_data)
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan ke Google Sheets: {e}")
        return False

# Tahap 1: Unggah CV & Generate Pertanyaan
if not st.session_state.cv_uploaded:
    st.subheader("📁 Langkah 1: Masukkan Identitas & Unggah CV Kandidat")
    nama_input = st.text_input("Nama Lengkap Kandidat")
    uploaded_file = st.file_uploader("Unggah CV (Format PDF)", type=["pdf"])
    
    if st.button("Mulai Wawancara"):
        if not nama_input:
            st.warning("⚠️ Mohon masukkan nama lengkap kandidat terlebih dahulu.")
        elif uploaded_file is None:
            st.warning("⚠️ Mohon unggah file CV kandidat (PDF).")
        elif not api_key:
            st.warning("⚠️ Masukkan OpenAI API Key di sidebar terlebih dahulu.")
        else:
            st.session_state.nama_kandidat = nama_input
            with st.spinner("Membaca CV dan membuat pertanyaan khusus..."):
                try:
                    reader = PdfReader(uploaded_file)
                    cv_text = ""
                    for page in reader.pages:
                        cv_text += page.extract_text()
                    
                    client = openai.OpenAI(api_key=api_key)
                    prompt_gen = f"""
                    Anda adalah expert recruiter. Berdasarkan teks CV kandidat di bawah ini dan posisi yang dilamar ({role}), 
                    buatlah tepat 3 pertanyaan wawancara yang spesifik menggali pengalaman, proyek, atau keahlian yang tertulis di CV tersebut.
                    
                    Format output HANYA berupa daftar 3 pertanyaan tanpa nomor atau teks tambahan, dipisahkan oleh baris baru (newline).
                    
                    Teks CV:
                    {cv_text}
                    """
                    
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt_gen}],
                        temperature=0.5
                    )
                    
                    questions_text = response.choices[0].message.content.strip()
                    questions_list = [q.strip() for q in questions_text.split("\n") if q.strip()]
                    
                    if len(questions_list) < 3:
                        questions_list = [
                            "Ceritakan proyek paling menantang yang tercantum di CV Anda.",
                            "Bagaimana pengalaman Anda relevan dengan posisi ini?",
                            "Apa pencapaian terbesar dalam karier profesional Anda sejauh ini?"
                        ]
                    
                    st.session_state.generated_questions = questions_list[:3]
                    st.session_state.cv_uploaded = True
                    st.success("CV berhasil dianalisis! Pertanyaan wawancara khusus telah dibuat.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Gagal memproses CV: {e}")

else:
    # Tahap 2: Sesi Tanya Jawab
    current_questions = st.session_state.generated_questions
    
    if st.session_state.step < len(current_questions):
        q_idx = st.session_state.step
        st.subheader(f"Pertanyaan {q_idx + 1} dari {len(current_questions)} untuk: **{st.session_state.nama_kandidat}**")
        st.markdown(f"> **{current_questions[q_idx]}**")
        
        with st.form(key=f"form_{q_idx}"):
            user_response = st.text_area(
                "Ketik jawaban atau transkrip wawancara:",
                placeholder="Berikan jawaban terstruktur...",
                height=150
            )
            submit_answer = st.form_submit_button("Kirim Jawaban & Lanjut")
            
            if submit_answer:
                if not user_response.strip():
                    st.warning("Mohon masukkan jawaban terlebih dahulu.")
                else:
                    st.session_state.answers.append({
                        "question": current_questions[q_idx],
                        "answer": user_response
                    })
                    st.session_state.step += 1
                    st.rerun()

    else:
        # Tahap 3: Evaluasi Akhir & Simpan ke Sheets
        st.success("🎉 Wawancara Selesai! AI sedang menyusun hasil evaluasi akhir...")
        
        transcript_text = ""
        for i, item in enumerate(st.session_state.answers):
            transcript_text += f"Pertanyaan {i+1}: {item['question']}\nJawaban: {item['answer']}\n\n"
            
        prompt_eval = f"""
        Bertindaklah sebagai Expert Recruiter. Analisis transkrip wawancara berikut untuk posisi {role} (berdasarkan CV kandidat):
        
        {transcript_text}
        
        Berikan penilaian dalam format berikut secara jelas:
        1. Skor Keseluruhan (angka 0-100)
        2. Rekomendasi Akhir (Lolos / Tidak Lolos)
        3. Analisis Kekuatan & Area Perhatian Kandidat
        """
        
        with st.spinner("Menghitung skor dan menyimpan data..."):
            try:
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt_eval}],
                    temperature=0.3
                )
                evaluation = response.choices[0].message.content
                
                st.subheader("📊 Hasil Evaluasi & Skor AI")
                st.markdown(evaluation)
                
                # Otomatis Simpan ke Google Sheets sekali saja
                if not st.session_state.saved_to_sheet:
                    # Contoh ekstraksi sederhana untuk skor/rekomendasi (bisa disesuaikan)
                    sukses = simpan_ke_googlesheet(
                        nama_kandidat=st.session_state.nama_kandidat,
                        posisi=role,
                        skor="Cek Detail", 
                        rekomendasi="Review", 
                        evaluasi=evaluation
                    )
                    if sukses:
                        st.info("📌 Hasil wawancara telah otomatis dicatat ke Google Sheets.")
                        st.session_state.saved_to_sheet = True
                
            except Exception as e:
                st.error(f"Terjadi kesalahan saat evaluasi: {e}")
                
        # Tombol Reset
        if st.button("Mulai Wawancara Baru (Kandidat Lain)"):
            st.session_state.step = 0
            st.session_state.answers = []
            st.session_state.generated_questions = []
            st.session_state.cv_uploaded = False
            st.session_state.saved_to_sheet = False
            st.rerun()
