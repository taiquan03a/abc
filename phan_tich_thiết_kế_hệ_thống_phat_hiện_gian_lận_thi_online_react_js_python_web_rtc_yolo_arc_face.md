# 1) Mục tiêu & phạm vi

**Mục tiêu:** Xây dựng hệ thống giám sát thi online theo thời gian thực, phát hiện và xử lý gian lận dựa trên camera, chia sẻ màn hình, âm thanh, và hành vi trình duyệt; hỗ trợ quy trình giám thị–thí sinh–ban tổ chức trước/đang/sau giờ thi.

**Phạm vi:**
- Frontend: ReactJS (SPA) chạy trong Secure Browser/Chrome.
- Backend: Python (FastAPI cho API + WebSocket/ WebRTC signaling), worker (Celery/Redis), model serving (YOLO, ArcFace, Liveness, ASR/OCR), DB (PostgreSQL), object storage (minio/S3), stream processing (Kafka/Redpanda tuỳ chọn).
- Truyền thông: WebRTC (camera/audio/screen), WebSocket (signaling & event bus tới client), gRPC nội bộ (service-to-service ML).
- Triển khai: K8s (Horizontal Pod Autoscaler), GPU nodes cho inference.

---

# 2) Kiến trúc tổng thể

```
[React Client]
  ├─ Secure Browser & Extension (tab guard, clipboard, process check)
  ├─ WebRTC Publisher: camera + mic + screenshare (getUserMedia)
  ├─ Local Pre-filter (blur/brightness check, fps, idle)
  └─ Event UI: cảnh báo, nhắc nhở, chat kỹ thuật

[API Gateway]
  ├─ AuthN/Z (JWT/OAuth2) + Policy Engine (OPA)
  └─ Routing tới services

[Signaling Service] (FastAPI/WebSocket)
  ├─ STUN/TURN (Coturn)
  └─ Session control (start/stop, renegotiate)

[Streaming Ingestion]
  ├─ WebRTC SFU (mediasoup/janus/ion-sfu) *khuyến nghị SFU*
  └─ RTP/WHIP/ WebRTC → FFmpeg/ GStreamer (trích keyframe, thumbnail)

[Realtime ML Services]
  ├─ Face Pipeline (ArcFace, face detection, liveness)
  ├─ Object/Human Pipeline (YOLO: multi-face, phone, book)
  ├─ OCR Pipeline (màn hình – tài liệu cấm)
  ├─ ASR/Audio (âm thanh hội thoại)
  └─ Behavior Engine (tab switch, VPN, secure-browser events)

[Rules & Decision Engine]
  ├─ Mapping A1–A11 → S1/S2/S3 theo ngưỡng
  └─ State machine phiên thi (cooldown, escalation, auto-pause)

[Supervisor Console]
  ├─ Live wall (N×N thí sinh), click-to-focus
  ├─ Timeline cảnh báo (tags, notes)
  ├─ Control: nhắc/ cảnh cáo/ tạm dừng/ kết thúc

[Storage]
  ├─ Object Store: video cam + screen, snapshots, audio
  ├─ DB: metadata, logs, cảnh báo, policy
  └─ Timeseries: Prometheus/Loki (metrics/logs)

[Offline Processing]
  ├─ Video summarization (key events), re-OCR, QA review
  └─ Report generator (PDF/HTML)
```

**Luồng dữ liệu chính:** Client → Signaling → SFU → (1) ML realtime (WebRTC→GStreamer→py pipeline) → Rules Engine → Event WS tới giám thị; đồng thời (2) record vào Object Store; sau thi (3) batch/async tổng hợp báo cáo.

---

# 3) Thiết kế chi tiết theo giai đoạn

## 3.1 Trước giờ thi (T−15’ → T0)
- **Check-in kỹ thuật**
  - `mediaProbe`: test camera/mic/fps/độ sáng; `screenShareProbe`; `secureBrowserProbe` (extension + native host).
  - Kiểm tra **số màn hình** qua `getDisplayMedia` + EDID (native helper nếu strict).
  - Pin/nguồn: navigator.getBattery, cảnh báo <20%.
