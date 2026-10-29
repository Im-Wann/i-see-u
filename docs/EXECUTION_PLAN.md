# Project Execution Plan: i-see-u (TheftTrace AI)
Panduan Pembagian Kerja Tim & Alur Dependensi (Anti-Tabrakan)

---

## 1. Prinsip Utama: Arsitektur Berbasis Kontrak (Contract-First)

Agar pekerjaan 5 orang (Iwan, Zaza, Ita, Yeskiel, Temi) berjalan paralel tanpa saling menunggu dan tanpa konflik git (*zero merge conflicts*):
1. **Satu Orang Satu Berkas:** Setiap anggota memiliki berkas `.py` sendiri. Dilarang mengubah berkas milik rekan lain.
2. **Mock Data First:** Anggota yang pekerjaannya bergantung pada tahap sebelumnya dapat menggunakan data tiruan (*mock data*) sejak Hari ke-1 tanpa menunggu kode rekan selesai.
3. **Branch Git Terisolasi:** Setiap anggota melakukan commit hanya pada branch fiturnya masing-masing.

---

## 2. Struktur Repositori & Kepemilikan Berkas

```text
i-see-u/
├── README.md            [Panduan Utama Repository]
├── docs/
│   ├── PRD.md           [Spesifikasi Kebutuhan Produk]
│   ├── DESIGN.md        [Desain Teknis & Mitigasi Masalah]
│   └── EXECUTION_PLAN.md[Panduan Pembagian Kerja Tim]
├── main.py              [Pemilik: Iwan     - Paket 1 (Tech Lead & Core Orchestrator)]
├── streamer.py          [Pemilik: Zaza     - Paket 2]
├── tracker.py           [Pemilik: Ita      - Paket 3]
├── rules.py             [Pemilik: Yeskiel  - Paket 4]
├── reporter.py          [Pemilik: Temi     - Paket 5]
├── requirements.txt     [Pemilik: Iwan     - Paket 1]
└── tests/
    ├── mock_data.py     [Pemilik: Iwan     - Paket 1 (Kontrak Data Bersama)]
    └── test_pipeline.py [Pemilik: Iwan     - Paket 1]
```

---

## 3. Matriks Alur Dependensi Tugas (Task Dependency Graph)

```text
[Task 0: Iwan (Paket 1)]
 Setup Repo, CLI Parser (main.py), & Mock Data Interface
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
[Task 1: Zaza]              [Task 2: Ita]
 Paket 2 (streamer.py)       Paket 3 (tracker.py)
       │                           │
       └─────────────┬─────────────┘
                     ▼
              [Task 3: Yeskiel]
               Paket 4 (rules.py)
               (Konsumsi output Paket 3)
                     │
                     ▼
              [Task 4: Temi]
               Paket 5 (reporter.py)
               (Konsumsi output Paket 2 & 4)
                     │
                     ▼
[Task 5: Iwan (Paket 1)]
 Integrasi Pipeline, Error Handling, Benchmarking, & Pengujian Menyeluruh
```

---

## 4. Rincian Tugas, Input/Output, & Cara Kerja Tanpa Nabrak

### Task 0 & 5: Paket 1 - Project Architecture, Core CLI & System Integration
- **Penanggung Jawab:** Iwan (Tech Lead / Core Orchestrator)
- **Berkas Kerja:** `main.py`, `requirements.txt`, `tests/mock_data.py`, `tests/test_pipeline.py`
- **Branch Git:** `main` (Protected) dan `feature/paket-1-core`
- **Rincian Pekerjaan Konkret:**
  1. Siapkan dependency proyek di `requirements.txt`.
  2. Tulis berkas `tests/mock_data.py` berisi data tiruan agar Yeskiel dan Temi bisa langsung ngoding tanpa menunggu Zaza dan Ita.
  3. Buat kerangka CLI argumen parser di `main.py` menggunakan `argparse` (`--video`, `--input-dir`, `--model`, `--output`, `--conf`, `--fps`).
  4. Lakukan review Pull Request (PR) dari 4 branch anggota.
  5. Sambungkan seluruh modul di `main.py` dengan lapisan *fault-tolerance* (graceful exit saat video putus / error / Ctrl+C).

