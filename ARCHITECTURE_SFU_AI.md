# Kiến trúc Real-time AI Analysis với SFU + aiortc (1 Proctor)

## 🎯 Mục tiêu
- Backend nhận WebRTC streams từ nhiều candidates
- Xử lý AI real-time (face detection, OCR, audio analysis)
- Forward streams đến **1 proctor duy nhất**
- Generate incidents tự động

## 📊 Simple Overview

```
[Candidate 1]  ──┐
[Candidate 2]  ──┤ WebRTC Streams
[Candidate 3]  ──┤ (camera + screen + audio)
[Candidate N]  ──┤
                 │
                 ▼
         ┌───────────────┐
         │    Backend    │
         │    (SFU +     │
         │   AI Analysis)│
         └───────┬───────┘
                 │
      ┌──────────┴──────────┐
      │                     │
      ▼                     ▼
[AI Incidents]      [Forwarded Streams]
      │                     │
      └──────────┬──────────┘
                 │
                 ▼
           [1 Proctor]
         (Xem tất cả + Alerts)
```

---

## Tổng quan kiến trúc chi tiết

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CANDIDATE BROWSER(S)                                 │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│  │   Camera     │         │    Screen    │         │     Mic      │         │
│  │  MediaStream │         │ MediaStream  │         │ MediaStream  │         │
│  └──────┬───────┘         └──────┬───────┘         └──────┬───────┘         │
│         │                        │                        │                 │
│         └────────────────────────┴────────────────────────┘                 │
│                                  │                                          │
│                         RTCPeerConnection                                   │
│                                  │                                          │
│                                  │ WebRTC (video/audio tracks)             │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND SERVER (Python)                             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    SFU Manager (aiortc)                                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │  RTCPeerConnection (per Candidate)                               │  │ │
│  │  │  - Receive video tracks (camera + screen)                        │  │ │
│  │  │  - Receive audio track                                           │  │ │
│  │  │  - Forward to single Proctor                                     │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────┬────────────────────────────────────────┬─────────────────┘ │
│                │                                         │                   │
│                │ Forward tracks                          │                   │
│        ┌───────▼────────┐                       ┌────────▼───────┐          │
│        │  Frame Buffer  │                       │  Audio Buffer  │          │
│        │  Queue         │                       │  Queue         │          │
│        └───────┬────────┘                       └────────┬───────┘          │
│                │                                         │                   │
│    ┌───────────┴──────────────┬──────────────────────────┘                  │
│    │                           │                                             │
│    ▼                           ▼                                             │
│  ┌─────────────────────┐  ┌──────────────────────┐                         │
│  │   AI Processing      │  │  Audio Processing    │                         │
│  │   Pipeline           │  │  Pipeline            │                         │
│  │                      │  │                      │                         │
│  │  1. Face Detection   │  │  1. Voice Activity   │                         │
│  │     - YOLO/MTCNN     │  │     - VAD            │                         │
│  │  2. Face Recognition │  │  2. Speech Detection │                         │
│  │     - ArcFace        │  │  3. Background Noise │                         │
│  │  3. Pose Estimation  │  │                      │                         │
│  │  4. Object Detection │  └──────────┬───────────┘                         │
│  │  5. OCR (screen)     │             │                                     │
│  └──────────┬───────────┘             │                                     │
│             │                          │                                     │
│             └──────────────┬───────────┘                                     │
│                            │                                                 │
│                            ▼                                                 │
│                  ┌─────────────────────┐                                    │
│                  │   Rules Engine       │                                    │
│                  │  - Detect violations │                                    │
│                  │  - Generate incidents│                                    │
│                  │  - Calculate scores  │                                    │
│                  └──────────┬──────────┘                                     │
│                             │                                                │
│                             ▼                                                │
│                  ┌─────────────────────┐                                    │
│                  │   WebSocket          │                                    │
│                  │   To Proctor         │                                    │
│                  └──────────┬──────────┘                                     │
└─────────────────────────────┼────────────────────────────────────────────────┘
                              │
                              │ Real-time incidents & streams
                              │
                              ▼
                   ┌─────────────────────┐
                   │     PROCTOR         │
                   │     Browser         │
                   │  - View all streams │
                   │  - See AI alerts    │
                   │  - Control exam     │
                   └─────────────────────┘