- **Xác thực danh tính (KYC)**
  - Thu ảnh ID (MRZ/Barcode optional) + selfie.
  - Face match (ArcFace cosine ≥ 0.45–0.6 tuỳ chính sách); Liveness (RGB active/passive – blink, head pose; hoặc camera challenge).
- **Công bố chính sách & hậu quả**
  - Splash modal + eSign (hash chính sách + timestamp).
- **Kênh hỗ trợ**
  - Chat kỹ thuật one-to-one (WebSocket), preset checklist.

**Checklist UI** hiển thị để giám thị tick: camera rõ mặt, ánh sáng, chia sẻ màn hình, no-headphone, desk clean, single display.

## 3.2 Trong giờ thi
- **Streaming**: WebRTC up to SFU (720p/24fps khuyến nghị), simulcast 360p cho ML để tiết kiệm băng thông.
- **Realtime inference**
  - Face tracking: mất mặt (A1), nhiều khuôn mặt (A2), match profile, liveness drift.
  - Object & posture (YOLO): điện thoại/sách/tai nghe; head pose > θ trong Δt (nhìn lệch lâu).
  - Screen OCR: phát hiện từ khóa cấm, tên file/pdf viewer.
  - Audio/ASR: phát hiện hội thoại/đa giọng, RMS ồn kéo dài.
  - Behavior: tab switch (Page Visibility + extension), VPN/IP change, secure browser violations.
- **Rules & Escalation** theo bảng A1–A11 (mục 4) → tự động sinh sự kiện, gửi **Xác minh nhanh ≤20s** tới giám thị.
- **Supervisor Console**: live mosaic, severity badges, hotkeys (S1/S2/S3), timeline + comment, nút tạm dừng/kết thúc.

## 3.3 Sau giờ thi
- **Tổng hợp bằng chứng**: ghép timeline sự kiện với snapshots/video/ocr/audio.
- **Phân loại**: sạch / cần review / vi phạm (tự động + thủ công 2 tầng).
- **Thông báo kết quả**: gửi mail/webhook.
- **Lưu trữ & privacy**: encrypt-at-rest; TTL (vd 90 ngày); de-identification (blur/box) khi export.

---

# 4) Ma trận cảnh báo & quy tắc (A1–A11)

| Mã | Tình huống | Detection | Ngưỡng gợi ý | Hướng xử lý | Mức độ |
|---|---|---|---|---|---|
| A1 | Mất khuôn mặt | Face detector không thấy bbox liên tục | > 30s hoặc >3 lần/15’ | Nhắc, tái diễn → cảnh báo/tạm dừng | S1→S2 |
| A2 | Nhiều khuôn mặt | YOLO/face count ≥2 | ≥2 frames trong 3s | Tạm dừng, quay 360°, có người → kết thúc | S2→S3 |
| A3 | Chuyển tab | Page Visibility + extension log | L1=1–2; L2=3–4; L3≥5 | Nhắc → cảnh báo → tạm dừng; app cấm → S3 | S1→S3 |
| A4 | Không chia sẻ màn hình | Stream track ended | >60s | Yêu cầu bật lại, không hợp tác → kết thúc | S2→S3 |
| A5 | Tài liệu cấm trên màn hình | OCR từ khóa/regex | ≥1 bằng chứng rõ ràng | Tạm dừng, yêu cầu đóng; tái phạm → kết thúc | S2→S3 |
| A6 | Âm thanh hội thoại | VAD/ASR nhiều speaker | >30s hoặc từ khóa hỗ trợ | Nhắc, kéo dài/hỗ trợ → kết thúc | S2→S3 |
| A7 | Thiết bị phụ/đa màn hình | YOLO headphone/monitor; extension | phát hiện/tín hiệu từ OS | Yêu cầu tháo/ngắt; không tuân thủ → nâng mức | S2 |
| A8 | VPN/đổi IP lạ | IP change + ASN list | khác ASN/country giữa phiên | Nhắc tắt, nghi chia sẻ → tạm dừng xác minh | S1→S2 |
| A9 | Vi phạm Secure Browser | Extension watchdog | event từ extension | Tạm dừng, yêu cầu mở lại; tái phạm → kết thúc | S2→S3 |
| A10 | Nghi ngờ giả mạo | Face mismatch/liveness fail | cosine < 0.4 hoặc liveness fail | Tạm dừng, re-KYC; không đạt → kết thúc | S3 |
| A11 | Không hoạt động/không phản hồi | Idle (no key/mouse) + face freeze | >2 phút | Nhắc, nếu không phản hồi → kiểm tra mạng/tạm dừng | S1→S2 |

