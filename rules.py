"""
rules.py - Paket 4: Spatial Engine & Crime Rules (Proyek i-see-u)
Penanggung Jawab: Yeskiel (Paket 4)

Modul ini bertanggung jawab untuk mengevaluasi aturan kejahatan berbasis spasial
dan temporal pada data hasil deteksi dan tracking kamera pengawas.

Aturan yang diimplementasikan:
1. OBJECT MAPPING: Menghubungkan helm dan tas (backpack) ke motor terdekat saat motor diam.
2. THEFT_REMOVAL: Mendeteksi pencurian helm/tas saat motor statis dan barang dibawa menjauh.
3. LOITERING: Mendeteksi orang yang berdiam di area yang sama melebihi batas waktu Tloiter.
4. INTRUSION: Mendeteksi orang yang masuk ke zona terlarang pada jam operasional tertentu.
5. TTL CLEANER: Membersihkan riwayat tracking yang sudah tidak aktif melebihi waktu TTL.
"""

import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set


class CrimeRuleEvaluator:
    """
    Evaluator utama untuk mendeteksi event pelanggaran dan kejahatan.
    """

    # Konfigurasi standar
    DEFAULT_CONFIG = {
        # --- 1. Object Mapping & Theft Detection ---
        # Jarak maksimum (pixel) helm/tas ke motor agar dapat dipetakan saat motor diam
        "max_mapping_distance": 150.0,
        # Toleransi perpindahan motor (pixel) agar tetap dianggap dalam kondisi diam (statis)
        "motor_static_tolerance": 15.0,
        # Batas pertambahan jarak Dtheft (pixel) untuk memicu indikasi pencurian
        "d_theft": 80.0,
        # Jarak maksimum person ke helm/tas untuk dianggap sebagai pembawa/pengambil barang
        "theft_person_proximity": 150.0,
        # Cooldown detik agar event THEFT_REMOVAL tidak berulang untuk target yang sama
        "theft_cooldown_seconds": 60.0,

        # --- 2. Loitering Detection ---
        # Batas waktu seseorang berdiam diri di area yang sama (detik)
        "t_loiter": 30.0,
        # Toleransi perpindahan posisi (pixel) agar gerak kecil tidak dianggap berpindah lokasi
        "loiter_movement_tolerance": 40.0,
        # Cooldown detik setelah event LOITERING dipicu untuk person tertentu
        "loiter_cooldown_seconds": 60.0,

        # --- 3. Intrusion Detection ---
        # Daftar polygon zona terlarang (setiap polygon berisi daftar titik (x, y))
        "restricted_zones": [
            [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]
        ],
        # Jam terlarang (format "HH:MM:SS" atau "HH:MM")
        # Default: 22:00:00 malam sampai 05:00:00 pagi
        "restricted_hours": {
            "start": "22:00:00",
            "end": "05:00:00"
        },
        # Cooldown detik untuk event INTRUSION per person
        "intrusion_cooldown_seconds": 60.0,

        # --- 4. TTL Cleaner ---
        # Waktu (detik) sebelum data track yang tidak lagi terdeteksi dihapus dari memori
        "ttl_seconds": 20.0
    }

    def __init__(self, config: Optional[dict] = None):
        """
        Inisialisasi evaluator dengan konfigurasi opsional.
        """
        self.config = dict(self.DEFAULT_CONFIG)
        if config:
            self.config.update(config)

        # ------------------------------------------------------------------
        # State Internal (Memori Penyimpanan Objek dan Riwayat)
        # ------------------------------------------------------------------

        # Riwayat terakhir setiap track_id terlihat: {track_id: last_timestamp_seconds}
        self.last_seen: Dict[Any, float] = {}

        # Riwayat motor: {motor_id: {"last_centroid": (x, y), "is_static": bool, "last_time": float}}
        self.motor_state: Dict[Any, dict] = {}

        # Pemetaan objek helm/tas ke motor:
        # {target_id: {
        #     "motorcycle_id": m_id,
        #     "initial_distance": float,
        #     "initial_motor_centroid": (x, y),
        #     "target_object": str,
        #     "mapped_time": float
        # }}
        self.object_mappings: Dict[Any, dict] = {}

        # Riwayat posisi person untuk Loitering:
        # {person_id: {
        #     "anchor_centroid": (x, y),
        #     "start_time": float,
        #     "last_time": float,
        #     "last_alert_time": Optional[float]
        # }}
        self.loiter_tracker: Dict[Any, dict] = {}

        # Riwayat event terakhir untuk pencegahan duplikat (cooldown):
        # {(event_type, target_id): last_alert_time_seconds}
        self.alert_history: Dict[Tuple[str, Any], float] = {}

        # Tracking internal waktu frame terakhir jika timestamp_str tidak valid
        self._internal_clock: float = 0.0

    # ======================================================================
    # METHOD UTAMA (KONTRAK KELAS WAJIB)
    # ======================================================================

    def evaluate(self, detections: list[dict], timestamp_str: str) -> list[dict]:
        """
        Mengevaluasi daftar deteksi pada timestamp tertentu dan menghasilkan daftar event kejahatan.

        Parameter:
            detections: List dictionary deteksi objek, contoh:
                        [{"track_id": 1, "class_name": "motorcycle", "bbox": [100, 100, 200, 200]}, ...]
            timestamp_str: String waktu saat ini, contoh: "02:14:05"

        Return:
            List dictionary event yang terdeteksi sesuai kontrak format output.
        """
        events: List[dict] = []

        # 1. Parsing timestamp secara aman
        current_time_seconds = self._parse_timestamp(timestamp_str)

        # 2. Tangani input kosong dengan aman
        if not detections:
            # Tetap jalankan pembersihan TTL jika ada data lama
            self._clean_ttl(current_time_seconds, active_track_ids=set())
            return events

        # 3. Kategorikan deteksi berdasarkan kelas objek
        motorcycles = []
        items = []     # helmet & backpack
        persons = []
        active_track_ids: Set[Any] = set()

        for det in detections:
            track_id, class_name, bbox, centroid = self._extract_detection_info(det)
            if track_id is None or centroid is None:
                continue

            active_track_ids.add(track_id)
            self.last_seen[track_id] = current_time_seconds

            item_data = {
                "track_id": track_id,
                "class_name": class_name,
                "bbox": bbox,
                "centroid": centroid
            }

            if class_name in ("motorcycle", "motorbike", "motor"):
                motorcycles.append(item_data)
            elif class_name in ("helmet", "backpack", "bag", "helm"):
                items.append(item_data)
            elif class_name in ("person", "human", "orang"):
                persons.append(item_data)

        # 4. Perbarui status motor (apakah diam/statis)
        self._update_motor_status(motorcycles, current_time_seconds)

        # 5. ATURAN 1: OBJECT MAPPING
        self._update_object_mapping(motorcycles, items, current_time_seconds)

        # 6. ATURAN 2: THEFT_REMOVAL
        theft_events = self._evaluate_theft(motorcycles, items, persons, timestamp_str, current_time_seconds)
        events.extend(theft_events)

        # 7. ATURAN 3: LOITERING
        loiter_events = self._evaluate_loitering(persons, timestamp_str, current_time_seconds)
        events.extend(loiter_events)

        # 8. ATURAN 4: INTRUSION
        intrusion_events = self._evaluate_intrusion(persons, timestamp_str, current_time_seconds)
        events.extend(intrusion_events)

        # 9. ATURAN 5: TTL CLEANER
        self._clean_ttl(current_time_seconds, active_track_ids)

        return events

    # ======================================================================
    # IMPLEMENTASI SETIAP ATURAN
    # ======================================================================

    # --- ATURAN 1: OBJECT MAPPING ---
    def _update_object_mapping(self, motorcycles: List[dict], items: List[dict], current_time: float):
        """
        Menghubungkan helm dan backpack ke motor terdekat saat motor dalam kondisi diam.
        """
        max_dist = self.config.get("max_mapping_distance", 150.0)

        for item in items:
            item_id = item["track_id"]
            item_centroid = item["centroid"]
            item_class = item["class_name"]

            # Jika objek sudah terpetakan, kita tidak perlu memetakan ulang
            if item_id in self.object_mappings:
                continue

            # Cari motor terdekat yang sedang berstatus statis (diam)
            nearest_motor = None
            min_dist = float("inf")

            for motor in motorcycles:
                motor_id = motor["track_id"]
                m_state = self.motor_state.get(motor_id, {})

                # Hanya petakan jika motor dalam kondisi statis
                if not m_state.get("is_static", True):
                    continue

                dist = self._calculate_distance(item_centroid, motor["centroid"])
                if dist <= max_dist and dist < min_dist:
                    min_dist = dist
                    nearest_motor = motor

            # Jika ditemukan motor terdekat dalam radius pemetaan
            if nearest_motor is not None:
                self.object_mappings[item_id] = {
                    "motorcycle_id": nearest_motor["track_id"],
                    "initial_distance": min_dist,
                    "initial_motor_centroid": nearest_motor["centroid"],
                    "target_object": item_class,
                    "mapped_time": current_time
                }

    # --- ATURAN 2: THEFT_REMOVAL ---
    def _evaluate_theft(self, motorcycles: List[dict], items: List[dict],
                        persons: List[dict], timestamp_str: str,
                        current_time: float) -> List[dict]:
        """
        Mendeteksi pencurian helm/tas ketika jarak ke motor bertambah > Dtheft,
        motor dalam kondisi statis, dan ada person terkait yang juga menjauh dari motor.
        """
        events = []
        d_theft = self.config.get("d_theft", 80.0)
        person_proximity_limit = self.config.get("theft_person_proximity", 150.0)
        cooldown = self.config.get("theft_cooldown_seconds", 60.0)

        # Buat dictionary motor aktif untuk lookup cepat
        active_motors = {m["track_id"]: m for m in motorcycles}

        for item in items:
            item_id = item["track_id"]

            # Periksa apakah objek ini sebelumnya sudah terpetakan ke motor
            mapping = self.object_mappings.get(item_id)
            if not mapping:
                continue

            motor_id = mapping["motorcycle_id"]

            # Periksa apakah motor dalam kondisi statis
            motor_current = active_motors.get(motor_id)
            m_state = self.motor_state.get(motor_id, {})

            if motor_current:
                motor_centroid = motor_current["centroid"]
                is_motor_static = m_state.get("is_static", True)
            else:
                # Motor tidak di frame, gunakan referensi posisi tersimpan
                motor_centroid = mapping["initial_motor_centroid"]
                is_motor_static = True

            # Syarat: Motor harus dalam kondisi statis
            if not is_motor_static:
                continue

            # Hitung jarak helm/tas saat ini ke motor
            current_dist = self._calculate_distance(item["centroid"], motor_centroid)
            dist_increase = current_dist - mapping["initial_distance"]

            # Syarat: Pertambahan jarak melebihi batas Dtheft
            if dist_increase >= d_theft or current_dist >= (mapping["initial_distance"] + d_theft):

                # Syarat: Periksa apakah person yang berkaitan juga menjauh dari motor
                related_person_id = None
                min_p_dist = float("inf")

                for p in persons:
                    p_to_item_dist = self._calculate_distance(p["centroid"], item["centroid"])
                    p_to_motor_dist = self._calculate_distance(p["centroid"], motor_centroid)

                    if p_to_item_dist <= person_proximity_limit:
                        if p_to_item_dist < min_p_dist:
                            min_p_dist = p_to_item_dist
                            if p_to_motor_dist > mapping["initial_distance"]:
                                related_person_id = p["track_id"]

                # Jika person teridentifikasi atau tidak ada filter ketat person
                if related_person_id is not None or not persons:
                    # Periksa anti-duplicate (cooldown)
                    alert_key = ("THEFT_REMOVAL", item_id)
                    last_alert = self.alert_history.get(alert_key)
                    if last_alert is None or (current_time - last_alert) >= cooldown:
                        self.alert_history[alert_key] = current_time

                        # Buat event sesuai kontrak format wajib
                        events.append({
                            "timestamp": timestamp_str,
                            "event_type": "THEFT_REMOVAL",
                            "target_object": mapping["target_object"],
                            "target_id": item_id,
                            "person_id": related_person_id if related_person_id is not None else -1,
                            "bbox_highlight": item["bbox"]
                        })

        # Bagian B: Deteksi pencurian kendaraan itu sendiri (motorcycle/bicycle) yang dipindahkan dari posisi parkir
        for motor in motorcycles:
            m_id = motor["track_id"]
            m_centroid = motor["centroid"]
            m_state = self.motor_state.get(m_id)
            if not m_state:
                continue

            parked_anchor = m_state.get("parked_anchor")
            static_frames = m_state.get("static_frames", 0)

            # Jika kendaraan sebelumnya sudah terparkir statis (>= 3 frame sampling)
            # lalu berpindah posisi melebihi ambang batas d_theft
            if parked_anchor and static_frames >= 3:
                displacement = self._calculate_distance(m_centroid, parked_anchor)
                if displacement >= d_theft:
                    alert_key = ("THEFT_REMOVAL", m_id)
                    last_alert = self.alert_history.get(alert_key)
                    if last_alert is None or (current_time - last_alert) >= cooldown:
                        self.alert_history[alert_key] = current_time

                        # Cari person terdekat jika ada di sekitar kendaraan
                        related_person_id = -1
                        min_p_dist = float("inf")
                        for p in persons:
                            p_dist = self._calculate_distance(p["centroid"], m_centroid)
                            if p_dist < min_p_dist:
                                min_p_dist = p_dist
                                related_person_id = p["track_id"]

                        events.append({
                            "timestamp": timestamp_str,
                            "event_type": "THEFT_REMOVAL",
                            "target_object": motor["class_name"],
                            "target_id": m_id,
                            "person_id": related_person_id,
                            "bbox_highlight": motor["bbox"]
                        })

        return events

    # --- ATURAN 3: LOITERING ---
    def _evaluate_loitering(self, persons: List[dict], timestamp_str: str,
                            current_time: float) -> List[dict]:
        """
        Mendeteksi seseorang yang berada di sekitar koordinat yang sama lebih lama dari Tloiter.
        """
        events = []
        t_loiter = self.config.get("t_loiter", 30.0)
        movement_tol = self.config.get("loiter_movement_tolerance", 40.0)
        cooldown = self.config.get("loiter_cooldown_seconds", 60.0)

        for person in persons:
            person_id = person["track_id"]
            centroid = person["centroid"]

            if person_id not in self.loiter_tracker:
                self.loiter_tracker[person_id] = {
                    "anchor_centroid": centroid,
                    "start_time": current_time,
                    "last_time": current_time,
                    "alerted": False
                }
            else:
                tracker = self.loiter_tracker[person_id]
                anchor = tracker["anchor_centroid"]
                displacement = self._calculate_distance(centroid, anchor)

                if displacement <= movement_tol:
                    tracker["last_time"] = current_time
                    duration = current_time - tracker["start_time"]

                    if duration >= t_loiter:
                        alert_key = ("LOITERING", person_id)
                        last_alert = self.alert_history.get(alert_key)

                        if last_alert is None or (current_time - last_alert) >= cooldown:
                            self.alert_history[alert_key] = current_time
                            tracker["alerted"] = True

                            events.append({
                                "timestamp": timestamp_str,
                                "event_type": "LOITERING",
                                "target_object": "person",
                                "target_id": person_id,
                                "person_id": person_id,
                                "bbox_highlight": person["bbox"]
                            })
                else:
                    self.loiter_tracker[person_id] = {
                        "anchor_centroid": centroid,
                        "start_time": current_time,
                        "last_time": current_time,
                        "alerted": False
                    }

        return events

    # --- ATURAN 4: INTRUSION ---
    def _evaluate_intrusion(self, persons: List[dict], timestamp_str: str,
                            current_time: float) -> List[dict]:
        """
        Mendeteksi person yang centroidnya berada di dalam polygon zona terlarang
        pada jam yang ditentukan konfigurasi.
        """
        events = []
        restricted_hours = self.config.get("restricted_hours")
        restricted_zones = self.config.get("restricted_zones", [])
        cooldown = self.config.get("intrusion_cooldown_seconds", 60.0)

        if not self._is_within_restricted_hours(current_time, restricted_hours):
            return events

        if not restricted_zones:
            return events

        for person in persons:
            person_id = person["track_id"]
            centroid = person["centroid"]

            in_restricted_zone = False
            for zone_polygon in restricted_zones:
                if self._is_point_in_polygon(centroid, zone_polygon):
                    in_restricted_zone = True
                    break

            if in_restricted_zone:
                alert_key = ("INTRUSION", person_id)
                last_alert = self.alert_history.get(alert_key)

                if last_alert is None or (current_time - last_alert) >= cooldown:
                    self.alert_history[alert_key] = current_time

                    events.append({
                        "timestamp": timestamp_str,
                        "event_type": "INTRUSION",
                        "target_object": "person",
                        "target_id": person_id,
                        "person_id": person_id,
                        "bbox_highlight": person["bbox"]
                    })

        return events

    # --- ATURAN 5: TTL CLEANER ---
    def _clean_ttl(self, current_time: float, active_track_ids: Set[Any]):
        """
        Menyimpan waktu terakhir setiap track ID terlihat, dan membersihkan
        data track yang sudah melewati TTL tanpa menghapus track yang masih aktif.
        """
        ttl_seconds = self.config.get("ttl_seconds", 20.0)

        expired_ids = set()
        for track_id, last_time in list(self.last_seen.items()):
            if track_id in active_track_ids:
                continue

            if (current_time - last_time) > ttl_seconds:
                expired_ids.add(track_id)

        for tid in expired_ids:
            self.last_seen.pop(tid, None)
            self.motor_state.pop(tid, None)
            self.loiter_tracker.pop(tid, None)
            self.object_mappings.pop(tid, None)

            keys_to_remove = [k for k in self.alert_history if k[1] == tid]
            for k in keys_to_remove:
                self.alert_history.pop(k, None)

        mappings_to_remove = []
        for item_id, mapping in self.object_mappings.items():
            motor_id = mapping.get("motorcycle_id")
            if motor_id in expired_ids:
                mappings_to_remove.append(item_id)

        for item_id in mappings_to_remove:
            self.object_mappings.pop(item_id, None)

    # ======================================================================
    # HELPER UTILITY & MATEMATIKA SPASIAL
    # ======================================================================

    def _update_motor_status(self, motorcycles: List[dict], current_time: float):
        """
        Memperbarui status pergerakan motor untuk menentukan apakah motor sedang statis/diam
        serta menyimpan anchor posisi parkirnya.
        """
        tol = self.config.get("motor_static_tolerance", 15.0)

        for motor in motorcycles:
            m_id = motor["track_id"]
            curr_centroid = motor["centroid"]

            if m_id not in self.motor_state:
                self.motor_state[m_id] = {
                    "last_centroid": curr_centroid,
                    "parked_anchor": curr_centroid,
                    "static_frames": 1,
                    "is_static": True,
                    "last_time": current_time
                }
            else:
                prev_info = self.motor_state[m_id]
                prev_centroid = prev_info["last_centroid"]
                displacement = self._calculate_distance(curr_centroid, prev_centroid)
                is_static = displacement <= tol

                parked_anchor = prev_info.get("parked_anchor", curr_centroid)
                static_frames = prev_info.get("static_frames", 1)

                dist_from_anchor = self._calculate_distance(curr_centroid, parked_anchor)
                if dist_from_anchor <= tol:
                    static_frames += 1
                elif is_static:
                    # Jika motor berpindah lalu diam di posisi parkir baru
                    parked_anchor = curr_centroid
                    static_frames = 1

                self.motor_state[m_id] = {
                    "last_centroid": curr_centroid,
                    "parked_anchor": parked_anchor,
                    "static_frames": static_frames,
                    "is_static": is_static,
                    "last_time": current_time
                }

    def _extract_detection_info(self, det: dict) -> Tuple[Optional[Any], str, list, Optional[Tuple[float, float]]]:
        """
        Mengekstrak track_id, class_name, bbox, dan centroid secara aman
        dari dictionary deteksi berbagai variasi penamaan tim.
        """
        if not isinstance(det, dict):
            return None, "", [], None

        # 1. ID Objek
        track_id = det.get("track_id")
        if track_id is None:
            track_id = det.get("id") if det.get("id") is not None else det.get("tracker_id")

        # 2. Nama Kelas
        class_name = det.get("class_name") or det.get("label") or det.get("class") or det.get("name") or ""
        class_name = str(class_name).lower().strip()

        # 3. Bounding Box & Centroid
        centroid = det.get("centroid")
        bbox = det.get("bbox") or det.get("box") or det.get("bounding_box") or []

        parsed_bbox = []
        if isinstance(bbox, (tuple, list)) and len(bbox) >= 4:
            parsed_bbox = [float(b) for b in bbox[:4]]
            if centroid is None:
                cx = (parsed_bbox[0] + parsed_bbox[2]) / 2.0
                cy = (parsed_bbox[1] + parsed_bbox[3]) / 2.0
                centroid = (cx, cy)
        elif isinstance(bbox, dict):
            x = float(bbox.get("x", 0))
            y = float(bbox.get("y", 0))
            w = float(bbox.get("w", 0))
            h = float(bbox.get("h", 0))
            parsed_bbox = [x, y, x + w, y + h]
            if centroid is None:
                centroid = (x + w / 2.0, y + h / 2.0)

        # Pastikan centroid tuple float
        parsed_centroid: Optional[Tuple[float, float]] = None
        if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
            parsed_centroid = (float(centroid[0]), float(centroid[1]))

        return track_id, class_name, parsed_bbox, parsed_centroid

    def _calculate_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        Menghitung jarak Euclidean 2D antara dua titik centroid.
        """
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def _is_point_in_polygon(self, point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """
        Menentukan apakah titik (x, y) berada di dalam polygon menggunakan Ray-Casting Algorithm.
        """
        if len(polygon) < 3:
            return False

        x, y = point
        inside = False
        n = len(polygon)

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        else:
                            xinters = p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def _parse_timestamp(self, ts_str: str) -> float:
        """
        Mengubah string timestamp menjadi detik dalam hari (0.0 s/d 86400.0) secara aman.
        """
        if not ts_str or not isinstance(ts_str, str):
            self._internal_clock += 1.0
            return self._internal_clock

        cleaned_str = ts_str.strip()
        formats = [
            "%H:%M:%S",
            "%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f"
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned_str, fmt)
                seconds = dt.hour * 3600.0 + dt.minute * 60.0 + dt.second + (dt.microsecond / 1_000_000.0)
                self._internal_clock = seconds
                return seconds
            except ValueError:
                continue

        self._internal_clock += 1.0
        return self._internal_clock

    def _is_within_restricted_hours(self, current_time_seconds: float, restricted_hours: Optional[dict]) -> bool:
        """
        Memeriksa apakah waktu saat ini berada dalam rentang jam terlarang.
        """
        if not restricted_hours:
            return True

        start_str = restricted_hours.get("start")
        end_str = restricted_hours.get("end")

        if not start_str or not end_str:
            return True

        start_sec = self._parse_time_to_seconds(start_str)
        end_sec = self._parse_time_to_seconds(end_str)

        if start_sec is None or end_sec is None:
            return True

        sec_of_day = current_time_seconds % 86400.0

        if start_sec <= end_sec:
            return start_sec <= sec_of_day <= end_sec
        else:
            return sec_of_day >= start_sec or sec_of_day <= end_sec

    def _parse_time_to_seconds(self, t_str: str) -> Optional[float]:
        """
        Helper untuk mengonversi string jam ("HH:MM:SS" atau "HH:MM") ke detik.
        """
        parts = t_str.strip().split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0
            elif len(parts) >= 3:
                return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
        except (ValueError, TypeError):
            return None
        return None
