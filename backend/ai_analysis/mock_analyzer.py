"""
Mock AI Analyzer - Simulates AI model outputs
"""

import random
import time
from typing import Dict, List, Optional
from .incident_types import IncidentTypes, SeverityLevel, get_incident_info


class MockAIAnalyzer:
    """
    Mock AI Analyzer that generates realistic AI analysis results
    without requiring actual AI models.
    
    This allows frontend development and system testing before
    integrating real AI models.
    """
    
    def __init__(self):
        # Scenario weights (probabilities)
        self.scenario_weights = {
            "normal": 0.75,              # 75% - Everything normal
            "no_face": 0.08,             # 8% - No face detected
            "multiple_faces": 0.02,      # 2% - Multiple people
            "face_mismatch": 0.01,       # 1% - Wrong person (critical)
            "face_turned": 0.03,         # 3% - Face turned away
            "search_engine": 0.04,       # 4% - Google/ChatGPT
            "chat_app": 0.02,            # 2% - Messenger/Zalo
            "voice_detected": 0.03,      # 3% - Speaking
            "multiple_speakers": 0.01,   # 1% - Multiple voices
            "looking_away": 0.01,        # 1% - Looking away
        }
        
        # Suspicious keywords for screen analysis
        self.suspicious_keywords = {
            "search": ["google", "search", "chatgpt", "bing", "stackoverflow"],
            "chat": ["messenger", "zalo", "discord", "telegram", "whatsapp"],
            "code": ["github", "copilot", "ide", "vscode"],
        }
    
    def analyze_frame(self, candidate_id: str, room_id: str) -> Dict:
        """
        Generate mock AI analysis for one frame
        
        Args:
            candidate_id: ID of candidate being analyzed
            room_id: Room ID
            
        Returns:
            Dict containing analysis results and any alerts
        """
        scenario = self._choose_scenario()
        
        results = {
            "timestamp": int(time.time() * 1000),
            "candidate_id": candidate_id,
            "room_id": room_id,
            "scenario": scenario,  # For debugging
            "analyses": []
        }
        
        # Generate appropriate analyses based on scenario
        if scenario == "normal":
            results["analyses"] = self._generate_normal()
        elif scenario == "no_face":
            results["analyses"] = self._generate_no_face()
        elif scenario == "multiple_faces":
            results["analyses"] = self._generate_multiple_faces()
        elif scenario == "face_mismatch":
            results["analyses"] = self._generate_face_mismatch()
        elif scenario == "face_turned":
            results["analyses"] = self._generate_face_turned()
        elif scenario == "search_engine":
            results["analyses"] = self._generate_search_engine()
        elif scenario == "chat_app":
            results["analyses"] = self._generate_chat_app()
        elif scenario == "voice_detected":
            results["analyses"] = self._generate_voice_detected()
        elif scenario == "multiple_speakers":
            results["analyses"] = self._generate_multiple_speakers()
        elif scenario == "looking_away":
            results["analyses"] = self._generate_looking_away()
        
        return results
    
    def _choose_scenario(self) -> str:
        """Randomly choose a scenario based on weights"""
        scenarios = list(self.scenario_weights.keys())
        weights = list(self.scenario_weights.values())
        return random.choices(scenarios, weights=weights)[0]
    
    # ==================== SCENARIO GENERATORS ====================
    
    def _generate_normal(self) -> List[Dict]:
        """Normal scenario - no violations"""
        return [
            {
                "type": "face_detection",
                "result": {
                    "faces_detected": 1,
                    "confidence": random.uniform(0.85, 0.98),
                    "bounding_boxes": [{
                        "x": random.randint(100, 150),
                        "y": random.randint(80, 120),
                        "width": random.randint(180, 220),
                        "height": random.randint(220, 260),
                        "confidence": random.uniform(0.85, 0.98)
                    }],
                    "status": "normal",
                    "alert": None
                }
            },
            {
                "type": "face_recognition",
                "result": {
                    "is_verified": True,
                    "similarity_score": random.uniform(0.78, 0.95),
                    "kyc_image_id": "kyc_" + str(random.randint(100000, 999999)),
                    "status": "verified",
                    "alert": None
                }
            },
            {
                "type": "screen_analysis",
                "result": {
                    "ocr_text": "Exam Question " + str(random.randint(1, 50)) + ": What is...",
                    "detected_apps": ["exam_browser"],
                    "suspicious_keywords": [],
                    "suspicious_score": 0.0,
                    "status": "clean",
                    "alert": None
                }
            },
            {
                "type": "audio_analysis",
                "result": {
                    "voice_detected": False,
                    "speaking_duration": 0,
                    "num_speakers": 0,
                    "confidence": 1.0,
                    "status": "silent",
                    "alert": None
                }
            },
            {
                "type": "behavior_analysis",
                "result": {
                    "gaze_direction": "center",
                    "looking_away_duration": 0,
                    "left_camera": False,
                    "movement_score": random.uniform(0.1, 0.3),
                    "status": "normal",
                    "alert": None
                }
            }
        ]
    
    def _generate_no_face(self) -> List[Dict]:
        """No face detected"""
        incident = get_incident_info(IncidentTypes.A1_NO_FACE)
        return [
            {
                "type": "face_detection",
                "result": {
                    "faces_detected": 0,
                    "confidence": 0.0,
                    "bounding_boxes": [],
                    "status": "no_face",
                    "alert": {
                        "type": IncidentTypes.A1_NO_FACE,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            },
            {
                "type": "behavior_analysis",
                "result": {
                    "gaze_direction": "unknown",
                    "looking_away_duration": random.uniform(2, 10),
                    "left_camera": True,
                    "movement_score": 0.0,
                    "status": "left_camera",
                    "alert": {
                        "type": IncidentTypes.D2_LEFT_CAMERA,
                        "level": SeverityLevel.WARNING,
                        "message": "Candidate left camera view"
                    }
                }
            }
        ]
    
    def _generate_multiple_faces(self) -> List[Dict]:
        """Multiple faces detected"""
        incident = get_incident_info(IncidentTypes.A2_MULTIPLE_FACES)
        num_faces = random.randint(2, 3)
        return [
            {
                "type": "face_detection",
                "result": {
                    "faces_detected": num_faces,
                    "confidence": random.uniform(0.75, 0.92),
                    "bounding_boxes": [
                        {
                            "x": random.randint(50, 150),
                            "y": random.randint(50, 150),
                            "width": random.randint(100, 150),
                            "height": random.randint(120, 180),
                            "confidence": random.uniform(0.75, 0.92)
                        }
                        for _ in range(num_faces)
                    ],
                    "status": "multiple_faces",
                    "alert": {
                        "type": IncidentTypes.A2_MULTIPLE_FACES,
                        "level": incident["default_level"],
                        "message": f"{num_faces} faces detected - " + incident["message"]
                    }
                }
            }
        ]
    
    def _generate_face_mismatch(self) -> List[Dict]:
        """Face does not match KYC"""
        incident = get_incident_info(IncidentTypes.A3_FACE_MISMATCH)
        return [
            {
                "type": "face_recognition",
                "result": {
                    "is_verified": False,
                    "similarity_score": random.uniform(0.25, 0.48),
                    "kyc_image_id": "kyc_" + str(random.randint(100000, 999999)),
                    "status": "mismatch",
                    "alert": {
                        "type": IncidentTypes.A3_FACE_MISMATCH,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_face_turned(self) -> List[Dict]:
        """Face turned away"""
        incident = get_incident_info(IncidentTypes.A4_FACE_TURNED)
        return [
            {
                "type": "face_detection",
                "result": {
                    "faces_detected": 1,
                    "confidence": random.uniform(0.35, 0.55),
                    "bounding_boxes": [{
                        "x": random.randint(100, 150),
                        "y": random.randint(80, 120),
                        "width": random.randint(150, 180),
                        "height": random.randint(180, 220),
                        "confidence": random.uniform(0.35, 0.55)
                    }],
                    "status": "face_turned",
                    "alert": {
                        "type": IncidentTypes.A4_FACE_TURNED,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_search_engine(self) -> List[Dict]:
        """Search engine detected"""
        incident = get_incident_info(IncidentTypes.B1_SEARCH_ENGINE)
        search_texts = [
            "Google Search: python tutorial",
            "ChatGPT - how to solve...",
            "Bing: javascript function",
            "Stack Overflow: algorithm help"
        ]
        return [
            {
                "type": "screen_analysis",
                "result": {
                    "ocr_text": random.choice(search_texts),
                    "detected_apps": ["chrome", "edge"],
                    "suspicious_keywords": ["google", "search", "chatgpt"],
                    "suspicious_score": random.uniform(0.8, 0.95),
                    "status": "suspicious",
                    "alert": {
                        "type": IncidentTypes.B1_SEARCH_ENGINE,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_chat_app(self) -> List[Dict]:
        """Chat application detected"""
        incident = get_incident_info(IncidentTypes.B2_CHAT_APP)
        chat_apps = ["messenger", "zalo", "discord", "telegram"]
        return [
            {
                "type": "screen_analysis",
                "result": {
                    "ocr_text": "Messenger: Hey, what's the answer?",
                    "detected_apps": [random.choice(chat_apps)],
                    "suspicious_keywords": ["messenger", "chat"],
                    "suspicious_score": random.uniform(0.85, 0.98),
                    "status": "violation",
                    "alert": {
                        "type": IncidentTypes.B2_CHAT_APP,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_voice_detected(self) -> List[Dict]:
        """Voice activity detected"""
        incident = get_incident_info(IncidentTypes.C1_VOICE_DETECTED)
        return [
            {
                "type": "audio_analysis",
                "result": {
                    "voice_detected": True,
                    "speaking_duration": random.uniform(1.5, 5.0),
                    "num_speakers": 1,
                    "confidence": random.uniform(0.85, 0.95),
                    "status": "speaking",
                    "alert": {
                        "type": IncidentTypes.C1_VOICE_DETECTED,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_multiple_speakers(self) -> List[Dict]:
        """Multiple speakers detected"""
        incident = get_incident_info(IncidentTypes.C2_MULTIPLE_SPEAKERS)
        return [
            {
                "type": "audio_analysis",
                "result": {
                    "voice_detected": True,
                    "speaking_duration": random.uniform(3.0, 8.0),
                    "num_speakers": random.randint(2, 3),
                    "confidence": random.uniform(0.75, 0.92),
                    "status": "multiple_speakers",
                    "alert": {
                        "type": IncidentTypes.C2_MULTIPLE_SPEAKERS,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]
    
    def _generate_looking_away(self) -> List[Dict]:
        """Looking away from screen"""
        incident = get_incident_info(IncidentTypes.D1_LOOKING_AWAY)
        directions = ["left", "right", "down", "up"]
        return [
            {
                "type": "behavior_analysis",
                "result": {
                    "gaze_direction": random.choice(directions),
                    "looking_away_duration": random.uniform(3, 8),
                    "left_camera": False,
                    "movement_score": random.uniform(0.4, 0.7),
                    "status": "looking_away",
                    "alert": {
                        "type": IncidentTypes.D1_LOOKING_AWAY,
                        "level": incident["default_level"],
                        "message": incident["message"]
                    }
                }
            }
        ]


# Global instance
mock_analyzer = MockAIAnalyzer()
