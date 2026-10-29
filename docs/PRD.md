# Product Requirement Document (PRD)
# TheftTrace AI (i-see-u) - CCTV Theft & Anomaly Event Indexer

## 1. Overview & Goal
Sistem command-line interface (CLI) berbasis computer vision untuk memindai berkas rekaman video CCTV berdurasi panjang secara offline/batch. Sistem mendeteksi indikasi kejahatan pencurian dan anomali (pencurian kendaraan/barang, pemindahan helm, loitering/mondar-mandir mencurigakan, dan penyusupan area terlarang/intrusion), mengindeks timestamp kejadian (`HH:MM:SS`), serta menyimpan citra bukti snapshot secara otomatis.

**Tujuan:** Mengeliminasi peninjauan manual video rekaman berjam-jam dengan mengekstrak menit-menit kritis terjadinya tindak kejahatan secara terstruktur, cepat, dan hemat sumber daya komputasi.

---

## 2. Scope & Target Deteksi

### In-Scope (MVP)
- **Zero-Wait Ingestion:** Pembacaan berkas langsung secara sequential stream via OpenCV dari disk tanpa duplikasi file ke memori (RAM konstan ~6 MB per frame).
- **Batch / Segment Support:** Mendukung pemrosesan satu berkas video (`--video`) maupun folder rekaman bersegmen (`--input-dir`).
- **Motion Pre-filtering (Gating):** Evaluasi perbedaan piksel (frame differencing) untuk melewati frame statis/kosong tanpa memicu inferensi model AI (efisiensi 70-80% pada rekaman malam).
- **Frame Sampling:** Pemrosesan 2–4 FPS dari video sumber 25-30 FPS.
- **Deteksi Objek Multi-Kelas:** Mendeteksi `person`, `motorcycle`, `car`, `bicycle`, `helmet`, dan `backpack` menggunakan YOLO.
- **Pelacakan Multi-Objek:** Mempertahankan identitas konsisten menggunakan ByteTrack bawaan Ultralytics.
- **Mesin Aturan Anomali (Multi-Rule Crime Engine):**
  1. *Theft / Removal of Property:* Pemindahan helm, motor, sepeda, atau tas dari posisi awal oleh orang yang menjauh.
  2. *Suspicious Loitering:* Seseorang berdiam/berputar-putar di area pantauan melampaui batas waktu wajar.
  3. *Zone Intrusion:* Seseorang memasuki batas polygon terlarang pada jam operasional tertentu.
- **Live Output Streaming & Interactive HTML Report:** Pencatatan langsung per insiden ke `incidents.csv`, terminal, penyimpanan snapshot `.jpg`, serta pembuatan berkas **`report.html` (Dashboard Interaktif berbasis Tailwind CSS)** yang memungkinkan pengguna mengeklik timestamp untuk langsung melompat (*seek & play*) ke detik kejadian pada pemutar video lokal.
- **Live Progress Reporting:** Indikator visual progres (`tqdm`) dengan persentase, FPS pemrosesan, dan estimasi selesai (ETA).

### Out-of-Scope
- Antarmuka GUI atau web dashboard.
- Pengenalan wajah (Face Recognition) dan plat nomor kendaraan (ANPR).
- Integrasi alarm fisik/sirine perangkat keras.
- Kamera bergerak (PTZ auto-pan).

---

## 3. Invariants & Detection Logic

Sistem menegakkan 4 invarian deteksi:

1. **Property Anchor Invariant (Kondisi Terikat):**
   Objek properti (helm/tas) yang berjarak dekat dengan motor atau berada di posisi statis selama $\ge N$ frame dianggap sebagai aset tertambat:
   $$\text{Distance}(C_{\text{property}}, C_{\text{anchor}}) \le D_{\text{park}}$$

2. **Authorized Departure Invariant (Pelepasan Sah):**
   Jika properti dipindahkan, tetapi `person` menaiki kendaraan dan kendaraan bergerak bersama orang tersebut dalam jendela toleransi ($T_{\text{grace}}$), status dinyatakan normal/valid (bukan insiden).