```

---

## Chi tiết các thành phần

### 1. **Frontend (Candidate)**

#### 1.1 WebRTC Setup
```javascript
// Gửi camera + screen + audio đến backend
const pc = new RTCPeerConnection()

// Camera stream
const cameraStream = await getUserMedia({video: true, audio: true})
cameraStream.getTracks().forEach(track => {
  pc.addTrack(track, cameraStream)
})

// Screen stream
const screenStream = await getDisplayMedia({video: true})
screenStream.getTracks().forEach(track => {
  pc.addTrack(track, screenStream)
})

// Create offer và gửi đến backend
const offer = await pc.createOffer()
await pc.setLocalDescription(offer)

// Send qua WebSocket
websocket.send(JSON.stringify({
  type: 'offer',
  sdp: pc.localDescription,
  trackInfo: [
    {trackId: 'xxx', label: 'camera', kind: 'video'},
    {trackId: 'yyy', label: 'screen', kind: 'video'},
    {trackId: 'zzz', label: 'audio', kind: 'audio'}
  ]
}))
```

---

### 2. **Backend SFU (aiortc)**

#### 2.1 Nhận WebRTC Tracks
```python
from aiortc import RTCPeerConnection, VideoStreamTrack, AudioStreamTrack

class CandidateConnection:
    def __init__(self, pc: RTCPeerConnection):
        self.pc = pc
        self.camera_track = None
        self.screen_track = None
        self.audio_track = None
        
        @pc.on("track")
        async def on_track(track):
            if isinstance(track, VideoStreamTrack):
                # Identify camera vs screen by trackInfo
                if track_label == 'camera':
                    self.camera_track = track
                    asyncio.create_task(self.process_camera_frames(track))
                elif track_label == 'screen':
                    self.screen_track = track
                    asyncio.create_task(self.process_screen_frames(track))
            
            elif isinstance(track, AudioStreamTrack):
                self.audio_track = track
                asyncio.create_task(self.process_audio_frames(track))
    
    async def process_camera_frames(self, track):
        """Process camera frames for AI analysis"""
        while True:
            frame = await track.recv()  # av.VideoFrame
            # Frame có định dạng: width, height, format (yuv420p, rgb24, etc.)
            
            # Convert to numpy array
            img = frame.to_ndarray(format="bgr24")
            
            # Send to AI pipeline
            await ai_processor.process_camera_frame(img, self.user_id)
    
    async def process_screen_frames(self, track):
        """Process screen frames for OCR"""
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")
            
            # Send to OCR pipeline (lower frequency)
            await ai_processor.process_screen_frame(img, self.user_id)
    
    async def process_audio_frames(self, track):
        """Process audio for voice detection"""
        while True:
            frame = await track.recv()  # av.AudioFrame
            # Audio processing
            await ai_processor.process_audio(frame, self.user_id)
```

#### 2.2 Frame Buffer Queue
```python
import asyncio
from collections import deque

class FrameBuffer:
    """Buffer frames để xử lý bất đồng bộ"""
    def __init__(self, maxsize=30):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.last_frame = None
    
    async def put(self, frame):
        """Add frame, drop oldest if full"""
        try:
            self.queue.put_nowait(frame)
            self.last_frame = frame
        except asyncio.QueueFull:
            # Drop oldest frame
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(frame)
            except:
                pass
    
    async def get(self):
        """Get next frame for processing"""
        return await self.queue.get()
    
    def get_latest(self):
        """Get latest frame (non-blocking)"""
        return self.last_frame
```

---

### 3. **AI Processing Pipeline**

#### 3.1 Face Detection & Recognition
```python
import cv2
import numpy as np
from ultralytics import YOLO
import insightface

