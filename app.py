import datetime
import json
import os
from gtts import gTTS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import openai
from pypdf import PdfReader
import streamlit as st

# Konfigurasi Halaman
st.set_page_config(
    page_title="AI Video Interviewer - Pro", page_icon="🤖", layout="wide"
)


# Fungsi untuk memutar suara AI
def putar_suara_ai(teks):
  try:
    tts = gTTS(text=teks, lang="id", slow=False)
    audio_file = "pertanyaan_ai.mp3"
    tts.save(audio_file)
    st.audio(audio_file, format="audio/mp3", autoplay=True)
  except Exception as e:
    st.warning(f"Gagal memutar audio: {e}")


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


# Inisialisasi state
if "step" not in st.session_state:
  st.session_state.step = 0
if "answers" not in st.session_state:
  st.session_state.answers = []
if "cv_uploaded" not in st.session_state:
  st.session_state.cv_uploaded = False
if "saved_to_sheet" not in st.session_state:
  st.session_state.saved_to_sheet = False

st.title("🤖 AI Interview Assistant (Suara, CV & Google Sheets)")

# Sidebar Konfigurasi Posisi
role = st.sidebar.selectbox(
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

st.sidebar.markdown("---")
st.sidebar.info(
    "Aplikasi otomatis menggunakan Groq AI (Llama 3.3), membacakan suara"
    " pertanyaan, dan merekap hasil ke Google Sheets."
)

# Tahap 1: Upload CV & Identitas
if not st.session_state.cv_uploaded:
  st.subheader("📁 Langkah 1: Masukkan Identitas & Unggah CV Kandidat")
  nama_input = st.text_input("Nama Lengkap Kandidat")
  uploaded_file = st.file_uploader("Unggah CV (Format PDF)", type=["pdf"])

  if st.button("Mulai Wawancara"):
    if not nama_input:
      st.warning("⚠️ Mohon masukkan nama lengkap kandidat terlebih dahulu.")
    elif uploaded_file is None:
      st.warning("⚠️ Mohon unggah file CV kandidat (PDF).")
    else:
      st.session_state.nama_kandidat = nama_input
      with st.spinner(
          "Membaca CV dan merancang pertanyaan khusus via Groq AI..."
      ):
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
                "Apa pencapaian terbesar dalam karier profesional Anda sejauh"
                " ini?",
            ]

          st.session_state.generated_questions = questions_list[:3]
          st.session_state.cv_uploaded = True
          st.success("CV berhasil dianalisis! Pertanyaan wawancara siap.")
          st.rerun()
        except Exception as e:
          st.error(f"Gagal memproses CV: {e}")

else:
  # Tahap 2: Sesi Tanya Jawab
  current_questions = st.session_state.generated_questions

  if st.session_state.step < len(current_questions):
    q = current_questions[st.session_state.step]
    st.subheader(
        f"Pertanyaan {st.session_state.step + 1} dari {len(current_questions)}"
        f" untuk: **{st.session_state.nama_kandidat}**"
    )
    st.markdown(f"> **{q}**")

    # Putar suara pertanyaan AI
    putar_suara_ai(q)

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
    # Tahap 3: Evaluasi Akhir & Simpan ke Google Sheets
    st.success(
        "🎉 Wawancara Selesai! Groq AI sedang menyusun hasil evaluasi akhir..."
    )

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

    with st.spinner("Menghitung skor dan menyimpan data ke Google Sheets..."):
      try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_eval}],
            temperature=0.3,
        )
        evaluation = response.choices[0].message.content

        st.subheader("📊 Hasil Evaluasi & Skor AI")
        st.markdown(evaluation)

        # Simpan otomatis ke Google Sheets sekali saja
        if not st.session_state.saved_to_sheet:
          sukses = simpan_ke_googlesheet(
              nama=st.session_state.nama_kandidat,
              posisi=role,
              skor="Cek Detail",
              rekomendasi="Review",
              evaluasi=evaluation,
          )
          if sukses:
            st.info("📌 Hasil wawancara berhasil dicatat ke Google Sheets!")
            st.session_state.saved_to_sheet = True

      except Exception as e:
        st.error(f"Terjadi kesalahan saat evaluasi atau penyimpanan: {e}")

    # Tombol Reset
    if st.button("Mulai Wawancara Baru (Kandidat Lain)"):
      st.session_state.clear()
      st.rerun()