3. **Theft Removal Invariant (Pencurian Properti):**
   Kejadian dicatat sebagai insiden pencurian jika properti berpindah bersama orang, aset asal tertinggal statis, dan orang tersebut menjauh melebihi radius aman ($R_{\text{safe}}$) setelah melewati batas waktu toleransi ($T_{\text{grace}} \approx 5\text{--}10\text{ detik}$).

4. **Loitering & Intrusion Invariants (Gelagat & Penyusupan):**
   - *Loitering:* `person` berada di area pantauan statis selama durasi $> T_{\text{loiter}}$ (misal: $> 45\text{ detik}$) dengan perpindahan koordinat minimal.
   - *Intrusion:* Bounding box `person` memotong polygon zona sensitif pada rentang jam terlarang.

---

## 4. Pipeline Architecture & Modular Boundary

```text
[Paket 2: Video Streamer] (Zaza)
      │ Mengeluarkan: (frame_idx, timestamp_sec, frame_bgr)
      ▼
[Paket 3: Detection & Tracking] (Ita)
      │ Mengeluarkan: List[TrackObject(id, cls, bbox, centroid)]
      ▼
[Paket 4: Spatial & Crime Rules] (Yeskiel)
      │ Mengeluarkan: IncidentEvent(timestamp, type, target_id, person_id, frame)
      ▼
[Paket 5: Storage & Reporting] (Temi)
      │ Menghasilkan: incidents.csv, snapshots/*.jpg, progress console
```

---

## 5. Functional Requirements

| ID | Modul | Deskripsi |
| :--- | :--- | :--- |
| **FR-01** | CLI & Orchestrator | File `main.py` menggabungkan modul Paket 2, 3, 4, dan 5 ke dalam pipeline sekuensial. |
| **FR-02** | Paket 2 (Streamer) | Stream video zero-copy dengan memori konstan, frame sampling, dan deteksi motion differencing. |
| **FR-03** | Paket 3 (Tracker) | Inferensi YOLO + ByteTrack menghasilkan track ID konsisten per entitas target. |
| **FR-04** | Paket 4 (Rules) | Evaluasi spasial-temporal untuk mendeteksi pencurian barang, mondar-mandir, dan pelanggaran zona. |
| **FR-05** | Paket 5 (Reporter) | Penyimpanan snapshot bukti visual dan penulisan berkas CSV real-time tanpa delay. |
| **FR-06** | Integrasi | Deduplikasi kejadian agar satu insiden yang sedang berlangsung tidak dicatat berulang kali. |

---

## 6. Non-Functional Requirements & Performance

- **Memory Footprint:** Konsumsi RAM stabil $< 500\text{ MB}$ sepanjang pemindaian berlangsung.
- **Throughput:** Kecepatan pemrosesan offline $5\times\text{--}10\times$ lebih cepat dari durasi asli video pada GPU standar.
- **Maintainability:** Modul terpisah secara tegas per file; tidak ada dependensi melingkar (*no circular imports*).
- **Fault Tolerance:** Melewati frame yang rusak tanpa menghentikan pemindaian keseluruhan.

---

## 7. Format Keluaran

### Berkas Log (`hasil_scan/incidents.csv`)
```csv
timestamp,event_type,target_object,target_id,person_id,snapshot_path
02:14:05,THEFT_REMOVAL,helmet,12,8,hasil_scan/snapshots/02_14_05.jpg
03:20:11,LOITERING,person,None,15,hasil_scan/snapshots/03_20_11.jpg
03:22:40,INTRUSION,person,None,15,hasil_scan/snapshots/03_22_40.jpg
```

### Tampilan Terminal
```text
Memulai pemindaian: parkir_malam_cam01.mp4 (Durasi: 24:00:00, FPS: 30)
Progres: [████████████░░░░░░░░░░░░] 48% | Frame 124000/2592000 | Speed: 145 FPS | ETA: 00:15:20

[ALERT - 02:14:05] THEFT: Helm #12 diambil oleh Person #8. Snapshot disimpan.
[ALERT - 03:20:11] LOITERING: Person #15 mondar-mandir di zona parkir.

============================================================
PEMINDAIAN SELESAI
Durasi Rekaman   : 24:00:00
Waktu Pemrosesan : 00:32:15 (Kecepatan rata-rata: ~44x real-time)
Total Insiden    : 2 Kejadian
Detail log tersimpan di: hasil_scan/incidents.csv
============================================================
```
