import numpy as np

# Mock data interface untuk memungkinkan rekan tim (Yeskiel & Temi) 
# melakukan unit test tanpa harus menunggu streamer.py atau tracker.py selesai.

MOCK_FRAME = np.zeros((720, 1280, 3), dtype=np.uint8)

MOCK_DETECTIONS = [
    {
        "track_id": 1,
        "class_name": "motorcycle",
        "bbox": [300, 400, 500, 650],
        "centroid": (400, 525)
    },
    {
        "track_id": 2,
        "class_name": "helmet",
        "bbox": [320, 410, 360, 450],
        "centroid": (340, 430)
    },
    {
        "track_id": 8,
        "class_name": "person",
        "bbox": [600, 350, 750, 700],
        "centroid": (675, 525)
    }
]

MOCK_INCIDENT = {
    "timestamp": "02:14:05",
    "event_type": "THEFT_REMOVAL",
    "target_object": "helmet",
    "target_id": 2,
    "person_id": 8,
    "bbox_highlight": [320, 410, 360, 450]
}
