"""
Incident Type Definitions for AI Analysis
"""

from enum import Enum


class IncidentTypes(str, Enum):
    """Incident type codes"""
    # Face Analysis
    A1_NO_FACE = "A1"
    A2_MULTIPLE_FACES = "A2"
    A3_FACE_MISMATCH = "A3"
    A4_FACE_TURNED = "A4"
    
    # Screen Analysis
    B1_SEARCH_ENGINE = "B1"
    B2_CHAT_APP = "B2"
    B3_SUSPICIOUS_TEXT = "B3"
    B4_EXAM_CONTENT = "B4"
    
    # Audio Analysis
    C1_VOICE_DETECTED = "C1"
    C2_MULTIPLE_SPEAKERS = "C2"
    
    # Behavior Analysis
    D1_LOOKING_AWAY = "D1"
    D2_LEFT_CAMERA = "D2"
    D3_EXCESSIVE_MOVEMENT = "D3"


class SeverityLevel(str, Enum):
    """Severity levels"""
    INFO = "S1"
    WARNING = "S2"
    SERIOUS = "S3"
    CRITICAL = "S4"


# Detailed incident definitions
INCIDENT_DEFINITIONS = {
    # Face Analysis
    "A1": {
        "name": "Không Phát Hiện Khuôn Mặt",
        "default_level": "S2",
        "description": "Không thấy khuôn mặt thí sinh trong camera",
        "message": "Không phát hiện khuôn mặt - thí sinh có thể đã rời khỏi vùng camera"
    },
    "A2": {
        "name": "Nhiều Khuôn Mặt",
        "default_level": "S3",
        "description": "Phát hiện nhiều hơn một khuôn mặt",
        "message": "Phát hiện nhiều khuôn mặt - có người không được phép trong phòng"
    },
    "A3": {
        "name": "Khuôn Mặt Không Khớp",
        "default_level": "S4",
        "description": "Khuôn mặt không khớp với xác minh KYC",
        "message": "Khuôn mặt không khớp - phát hiện nghi ngờ mạo danh"
    },
    "A4": {
        "name": "Khuôn Mặt Quay Đi",
        "default_level": "S2",
        "description": "Khuôn mặt quay ra khỏi camera",
        "message": "Khuôn mặt quay đi hoặc bị che khuất một phần"
    },
    
    # Screen Analysis
    "B1": {
        "name": "Phát Hiện Công Cụ Tìm Kiếm",
        "default_level": "S3",
        "description": "Phát hiện trình duyệt có công cụ tìm kiếm",
        "message": "Phát hiện công cụ tìm kiếm trên màn hình"
    },
    "B2": {
        "name": "Ứng Dụng Chat",
        "default_level": "S3",
        "description": "Phát hiện ứng dụng nhắn tin",
        "message": "Phát hiện ứng dụng chat trên màn hình"
    },
    "B3": {
        "name": "Văn Bản Đáng Ngờ",
        "default_level": "S2",
        "description": "Phát hiện từ khóa đáng ngờ",
        "message": "Phát hiện văn bản đáng ngờ trên màn hình"
    },
    "B4": {
        "name": "Nội Dung Bài Thi Bị Rò Rỉ",
        "default_level": "S4",
        "description": "Phát hiện câu hỏi/đáp án bài thi",
        "message": "Phát hiện nội dung bài thi trên màn hình không được phép"
    },
    
    # Audio Analysis
    "C1": {
        "name": "Phát Hiện Giọng Nói",
        "default_level": "S1",
        "description": "Thí sinh đang nói",
        "message": "Phát hiện hoạt động giọng nói"
    },
    "C2": {
        "name": "Nhiều Người Nói",
        "default_level": "S3",
        "description": "Phát hiện nhiều giọng nói",
        "message": "Phát hiện nhiều người nói - nghi ngờ có sự hỗ trợ"
    },
    
    # Behavior Analysis
    "D1": {
        "name": "Nhìn Ra Ngoài",
        "default_level": "S2",
        "description": "Thí sinh nhìn ra ngoài màn hình",
        "message": "Thí sinh đang nhìn ra ngoài màn hình"
    },
    "D2": {
        "name": "Rời Khỏi Camera",
        "default_level": "S2",
        "description": "Thí sinh rời khỏi vùng hiển thị camera",
        "message": "Thí sinh đã rời khỏi vùng camera"
    },
    "D3": {
        "name": "Cử Động Quá Mức",
        "default_level": "S1",
        "description": "Phát hiện cử động bất thường",
        "message": "Phát hiện cử động quá mức"
    }
}


def get_incident_info(incident_type: str) -> dict:
    """Get incident information by type"""
    return INCIDENT_DEFINITIONS.get(incident_type, {
        "name": "Unknown",
        "default_level": "S1",
        "description": "Unknown incident type",
        "message": f"Unknown incident: {incident_type}"
    })
