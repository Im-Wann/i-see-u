"""
tests/test_rules.py - Unit Test untuk Paket 4 (rules.py)
Menggunakan kontrak data dari tests/mock_data.py dan skenario pengujian komprehensif.
"""

import unittest
from rules import CrimeRuleEvaluator
from tests.mock_data import MOCK_DETECTIONS, MOCK_INCIDENT


class TestCrimeRuleEvaluator(unittest.TestCase):

    def setUp(self):
        # Default evaluator untuk pengujian terisolasi
        self.evaluator = CrimeRuleEvaluator(config={
            "d_theft": 80.0,
            "max_mapping_distance": 150.0,
            "t_loiter": 30.0,
            "loiter_movement_tolerance": 40.0,
            "ttl_seconds": 15.0,
            "restricted_zones": [[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]],
            "restricted_hours": {"start": "22:00:00", "end": "05:00:00"}
        })

    def test_mock_incident_contract(self):
        """Memastikan format event yang dihasilkan rules.py sesuai dengan MOCK_INCIDENT milik tim."""
        evaluator = CrimeRuleEvaluator(config={"restricted_zones": []})

        # Frame 1: Objek sesuai MOCK_DETECTIONS (motor di 400,525 dan helm di 340,430 -> jarak ~112px, dekat motor)
        evaluator.evaluate(MOCK_DETECTIONS, "02:14:00")
        self.assertIn(2, evaluator.object_mappings, "Helm (id=2) harus terpetakan ke motor (id=1)")

        # Frame 2: Helm dibawa orang menjauh ke koordinat baru (jarak menjauh > Dtheft)
        moved_detections = [
            {"track_id": 1, "class_name": "motorcycle", "bbox": [300, 400, 500, 650], "centroid": (400, 525)},
            {"track_id": 2, "class_name": "helmet", "bbox": [320, 410, 360, 450], "centroid": (650, 520)},
            {"track_id": 8, "class_name": "person", "bbox": [600, 350, 750, 700], "centroid": (675, 525)}
        ]

        events = evaluator.evaluate(moved_detections, MOCK_INCIDENT["timestamp"])
        self.assertEqual(len(events), 1)

        event = events[0]
        # Validasi kecocokan kontrak dengan MOCK_INCIDENT
        self.assertEqual(event["timestamp"], MOCK_INCIDENT["timestamp"])
        self.assertEqual(event["event_type"], MOCK_INCIDENT["event_type"])
        self.assertEqual(event["target_object"], MOCK_INCIDENT["target_object"])
        self.assertEqual(event["target_id"], MOCK_INCIDENT["target_id"])
        self.assertEqual(event["person_id"], MOCK_INCIDENT["person_id"])
        self.assertEqual(event["bbox_highlight"], MOCK_INCIDENT["bbox_highlight"])

    def test_object_mapping_and_theft_removal(self):
        """Uji Aturan 1 (Mapping) dan Aturan 2 (Theft Removal) secara terpisah."""
        evaluator = CrimeRuleEvaluator(config={
            "d_theft": 80.0,
            "max_mapping_distance": 150.0,
            "restricted_zones": []
        })

        # Frame 1: Mapping saat motor diam
        f1 = [
            {"track_id": 10, "class_name": "motorcycle", "bbox": [100, 100, 200, 200], "centroid": (150, 150)},
            {"track_id": 20, "class_name": "helmet", "bbox": [120, 120, 160, 160], "centroid": (140, 140)}
        ]
        events_f1 = evaluator.evaluate(f1, "10:00:00")
        self.assertEqual(len(events_f1), 0)
        self.assertIn(20, evaluator.object_mappings)
        self.assertEqual(evaluator.object_mappings[20]["motorcycle_id"], 10)

        # Frame 2: Helm dijauhkan oleh orang
        f2 = [
            {"track_id": 10, "class_name": "motorcycle", "bbox": [100, 100, 200, 200], "centroid": (150, 150)},
            {"track_id": 20, "class_name": "helmet", "bbox": [280, 280, 320, 320], "centroid": (300, 300)},
            {"track_id": 30, "class_name": "person", "bbox": [270, 260, 330, 380], "centroid": (300, 320)}
        ]
        events_f2 = evaluator.evaluate(f2, "10:00:05")
        self.assertEqual(len(events_f2), 1)
        self.assertEqual(events_f2[0]["event_type"], "THEFT_REMOVAL")
        self.assertEqual(events_f2[0]["target_id"], 20)
        self.assertEqual(events_f2[0]["person_id"], 30)

    def test_loitering(self):
        """Uji Aturan 3 (Loitering) secara terpisah."""
        evaluator = CrimeRuleEvaluator(config={
            "t_loiter": 30.0,
            "loiter_movement_tolerance": 40.0,
            "restricted_zones": []
        })

        p = [{"track_id": 7, "class_name": "person", "bbox": [200, 200, 250, 300], "centroid": (225, 250)}]

        # Detik ke-0
        self.assertEqual(evaluator.evaluate(p, "08:00:00"), [])

        # Detik ke-15 (masih di koordinat yang sama)
        self.assertEqual(evaluator.evaluate(p, "08:00:15"), [])

        # Detik ke-35 (> Tloiter 30s) -> harus memicu event LOITERING
        events = evaluator.evaluate(p, "08:00:35")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "LOITERING")
        self.assertEqual(events[0]["person_id"], 7)

        # Frame berikutnya (anti-duplicate) -> tidak boleh berulang
        self.assertEqual(evaluator.evaluate(p, "08:00:36"), [])

    def test_intrusion(self):
        """Uji Aturan 4 (Intrusion) pada jam terlarang vs jam aman."""
        evaluator = CrimeRuleEvaluator(config={
            "restricted_zones": [[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]],
            "restricted_hours": {"start": "22:00:00", "end": "05:00:00"}
        })

        inside_person = [{"track_id": 99, "class_name": "person", "bbox": [180, 180, 220, 260], "centroid": (200, 220)}]

        # 1. Jam terlarang (23:30:00) -> INTRUSION terdeteksi
        night_events = evaluator.evaluate(inside_person, "23:30:00")
        self.assertEqual(len(night_events), 1)
        self.assertEqual(night_events[0]["event_type"], "INTRUSION")
        self.assertEqual(night_events[0]["person_id"], 99)

        # 2. Jam siang aman (13:00:00) -> Tidak boleh terdeteksi
        day_evaluator = CrimeRuleEvaluator(config={
            "restricted_zones": [[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]],
            "restricted_hours": {"start": "22:00:00", "end": "05:00:00"}
        })
        day_events = day_evaluator.evaluate(inside_person, "13:00:00")
        self.assertEqual(len(day_events), 0)

    def test_ttl_cleaner(self):
        """Uji Aturan 5 (TTL Cleaner) untuk membersihkan track yang tidak aktif."""
        evaluator = CrimeRuleEvaluator(config={"ttl_seconds": 10.0, "restricted_zones": []})

        d_all = [
            {"track_id": 1, "class_name": "person", "bbox": [10, 10, 30, 30]},
            {"track_id": 2, "class_name": "motorcycle", "bbox": [50, 50, 90, 90]}
        ]
        evaluator.evaluate(d_all, "10:00:00")
        self.assertIn(1, evaluator.last_seen)
        self.assertIn(2, evaluator.last_seen)

        # Setelah 15 detik (> 10s TTL), hanya objek 2 yang masih terdeteksi
        d_active = [{"track_id": 2, "class_name": "motorcycle", "bbox": [50, 50, 90, 90]}]
        evaluator.evaluate(d_active, "10:00:15")

        self.assertNotIn(1, evaluator.last_seen, "Objek 1 harus dibersihkan oleh TTL cleaner")
        self.assertIn(2, evaluator.last_seen, "Objek 2 harus tetap ada karena masih aktif")


if __name__ == "__main__":
    unittest.main()
