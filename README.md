Kelompok L

Nama:
1. Ulvi Azzahra (164221109)
2. Syachazriel Riezqa Zahran (164231049)
3. Ario Rizky Muhammad (164231080)
4. Ryan Zufar Ahmadi (164231096)

APPs untuk mentranskrip wawancara medis 

Healthvoice - Medical Transcription & Analysis

Aplikasi web untuk transkripsi wawancara medis (Dokter & Pasien) dan analisis tanya-jawab otomatis menggunakan AI lokal (Whisper & Qwen).

PRASYARAT SISTEM
Pastikan Anda telah menginstal:
1. Python 3.10+
2. FFmpeg (Wajib untuk Whisper)
   - Download dari ffmpeg.org
   - Tambahkan ke PATH environment variable Windows.
3. CUDA Toolkit 12.x (Sangat disarankan untuk pengguna GPU NVIDIA agar proses cepat). Kalau memiliki gpu nvidia, kalau gpu yang lain atau hanya menggunakan cpu harus menyesuaikan kodenya.

INSTALASI LIBRARY
Buka terminal di folder proyek dan jalankan:

pip install -r backend/requirements.txt

Atau instal manual library utama:

pip install fastapi uvicorn sqlalchemy python-multipart python-docx
pip install openai-whisper
pip install sentence-transformers
pip install llama-cpp-python

Catatan untuk llama-cpp-python dengan GPU NVIDIA:
Jalankan perintah berikut agar GPU aktif:
set CMAKE_ARGS=-DGGML_CUDA=on
pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir

PERSIAPAN MODEL AI
Aplikasi ini menggunakan 3 model AI. Siapkan folder cache (Default: D:\hf_cache).

1. Whisper (Speech-to-Text)
   - Model: Medium
   - Cara: Otomatis didownload saat pertama kali jalan.
   - Manual: Download medium.pt dari OpenAI Whisper dan simpan di D:\hf_cache\medium.pt

2. Embedding (Pencarian Semantik)
   - Model: paraphrase-multilingual-MiniLM-L12-v2
   - Cara: Otomatis didownload via sentence-transformers saat pertama kali jalan.

3. LLM (Generasi Jawaban)
   - Model: Qwen 2.5 7B Instruct (Format GGUF, Kuantisasi Q4_K_M)
   - Link Download: Cari "Bartowski Qwen2.5-7B-Instruct-GGUF" di HuggingFace.
   - File yang didownload: Qwen2.5-7B-Instruct-Q4_K_M.gguf
   - Lokasi Simpan: Simpan file tersebut di D:\hf_cache\

Struktur folder cache yang diharapkan:
D:\hf_cache\
   - medium.pt
   - Qwen2.5-7B-Instruct-Q4_K_M.gguf

CARA MENJALANKAN APLIKASI
1. Pastikan semua library terinstal dan model siap.
2. Jalankan server backend:
   
   python backend/app.py

3. Tunggu sampai muncul pesan "HEALTHVOICE SERVER IS READY".
4. Buka browser dan akses http://localhost:8000

CARA PENGGUNAAN
1. Menu Transkrip: Upload file audio (.wav, .mp3) atau rekam langsung.
2. Tunggu Proses: Sistem akan memproses audio menjadi teks.
3. Menu Dashboard:
   - Lihat daftar file yang selesai.
   - Download Teks: Unduh hasil transkrip mentah.
   - Tanya Jawab (Q&A): Masukkan pertanyaan terkait transkrip.
   - Download Laporan: Unduh file Word berisi sesi tanya-jawab.

TROUBLESHOOTING
- Error "GPU Out of Memory": Tutup aplikasi lain yang menggunakan VRAM.
- Error "Context Limit": Sistem akan otomatis mencoba memendekkan konteks jika jawaban gagal dibuat.
- LLM Lambat: Pastikan llama-cpp-python terinstal dengan dukungan CUDA.