class FaceAnalyzer:
    def __init__(self):
        self.face_detector = YOLO('yolov8n-face.pt')
        self.face_recognizer = insightface.app.FaceAnalysis()
        self.face_recognizer.prepare(ctx_id=0)
        self.registered_faces = {}  # user_id -> embedding
    
    async def analyze_frame(self, frame, user_id):
        """
        Analyze frame for face violations
        Returns: {
            'face_count': int,
            'is_registered_face': bool,
            'pose_angle': float,
            'confidence': float
        }
        """
        # Detect faces
        results = self.face_detector(frame)
        faces = results[0].boxes
        
        face_count = len(faces)
        
        if face_count == 0:
            return {
                'violation': 'A1',  # Mất khuôn mặt
                'face_count': 0,
                'confidence': 0.0
            }
        
        if face_count > 1:
            return {
                'violation': 'A2',  # Nhiều khuôn mặt
                'face_count': face_count,
                'confidence': 0.9
            }
        
        # Get face embedding for verification
        face_embedding = self.face_recognizer.get(frame)[0].embedding
        
        # Compare with registered face
        if user_id in self.registered_faces:
            registered = self.registered_faces[user_id]
            similarity = np.dot(face_embedding, registered) / (
                np.linalg.norm(face_embedding) * np.linalg.norm(registered)
            )
            
            if similarity < 0.6:
                return {
                    'violation': 'A10',  # Nghi ngờ giả mạo
                    'face_count': 1,
                    'confidence': 1 - similarity
                }
        
        return {
            'violation': None,
            'face_count': 1,
            'confidence': 1.0
        }
```

#### 3.2 Screen OCR Analysis
```python
import pytesseract
from PIL import Image

class ScreenAnalyzer:
    def __init__(self):
        self.blacklist_keywords = [
            'chatgpt', 'google', 'stackoverflow', 
            'answer', 'cheat', 'solution'
        ]
    
    async def analyze_screen(self, frame, user_id):
        """
        OCR screen for blacklisted content
        """
        # Convert to PIL Image
        img = Image.fromarray(frame)
        
        # OCR
        text = pytesseract.image_to_string(img).lower()
        
        # Check blacklist
        detected = [kw for kw in self.blacklist_keywords if kw in text]
        
        if detected:
            return {
                'violation': 'A5',  # Tài liệu cấm
                'detected_keywords': detected,
                'confidence': 0.8
            }
        
        return {'violation': None}
```

#### 3.3 Audio Analysis
```python
import webrtcvad

class AudioAnalyzer:
    def __init__(self):
        self.vad = webrtcvad.Vad(3)  # Aggressiveness 3
        self.speech_duration = {}  # user_id -> duration
    
    async def analyze_audio(self, audio_frame, user_id):
        """
        Detect voice activity
        """
        # Convert audio frame to bytes
        audio_data = audio_frame.to_ndarray()
        
        # Check if speech
        is_speech = self.vad.is_speech(audio_data.tobytes(), sample_rate=16000)
        
        if is_speech:
            self.speech_duration[user_id] = self.speech_duration.get(user_id, 0) + 0.02
            
            # Alert if speaking too long
            if self.speech_duration[user_id] > 30:  # 30 seconds
                return {
                    'violation': 'A6',  # Âm thanh hội thoại
                    'duration': self.speech_duration[user_id]
                }
        else:
            # Reset counter if silence
            self.speech_duration[user_id] = 0
        
        return {'violation': None}