**Chú ý:** Ngưỡng cần hiệu chỉnh theo ROC/PR sau pilot.

---

# 5) Thiết kế mô-đun & giao diện

## 5.1 Frontend (React)
- Tech: React 18, TypeScript, Zustand/Redux Toolkit, WebRTC (adapter.js), WebSocket, Web Worker (pre-processing), WebAssembly (OCR lite nếu cần), Service Worker (offline assets cho secure browser).
- Chính:
  - `ExamApp`: state phiên thi, policy.
  - `MediaManager`: camera/mic/screen, kiểm soát bitrate (RTCRtpSender.setParameters), simulcast.
  - `ProbeWizard`: check-in T−15’.
  - `KYCFlow`: ID upload, selfie, challenge.
  - `SupervisorConsole`: mosaic, timeline, control panel.
  - `AlertsPanel`: A1–A11, mức S, tag/note.
  - `TechChat`: chat kỹ thuật 1–1.
- Bảo mật: full-screen enforced, clipboard guard, key combo block (extension), focus trap.

## 5.2 Backend (Python)
- Tech: FastAPI, Uvicorn, SQLAlchemy, Pydantic v2, Celery + Redis, Kafka, gRPC (ml.req/resp), aiortc/WHIP ingest, Coturn.
- Services tách:
  - **auth-svc** (JWT, MFA tuỳ chọn), **policy-svc**, **signaling-svc**, **realtime-ml-svc**, **rules-svc**, **exam-svc** (quản lý phiên), **recording-svc** (mux cam+screen), **report-svc**, **supervisor-svc** (WS fanout), **secure-ext-host** (native messaging).

## 5.3 ML Inference
- **Face**: Detection (SCRFD/RetinaFace), Embedding (ArcFace), Tracker (BYTE/OC-SORT), Liveness (depth/texture hoặc action challenge).
- **Object**: YOLOv7/8/11 tuỳ GPU (custom heads cho headphone/phone/book/monitor).
- **OCR**: PaddleOCR/Tesseract + whitelist từ khóa cấm.
- **Audio**: VAD (WebRTC VAD), diarization nhẹ, từ khóa “giải bài”, “tra cứu”… (list tuỳ ngôn ngữ).
- **Throughput mục tiêu**: 1 GPU T4 xử lý ~20–30 stream 360p@10–15fps (tối ưu batching + TensorRT), latency < 500ms end-to-end.

## 5.4 Rules & State Machine
- CEP đơn giản: cửa sổ thời gian (sliding windows), debouncing, hysteresis để giảm false positive.
- Escalation policy cấu hình theo tổ chức/kỳ thi; cooldown giữa các cảnh báo cùng loại.

---

# 6) API (ví dụ)

**Auth**
- `POST /auth/login` → {token}

**Signaling**
- `WS /signal` → events: `offer/answer/ice`, `join`, `pause`, `resume`.

**Exam session**
- `POST /exams/{examId}/sessions` → tạo phiên
- `PATCH /sessions/{id}`: pause/resume/end (giám thị)
- `GET /sessions/{id}/timeline`