---

### Task 1: Paket 2 - Video Ingestion & Motion Gating
- **Penanggung Jawab:** Zaza
- **Berkas Kerja:** `streamer.py`
- **Branch Git:** `feature/paket-2-streamer`
- **Dependensi:** Tidak bergantung pada siapa pun (dapat langsung mulai dari Hari ke-1).
- **Rincian Pekerjaan:**
  1. Buat generator pembaca video berbasis OpenCV `cv2.VideoCapture`.
  2. Implementasikan parameter sampling FPS (default: 3 FPS, skip frame berlebih).
  3. Implementasikan *Cheap Motion Gate* menggunakan `cv2.absdiff` antar frame grayscale. Jika selisih piksel $< 1\%$, set `has_motion = False`.
  4. Hitung stempel waktu persis: `frame_idx / fps` dikonversi ke format teks `HH:MM:SS`.
- **Kontrak Fungsi Wajib (Jangan Diubah):**
  ```python
  def stream_frames(video_source: str, sample_fps: int = 3):
      """
      Yields:
          frame_idx (int): Nomor indeks frame asli video.
          timestamp_str (str): Format 'HH:MM:SS'.
          frame (np.ndarray): Frame citra BGR OpenCV.
          has_motion (bool): True jika ada perubahan piksel signifikan.
      """
  ```

---

### Task 2: Paket 3 - Object Detection & Tracking
- **Penanggung Jawab:** Ita
- **Berkas Kerja:** `tracker.py`
- **Branch Git:** `feature/paket-3-tracker`
- **Dependensi:** Tidak bergantung pada kode Zaza. Ita cukup menguji kodenya menggunakan 1 citra dummy (`cv2.imread`) atau video lokal pendek.
- **Rincian Pekerjaan:**
  1. Muat model YOLO menggunakan modul Ultralytics (`from ultralytics import YOLO`).
  2. Jalankan tracking native ByteTrack: `model.track(source=frame, persist=True)`.
  3. Filter kelas relevan: `person`, `motorcycle`, `car`, `bicycle`, `helmet`, `backpack`.
  4. Ekstrak koordinat bounding box `[x1, y1, x2, y2]`, hitung titik tengah (centroid) `(cx, cy)`, dan simpan `track_id`.
- **Kontrak Kelas Wajib (Jangan Diubah):**
  ```python
  class ObjectTracker:
      def __init__(self, model_path: str = "yolov8n.pt", conf_thresh: float = 0.35): ...
      def update(self, frame) -> list[dict]:
          """
          Returns:
          [
              {
                  "track_id": 12,
                  "class_name": "motorcycle",
                  "bbox": [100, 200, 300, 450],
                  "centroid": (200, 325)
              }
          ]
          """
  ```

---

### Task 3: Paket 4 - Spatial Engine & Crime Rules
- **Penanggung Jawab:** Yeskiel
- **Berkas Kerja:** `rules.py`
- **Branch Git:** `feature/paket-4-rules`
- **Dependensi:** Logika bergantung pada list deteksi (output Paket 3). Yeskiel menggunakan `mock_data.py` untuk mengetes aturan logikanya tanpa menunggu Ita.
- **Rincian Pekerjaan:**
  1. Buat pemetaan penambatan objek: tautkan `helmet` / `backpack` ke `motorcycle` terdekat saat posisi diam.
  2. Implementasikan evaluasi 3 aturan:
     - **THEFT_REMOVAL:** Jarak properti ke motor bertambah $> D_{\text{theft}}$ bersamaan dengan orang yang menjauh dari motor statis.
     - **LOITERING:** `person_id` menetap di koordinat serupa selama $> T_{\text{loiter}}$ detik.
     - **INTRUSION:** Titik centroid `person` berada di dalam polygon zona terlarang pada jam tertentu.
  3. Implementasikan TTL cleaner untuk membersihkan track ID yang sudah keluar dari kamera (cegah memory leak).
