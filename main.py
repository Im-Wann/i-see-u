import argparse
import sys
import os
import cv2

from streamer import stream_frames
from tracker import ObjectTracker
from rules import CrimeRuleEvaluator
from reporter import IncidentReporter

def get_video_files(source_path: str) -> list[str]:
    """Mengembalikan daftar path file video jika source adalah direktori atau file tunggal."""
    if os.path.isfile(source_path):
        return [source_path]
    
    if os.path.isdir(source_path):
        supported_exts = {".mp4", ".avi", ".mkv", ".mov"}
        files = []
        for f in sorted(os.listdir(source_path)):
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_exts:
                files.append(os.path.join(source_path, f))
        return files
        
    return []

def main():
    parser = argparse.ArgumentParser(description="i-see-u: CCTV Theft & Anomaly Event Indexer")
    parser.add_argument("--video", type=str, help="Path ke berkas video CCTV tunggal")
    parser.add_argument("--input-dir", type=str, help="Path ke folder berisi segmen video CCTV")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Path bobot model YOLO")
    parser.add_argument("--output", type=str, default="./hasil_scan", help="Direktori penyimpanan hasil output dan snapshot")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold deteksi YOLO")
    parser.add_argument("--fps", type=int, default=3, help="Target sampling FPS")
    
    args = parser.parse_args()

    raw_source = args.video or args.input_dir
    if not raw_source:
        print("[ERROR] Harap berikan argumen --video <path> atau --input-dir <path>.")
        sys.exit(1)

    video_files = get_video_files(raw_source)
    if not video_files:
        print(f"[ERROR] Berkas video tidak ditemukan pada: {raw_source}")
        sys.exit(1)

    print(f"[INFO] Memulai TheftTrace AI (i-see-u)")
    print(f"[INFO] Target: {len(video_files)} berkas video")
    print(f"[INFO] Output direktori: {args.output}")

    # Hitung total frames yang akan diproses (setelah downsampling FPS) untuk progress bar
    total_frames = 0
    for vf in video_files:
        cap = cv2.VideoCapture(vf)
        if cap.isOpened():
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or fps != fps:
                fps = 25.0
            step = max(1, round(fps / args.fps))
            total_frames += fc // step
            cap.release()

    try:
        tracker = ObjectTracker(model_path=args.model, conf_thresh=args.conf)
        evaluator = CrimeRuleEvaluator()
        reporter = IncidentReporter(output_dir=args.output, total_frames=total_frames)

        for vf in video_files:
            print(f"\n[INFO] Memindai berkas: {os.path.basename(vf)}")
            for frame_idx, timestamp_str, frame, has_motion in stream_frames(vf, sample_fps=args.fps):
                reporter.update_progress(frame_idx)
                
                # Cheap Motion Gating: Lewati jika tidak ada pergerakan piksel signifikan
                if not has_motion:
                    continue

                detections = tracker.update(frame)
                incidents = evaluator.evaluate(detections, timestamp_str)

                for inc in incidents:
                    reporter.record_incident(inc, frame)

        reporter.finish_summary()

    except KeyboardInterrupt:
        print("\n[INFO] Pemindaian dihentikan oleh pengguna (Ctrl+C). Menyimpan progress terakhir...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Terjadi kesalahan sistem pada pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
