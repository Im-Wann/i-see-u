python
import cv2
import numpy as np

def stream_frames(video_source: str, sample_fps: int = 3):
    """
    Generator pembaca video berbasis OpenCV cv2.VideoCapture dengan cheap motion gating
    dan frame sampling.
    """
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise ValueError(f"Tidak dapat membuka sumber video: {video_source}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 25.0

    step = max(1, round(fps / sample_fps))
    frame_idx = 0
    prev_gray = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_gray is None:
                has_motion = True
            else:
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                changed_pixels = cv2.countNonZero(thresh)
                total_pixels = gray.shape[0] * gray.shape[1]
                motion_ratio = changed_pixels / total_pixels if total_pixels > 0 else 0
                has_motion = motion_ratio >= 0.01

            prev_gray = gray

            if frame_idx % step == 0:
                total_seconds = frame_idx / fps
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                yield frame_idx, timestamp_str, frame, has_motion

            frame_idx += 1

    finally:
        cap.release()