**KYC**
- `POST /kyc/id` (upload ảnh ID)
- `POST /kyc/selfie`
- `POST /kyc/verify` → {score, liveness}

**Alerts**
- `POST /sessions/{id}/events` (client/ML push)
- `GET /sessions/{id}/events?type=A1`

**Reports**
- `POST /sessions/{id}/report`
- `GET /reports/{id}` (PDF/HTML)

**Policy**
- `GET /policy/{examId}`
- `PUT /policy/{examId}` (ngưỡng, bật/tắt liveness, 1 màn hình…)

---

# 7) Mô hình dữ liệu (DB)

```
users(id, email, role, org_id, status, created_at)
exams(id, org_id, name, start_at, end_at, policy_json)
sessions(id, exam_id, user_id, status, started_at, ended_at, ip, asn, device, risk_score)
kyc(id, user_id, doc_type, doc_hash, face_vec, liveness_score, verified_at)
streams(id, session_id, type[cam/screen/audio], webrtc_id, started_at, ended_at)
alerts(id, session_id, code[A1..A11], level[S1..S3], payload_json, created_at, actor[auto/mod])
notes(id, session_id, alert_id, author_id, note, created_at)
artifacts(id, session_id, type[image/video/ocr/asr], uri, meta_json, created_at)
secure_events(id, session_id, event_type, detail, created_at)
reports(id, session_id, verdict[clean/review/violation], summary, uri, created_at)
```

**Event schema (Kafka)**
```json
{
  "ts":"2025-11-08T10:00:00Z",
  "session_id":"...",
  "type":"alert",
  "code":"A2",
  "level":"S2",
  "metrics":{"face_count":2,"duration_ms":1800},
  "snap_uri":"s3://.../a2-...jpg"
}
```

---

# 8) Bảo mật, quyền riêng tư, tuân thủ

- **Transport:** TLS 1.3, DTLS-SRTP cho WebRTC.
- **Identity/Access:** OAuth2/OIDC, RBAC (thí sinh/giám thị/QA/admin), MFA cho giám thị.
- **Data-at-rest:** AES-256, KMS; tách bucket: `raw/processed/public-export`.
- **Privacy:** TTL dữ liệu (vd 90 ngày), pseudonym hóa khi export, quyền truy cập theo phòng thi, watermark bản ghi.
- **Secure Browser:** extension + native helper (Chromium) kiểm soát: task switch, process list (blacklist), multi-monitor, clipboard.
- **Compliance gợi ý:** GDPR (right to be forgotten), audit log, consent record, DPIA.

---

# 9) Hiệu năng & khả năng mở rộng

- **Target E2E latency:** ≤ 800ms (camera → cảnh báo UI).
- **Backpressure:** SFU + adaptive bitrate; drop frame ML bằng sampler (e.g. 10–15 fps).
- **Autoscaling:** HPA cho rules/WS; GPU autoscaler cho ML; queue depth → scale workers.
- **Recording**: chọn **server-side** (SFU record) để không phụ thuộc client; segment 1–2 phút HLS/MP4.
- **Cost control:** ưu tiên 360p cho ML, lưu keyframes + clip ngắn thay vì full nếu policy cho phép.

---

# 10) Chiến lược giảm false positive

- Multi-signal fusion (camera + screen + audio + behavior).
- Hysteresis & cooldown.
- Re-check sau 1–2s trước khi phát cảnh báo.
- Human-in-the-loop cho S2/S3; yêu cầu quay 360° với A2.
- Liên tục hiệu chỉnh ngưỡng từ dữ liệu pilot (ROC/PR, confusion matrix).

---

# 11) Logging, quan sát & an toàn vận hành

- Metrics: fps, bitrate, inference time, queue lag, alert rate/type.
- Tracing: OpenTelemetry (signaling → ML → rules).
- Logs: cấu trúc JSON; PII redaction trước khi ship.
- Alerting: tỷ lệ S3 bất thường, spike A3, lỗi liveness.
- Chaos testing: rớt mạng, loss 10–20%, jitter.

