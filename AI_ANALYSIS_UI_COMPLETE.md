# ✅ Hoàn thành: Hiển thị AI Analysis trên giao diện Proctor và Candidate

## Những gì đã làm

### 1. ✅ Proctor - Thêm AI Analysis Status Panel

**File: `frontend/src/pages/Proctor.jsx`**

#### Panel hiển thị trạng thái AI (Line ~912)
```jsx
<h4>AI Analysis & Incidents</h4>

{/* AI Analysis Status Panel */}
<div style={{ marginBottom: 12, padding: 8, background: '#f0f8ff', border: '1px solid #b3d9ff', borderRadius: 4 }}>
  <div style={{ fontSize: 12, fontWeight: 'bold', marginBottom: 6, color: '#0066cc' }}>
    🤖 AI Monitoring Status
  </div>
  {Object.keys(aiAnalysis).length === 0 ? (
    <div style={{ fontSize: 11, color: '#666' }}>Chờ thí sinh kết nối...</div>
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {Object.entries(aiAnalysis).map(([candidateId, analysis]) => {
        const hasAlert = analysis?.analyses?.some(a => a.result?.alert)
        const alertCount = analysis?.analyses?.filter(a => a.result?.alert).length || 0
        return (
          <div key={candidateId} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            padding: 6,
            background: hasAlert ? '#fff3cd' : 'white',
            borderRadius: 4,
            fontSize: 11
          }}>
            <span style={{ 
              width: 8, 
              height: 8, 
              borderRadius: '50%', 
              background: hasAlert ? '#ff9800' : '#4ade80',
              animation: 'pulse 2s infinite'
            }}></span>
            <span style={{ fontWeight: 'bold' }}>{candidateId}</span>
            <span style={{ color: '#666' }}>→</span>
            <span>{analysis?.scenario || 'unknown'}</span>
            {alertCount > 0 && (
              <span style={{ marginLeft: 'auto', color: '#ff9800', fontWeight: 'bold' }}>
                ⚠️ {alertCount} alert{alertCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )}
</div>
```

**Hiển thị:**
- 🟢 Chấm xanh nhấp nháy khi không có alert (normal)
- 🟠 Chấm cam nhấp nháy khi có alert
- Tên candidate + scenario hiện tại
- Số lượng alert (nếu có)

#### Cải thiện Incidents List (Line ~1000+)
```jsx
// Timeline view
<div><b>{it.tag || it.type}</b> ...</div>
<div>{it.message || it.note}</div>

// Grid view  
<div><b>{it.tag || it.type}</b> ... by {it.by || it.from || it.userId}</div>
<div>{new Date(it.ts || it.timestamp).toLocaleTimeString()} - {it.message || it.note}</div>
```

**Cải tiến:**
- Hiển thị `it.type` nếu không có `it.tag` (cho AI alerts)
- Hiển thị `it.message` từ AI alerts
- Hiển thị `it.userId` cho alerts từ AI
- Hỗ trợ cả `it.ts` và `it.timestamp`

---

### 2. ✅ Candidate - Thêm AI Monitoring Status

**File: `frontend/src/pages/Candidate.jsx`**

#### Thêm state (Line ~26)
```jsx
const [aiStatus, setAiStatus] = useState(null) // Store AI monitoring status
const [recentAlerts, setRecentAlerts] = useState([]) // Store recent alerts (last 5)
```

#### Thêm listener (Line ~95)
```jsx
// Listen for AI analysis updates
signaling.on('ai_analysis', (data) => {
  console.log('[Candidate] AI Analysis received:', data)
  // Only process if this is for current candidate
  if (data.data?.candidate_id === userId) {
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
        setRecentAlerts(prev => [...alerts, ...prev].slice(0, 5))
      }
    }
  }
})
```

#### Hiển thị UI (Line ~632)
```jsx
{/* AI Monitoring Status Panel */}
{connected && aiStatus && (
  <div style={{ 
    padding: 12, 
    background: recentAlerts.length > 0 ? '#fff3cd' : '#d4edda', 
    border: `1px solid ${recentAlerts.length > 0 ? '#ffc107' : '#28a745'}`,
    borderRadius: 8, 
    marginBottom: 16 
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ 
        width: 10, 
        height: 10, 
        borderRadius: '50%', 
        background: recentAlerts.length > 0 ? '#ff9800' : '#28a745',
        animation: 'pulse 2s infinite'
      }}></span>
      <strong style={{ fontSize: 14 }}>🤖 AI đang theo dõi phiên thi của bạn</strong>
    </div>
    <div style={{ fontSize: 12, color: '#666' }}>
      Trạng thái: <span style={{ fontWeight: 'bold' }}>
        {aiStatus.scenario === 'normal' ? '✓ Bình thường' : `⚠ ${aiStatus.scenario}`}
      </span>
    </div>
    {recentAlerts.length > 0 && (
      <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #ffc107' }}>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#856404', marginBottom: 4 }}>
          Cảnh báo gần đây:
        </div>
        {recentAlerts.slice(0, 3).map((alert, idx) => (
          <div key={idx} style={{ fontSize: 11, color: '#856404', marginBottom: 2 }}>
            • {alert.message}
          </div>
        ))}
      </div>
    )}
  </div>
)}
```

