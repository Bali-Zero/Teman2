import cv2
import mediapipe as mp
import numpy as np
import math

class FaceTracker:
    def __init__(self):
        """
        Inizializza MediaPipe Face Mesh per tracciare il viso a 60fps con minimo impatto CPU.
        """
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True, # Rileva l'iride per maggiore precisione sugli occhi
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        
        # Indici dei landmarks MediaPipe
        self.NOSE_TIP = 4
        
        # Occhio Sinistro (nella telecamera specchiata)
        self.LEFT_EYE = [33, 160, 158, 133, 153, 144]
        # Occhio Destro (nella telecamera specchiata)
        self.RIGHT_EYE = [362, 385, 387, 263, 373, 380]

    def _euclidean_distance(self, p1, p2):
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    def _calculate_ear(self, eye_points, landmarks, frame_w, frame_h):
        """Calcola l'Eye Aspect Ratio per rilevare i battiti di ciglia (winks)"""
        # Coordinate 2D
        pts = [(int(landmarks[i].x * frame_w), int(landmarks[i].y * frame_h)) for i in eye_points]
        
        # EAR formula: (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        vert1 = self._euclidean_distance(pts[1], pts[5])
        vert2 = self._euclidean_distance(pts[2], pts[4])
        horiz = self._euclidean_distance(pts[0], pts[3])
        
        if horiz == 0:
            return 0.0
        return (vert1 + vert2) / (2.0 * horiz)

    def process_frame(self, frame):
        """
        Elabora il frame RGB e restituisce i dati di tracciamento.
        """
        h, w, _ = frame.shape
        # Converti BGR a RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Passa a MediaPipe
        results = self.face_mesh.process(rgb_frame)
        
        tracking_data = {
            "found": False,
            "nose": (0, 0),
            "left_ear": 0.0,
            "right_ear": 0.0
        }
        
        if results.multi_face_landmarks:
            tracking_data["found"] = True
            face_landmarks = results.multi_face_landmarks[0].landmark
            
            # Naso
            nose = face_landmarks[self.NOSE_TIP]
            tracking_data["nose"] = (nose.x, nose.y)
            
            # EAR
            tracking_data["left_ear"] = self._calculate_ear(self.LEFT_EYE, face_landmarks, w, h)
            tracking_data["right_ear"] = self._calculate_ear(self.RIGHT_EYE, face_landmarks, w, h)
            
        return tracking_data
