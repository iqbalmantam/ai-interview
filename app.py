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
    page_title="AI Video Interviewer - Pro", page_icon="🤖", layout="wide"
)

# Custom CSS untuk menyembunyikan header bawaan (termasuk icon github & deploy)
st.markdown(
    """
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


# Fungsi untuk memanggil Groq Client
def get_groq_client():
  groq_api_key = st.secrets.get("GROQ_API_KEY", "")
  return openai.OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")


# Fungsi simpan ke Google Sheets
def simpan_ke_googlesheet(nama, posisi, skor, rekomendasi, evaluasi):
  try:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Data_Hasil_Wawancara_AI").sheet1
    waktu = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([waktu, nama, posisi, skor, rekomendasi, evaluasi])
    return True
  except Exception as e:
    st.error(f"Gagal simpan ke Google Sheet: {e}")
    return False


# Fungsi untuk membaca data dari Google Sheets (Dashboard Admin)
def ambil_data_googlesheet():
  try:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Data_Hasil_Wawancara_AI").sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)
  except Exception as e:
    return pd.DataFrame()


# Inisialisasi state
if "step" not in st.session_state:
  st.session_state.step = 0
if "answers" not in st.session_state:
  st.session_state.answers = []
if "cv_uploaded" not in st.session_state:
  st.session_state.cv_uploaded = False
if "saved_to_sheet" not in st.session_state:
  st.session_state.saved_to_sheet = False

# MENU UTAMA DI HEADER ATAS MENGGUNAKAN TABS
tab_kandidat, tab_admin = st.tabs(
    ["📝 Portal Kandidat (Wawancara)", "🔐 Dashboard Admin"]
)

with tab_admin:
  st.title("🔐 Dashboard Admin - Rekap Hasil Wawancara")
  password_input = st.text_input(
      "Masukkan Password Admin", type="password", key="admin_pass"
  )

  if password_input == "2273":
    st.success("Password Benar!")
    st.markdown("Berikut adalah data rekap hasil wawancara kandidat:")

    with st.spinner("Memuat data dari Google Sheets..."):
      df_hasil = ambil_data_googlesheet()

    if not df_hasil.empty:
      st.dataframe(df_hasil, use_container_width=True)
    else:
      st.info("Belum ada data atau Google Sheets masih kosong.")
  elif password_input != "":
    st.warning("⚠️ Password salah!")
  else:
    st.info("Silakan masukkan password admin (`2273`) untuk melihat data.")

with tab_kandidat:
  st.title("🤖 AI Interview Assistant (Berbasis CV)")

  role = st.selectbox(
      "Pilih Posisi yang Dilamar",
      [
          "Administrative Staff (Admin)",
          "Operations Supervisor",
          "Software Engineer (Full Stack)",
          "Product Manager",
          "Customer Success Specialist",
          "Data Analyst",
          "Finance & Accounting Staff",
          "HR & Recruitment Officer",
          "Marketing Specialist",
      ],
  )
  st.markdown("---")

  # Tahap 1: Upload CV & Identitas
  if not st.session_state.cv_uploaded:
    st.subheader("📁 Langkah 1: Masukkan Identitas & Unggah CV Kandidat")
    nama_input = st.text_input("Nama Lengkap Kandidat", key="nama_kand")
    uploaded_file = st.file_uploader(
        "Unggah CV (Format PDF)", type=["pdf"], key="file_cv"
    )

    if st.button("Mulai Wawancara"):
      if not nama_input:
        st.warning("⚠️ Mohon masukkan nama lengkap kandidat terlebih dahulu.")
      elif uploaded_file is None:
        st.warning("⚠️ Mohon unggah file CV kandidat (PDF).")
      else:
        st.session_state.nama_kandidat = nama_input
        with st.spinner("Membaca CV dan merancang pertanyaan khusus via Groq AI..."):
          try:
            reader = PdfReader(uploaded_file)
            cv_text = "".join([p.extract_text() for p in reader.pages])

            client = get_groq_client()
            prompt = f"""
                        Anda adalah expert recruiter. Berdasarkan teks CV kandidat di bawah ini dan posisi yang dilamar ({role}), 
                        buatlah tepat 3 pertanyaan wawancara yang spesifik menggali pengalaman, proyek, atau keahlian yang tertulis di CV tersebut.
                        
                        Format output HANYA berupa daftar 3 pertanyaan tanpa nomor atau teks tambahan, dipisahkan oleh baris baru (newline).
                        
                        Teks CV:
                        {cv_text}
                        """

            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )

            questions_list = [
                q.strip()
                for q in resp.choices[0].message.content.split("\n")
                if q.strip()
            ]
            if len(questions_list) < 3:
              questions_list = [
                  "Ceritakan proyek paling menantang yang tercantum di CV Anda.",
                  "Bagaimana pengalaman Anda relevan dengan posisi ini?",
                  "Apa pencapaian terbesar dalam karier profesional Anda sejauh ini?",
              ]

            st.session_state.generated_questions = questions_list[:3]
            st.session_state.cv_uploaded = True
            st.success("CV berhasil dianalisis! Pertanyaan wawancara siap.")
            st.rerun()
          except Exception as e:
            st.error(f"Gagal memproses CV: {e}")

  else:
    # Tahap 2: Sesi Tanya Jawab (Tanpa Suara AI)
    current_questions = st.session_state.generated_questions

    if st.session_state.step < len(current_questions):
      q = current_questions[st.session_state.step]
      st.subheader(
          f"Pertanyaan {st.session_state.step + 1} dari {len(current_questions)}"
          f" untuk: **{st.session_state.nama_kandidat}**"
      )
      st.markdown(f"> **{q}**")

      with st.form(key=f"form_{st.session_state.step}"):
        ans = st.text_area(
            "Ketik jawaban atau transkrip wawancara:",
            placeholder="Berikan jawaban terstruktur...",
            height=150,
        )
        if st.form_submit_button("Kirim Jawaban & Lanjut"):
          if not ans.strip():
            st.warning("Mohon masukkan jawaban terlebih dahulu.")
          else:
            st.session_state.answers.append({"q": q, "a": ans})
            st.session_state.step += 1
            st.rerun()

    else:
      # Tahap 3: Selesai (Otomatis dievaluasi & masuk ke Google Sheets di background)
      if not st.session_state.saved_to_sheet:
        with st.spinner("Menyimpan hasil wawancara ke sistem..."):
          transcript_text = ""
          for i, item in enumerate(st.session_state.answers):
            transcript_text += (
                f"Pertanyaan {i+1}: {item['q']}\nJawaban: {item['a']}\n\n"
            )

          prompt_eval = f"""
                Bertindaklah sebagai Expert Recruiter. Analisis transkrip wawancara berikut untuk posisi {role} (berdasarkan CV kandidat):
                
                {transcript_text}
                
                Berikan penilaian dalam format berikut secara jelas:
                1. Skor Keseluruhan (angka 0-100)
                2. Rekomendasi Akhir (Lolos / Tidak Lolos)
                3. Analisis Kekuatan & Area Perhatian Kandidat
                """

          try:
            client = get_groq_client()
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_eval}],
                temperature=0.3,
            )
            evaluation = response.choices[0].message.content

            sukses = simpan_ke_googlesheet(
                nama=st.session_state.nama_kandidat,
                posisi=role,
                skor="Selesai Evaluasi",
                rekomendasi="Cek Dashboard Admin",
                evaluasi=evaluation,
            )
            if sukses:
              st.session_state.saved_to_sheet = True
          except Exception as e:
            st.error(f"Gagal memproses evaluasi: {e}")

      st.success("🎉 Wawancara Telah Selesai!")
      st.markdown(
          "Terima kasih telah menyelesaikan sesi wawancara. Data Anda telah"
          " berhasil direkam dan dikirimkan kepada tim perekrut."
      )

      if st.button("Mulai Sesi Baru"):
        st.session_state.clear()
        st.rerun()

# WATERMARK
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray; font-size: small;'>Developed by"
    " iqbalmantam</p>",
    unsafe_allow_html=True,
)
