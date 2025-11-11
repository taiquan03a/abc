# Phase 1: SFU Setup - Installation Guide

## ✅ Changes Made

### Backend:
1. ✅ `backend/requirements.txt` - Added aiortc, aiohttp, av
2. ✅ `backend/sfu_service.py` - Created SFU manager service
3. ✅ `backend/main.py` - Integrated SFU with WebSocket handler

### Frontend:
4. ✅ `frontend/src/pages/Candidate.jsx` - Updated to accept answer from server
5. ✅ `frontend/src/pages/Proctor.jsx` - Added SFU mode detection and handling

---

## 🚀 Installation Steps

### 1. Install Backend Dependencies

```powershell
cd backend

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install new dependencies (aiortc may take 5-10 minutes)
pip install -r requirements.txt

# Verify installation
python -c "import aiortc; print('aiortc version:', aiortc.__version__)"
```

**Note:** aiortc installation requires:
- Visual C++ Build Tools (on Windows)
- May need to install: `pip install wheel setuptools`

---

## 🧪 Testing Phase 1

### Test 1: Check Backend Health

```powershell
# Start backend
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open browser: http://localhost:8000/health

Expected response:
```json
{
  "ok": true,
  "sfu_enabled": true,
  "mode": "SFU"
}
```

### Test 2: Start Frontend

```powershell
# In another terminal
cd frontend
npm run dev
```

### Test 3: Test SFU Connection

1. Open Proctor page: http://localhost:5173/proctor/room1/proctor1
   - Check console: Should see "=== SFU MODE ==="
   - Should see "Sending offer to SFU backend"

2. Open Candidate page: http://localhost:5173/candidate/room1/candidate1
   - Allow camera/mic permissions
   - Complete KYC and check-in
   - Check console: Should see "Received answer from: server"

3. Check Backend Logs:
   - Should see "Created answer for candidate candidate1"
   - Should see "Created answer for proctor proctor1"

4. Check Proctor Page:
   - Should receive video tracks from candidate
   - Videos should appear in grid

---

## 🐛 Troubleshooting

### Issue: "aiortc not available"
**Solution:** Install Visual C++ Build Tools or use WSL2

### Issue: No video in proctor
**Check:**
1. Backend logs - are tracks being received?
2. Browser console - check for WebRTC errors
3. Network tab - check WebSocket connection

### Issue: ICE connection failed
**Check:**
1. STUN server accessible
2. Firewall settings
3. ICE candidates in console

---

## 📊 Phase 1 Completion Checklist

- [ ] aiortc installed successfully
- [ ] Backend health check shows "SFU mode"
- [ ] Candidate can send streams to backend
- [ ] Proctor receives offer/answer from server
- [ ] Video tracks visible in proctor (at least camera)
- [ ] No console errors

---

## 🎯 Next: Phase 2 Preview

After Phase 1 works, we'll add:
- AI face detection (YOLO)
- Face recognition (ArcFace)
- Screen OCR
- Audio VAD

**Estimated time:** 3-5 days

---

## 📝 Known Limitations (Phase 1)

1. ⚠️ All tracks from all candidates shown in single "sfu-all" stream
   - Need to implement per-candidate track identification
2. ⚠️ No renegotiation when new candidate joins
   - Proctor needs to refresh to see new candidates
3. ⚠️ No AI analysis yet (Phase 2)

These will be fixed in upcoming phases.

---

## 💡 Testing Commands

### Quick Test Script (PowerShell)
```powershell
# Terminal 1: Backend
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload

# Terminal 2: Frontend  
cd frontend
npm run dev

# Terminal 3: Check health
curl http://localhost:8000/health

# Terminal 4: Check SFU stats
curl http://localhost:8000/rooms/room1/sfu/stats
```

---

## 📞 Need Help?

If you encounter issues:
1. Check backend console for errors
2. Check browser console (F12)
3. Verify all dependencies installed
4. Try P2P mode first (if SFU fails, should fallback)

Good luck! 🚀
