# i-see-u (TheftTrace AI)

Sistem *command-line interface* (CLI) cerdas berbasis Computer Vision untuk mendeteksi indikasi tindak pencurian dan anomali pada rekaman CCTV parkiran secara cepat dan efisien.

---

## 📁 Dokumentasi Proyek & Spesifikasi

- **[PRD (Product Requirement Document)](docs/PRD.md):** Spesifikasi teknis, invarian deteksi, arsitektur pipeline, dan format masukan/keluaran.
- **[System Architecture & Design](docs/DESIGN.md):** Detail desain sistem, mitigasi memory leak, normalisasi koordinat, dan strategi debouncing.
- **[Team Execution Plan](docs/EXECUTION_PLAN.md):** Pembagian kerja tim (Paket 1 - 5), kontrak fungsi antarmuka (API contract), alur dependensi tugas, dan panduan branch Git.

---

## 👥 Pembagian Paket Kerja Tim

| Paket | Penanggung Jawab | Berkas Modul | Tanggung Jawab Utama |
| :--- | :--- | :--- | :--- |
| **Paket 1** | **Iwan (Tech Lead)** | `main.py`, `tests/` | CLI Parser, Contract Gatekeeper, Pipeline Integration, & Fault-Tolerance |
| **Paket 2** | **Zaza** | `streamer.py` | Video Stream Ingestion, Frame Sampling (2-4 FPS), & Cheap Motion Gating |
| **Paket 3** | **Ita** | `tracker.py` | YOLOv8/YOLO11 Object Detection & ByteTrack Multi-Object Tracking |
| **Paket 4** | **Yeskiel** | `rules.py` | Spatial Engine, Property Binding, Theft/Loitering/Intrusion Invariant Evaluator |
| **Paket 5** | **Temi** | `reporter.py` | Real-time CSV Logger, Snapshot Evidence Saver, & Terminal Progress (`tqdm`) |

---

## 🚀 Alur Kerja Cepat (Quick Start)

```bash
# 1. Clone repository
git clone https://github.com/Im-Wann/i-see-u.git
cd i-see-u

# 2. Install dependensi
pip install -r requirements.txt

# 3. Jalankan pemindaian video CCTV
python main.py --video "path/to/cctv_recording.mp4" --output "./hasil_scan"
```