- **Kontrak Kelas Wajib (Jangan Diubah):**
  ```python
  class CrimeRuleEvaluator:
      def __init__(self, config: dict = None): ...
      def evaluate(self, detections: list[dict], timestamp_str: str) -> list[dict]:
          """
          Returns:
          [
              {
                  "timestamp": "02:14:05",
                  "event_type": "THEFT_REMOVAL",
                  "target_object": "helmet",
                  "target_id": 12,
                  "person_id": 8,
                  "bbox_highlight": [120, 210, 180, 270]
              }
          ]
          """
  ```

---

### Task 4: Paket 5 - Incident Logger, Snapshot & CLI Reporter
- **Penanggung Jawab:** Temi
- **Berkas Kerja:** `reporter.py`
- **Branch Git:** `feature/paket-5-reporter`
- **Dependensi:** Logika bergantung pada event insiden (output Paket 4) dan citra frame (output Paket 2). Temi menggunakan event tiruan dari `mock_data.py` tanpa menunggu Yeskiel dan Zaza.
- **Rincian Pekerjaan:**
  1. Inisialisasi folder output: `hasil_scan/` dan `hasil_scan/snapshots/`.
  2. Buka berkas `incidents.csv` dengan header standar.
  3. Fungsi snapshot: salin frame, gambar bounding box merah (`cv2.rectangle`) pada objek pelaku/target, simpan sebagai `.jpg`.
  4. Lakukan penulisan baris CSV dan panggil `file.flush()` seketika (*immediate write*).
  5. Kelola progress bar visual terminal menggunakan library `tqdm`.
- **Kontrak Kelas Wajib (Jangan Diubah):**
  ```python
  class IncidentReporter:
      def __init__(self, output_dir: str = "./hasil_scan", total_frames: int = 0): ...
      def record_incident(self, incident: dict, frame) -> str: ...
      def update_progress(self, current_frame_idx: int): ...
      def finish_summary(self): ...
  ```

---

## 6. Aturan Git Workflow: Branching, Commit, & Pull Request

Untuk menjaga stabilitas repositori dan mencegah konflik kode (*merge conflict*), seluruh anggota tim wajib mematuhi aturan Git berikut:

### A. Penamaan Branch Wajib (Branch Naming Convention)
Setiap anggota tim dilarang bekerja atau melakukan commit langsung di branch `main`. Buat branch baru dari `main` sesuai dengan modul tugas masing-masing:
- **Iwan (Paket 1):** `feature/paket-1-core`
- **Zaza (Paket 2):** `feature/paket-2-streamer`
- **Ita (Paket 3):** `feature/paket-3-tracker`
- **Yeskiel (Paket 4):** `feature/paket-4-rules`
- **Temi (Paket 5):** `feature/paket-5-reporter`

### B. Format Pesan Commit (Conventional Commits)
Gunakan awalan konvensional yang jelas pada setiap pesan commit agar riwayat perubahan mudah dibaca:
- `feat: [deskripsi]` — penambahan fungsi atau modul baru (contoh: `feat: implement cheap motion gating in streamer.py`)
- `fix: [deskripsi]` — perbaikan bug atau error
- `docs: [deskripsi]` — pembaruan dokumentasi
- `test: [deskripsi]` — penambahan atau penyesuaian skrip uji

### C. Alur Pull Request (PR) & Code Review
1. Setelah kode di branch masing-masing selesai, lakukan *push* ke remote repository:
   ```bash
   git push origin feature/paket-X-nama-anda
   ```
2. Buka halaman GitHub repository **i-see-u** dan buat **Pull Request (PR)** dari branch fitur anda ke branch `main`.
3. **Iwan (Tech Lead)** akan meninjau (*review*) dan melakukan *merge* setelah kode dipastikan memenuhi kontrak antarmuka. Dilarang melakukan *force push* atau *merge* mandiri ke `main`.