```

---

### 4. **AI Processor Coordinator**

```python
class AIProcessor:
    def __init__(self):
        self.face_analyzer = FaceAnalyzer()
        self.screen_analyzer = ScreenAnalyzer()
        self.audio_analyzer = AudioAnalyzer()
        
        # Processing rates
        self.camera_fps = 5  # Process 5 fps for face detection
        self.screen_interval = 6  # Process screen every 6 seconds
        self.audio_rate = 50  # Process audio every 50ms
        
        # Counters
        self.frame_counters = {}
        self.last_screen_time = {}
    
    async def process_camera_frame(self, frame, user_id):
        """Process camera frame at controlled rate"""
        # Rate limiting
        count = self.frame_counters.get(user_id, 0)
        self.frame_counters[user_id] = count + 1
        
        # Process every N frames to achieve target FPS
        if count % (30 // self.camera_fps) != 0:
            return
        
        # Analyze
        result = await self.face_analyzer.analyze_frame(frame, user_id)
        
        # If violation detected, send incident
        if result.get('violation'):
            await self.send_incident(user_id, result)
    
    async def process_screen_frame(self, frame, user_id):
        """Process screen frame at controlled rate"""
        now = time.time()
        last_time = self.last_screen_time.get(user_id, 0)
        
        if now - last_time < self.screen_interval:
            return
        
        self.last_screen_time[user_id] = now
        
        # Analyze
        result = await self.screen_analyzer.analyze_screen(frame, user_id)
        
        if result.get('violation'):
            await self.send_incident(user_id, result)
    
    async def process_audio(self, audio_frame, user_id):
        """Process audio frame"""
        result = await self.audio_analyzer.analyze_audio(audio_frame, user_id)
        
        if result.get('violation'):
            await self.send_incident(user_id, result)
    
    async def send_incident(self, user_id, result):
        """Send incident to WebSocket clients"""
        incident = {
            'type': 'incident',
            'userId': user_id,
            'tag': result['violation'],
            'confidence': result.get('confidence', 0.5),
            'timestamp': time.time(),
            'data': result
        }
        
        # Broadcast via WebSocket
        await websocket_manager.broadcast_incident(incident)
```

---

### 5. **Forward Streams đến Proctor (Đơn giản hóa)**

```python
class SFUManager:
    def __init__(self):
        # Candidate connections: user_id -> CandidateConnection
        self.candidates = {}
        
        # Single proctor connection
        self.proctor_pc = None
        self.proctor_user_id = None
    
    async def handle_proctor_connection(self, proctor_user_id):
        """Setup single proctor connection"""
        self.proctor_user_id = proctor_user_id
        self.proctor_pc = RTCPeerConnection()
        
        # Add all existing candidate tracks to proctor
        for candidate_id, candidate_conn in self.candidates.items():
            if candidate_conn.camera_track:
                self.proctor_pc.addTrack(candidate_conn.camera_track)
            if candidate_conn.screen_track:
                self.proctor_pc.addTrack(candidate_conn.screen_track)
            if candidate_conn.audio_track:
                self.proctor_pc.addTrack(candidate_conn.audio_track)
        
        # Create offer to proctor
        offer = await self.proctor_pc.createOffer()
        await self.proctor_pc.setLocalDescription(offer)
        
        return offer
    
    async def on_new_candidate_track(self, track, candidate_id):
        """When new candidate connects, forward to proctor"""
        if self.proctor_pc:
            self.proctor_pc.addTrack(track)
            
            # Renegotiate with proctor
            offer = await self.proctor_pc.createOffer()
            await self.proctor_pc.setLocalDescription(offer)
            
            # Send offer to proctor via WebSocket
            await self.send_to_proctor({
                'type': 'renegotiate',
                'sdp': offer
            })
```

---

## Data Flow Timeline

```
Time: 0ms
├─ Candidate: Camera frame captured
├─ WebRTC: Frame sent to backend
└─ Backend: Frame received (av.VideoFrame)

Time: 10ms
├─ Backend: Frame added to buffer
└─ AI Pipeline: Frame dequeued

Time: 50ms
├─ AI: Face detection running (YOLO inference ~40ms)
└─ AI: Face recognition running (ArcFace inference ~10ms)

Time: 60ms
├─ AI: Results ready
├─ Rules Engine: Check violations
└─ If violation → Generate incident

Time: 65ms
├─ WebSocket: Broadcast incident to proctors
└─ Proctor: Receive alert in real-time

Time: 100ms (next frame cycle)
└─ Repeat...
```

---

## Performance Considerations

### 1. **Processing Rate**
- Camera: 5 FPS (process every 6th frame from 30fps stream)
- Screen: Every 6 seconds (OCR is expensive)
- Audio: Every 50ms (20 FPS)

### 2. **GPU Usage**
- YOLO face detection: ~40ms per frame on GPU
- ArcFace: ~10ms per face
- Target: Process 5 fps = 200ms per frame budget ✓

### 3. **Memory (Simplified for 1 Proctor)**
- Frame buffer: Max 30 frames × 1920×1080×3 bytes = ~180MB per candidate
- With 10 candidates: ~1.8GB RAM
- **No duplication**: Single proctor receives forwarded tracks (không cần duplicate)

### 4. **Network Bandwidth (Simplified for 1 Proctor)**
- **Incoming**: 2 Mbps per candidate (1080p @ 30fps)
  - 10 candidates = 20 Mbps in
- **Outgoing to proctor**: 2 Mbps × số candidate đang xem
  - Nếu proctor xem 10 candidates = 20 Mbps out
- **Total**: 20 Mbps in + 20 Mbps out = **40 Mbps** (rất khả thi)

---

## Technology Stack

### Backend
- **FastAPI**: REST API + WebSocket
- **aiortc**: WebRTC implementation in Python
- **OpenCV**: Image processing
- **YOLO (Ultralytics)**: Face detection
- **InsightFace (ArcFace)**: Face recognition
- **Tesseract/PaddleOCR**: Screen OCR
- **webrtcvad**: Voice activity detection

### Dependencies
```bash
pip install fastapi uvicorn[standard]
pip install aiortc opencv-python numpy
pip install ultralytics insightface
pip install pytesseract pillow
pip install webrtcvad
```

---

## Deployment Architecture (Simplified for 1 Proctor)

```
┌─────────────────────────────────────────┐
│         Frontend (React + Vite)         │
│    - Candidate pages (nhiều)            │
│    - Proctor page (1)                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
        ┌──────────────────┐
        │   Backend        │
        │   FastAPI        │
        │   + aiortc       │
        │   + GPU (YOLO)   │
        │                  │
        │ Max: 10-20 candidates│
        └──────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
      ▼                       ▼
┌──────────────┐      ┌──────────────┐
│   Redis      │      │  PostgreSQL  │
│  (optional)  │      │  (Incidents) │
└──────────────┘      └──────────────┘
```

**Note**: Với 1 proctor, không cần load balancer hay clustering phức tạp

---

## 🎯 Simplified Flow (1 Proctor)

### Connection Flow:
```
1. Proctor connects → Backend tạo RTCPeerConnection cho proctor
2. Candidate 1 connects → Backend nhận tracks → Forward đến proctor
3. Candidate 2 connects → Backend nhận tracks → Forward đến proctor
4. Candidate N connects → Backend nhận tracks → Forward đến proctor
...
```

### Data Flow per Candidate:
```
Candidate
  └─> Camera (2 Mbps) ──┐
  └─> Screen (2 Mbps) ──┤
  └─> Audio (128 Kbps) ─┤
                        │
                        ▼
                   Backend (SFU)
                        │
                ┌───────┴────────┐
                │                │
                ▼                ▼
           AI Analysis      Forward to
           (async)          Proctor
                │                │
                ▼                │
           Incidents ────────────┘
                                 │
                                 ▼
                           Proctor sees:
                           - All candidate streams
                           - AI-generated alerts
```

### Advantages of 1 Proctor:
✅ **Đơn giản hơn**: Không cần quản lý multiple proctor connections
✅ **Ít bandwidth hơn**: Chỉ forward 1 lần, không duplicate
✅ **Easier debugging**: 1 connection path duy nhất
✅ **Lower latency**: Ít hop, ít processing

### Scale Limits:
- **Max candidates**: ~10-20 (giới hạn bởi proctor browser rendering)
- **Bandwidth**: 40 Mbps (20 in + 20 out) - OK cho 10 candidates
- **CPU/GPU**: YOLO processing 5fps × 10 candidates = 50 inferences/sec

---

## Next Steps để Implement

**Phase 1: Setup SFU cơ bản (2-3 ngày)**
1. Install aiortc dependencies
2. Create SFU service (nhận tracks từ 1 candidate)
3. Forward tracks đến proctor
4. Test WebRTC end-to-end

**Phase 2: AI Pipeline (3-5 ngày)**
5. Setup YOLO face detection
6. Setup ArcFace face recognition  
7. Setup Screen OCR (Tesseract/PaddleOCR)
8. Audio VAD

**Phase 3: Integration (2-3 ngày)**
9. Connect AI → Rules Engine
10. WebSocket broadcast incidents
11. Recording service
12. Performance optimization

**Total**: ~7-11 ngày development

---

Bạn muốn tôi bắt đầu implement từ bước nào?
