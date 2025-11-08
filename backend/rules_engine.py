"""
Rules Engine: Xử lý escalation A1-A11 theo SOP
"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime, timedelta


@dataclass
class AlertState:
    """State tracking cho từng loại cảnh báo"""
    code: str
    first_seen: float = 0
    count: int = 0
    last_escalated: float = 0
    cooldown_until: float = 0


@dataclass
class SessionState:
    """State của một phiên thi"""
    session_id: str
    room_id: str
    user_id: str
    started_at: float
    alerts: Dict[str, AlertState] = field(default_factory=dict)
    status: str = "active"  # active, paused, ended
    
    def get_alert_state(self, code: str) -> AlertState:
        if code not in self.alerts:
            self.alerts[code] = AlertState(code=code)
        return self.alerts[code]


class RulesEngine:
    """Rules Engine xử lý escalation theo SOP"""
    
    # Ngưỡng theo thiết kế
    THRESHOLDS = {
        "A1": {"duration_sec": 30, "max_per_15min": 3},
        "A2": {"min_frames": 2, "window_sec": 3},
        "A3": {"L1": 2, "L2": 4, "L3": 5},
        "A4": {"timeout_sec": 60},
        "A5": {"immediate": True},
        "A6": {"duration_sec": 30},
        "A7": {"immediate": True},
        "A8": {"immediate": True},
        "A9": {"immediate": True},
        "A10": {"cosine_threshold": 0.4},
        "A11": {"idle_sec": 120},
    }
    
    # Mapping code -> default level
    DEFAULT_LEVELS = {
        "A1": "S1", "A2": "S2", "A3": "S1", "A4": "S2",
        "A5": "S2", "A6": "S2", "A7": "S2", "A8": "S1",
        "A9": "S2", "A10": "S3", "A11": "S1"
    }
    
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
    
    def get_or_create_session(self, room_id: str, user_id: str) -> SessionState:
        key = f"{room_id}:{user_id}"
        if key not in self.sessions:
            self.sessions[key] = SessionState(
                session_id=key,
                room_id=room_id,
                user_id=user_id,
                started_at=datetime.now().timestamp()
            )
        return self.sessions[key]
    
    def process_incident(self, room_id: str, user_id: str, incident: dict) -> dict:
        """
        Xử lý incident và quyết định level/escalation
        Returns: incident dict với level/escalation đã cập nhật
        """
        session = self.get_or_create_session(room_id, user_id)
        code = incident.get("tag", "")
        now = datetime.now().timestamp()
        
        if not code or code not in self.DEFAULT_LEVELS:
            return incident
        
        alert_state = session.get_alert_state(code)
        level = self.DEFAULT_LEVELS[code]
        
        # Escalation logic theo từng mã
        if code == "A1":
            # Mất khuôn mặt >30s hoặc >3 lần/15'
            if alert_state.first_seen == 0:
                alert_state.first_seen = now
            duration = now - alert_state.first_seen
            if duration > self.THRESHOLDS["A1"]["duration_sec"]:
                level = "S2"
                alert_state.count += 1
                alert_state.first_seen = 0  # reset
            # Check count trong 15 phút
            recent_count = sum(1 for a in session.alerts.values() 
                             if a.code == code and now - a.last_escalated < 900)
            if recent_count >= self.THRESHOLDS["A1"]["max_per_15min"]:
                level = "S2"
        
        elif code == "A2":
            # Nhiều khuôn mặt: S2 ngay, nếu tái diễn → S3
            alert_state.count += 1
            if alert_state.count >= 2:
                level = "S3"
        
        elif code == "A3":
            # Chuyển tab: L1=1-2 (S1), L2=3-4 (S2), L3≥5 (S3)
            alert_state.count += 1
            if alert_state.count >= self.THRESHOLDS["A3"]["L3"]:
                level = "S3"
                session.status = "paused"
            elif alert_state.count >= self.THRESHOLDS["A3"]["L2"]:
                level = "S2"
            else:
                level = "S1"
        
        elif code == "A4":
            # Không chia sẻ màn hình >60s → S3
            if alert_state.first_seen == 0:
                alert_state.first_seen = now
            if now - alert_state.first_seen > self.THRESHOLDS["A4"]["timeout_sec"]:
                level = "S3"
                session.status = "paused"
        
        elif code == "A5":
            # Tài liệu cấm: S2 ngay, tái phạm → S3
            alert_state.count += 1
            if alert_state.count > 1:
                level = "S3"
                session.status = "paused"
        
        elif code == "A6":
            # Âm thanh hội thoại >30s → S3
            if alert_state.first_seen == 0:
                alert_state.first_seen = now
            if now - alert_state.first_seen > self.THRESHOLDS["A6"]["duration_sec"]:
                level = "S3"
        
        elif code == "A10":
            # Giả mạo: S3 ngay
            level = "S3"
            session.status = "paused"
        
        # Update state
        alert_state.last_escalated = now
        incident["level"] = level
        incident["escalated"] = alert_state.count
        incident["session_status"] = session.status
        
        return incident
    
    def get_session_summary(self, room_id: str, user_id: str) -> dict:
        """Lấy summary của session"""
        key = f"{room_id}:{user_id}"
        session = self.sessions.get(key)
        if not session:
            return {}
        return {
            "session_id": session.session_id,
            "status": session.status,
            "alerts_count": len(session.alerts),
            "alerts": {code: {"count": state.count, "last": state.last_escalated} 
                      for code, state in session.alerts.items()}
        }


# Global instance
rules_engine = RulesEngine()

