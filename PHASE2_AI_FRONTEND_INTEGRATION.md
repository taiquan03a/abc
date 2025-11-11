# Phase 2: Tích hợp AI Analysis vào Frontend ✅

## Vấn đề
Backend đã gửi thông báo AI analysis qua WebSocket nhưng frontend chưa lắng nghe và hiển thị.

## Giải pháp đã triển khai

### 1. Backend - Thêm `candidate_id` vào response (`main.py`)

**File:** `backend/main.py` - Line ~181

**Thay đổi:**
```python
if proctor:
    # Add candidate_id to results
    results["candidate_id"] = candidate_id
    
    await proctor.websocket.send_text(json.dumps({
        "type": "ai_analysis",
        "data": results
    }))
```

**Lý do:** Frontend cần biết analysis này thuộc về candidate nào để hiển thị đúng chỗ.

---

### 2. Frontend - Thêm State cho AI Analysis (`Proctor.jsx`)

**File:** `frontend/src/pages/Proctor.jsx` - Line ~92

**Thêm state:**
```jsx
const [aiAnalysis, setAiAnalysis] = useState({}) // candidateId -> latest analysis results
```

**Mục đích:** Lưu trữ kết quả phân tích AI mới nhất cho từng thí sinh.

---

### 3. Frontend - Lắng nghe WebSocket Message (`Proctor.jsx`)

**File:** `frontend/src/pages/Proctor.jsx` - Line ~548

**Thêm listener:**
```jsx
signaling.on('ai_analysis', (data) => {
  console.log('[AI Analysis] Received:', data)
  
  // Store latest analysis for this candidate
  setAiAnalysis(prev => ({
    ...prev,
    [data.candidate_id || 'unknown']: data
  }))
  
  // If there are alerts, add them as incidents
  if (data.analyses) {
    data.analyses.forEach(analysis => {
      const alert = analysis.result?.alert
      if (alert) {
        console.log('[AI Analysis] Alert:', alert)
        setIncidents(list => [...list, {
          id: Date.now() + Math.random(),
          userId: data.candidate_id,
          type: alert.type,
          level: alert.level,
          message: alert.message,
          timestamp: data.timestamp
        }])
      }
    })
  }
})
```

**Chức năng:**
- Nhận dữ liệu AI analysis từ WebSocket
- Lưu vào state `aiAnalysis`
- Tự động tạo incident nếu có alert (cảnh báo)
- Log ra console để debug

---

### 4. Frontend - Hiển thị AI Status Badge (`Proctor.jsx`)

**File:** `frontend/src/pages/Proctor.jsx` - Line ~745

**Thêm vào mỗi candidate card:**
```jsx
const analysis = aiAnalysis[uid]

{/* AI Analysis Status Badge */}
{analysis && (
  <div style={{ 
    position: 'absolute', 
    top: 8, 
    left: 8, 
    background: 'rgba(0,0,0,0.7)', 
    color: 'white', 
    padding: '4px 8px', 
    borderRadius: 4, 
    fontSize: 10,
    zIndex: 20,
    display: 'flex',
    alignItems: 'center',
    gap: 4
  }}>
    <span style={{ 
      width: 6, 
      height: 6, 
      borderRadius: '50%', 
      background: '#4ade80',
      animation: 'pulse 2s infinite'
    }}></span>
    AI: {analysis.scenario}
  </div>
)}
```

**Hiển thị:**
- Badge màu đen trong suốt ở góc trên bên trái video
- Chấm xanh nhấp nháy (pulse animation) - hiệu ứng "live"
- Text hiển thị scenario hiện tại (normal, no_face, search_engine, v.v.)

---

### 5. Frontend - Thêm CSS Animation (`Proctor.jsx`)

**File:** `frontend/src/pages/Proctor.jsx` - Line ~675

**Thêm style tag:**
```jsx
return (
  <>
    <style>{`
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
      }
    `}</style>
    <div style={{ display: 'grid', ... }}>
```

**Hiệu ứng:** Chấm xanh sẽ nhấp nháy liên tục với animation `pulse`.

---

## Kết quả

### 📊 Flow hoạt động:

```
Backend (every 2-5s)
  ↓
Generate mock analysis (mock_analyzer.py)
  ↓
Add candidate_id to results
  ↓
Send via WebSocket: {"type": "ai_analysis", "data": {...}}
  ↓
Frontend Proctor.jsx
  ↓
signaling.on('ai_analysis') receives data
  ↓
Update aiAnalysis state
  ↓
If alert exists → Add to incidents list
  ↓
Render AI badge with scenario name
```