---

# 12) Xử lý sự cố & kịch bản dự phòng

- Mất camera: hướng dẫn fallback (đổi camera, giảm độ phân giải), giữ trạng thái pause.
- Mạng yếu: hạ bitrate, tắt screen temporally, ưu tiên camera.
- WebRTC thất bại P2P: ép route qua TURN.
- Model lỗi/GPU full: degrade sang CPU detector + giảm tần suất.

---

# 13) Kiểm thử & QA

- **Unit**: rules, policy, API contracts.
- **Load**: 1k concurrent sessions (no-ML) rồi 200–300 có ML trên 10 GPU.
- **E2E**: script puppeteer để mô phỏng hành vi A1–A11.
- **Bias & fairness**: kiểm định ArcFace across skin tones/lighting.
- **Security**: pentest extension/native helper, CSRF, JWT leak, TURN abuse.

---

# 14) Lộ trình triển khai (roadmap)

1. **MVP (4–6 tuần):** WebRTC + SFU, A1/A3/A4/A9 cơ bản, console giám thị, recording, báo cáo cơ bản.
2. **Phase 2:** ArcFace + liveness, YOLO headphone/phone, OCR màn hình, ASR VAD, rules nâng cao.
3. **Phase 3:** Tối ưu GPU (TensorRT), autoscaling, report 2 tầng, privacy tooling, BI dashboard.

---

# 15) Pseudocode tham khảo

**Client – tab switch logger**
```ts
// React hook
useEffect(() => {
  const onVis = () => ws.send({t:"visibility", hidden: document.hidden});
  document.addEventListener('visibilitychange', onVis);
  return () => document.removeEventListener('visibilitychange', onVis);
}, []);
```

**Server – rule A1 (mất khuôn mặt)**
```py
if event.type == 'face_tracks':
    if event.count == 0:
        state.a1_missing_since = state.a1_missing_since or now()
    else:
        state.a1_missing_since = None

if state.a1_missing_since and now()-state.a1_missing_since > 30s:
    emit_alert(session_id, code='A1', level='S1', payload={"dur":seconds})
```

**Server – escalation**
```py
def escalate(session, code):
    count = recent_alert_count(session, code, window=15*60)
    if code=='A3' and count>=4:
        set_session_status(session, 'paused')
        level='S2'
    else:
        level = 'S1'
    push_supervisor(session, {"code":code, "level":level})
```

---

# 16) Ma trận RACI & nhân sự

- **Product/Policy:** định nghĩa ngưỡng, quy tắc.
- **AI/ML:** training, eval, drift monitoring.
- **Backend/Infra:** signaling, SFU, storage, DB, CI/CD.
- **Frontend:** React app + supervisor console + extension.
- **Security/Compliance:** DPIA, audit, key management.

---

# 17) Rủi ro & biện pháp

- **Ánh sáng kém** → hướng dẫn chiếu sáng, auto-exposure, nâng ISO.
- **Đa dạng thiết bị** → chế độ tương thích, fallback TURN, bitrate adaptive.
- **VPN/doanh nghiệp chặn WebRTC** → fallback WHIP/HTTPS ingest.
- **Sai lệch mô hình** → retrain định kỳ, human review.

---

# 18) KPI đề xuất

- Mean time to alert (MTTA) < 1s.
- False positive rate (FPR) < 5% với A1/A3/A4.
- % phiên phải human review < 10% (mục tiêu sau tối ưu).
- Tỷ lệ hoàn tất KYC không trợ giúp > 95%.

---

# 19) Checklist triển khai nhanh

- [ ] SFU + STUN/TURN hoạt động ổn định
- [ ] Signaling WS HA + reconnect
- [ ] Ghi 360p stream cho ML + 720p cho record
- [ ] ArcFace/Liveness benchmark theo ánh sáng VN
- [ ] OCR dictionary tài liệu cấm theo môn thi
- [ ] Extension secure-browser và native helper
- [ ] Console giám thị + hotkeys + timeline
- [ ] Báo cáo sau thi + export PDF

