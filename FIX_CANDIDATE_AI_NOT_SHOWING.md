# Fix: AI Analysis không hiển thị ở Candidate ✅

## Vấn đề
Backend chỉ gửi AI analysis message cho **proctor**, không gửi cho **candidate**.

## Nguyên nhân
Trong `backend/main.py`, hàm `_run_mock_analysis()` chỉ tìm và gửi cho proctor:

```python
# CHỈ GỬI CHO PROCTOR
for participant in room.participants.values():
    if participant.role == "proctor":
        proctor = participant
        break

if proctor:
    await proctor.websocket.send_text(json.dumps({
        "type": "ai_analysis",
        "data": results
    }))
```

## Giải pháp

### Backend - Gửi cho cả Proctor và Candidate

**File: `backend/main.py` - Line ~173**

```python
# Find proctor in room and send results
try:
    room = await rooms.get_or_create(room_id)
    proctor = None
    candidate = None
    
    # Tìm cả proctor và candidate
    for participant in room.participants.values():
        if participant.role == "proctor":
            proctor = participant
        elif participant.user_id == candidate_id:
            candidate = participant
    
    # Send to proctor
    if proctor:
        results["candidate_id"] = candidate_id
        
        await proctor.websocket.send_text(json.dumps({
            "type": "ai_analysis",
            "data": results
        }))
    
    # ✅ THÊM: Gửi cho candidate (để họ thấy trạng thái của mình)
    if candidate:
        await candidate.websocket.send_text(json.dumps({
            "type": "ai_analysis",
            "data": results
        }))
```

### Frontend - Cải thiện log để debug

**File: `frontend/src/pages/Candidate.jsx` - Line ~100**

```javascript
signaling.on('ai_analysis', (data) => {
  console.log('[Candidate] AI Analysis received:', data)
  console.log('[Candidate] Current userId:', userId, 'Data candidate_id:', data.data?.candidate_id)
  
  // Only process if this is for current candidate
  if (data.data?.candidate_id === userId) {
    console.log('[Candidate] ✅ Processing AI analysis for this candidate')
    setAiStatus(data.data)
    
    // If there are alerts, add to recent alerts (keep last 5)
    if (data.data?.analyses) {
      const alerts = data.data.analyses
        .filter(a => a.result?.alert)
        .map(a => ({
          ...a.result.alert,
          timestamp: data.data.timestamp
        }))
      
      if (alerts.length > 0) {
        console.log('[Candidate] ⚠️ Alerts found:', alerts.length)
        setRecentAlerts(prev => [...alerts, ...prev].slice(0, 5))
      }
    }
  } else {
    console.log('[Candidate] ❌ Skipping - not for this candidate')
  }
})
```

## Test sau khi fix

### 1. Restart backend
```bash
# Backend sẽ tự động reload nếu dùng --reload
# Hoặc Ctrl+C và chạy lại
cd backend
python -m uvicorn main:app --reload
```

### 2. Refresh frontend
- Refresh trang Candidate (Ctrl + Shift + R)

### 3. Kiểm tra console logs

**Console Candidate phải thấy:**
```
[SignalingClient] Received message: ai_analysis {...}
[Candidate] AI Analysis received: {type: "ai_analysis", data: {...}}
[Candidate] Current userId: candidate123 Data candidate_id: candidate123
[Candidate] ✅ Processing AI analysis for this candidate
```

**Nếu có alert:**
```
[Candidate] ⚠️ Alerts found: 2
```

### 4. Kiểm tra UI

**Candidate page phải hiển thị:**

✅ **Normal (không có alert):**
```
┌───────────────────────────────────────────┐
│ 🟢 AI đang theo dõi phiên thi của bạn    │
│ Trạng thái: ✓ Bình thường                 │
└───────────────────────────────────────────┘
```

⚠️ **Có alert:**
```
┌───────────────────────────────────────────┐
│ 🟠 AI đang theo dõi phiên thi của bạn    │
│ Trạng thái: ⚠ search_engine               │
│ ─────────────────────────────────────────│
│ Cảnh báo gần đây:                         │
│ • Phát hiện công cụ tìm kiếm trên màn hình│
│ • Không phát hiện khuôn mặt               │
└───────────────────────────────────────────┘
```

## Debug checklist

### ❌ Nếu vẫn không thấy banner:

**A. Kiểm tra backend log:**
```
[MOCK] Started analysis for candidate123 in room456
[MOCK] Generated analysis for candidate123: scenario=normal
```

**B. Kiểm tra frontend console:**
- Có `[SignalingClient] Received message: ai_analysis` → Backend đã gửi ✅
- Không có log → Backend chưa gửi hoặc WebSocket bị disconnect ❌

**C. Kiểm tra điều kiện hiển thị:**
```jsx
{connected && aiStatus && (
  <div>Banner sẽ hiện ở đây</div>
)}
```
- `connected` phải = `true`
- `aiStatus` phải có giá trị (không null)

**D. Kiểm tra userId matching:**
```javascript
if (data.data?.candidate_id === userId)
```
- `data.data.candidate_id` phải khớp với `userId` của candidate
- Check console log: `[Candidate] Current userId: ... Data candidate_id: ...`

## Flow hoàn chỉnh

```
Backend (_run_mock_analysis)
  ↓
Generate mock analysis
  ↓
Find participants in room:
  - proctor ✅
  - candidate ✅
  ↓
Send via WebSocket to BOTH:
  - proctor.websocket.send_text(...)
  - candidate.websocket.send_text(...)
  ↓
Frontend Proctor:
  - Receive message
  - Update aiAnalysis state
  - Display in status panel
  ↓
Frontend Candidate:
  - Receive message
  - Check: data.candidate_id === userId
  - Update aiStatus state
  - Display banner
  - Show alerts if any
```

## Tổng kết

✅ **Backend:** Gửi AI analysis cho cả proctor và candidate
✅ **Frontend Candidate:** Đã có listener và UI component
✅ **Logs:** Thêm debug logs chi tiết để dễ troubleshoot

🎯 **Kết quả:** 
- Proctor thấy trạng thái tất cả candidates
- Candidate thấy trạng thái của chính mình
- Real-time updates mỗi 2-5 giây
- Cảnh báo hiển thị rõ ràng cho cả hai bên
