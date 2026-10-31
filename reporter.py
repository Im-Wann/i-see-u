import os
import csv
import cv2
from tqdm import tqdm
from datetime import datetime

class IncidentReporter:
    def __init__(self, output_dir: str = "./hasil_scan", total_frames: int = 0):
        self.output_dir = output_dir
        self.snapshots_dir = os.path.join(output_dir, "snapshots")
        os.makedirs(self.snapshots_dir, exist_ok=True)
        
        self.csv_path = os.path.join(output_dir, "incidents.csv")
        self.csv_file = open(self.csv_path, mode="w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header according to PRD / contract
        self.csv_writer.writerow([
            "timestamp", "event_type", "target_object", "target_id", "person_id", "snapshot_path"
        ])
        self.csv_file.flush()
        
        self.total_frames = total_frames
        self.pbar = tqdm(total=total_frames, desc="Scanning Video", unit="frame") if total_frames > 0 else None
        self.incidents_collected = []
        self.start_time = datetime.now()

    def update_progress(self, current_frame_idx: int):
        if self.pbar:
            if self.pbar.total == 0 and current_frame_idx > 0:
                # If total frames wasn't known upfront, update total or refresh
                pass
            self.pbar.update(1)

    def record_incident(self, incident: dict, frame) -> str:
        timestamp = incident.get("timestamp", "00:00:00")
        event_type = incident.get("event_type", "UNKNOWN")
        target_object = incident.get("target_object", "None")
        target_id = incident.get("target_id", "None")
        person_id = incident.get("person_id", "None")
        bbox = incident.get("bbox_highlight")

        # Draw snapshot with bounding box highlight
        snapshot_filename = f"{timestamp.replace(':', '_')}_{event_type}_{target_id}.jpg"
        snapshot_path = os.path.join(self.snapshots_dir, snapshot_filename)
        
        if frame is not None:
            annotated_frame = frame.copy()
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)
                # Draw red rectangle for highlight
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                label = f"{event_type} (T:{target_id}, P:{person_id})"
                cv2.putText(annotated_frame, label, (x1, max(y1 - 10, 10)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imwrite(snapshot_path, annotated_frame)

        relative_snapshot_path = os.path.join("snapshots", snapshot_filename)
        
        # Write to CSV immediately and flush
        self.csv_writer.writerow([
            timestamp, event_type, target_object, target_id, person_id, relative_snapshot_path
        ])
        self.csv_file.flush()

        # Collect for HTML report summary
        incident_record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "target_object": target_object,
            "target_id": target_id,
            "person_id": person_id,
            "snapshot_path": relative_snapshot_path.replace("\\", "/")
        }
        self.incidents_collected.append(incident_record)

        # Print alert to terminal
        print(f"\n[ALERT - {timestamp}] {event_type}: Object {target_object} (ID:{target_id}) with Person (ID:{person_id}). Snapshot saved.")
        return snapshot_path

    def finish_summary(self):
        if self.pbar:
            self.pbar.close()
        
        if not self.csv_file.closed:
            self.csv_file.close()

        elapsed = datetime.now() - self.start_time
        
        print("\n" + "="*60)
        print("PEMINDAIAN SELESAI")
        print(f"Waktu Pemrosesan : {str(elapsed).split('.')[0]}")
        print(f"Total Insiden    : {len(self.incidents_collected)} Kejadian")
        print(f"Detail log tersimpan di: {self.csv_path}")
        print("="*60)

        # Generate Interactive HTML Report (report.html) as per DESIGN.md
        self._generate_html_report()

    def _generate_html_report(self):
        html_path = os.path.join(self.output_dir, "report.html")
        
        # Build rows for incidents table
        rows_html = ""
        for inc in self.incidents_collected:
            # Convert timestamp HH:MM:SS to seconds for video seeking
            parts = inc["timestamp"].split(":")
            seconds = 0
            if len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                seconds = int(parts[0]) * 60 + float(parts[1])
            
            rows_html += f"""
            <tr class="border-b hover:bg-gray-100 cursor-pointer transition" onclick="seekVideo({seconds})">
                <td class="py-3 px-4 font-mono text-sm text-red-600 font-bold">{inc['timestamp']}</td>
                <td class="py-3 px-4 font-semibold text-gray-800">{inc['event_type']}</td>
                <td class="py-3 px-4 text-gray-600">{inc['target_object']} (ID: {inc['target_id']})</td>
                <td class="py-3 px-4 text-gray-600">Person ID: {inc['person_id']}</td>
                <td class="py-3 px-4">
                    <img src="{inc['snapshot_path']}" alt="Snapshot" class="w-24 h-14 object-cover rounded shadow border">
                </td>
            </tr>
            """

        if not rows_html:
            rows_html = '<tr><td colspan="5" class="text-center py-6 text-gray-500">Tidak ada insiden terdeteksi selama pemindaian.</td></tr>'

        html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>i-see-u (TheftTrace AI) - Incident Report Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-gray-100 font-sans antialiased min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8 border-b border-gray-800 pb-4 flex justify-between items-center">
            <div>
                <h1 class="text-3xl font-extrabold text-red-500 tracking-wider">i-see-u / TheftTrace AI</h1>
                <p class="text-sm text-gray-400 mt-1">Laporan Pemindaian Anomali & Deteksi Pencurian CCTV</p>
            </div>
            <div class="text-right">
                <span class="inline-block bg-red-900 text-red-200 text-xs px-3 py-1 rounded-full uppercase font-bold tracking-wide">
                    {len(self.incidents_collected)} Insiden Tercatat
                </span>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Video Player Panel -->
            <div class="lg:col-span-1 bg-gray-800 p-4 rounded-xl shadow-2xl border border-gray-700">
                <h2 class="text-lg font-bold mb-3 text-gray-200">Pemutar Rekaman CCTV</h2>
                <div class="mb-4">
                    <input type="file" id="videoFilePicker" accept="video/*" class="block w-full text-sm text-gray-400
                        file:mr-4 file:py-2 file:px-4
                        file:rounded-lg file:border-0
                        file:text-sm file:font-semibold
                        file:bg-red-600 file:text-white
                        hover:file:bg-red-750 cursor-pointer">
                    <p class="text-xs text-gray-400 mt-1">Pilih berkas video CCTV lokal untuk diputar bersama laporan.</p>
                </div>
                <div class="aspect-video bg-black rounded-lg overflow-hidden relative flex items-center justify-center border border-gray-900">
                    <video id="cctvPlayer" controls class="w-full h-full object-contain">
                        Browser Anda tidak mendukung elemen video.
                    </video>
                </div>
            </div>

            <!-- Incident Table Panel -->
            <div class="lg:col-span-2 bg-gray-800 p-6 rounded-xl shadow-2xl border border-gray-700">
                <h2 class="text-lg font-bold mb-4 text-gray-200">Daftar Insiden & Bukti Snapshot</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left bg-white rounded-lg overflow-hidden text-gray-800 shadow">
                        <thead class="bg-gray-200 text-gray-700 uppercase text-xs tracking-wider">
                            <tr>
                                <th class="py-3 px-4">Timestamp</th>
                                <th class="py-3 px-4">Jenis Event</th>
                                <th class="py-3 px-4">Target Objek</th>
                                <th class="py-3 px-4">Pelaku</th>
                                <th class="py-3 px-4">Snapshot</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        const videoPlayer = document.getElementById('cctvPlayer');
        const videoFilePicker = document.getElementById('videoFilePicker');

        videoFilePicker.addEventListener('change', function(event) {{
            const file = event.target.files[0];
            if (file) {{
                const fileURL = URL.createObjectURL(file);
                videoPlayer.src = fileURL;
            }}
        }});

        function seekVideo(seconds) {{
            if (!videoPlayer.src || videoPlayer.src === window.location.href) {{
                alert('Silakan pilih berkas video CCTV lokal terlebih dahulu melalui tombol pemilih di panel kiri.');
                return;
            }}
            videoPlayer.currentTime = seconds;
            videoPlayer.play();
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}
    </script>
</body>
</html>
"""

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[INFO] Laporan HTML interaktif berhasil dirender di: {html_path}")