### 🎨 UI hiển thị:

**Trong mỗi candidate card:**
```
┌─────────────────────────────────────┐
│ [🟢 AI: normal]   Candidate: user123│
│                                      │
│  ┌──────────┐    ┌──────────┐      │
│  │ Camera   │    │  Screen  │      │
│  │  Video   │    │   Video  │      │
│  └──────────┘    └──────────┘      │
│                                      │
│  [S3:2] [S2:5]                      │
└─────────────────────────────────────┘
```

**Khi có cảnh báo:**
```
┌─────────────────────────────────────┐
│ [🟢 AI: search_engine] Candidate: u1│
│                                      │
│  Incidents panel sẽ hiện:           │
│  ⚠️ B1 (S3) - Phát hiện công cụ     │
│     tìm kiếm trên màn hình          │
└─────────────────────────────────────┘
```

---

## Cách kiểm tra

### 1. Mở browser console (F12)
- Vào trang Proctor
- Xem log: `[AI Analysis] Received:` mỗi 2-5 giây

### 2. Kiểm tra UI
- Mỗi candidate card phải có badge "AI: scenario_name"
- Chấm xanh phải nhấp nháy
- Khi có alert, incidents panel tự động thêm mục mới

### 3. Kiểm tra Backend logs
```
[MOCK] Started analysis for candidate123 in room456
[MOCK] Generated analysis for candidate123: scenario=normal
[MOCK] Generated analysis for candidate123: scenario=search_engine
[MOCK] Alert generated: B1 (S3) - Phát hiện công cụ tìm kiếm trên màn hình
```

---

## Debug nếu không thấy

### Nếu không thấy badge:
1. Check console: có log `[AI Analysis] Received:` không?
   - **Không có** → Backend không gửi hoặc WebSocket chưa kết nối
   - **Có log** → Kiểm tra `data.candidate_id` có đúng không

2. Check state:
   ```jsx
   console.log('aiAnalysis state:', aiAnalysis)
   ```

### Nếu không thấy incidents:
1. Check alert có tồn tại: `analysis.result?.alert`
2. Check scenario: Chỉ một số scenario có alert (search_engine, no_face, etc.)

### Nếu backend không gửi:
1. Check `AI_ANALYSIS_ENABLED = True` trong `main.py`
2. Check auto-start logs khi candidate join:
   ```
   [AUTO] Auto-starting mock analysis for candidate...
   ```

---

## Các scenario và alert tương ứng

| Scenario | Tần suất | Alert? | Level | Message (Tiếng Việt) |
|----------|----------|--------|-------|----------------------|
| normal | 75% | ❌ | - | - |
| no_face | 8% | ✅ | S2 | Không phát hiện khuôn mặt |
| search_engine | 4% | ✅ | S3 | Phát hiện công cụ tìm kiếm |
| chat_app | 2% | ✅ | S3 | Phát hiện ứng dụng chat |
| looking_away | 3% | ✅ | S2 | Thí sinh nhìn ra ngoài màn hình |
| multiple_faces | 2% | ✅ | S3 | Phát hiện nhiều khuôn mặt |
| face_mismatch | 1% | ✅ | S4 | Khuôn mặt không khớp |
| face_turned | 2% | ✅ | S2 | Khuôn mặt quay đi |
| voice_detected | 2% | ✅ | S1 | Phát hiện hoạt động giọng nói |
| multiple_speakers | 1% | ✅ | S3 | Phát hiện nhiều người nói |

---

## Tổng kết

✅ **Đã hoàn thành:**
- Backend gửi AI analysis mỗi 2-5 giây
- Frontend nhận và lưu trữ trong state
- Hiển thị real-time badge với scenario name
- Auto tạo incident khi có alert
- Tất cả message đã được dịch sang tiếng Việt

🎯 **Sẵn sàng cho:**
- Testing toàn bộ flow
- Demo cho người dùng
- Chuyển sang Phase 2.3: Real AI Models

📝 **Lưu ý:**
- Badge hiện ở góc trên trái, không che video
- Pulse animation giúp thấy hệ thống đang hoạt động
- Mỗi alert sẽ tự động thêm vào incidents list
- Có thể filter incidents theo candidate bằng cách click "Select"