---

> Tài liệu này có thể mở rộng thành SRS/SDD chính thức, thêm sơ đồ sequence UML và chi tiết triển khai theo hạ tầng cụ thể (on-prem/cloud).



---

# 20) Kế hoạch triển khai theo phase (đề xuất)

> Giả định team ~10–14 người (FE 3, BE 3, ML 3, QA 2, DevOps 2, PM/PO 1). Có thể thu nhỏ/mở rộng. Mỗi sprint 2 tuần.

## Phase 0 — Inception & Foundation (2–3 tuần)
**Mục tiêu:** Chốt yêu cầu, rủi ro, baseline kỹ thuật.
- Deliverables:
  - SRS/SAD v1, backlog ưu tiên (MoSCoW), ma trận A1–A11 cuối.
  - POC WebRTC + STUN/TURN + SFU hoạt động nội bộ.
  - Khung FastAPI + auth skeleton, schema DB v0.
  - CI/CD cơ bản (build, lint, test, container registry).
- Entry criteria: Có stakeholder & chính sách thi rõ; môi trường cloud/on-prem được cấp.
- Exit criteria: Demo call WebRTC 1–N, API auth login, migration DB chạy.
- Rủi ro chính: Môi trường mạng/TURN; quyết định secure-browser (extension/native helper).

## Phase 1 — MVP giám sát nền (4–6 tuần)
**Mục tiêu:** Vận hành được một kỳ thi nhỏ với các cảnh báo cốt lõi.
- Phạm vi/Deliverables:
  - Streaming WebRTC → SFU → record server-side (cam 720p, screen 720p tuỳ băng thông).
  - A1 (mất mặt), A3 (chuyển tab), A4 (mất screen), A9 (secure-browser event) — realtime + console giám thị.
  - Supervisor Console: mosaic, focus view, timeline sự kiện, S1/S2/S3 thủ công, chat kỹ thuật.
  - Báo cáo sau thi cơ bản (timeline + snapshot), lưu trữ 30–90 ngày.
  - Policy engine v1 (bật/tắt rule, ngưỡng, 1 màn hình).
- QA/Gates:
  - Load: 100 concurrent sessions qua SFU (no-ML) ổn định ≥ 60 phút.
  - E2E latency cảnh báo < 1s P50 / < 2s P95.
  - Security smoke: TLS/DTLS, JWT, CORS, rate limit.
- Exit criteria: Thi pilot nội bộ 20–50 thí sinh không sự cố blocker; MTBF ≥ 4 giờ.

## Phase 2 — Nhận diện & liveness (4–6 tuần)
**Mục tiêu:** KYC, ArcFace, liveness, YOLO cơ bản; giảm gian lận người thứ ba.
- Deliverables:
  - KYC flow: ID + selfie, face match (ArcFace), liveness (active/passive) với ngưỡng hiệu chỉnh.
  - YOLO: phát hiện headphone/phone/book; đa khuôn mặt (A2) + quay 360°.
  - OCR màn hình (từ khóa cấm cơ bản) → A5.
  - VAD/ASR nhẹ để A6 (âm thanh hội thoại) với ngưỡng thời lượng.
  - Escalation policy hoàn chỉnh theo bảng A1–A11.
- QA/Gates:
  - Độ chính xác: Face match ROC AUC ≥ 0.95 trên bộ dữ liệu pilot; FAR/FRR theo chính sách.
  - Liveness TPR ≥ 98% @ FPR ≤ 2% (pilot). YOLO mAP50 ≥ 0.85 cho class mục tiêu.
  - Throughput: 1 GPU T4 ≥ 20 stream 360p@10–15fps.
- Exit criteria: Thi pilot mở rộng 100–200 thí sinh, false positive A1/A3/A4 < 5%.

