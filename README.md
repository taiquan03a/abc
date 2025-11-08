# Proctoring System (React + FastAPI + WebRTC)

Hệ thống giám sát thi online theo thiết kế SOP, với các tính năng:
- **KYC Flow**: Xác thực danh tính (ID + selfie + face match)
- **Pre-exam Check-in**: Kiểm tra kỹ thuật (T-15')
- **Real-time Detection**: A1-A11 tự động phát hiện (face, tab, audio, OCR)
- **Rules Engine**: Escalation logic S1/S2/S3 theo SOP
- **Supervisor Console**: Live wall, timeline, hotkeys, control
- **Recording**: Ghi video camera + screen
- **ML Endpoints**: Mock YOLO/ArcFace/OCR/ASR (có thể thay bằng real service)

## Prerequisites
- Node.js 18+
- Python 3.10+

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Endpoints:**
- `GET /health` - Health check
- `WS /ws/{room_id}` - WebSocket signaling
- `GET /rooms/{room_id}/incidents` - Lấy incidents
- `POST /rooms/{room_id}/incidents` - Tạo incident
- `GET /rooms/{room_id}/sessions/{user_id}/summary` - Session summary
- `POST /ml/face/detect` - Face detection (mock)
- `POST /ml/face/embed` - ArcFace embedding (mock)
- `POST /ml/face/match` - Face matching (mock)
- `POST /ml/object/detect` - YOLO object detection (mock)
- `POST /ml/ocr/scan` - OCR màn hình (mock)

## Frontend (React Vite)

```bash
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173`.

**Environment variables** (optional):
```
VITE_SIGNALING_URL=http://localhost:8000
VITE_OCR_BLACKLIST=cheat,answer,google,chatgpt
VITE_OCR_INTERVAL_MS=6000
```

## Usage Flow

### Candidate:
1. Join với role "candidate"
2. **KYC Flow**: Upload ID → Chụp selfie → Xác minh (mock)
3. **Check-in**: Kiểm tra camera/mic/screen/network/battery
4. Bắt đầu thi: Camera/mic tự động, có thể share screen
5. Tự động phát hiện: A1 (mất mặt), A2 (nhiều mặt), A3 (tab switch), A5 (OCR), A6 (audio)

### Proctor:
1. Join với role "proctor"
2. Xem live wall nhiều thí sinh
3. Pin/focus một thí sinh
4. Tag incidents thủ công (A1-A11)
5. Chat với macro S1/S2/S3 (hotkeys: Ctrl+1/2/3)
6. Pause/End phiên thí sinh
7. Xem timeline incidents

## Features Implemented

### ✅ Trước giờ thi (T-15')
- [x] Check-in wizard (camera, mic, screen, network, battery)
- [x] KYC flow (ID upload + selfie + face match mock)
- [x] Checklist UI

### ✅ Trong giờ thi
- [x] WebRTC P2P (camera + mic + screen share)
- [x] A1: Face detection (mất mặt >30s)
- [x] A2: Multi-face detection
- [x] A3: Tab visibility/blur detection
- [x] A5: OCR màn hình (Tesseract.js) với blacklist
- [x] A6: Voice activity detection (WebAudio RMS)
- [x] Rules Engine: Escalation A1-A11 → S1/S2/S3
- [x] Recording service (client-side MediaRecorder)

### ✅ Supervisor Console
- [x] Live wall (grid nhiều thí sinh)
- [x] Pin/focus một thí sinh
- [x] Severity badges (S2/S3 count)
- [x] Timeline view incidents
- [x] Filter by candidate
- [x] Macro chat S1/S2/S3
- [x] Hotkeys (Ctrl+1/2/3)
- [x] Pause/End controls

### ✅ Backend Services
- [x] WebSocket signaling với routing
- [x] Rules Engine (escalation logic)
- [x] ML endpoints mock (YOLO/ArcFace/OCR/ASR)
- [x] Session summary API

## Architecture Notes

- **No Database**: Tất cả state in-memory (phù hợp demo/MVP)
- **No Auth**: Mock role/user (có thể thêm JWT sau)
- **P2P WebRTC**: Đơn giản, có thể nâng cấp SFU (mediasoup/janus)
- **ML Mock**: Endpoints trả về mock data, có thể thay bằng real service
- **Recording**: Client-side, có thể nâng cấp server-side (SFU record)

## Next Steps (Production)

1. **SFU**: Thay P2P bằng SFU cho scale
2. **Real ML**: Tích hợp YOLO/ArcFace thật (GPU inference)
3. **Database**: PostgreSQL cho persistence
4. **Auth**: JWT/OAuth2
5. **TURN**: Coturn cho NAT traversal
6. **Secure Browser**: Extension + native helper
7. **Server-side Recording**: SFU record → Object storage
8. **Observability**: Metrics, tracing, logging

## SOP Mapping

| Mã | Detection | Status |
|---|---|---|
| A1 | Face detector (mất mặt >30s) | ✅ |
| A2 | Multi-face (YOLO mock) | ✅ |
| A3 | Tab visibility/blur | ✅ |
| A4 | Screen share check | ✅ |
| A5 | OCR blacklist | ✅ |
| A6 | VAD (WebAudio) | ✅ |
| A7 | Object detection (YOLO mock) | ⚠️ Mock |
| A8 | VPN/IP check | ⚠️ Mock |
| A9 | Secure browser | ⚠️ Mock |
| A10 | Face match/liveness | ⚠️ Mock |
| A11 | Idle detection | ⚠️ Mock |

---

**Note**: Đây là MVP theo thiết kế. Các tính năng ML đang mock, có thể thay bằng real service khi có GPU/infrastructure.
