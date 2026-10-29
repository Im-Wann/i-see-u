import cv2
from ultralytics import YOLO

class ObjectTracker:
    def __init__(self, model_path: str = "yolov8n.pt", conf_thresh: float = 0.35):
        self.model = YOLO(model_path)
        self.conf_thresh = conf_thresh
        # Target classes relevant to i-see-u theft detection
        self.target_classes = {"person", "motorcycle", "car", "bicycle", "helmet", "backpack"}

    def update(self, frame) -> list[dict]:
        """
        Runs YOLO tracking on the frame and returns filtered detected objects with track IDs and centroids.
        
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
        results = self.model.track(source=frame, persist=True, conf=self.conf_thresh, verbose=False)
        detections = []
        
        if not results or results[0].boxes is None:
            return detections
            
        boxes = results[0].boxes
        for box in boxes:
            if box.id is None:
                continue
                
            track_id = int(box.id.item())
            cls_idx = int(box.cls.item())
            class_name = self.model.names.get(cls_idx, str(cls_idx))
            
            if class_name not in self.target_classes:
                continue
                
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = map(int, xyxy)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            detections.append({
                "track_id": track_id,
                "class_name": class_name,
                "bbox": [x1, y1, x2, y2],
                "centroid": (cx, cy)
            })
            
        return detections