## Phase 3 — Scale-out & độ tin cậy (3–4 tuần)
**Mục tiêu:** Mở rộng, tối ưu chi phí, tăng độ bền.
- Deliverables:
  - Autoscaling (HPA + GPU autoscaler), queue-based backpressure.
  - Recording segment HLS/MP4, resume khi rớt mạng, TURN fallback.
  - Observability: metrics, tracing, alerting SLO (latency, drop rate).
  - Hardening secure-browser + native helper (đa màn hình, clipboard, hotkeys blacklist).
- QA/Gates:
  - Load: 300–500 concurrent (ML on) trên 8–12 GPU; error rate < 0.5%.
  - DR test: node failover, TURN outage, packet loss 10–20%.
- Exit criteria: Sẵn sàng mở rộng kỳ thi thật 500+ thí sinh.

## Phase 4 — Compliance, privacy & báo cáo nâng cao (2–3 tuần)
**Mục tiêu:** Chuẩn hóa tuân thủ và quy trình hậu kiểm 2 tầng.
- Deliverables:
  - Report 2 tầng (giám thị → QA), chữ ký số báo cáo, watermark.
  - Privacy tooling: TTL, pseudonymize khi export, right-to-be-forgotten.
  - Audit log & consent record; vai trò RBAC đầy đủ.
- Gates: Kiểm toán nội bộ bảo mật; DPIA/GDPR checklist đạt.
- Exit criteria: Được phê duyệt vận hành chính thức bởi tổ chức.

## Phase 5 — Analytics & tối ưu (liên tục)
**Mục tiêu:** Tối ưu FP/FN, chi phí GPU, trải nghiệm giám thị.
- Deliverables:
  - Dashboard BI: tỉ lệ cảnh báo theo mã, heatmap thời gian, ROC/PR theo phiên bản model.
  - A/B ngưỡng rule & model versioning; auto-retune theo kỳ thi.
  - Tối ưu pipeline (TensorRT, batching, frame sampler).
- KPIs: % phiên cần review < 10%; MTTA < 1s; chi phí/Giờ/Thí sinh giảm ≥ 20%.

---

## Bảng phân công & mốc kiểm soát (RACI rút gọn)

| Hạng mục | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---:|---:|---:|---:|---:|---:|
| WebRTC/SFU | R | R | C | R | C | C |
| Secure Browser | C | R | C | R | C | C |
| ML Face/Liveness | C | C | R | C | C | R |
| ML YOLO/OCR/ASR | C | C | R | C | C | R |
| Rules/Decision | C | R | R | C | C | R |
| Storage/Recording | C | R | C | R | C | C |
| Observability/SRE | C | C | C | R | R | R |
| Privacy/Compliance | A | C | C | C | R | C |
| QA & Test | R | R | R | R | R | R |

Legend: R = Responsible, A = Accountable, C = Consulted.

---

## Lịch biểu gợi ý (12–18 tuần)
- Tuần 1–3: Phase 0
- Tuần 4–9: Phase 1
- Tuần 10–15: Phase 2
- Tuần 16–19: Phase 3
- Tuần 20–22: Phase 4
- Tuần 23+: Phase 5 liên tục

---

## Tiêu chí chấp nhận tổng (DoD)
- Latency E2E cảnh báo P95 ≤ 2s trong điều kiện mạng thực tế.
- FPR tổng hợp cho A1/A3/A4 ≤ 5% trong 2 kỳ thi pilot.
- 100% hành động S1/S2/S3 có log, người thực hiện, timestamp.
- Toàn bộ dữ liệu nhạy cảm được mã hóa at-rest; TTL vận hành được.

---

## Phụ lục: non-goals của MVP
- Chấm điểm tự động nội dung bài thi.
- Nhận diện thiết bị phần cứng chuyên sâu ngoài scope (ví dụ HWID spoofing mức kernel).
- Phát hiện gian lận bằng mô hình ngôn ngữ lớn trong giai đoạn đầu.