**Hiển thị:**
- 🟢 Panel màu xanh khi không có alert
- 🟡 Panel màu vàng khi có alert
- Chấm nhấp nháy (xanh/cam)
- Text "AI đang theo dõi phiên thi của bạn"
- Trạng thái: "✓ Bình thường" hoặc "⚠ scenario_name"
- Danh sách 3 cảnh báo gần nhất (nếu có)

#### Thêm CSS animation (Line ~568)
```jsx
return (
  <>
    <style>{`
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
      }
    `}</style>
    <div>...
```

---

## Kết quả

### 🎨 UI Proctor:
```
┌─────────────────────────────────────┐
│ 🤖 AI Monitoring Status             │
├─────────────────────────────────────┤
│ 🟢 candidate123 → normal            │
│ 🟠 candidate456 → search_engine     │
│                    ⚠️ 2 alerts      │
└─────────────────────────────────────┘

Incidents:
├─ B1 (S3) by candidate456
│  10:30:15 - Phát hiện công cụ tìm kiếm...
├─ A1 (S2) by candidate123  
│  10:29:42 - Không phát hiện khuôn mặt...
└─ ...
```

### 🎨 UI Candidate:
```
┌───────────────────────────────────────────┐
│ 🟢 AI đang theo dõi phiên thi của bạn    │
│ Trạng thái: ✓ Bình thường                 │
└───────────────────────────────────────────┘

Khi có alert:
┌───────────────────────────────────────────┐
│ 🟠 AI đang theo dõi phiên thi của bạn    │
│ Trạng thái: ⚠ search_engine               │
│ ─────────────────────────────────────────│
│ Cảnh báo gần đây:                         │
│ • Phát hiện công cụ tìm kiếm trên màn hình│
│ • Không phát hiện khuôn mặt               │
└───────────────────────────────────────────┘
```

---

## Flow hoạt động

### Backend → Frontend:
```
Backend (every 2-5s)
  ↓
Generate AI analysis
  ↓
Send via WebSocket: {
  type: "ai_analysis",
  data: {
    candidate_id: "user123",
    scenario: "search_engine",
    analyses: [...]
  }
}
  ↓
Frontend Proctor:
  - Update aiAnalysis state
  - Display in status panel
  - Add alerts to incidents list
  ↓
Frontend Candidate (if userId matches):
  - Update aiStatus state
  - Add to recentAlerts array
  - Display warning banner
```

---

## Test checklist

### ✅ Proctor:
1. Mở `/proctor/room123/proctor1`
2. Đợi candidate join
3. Kiểm tra panel "AI Monitoring Status" xuất hiện
4. Thấy dòng với tên candidate + scenario
5. Khi có alert: thấy số lượng alert và màu cam
6. Incidents list hiển thị message tiếng Việt

### ✅ Candidate:
1. Mở `/candidate/room123/candidate1`
2. Hoàn thành KYC + Check-in
3. Sau vài giây, thấy banner "🤖 AI đang theo dõi phiên thi của bạn"
4. Banner màu xanh khi normal
5. Banner màu vàng + danh sách cảnh báo khi có alert
6. Message tiếng Việt hiển thị rõ ràng

---

## Console logs để debug

### Proctor:
```
[SignalingClient] Received message: ai_analysis {...}
[AI Analysis] Received: {type: "ai_analysis", data: {...}}
[AI Analysis] Alert: {type: "B1", level: "S3", message: "..."}
```

### Candidate:
```
[Candidate] AI Analysis received: {type: "ai_analysis", data: {...}}
```

---

## Các scenario hiển thị

| Scenario | Proctor Panel | Candidate Banner | Color |
|----------|---------------|------------------|-------|
| normal | 🟢 normal | ✓ Bình thường | Xanh |
| no_face | 🟠 no_face ⚠️ 1 alert | ⚠ no_face + Cảnh báo | Vàng |
| search_engine | 🟠 search_engine ⚠️ 1 alert | ⚠ search_engine + Cảnh báo | Vàng |
| multiple_faces | 🟠 multiple_faces ⚠️ 1 alert | ⚠ multiple_faces + Cảnh báo | Vàng |
| face_mismatch | 🔴 face_mismatch ⚠️ 1 alert | ⚠ face_mismatch + Cảnh báo | Đỏ (S4) |

---

## Tổng kết

✅ **Proctor:**
- Panel real-time với trạng thái mỗi candidate
- Incidents list hiển thị AI alerts với message tiếng Việt
- Visual indicators: màu sắc, badge count, pulse animation

✅ **Candidate:**
- Banner thông báo AI đang theo dõi
- Màu sắc thay đổi theo trạng thái (xanh/vàng)
- Hiển thị 3 cảnh báo gần nhất
- Giúp candidate nhận biết và tự điều chỉnh hành vi

✅ **UX Improvements:**
- Real-time feedback
- Clear visual hierarchy
- Tiếng Việt throughout
- Non-intrusive but informative

🎉 **Ready for testing!**
