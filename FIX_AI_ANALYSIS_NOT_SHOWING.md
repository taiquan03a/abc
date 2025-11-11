# Fix: AI Analysis không hiển thị trong Proctor ✅

## Vấn đề
Backend đã gửi message `ai_analysis` qua WebSocket (đã verify bằng test script) nhưng frontend Proctor không nhận được.

## Nguyên nhân
**Frontend listeners chỉ được đăng ký trong P2P mode, KHÔNG được đăng ký trong SFU mode!**

```jsx
if (sfuMode) {
  await signaling.connect()  // ❌ Connect trước khi đăng ký listeners!
  // ... SFU logic
} else {
  // P2P Mode
  signaling.on('ai_analysis', ...) // ✅ Chỉ có trong P2P
  await signaling.connect()
}
```

## Giải pháp
Di chuyển listeners cho `chat`, `incident`, và `ai_analysis` vào SFU mode block, TRƯỚC khi `signaling.connect()`.

### File: `frontend/src/pages/Proctor.jsx` - Line ~117

**Thêm vào SFU mode block:**
```jsx
if (sfuMode) {
  console.log('=== SFU MODE ===')
  
  // Register message listeners BEFORE connecting
  signaling.on('chat', (data) => {
    setMsgs(m => [...m, { from: data.from, text: data.text }])
  })
  
  signaling.on('incident', (data) => {
    setIncidents(list => [...list, { ...data, id: Date.now() + Math.random() }])
  })
  
  signaling.on('ai_analysis', (data) => {
    console.log('[AI Analysis] Received:', data)
    // Store latest analysis for this candidate
    setAiAnalysis(prev => ({
      ...prev,
      [data.data?.candidate_id || 'unknown']: data.data  // ⚠️ Chú ý: data.data
    }))
    
    // If there are alerts, add them as incidents
    if (data.data?.analyses) {
      data.data.analyses.forEach(analysis => {
        const alert = analysis.result?.alert
        if (alert) {
          console.log('[AI Analysis] Alert:', alert)
          setIncidents(list => [...list, {
            id: Date.now() + Math.random(),
            userId: data.data.candidate_id,
            type: alert.type,
            level: alert.level,
            message: alert.message,
            timestamp: data.data.timestamp
          }])
        }
      })
    }
  })
  
  await signaling.connect()  // ✅ Connect SAU khi đã đăng ký
  // ...
}
```

### Lưu ý quan trọng
**Backend gửi:** `{type: "ai_analysis", data: {...}}`
**Frontend phải truy cập:** `data.data.candidate_id` (không phải `data.candidate_id`)

## Verify fix hoạt động

### 1. Test backend (đã verify ✅)
```bash
cd backend
python test_websocket_ai.py
```

**Expected output:**
```
🤖 AI ANALYSIS: {'type': 'ai_analysis', 'data': {...}}
   Scenario: search_engine
   Candidate: candidate456
```

### 2. Test frontend
1. Mở browser console (F12)
2. Vào `/proctor/room123/proctor1`
3. Mở tab khác `/candidate/room123/candidate1`
4. Trong console proctor, sau 2-5 giây phải thấy:

```
[SignalingClient] Received message: ai_analysis {...}
[AI Analysis] Received: {type: "ai_analysis", data: {...}}
```

5. Kiểm tra UI - phải có badge "AI: scenario_name" ở góc video
6. Khi có alert (search_engine, no_face, etc.) - incidents panel tự động thêm mục mới

### 3. Debug nếu vẫn không thấy

**A. Kiểm tra backend có gửi không:**
```
[MOCK] Started analysis for candidate1 in room123
[MOCK] Generated analysis for candidate1: scenario=normal
```

**B. Kiểm tra frontend có nhận không:**
```
[SignalingClient] Received message: ai_analysis
```

- **Không thấy log này** → Listener không được đăng ký hoặc đăng ký sai
- **Thấy log** → Kiểm tra `data.data.candidate_id` có đúng không

**C. Kiểm tra structure của message:**
```js
console.log('Full message:', JSON.stringify(data, null, 2))
```

## Files đã sửa

1. ✅ `frontend/src/lib/signaling.js` - Thêm debug log cho mọi message
2. ✅ `frontend/src/pages/Proctor.jsx` - Di chuyển listeners vào SFU mode block
3. ✅ `backend/main.py` - Thêm debug logs cho auto-start

## Test script helper

File: `backend/test_websocket_ai.py`
- Simulate proctor + candidate connection
- Verify backend sends `ai_analysis` message
- Check message structure

## Tổng kết

✅ **Root cause:** Listeners không được đăng ký trong SFU mode
✅ **Fix:** Di chuyển listeners vào SFU block, TRƯỚC `signaling.connect()`
✅ **Verified:** Backend đang gửi đúng message structure
✅ **Next:** Reload frontend và test lại

## Checklist test sau khi fix

- [ ] Refresh browser (Ctrl + Shift + R để clear cache)
- [ ] Mở console (F12)
- [ ] Proctor join room
- [ ] Candidate join room
- [ ] Đợi 2-5 giây
- [ ] Thấy log `[AI Analysis] Received:`
- [ ] Thấy badge "AI: scenario_name"
- [ ] Khi có alert, thấy mục mới trong incidents panel
