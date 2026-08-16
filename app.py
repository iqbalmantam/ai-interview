import streamlit as st
import openai
import pandas as pd
from pypdf import PdfReader

# Konfigurasi Halaman
st.set_page_config(
    page_title="AI Video Interviewer - Dynamic CV-Based",
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
st.sidebar.info("Aplikasi ini membaca CV kandidat dan menghasilkan pertanyaan wawancara otomatis yang dipersonalisasi.")

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

# Tahap 1: Unggah CV & Generate Pertanyaan
if not st.session_state.cv_uploaded:
    st.subheader("📁 Langkah 1: Unggah CV Kandidat")
    uploaded_file = st.file_uploader("Unggah CV (Format PDF)", type=["pdf"])
    
    if uploaded_file is not None:
        if not api_key:
            st.warning("⚠️ Masukkan OpenAI API Key di sidebar terlebih dahulu untuk memproses CV.")
        else:
            with st.spinner("Membaca CV dan membuat pertanyaan khusus..."):
                try:
                    # Baca file PDF
                    reader = PdfReader(uploaded_file)
                    cv_text = ""
                    for page in reader.pages:
                        cv_text += page.extract_text()
                    
                    # Minta AI membuat 3 pertanyaan berdasarkan CV & Role
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
                    
                    # Ambil pertanyaan hasil generate AI
                    questions_text = response.choices[0].message.content.strip()
                    questions_list = [q.strip() for q in questions_text.split("\n") if q.strip()]
                    
                    # Pastikan minimal ada pertanyaan (fallback jika format meleset)
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
    # Tahap 2: Sesi Tanya Jawab Berdasarkan Pertanyaan Hasil AI
    current_questions = st.session_state.generated_questions
    
    if st.session_state.step < len(current_questions):
        q_idx = st.session_state.step
        st.subheader(f"Pertanyaan {q_idx + 1} dari {len(current_questions)} (Disesuaikan dari CV)")
        st.markdown(f"> **{current_questions[q_idx]}**")
        
        with st.form(key=f"form_{q_idx}"):
            user_response = st.text_area(
                "Ketik jawaban atau transkrip wawancara Anda:",
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
        # Tahap 3: Evaluasi Akhir
        st.success("🎉 Wawancara Selesai! AI sedang menyusun hasil evaluasi akhir...")
        
        transcript_text = ""
        for i, item in enumerate(st.session_state.answers):
            transcript_text += f"Pertanyaan {i+1}: {item['question']}\nJawaban: {item['answer']}\n\n"
            
        prompt_eval = f"""
        Bertindaklah sebagai Expert Recruiter. Analisis transkrip wawancara berikut untuk posisi {role} (berdasarkan CV kandidat):
        
        {transcript_text}
        
        Berikan penilaian dalam format berikut:
        1. Skor Keseluruhan (0-100)
        2. Analisis Kecocokan Berdasarkan CV & Jawaban
        3. Kekuatan Kandidat
        4. Area Perhatian / Kekurangan
        5. Rekomendasi Akhir (Lolos/Tidak Lolos)
        """
        
        with st.spinner("Menghitung skor dan rubrik penilaian..."):
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
                
            except Exception as e:
                st.error(f"Terjadi kesalahan saat evaluasi: {e}")
                
        # Tombol Reset
        if st.button("Mulai Wawancara Baru (Upload CV Lain)"):
            st.session_state.step = 0
            st.session_state.answers = []
            st.session_state.generated_questions = []
            st.session_state.cv_uploaded = False
            st.rerun()
