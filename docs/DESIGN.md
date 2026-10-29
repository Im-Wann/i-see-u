# System Design & Technical Specifications: i-see-u (TheftTrace AI)

Dokumen ini mendetailkan prinsip arsitektur tingkat rendah, mitigasi performa, penanganan memori, dan kontrak komputasi spasial untuk sistem deteksi anomali/pencurian CCTV offline.

---

## 1. Arsitektur Komputasi 3-Layer

```text
[Layer 1: Ingestion & Fast Filter (OpenCV)]
  - cv2.VideoCapture Sequential Stream (RAM ~6MB)
  - Cheap Motion Gating (cv2.absdiff): Perubahan pixel < 1% -> Skip YOLO
  - Downsampling FPS: 25/30 FPS -> 2-4 FPS

[Layer 2: Inference & Multi-Object Tracking (YOLO + ByteTrack)]
  - Model: Ultralytics YOLOv8 / YOLO11
  - Deteksi: person, motorcycle, car, bicycle, helmet, backpack
  - Output: Bounding box piksel absolut + Track ID unik

[Layer 3: Spatial Engine, Invariants & Persistence]
  - Normalisasi Koordinat Spasial
  - Rule Checker: Theft Removal, Loitering, Zone Intrusion
  - State TTL Garbage Collector (Anti Memory Leak)
  - Debounce / Incident Deduplicator
  - Immediate CSV Flush & Snapshot Writer
```

---

## 2. Pencegahan Masalah Teknis Utama (Design Mitigations)

### A. Desain Normalisasi Koordinat Spasial (Resolution Agnostic)
- **Tantangan:** CCTV memiliki resolusi beragam (720p, 1080p, 4K). Threshold jarak dalam piksel absolut akan rusak bila resolusi berubah.
- **Solusi Desain:**
  - Modul deteksi mengeluarkan koordinat absolut `[x1, y1, x2, y2]`.
  - Modul aturan (`rules.py`) menghitung centroid $(c_x, c_y)$ dan menormalisasi jarak terhadap diagonal frame $D_{\text{frame}} = \sqrt{W^2 + H^2}$:
    $$d_{\text{norm}} = \frac{\sqrt{(c_{x1} - c_{x2})^2 + (c_{y1} - c_{y2})^2}}{\sqrt{W^2 + H^2}}$$
  - Threshold jarak ditetapkan dalam rasio (misal: radius pencurian $d_{\text{norm}} > 0.15$).

### B. State Expiry & Garbage Collection (Pencegahan Memory Leak)
- **Tantangan:** Video 24 jam dapat menghasilkan puluhan ribu `track_id` sementara. Menyimpan riwayat semua ID akan menghabiskan memori RAM secara perlahan (*memory leak*).
- **Solusi Desain:**
  - Terapkan mekanisme TTL (*Time-To-Live*) di modul `rules.py`.
  - Jika objek tertentu tidak terdeteksi lagi selama $> N$ frame berturut-turut (misal: $> 30\text{ detik}$), entri objek tersebut otomatis dihapus (`del state[track_id]`).

### C. Strategi Debouncing & Deduplikasi Insiden
- **Tantangan:** Aksi kejahatan berlangsung dalam rentang waktu beberapa detik (misal: 10 detik). Tanpa filter, sistem akan mencatat puluhan insiden duplikat untuk 1 peristiwa yang sama.
- **Solusi Desain:**
  - Saat suatu entitas objek memicu `THEFT_REMOVAL`, set status `is_alerted = True`.
  - Sistem hanya menghasilkan **1 baris CSV dan 1 frame snapshot bukti terbaik** per entitas kejadian.

### D. Graceful Termination & Data Flush (Ctrl+C Safety)
- **Tantangan:** Pembatalan pemindaian di tengah proses bisa menyebabkan file CSV korup atau tidak tertutup dengan benar.
- **Solusi Desain:**
  - Penulisan berkas CSV menggunakan `file.flush()` seketika pada tiap baris.
  - Modul `main.py` membungkus loop pemindaian dengan blok `try...except KeyboardInterrupt...finally` untuk memastikan sumber daya kamera dilepas dan laporan parsial tercetak rapi.

### E. Interactive HTML Dashboard Viewer (`report.html`)
- **Tantangan:** Pengguna membutuhkan cara visual yang mudah untuk meninjau kejadian tanpa harus mencari manual di file video 24 jam.
- **Solusi Desain:**
  - Di akhir pemindaian, modul `reporter.py` merender file **`report.html`** tunggal berbasis **Tailwind CSS via CDN**.
  - **Arsitektur Dashboard:**
    - Kolom / Panel Utama: Pemutar video HTML5 lokal (`<video controls>`).
    - Kolom / Panel Samping: Tabel daftar insiden interaktif (timestamp, jenis kejahatan, thumbnail snapshot).
    - Interaksi Klik & Play (JS Client-side): Saat baris tabel atau stempel waktu diklik, JavaScript mengeksekusi `video.currentTime = seconds` dan otomatis memanggil `video.play()`, membuat browser langsung melompat ke detik kejadian tanpa server backend.

---

## 3. Format Data Kontrak Antar Modul

### Deteksi Objek (Output `tracker.py` -> Input `rules.py`):
```python
[
    {
        "track_id": 12,
        "class_name": "helmet",
        "bbox": [120, 240, 180, 300],  # [x1, y1, x2, y2]
        "centroid": (150, 270)          # (cx, cy)
    }
]
```

### Event Insiden (Output `rules.py` -> Input `reporter.py`):
```python
[
    {
        "timestamp": "02:14:05",
        "event_type": "THEFT_REMOVAL",
        "target_object": "helmet",
        "target_id": 12,
        "person_id": 8,
        "bbox_highlight": [120, 240, 180, 300]
    }
]
```
