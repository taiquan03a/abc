from __future__ import annotations

import asyncio
import json
import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rules_engine import rules_engine

# Suppress specific aioice/asyncio warnings that occur during cleanup
warnings.filterwarnings("ignore", message=".*NoneType.*has no attribute.*")
logging.getLogger("aioice").setLevel(logging.ERROR)

try:
    from ml_service import router as ml_router
except ImportError:
    ml_router = None

try:
    from sfu_service import sfu_manager
    SFU_ENABLED = sfu_manager.is_available()
except ImportError:
    sfu_manager = None
    SFU_ENABLED = False

try:
    from ai_analysis import MockAIAnalyzer
    mock_analyzer = MockAIAnalyzer()
    AI_ANALYSIS_ENABLED = True
except ImportError:
    mock_analyzer = None
    AI_ANALYSIS_ENABLED = False


@dataclass
class Participant:
    websocket: WebSocket
    role: str  # "proctor" | "candidate" | "observer"
    user_id: str


@dataclass
class Room:
    room_id: str
    participants: Dict[str, Participant] = field(default_factory=dict)
    incidents: List[dict] = field(default_factory=list)

    async def broadcast(self, sender_id: str, message: dict):
        target_id = message.get("to")
        payload = json.dumps({"from": sender_id, **message})
        if target_id:
            # Route only to target if present
            target = self.participants.get(str(target_id))
            if target:
                try:
                    await target.websocket.send_text(payload)
                except RuntimeError:
                    pass
            return
        # Fanout to all except sender
        for pid, participant in list(self.participants.items()):
            if pid == sender_id:
                continue
            try:
                await participant.websocket.send_text(payload)
            except RuntimeError:
                # Skip if closed
                pass


class RoomManager:
    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, room_id: str) -> Room:
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = Room(room_id=room_id)
            return self._rooms[room_id]

    async def remove_if_empty(self, room_id: str):
        async with self._lock:
            room = self._rooms.get(room_id)
            if room and not room.participants:
                del self._rooms[room_id]


rooms = RoomManager()

# Global dict to track analysis tasks: candidate_id -> asyncio.Task
analysis_tasks: Dict[str, asyncio.Task] = {}

# Custom exception handler to suppress ICE cleanup errors
def custom_exception_handler(loop, context):
    """Suppress aioice/asyncio cleanup errors"""
    exception = context.get('exception')
    message = context.get('message', '')
    
    # Ignore specific cleanup errors
    if exception and isinstance(exception, AttributeError):
        error_msg = str(exception)
        if "NoneType" in error_msg and ("sendto" in error_msg or "call_exception_handler" in error_msg):
            # This is a known cleanup issue with aioice, ignore it
            return
    
    # For other exceptions, use default handler
    loop.default_exception_handler(context)

# Set the custom exception handler for the event loop
try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(custom_exception_handler)
except RuntimeError:
    # If no event loop is running, it will be set when FastAPI starts
    pass

app = FastAPI(title="Proctoring Signaling Server", version="0.1.0")

@app.on_event("startup")
async def startup_event():
    """Set exception handler on startup"""
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(custom_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if ml_router:
    app.include_router(ml_router)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "sfu_enabled": SFU_ENABLED,
        "ai_analysis_enabled": AI_ANALYSIS_ENABLED,
        "mode": "SFU" if SFU_ENABLED else "P2P"
    }


# ==================== AI ANALYSIS ENDPOINTS ====================

async def _run_mock_analysis(room_id: str, candidate_id: str):
    """
    Background task that runs mock AI analysis periodically
    """
    if not AI_ANALYSIS_ENABLED:
        print(f"[MOCK] AI Analysis not enabled")
        return
    
    print(f"[MOCK] Started analysis for {candidate_id} in room {room_id}")
    
    try:
        while candidate_id in analysis_tasks:
            # Generate mock AI analysis
            results = mock_analyzer.analyze_frame(candidate_id, room_id)
            
            print(f"[MOCK] Generated analysis for {candidate_id}: scenario={results.get('scenario')}")
            
            # Find proctor in room and send results
            try:
                room = await rooms.get_or_create(room_id)
                proctor = None
                candidate = None
                
                for participant in room.participants.values():
                    if participant.role == "proctor":
                        proctor = participant
                    elif participant.user_id == candidate_id:
                        candidate = participant
                
                # Send to proctor
                if proctor:
                    # Add candidate_id to results
                    results["candidate_id"] = candidate_id
                    
                    await proctor.websocket.send_text(json.dumps({
                        "type": "ai_analysis",
                        "data": results
                    }))
                
                # Also send to candidate (so they can see their own status)
                if candidate:
                    await candidate.websocket.send_text(json.dumps({
                        "type": "ai_analysis",
                        "data": results
                    }))
                    
                    # Check for alerts and log incidents
                    for analysis in results.get("analyses", []):
                        alert = analysis.get("result", {}).get("alert")
                        if alert:
                            print(f"[MOCK] Alert generated: {alert['type']} ({alert['level']}) - {alert['message']}")
                            
                            # Log to incidents (optional - already handled in rules_engine)
                            # rules_engine can pick this up from WebSocket messages
                
            except Exception as e:
                print(f"[MOCK] Error broadcasting analysis: {e}")
            
            # Wait 2-5 seconds before next analysis
            import random
            await asyncio.sleep(random.uniform(2, 5))
    
    except asyncio.CancelledError:
        print(f"[MOCK] Analysis cancelled for {candidate_id}")
    except Exception as e:
        print(f"[MOCK] Error in analysis loop for {candidate_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[MOCK] Stopped analysis for {candidate_id}")


@app.post("/api/analysis/start/{room_id}/{candidate_id}")
async def start_mock_analysis(room_id: str, candidate_id: str):
    """
    Start mock AI analysis for a candidate
    
    This creates a background task that generates mock AI analysis results
    every 2-5 seconds and sends them to the proctor via WebSocket.
    """
    if not AI_ANALYSIS_ENABLED:
        raise HTTPException(status_code=503, detail="AI Analysis not available")
    
    # Check if already running
    if candidate_id in analysis_tasks:
        return {
            "status": "already_running",
            "candidate_id": candidate_id,
            "room_id": room_id
        }
    
    # Create background task
    task = asyncio.create_task(_run_mock_analysis(room_id, candidate_id))
    analysis_tasks[candidate_id] = task
    
    print(f"[API] Started mock analysis for {candidate_id} in room {room_id}")
    
    return {
        "status": "started",
        "candidate_id": candidate_id,
        "room_id": room_id
    }


@app.post("/api/analysis/stop/{candidate_id}")
async def stop_mock_analysis(candidate_id: str):
    """
    Stop mock AI analysis for a candidate
    
    This cancels the background task and cleans up resources.
    """
    if candidate_id not in analysis_tasks:
        return {
            "status": "not_running",
            "candidate_id": candidate_id
        }
    
    # Cancel the task
    task = analysis_tasks[candidate_id]
    task.cancel()
    
    # Wait a bit for cancellation
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    
    # Remove from dict
    del analysis_tasks[candidate_id]
    
    print(f"[API] Stopped mock analysis for {candidate_id}")
    
    return {
        "status": "stopped",
        "candidate_id": candidate_id
    }


@app.get("/api/analysis/history/{room_id}/{candidate_id}")
async def get_analysis_history(
    room_id: str,
    candidate_id: str,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    level: Optional[str] = None,
    type: Optional[str] = None
):
    """
    Get analysis history (incidents) for a candidate
    
    Query parameters:
    - from_ts: Filter incidents from this timestamp (ms)
    - to_ts: Filter incidents to this timestamp (ms)
    - level: Filter by severity level (S1/S2/S3/S4)
    - type: Filter by incident type (A1/A2/B1/etc.)
    """
    try:
        # Get incidents from rules_engine
        session_summary = rules_engine.get_session_summary(room_id, candidate_id)
        incidents = session_summary.get("incidents", [])
        
        # Apply filters
        if from_ts:
            incidents = [i for i in incidents if i.get("ts", 0) >= from_ts]
        
        if to_ts:
            incidents = [i for i in incidents if i.get("ts", 0) <= to_ts]
        
        if level:
            incidents = [i for i in incidents if i.get("level") == level]
        
        if type:
            incidents = [i for i in incidents if i.get("tag") == type]
        
        # Calculate summary statistics
        summary = {
            "S1": len([i for i in incidents if i.get("level") == "S1"]),
            "S2": len([i for i in incidents if i.get("level") == "S2"]),
            "S3": len([i for i in incidents if i.get("level") == "S3"]),
            "S4": len([i for i in incidents if i.get("level") == "S4"])
        }
        
        return {
            "candidate_id": candidate_id,
            "room_id": room_id,
            "total_incidents": len(incidents),
            "summary": summary,
            "incidents": incidents
        }
    
    except KeyError:
        raise HTTPException(status_code=404, detail="Candidate not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    participant: Optional[Participant] = None
    room: Optional[Room] = None
    try:
        # First message must be a join with {type:"join", userId, role}
        join_raw = await websocket.receive_text()
        join_msg = json.loads(join_raw)
        if join_msg.get("type") != "join":
            await websocket.send_text(json.dumps({"type": "error", "reason": "expected_join"}))
            await websocket.close()
            return

        user_id = str(join_msg.get("userId"))
        role = str(join_msg.get("role", "candidate"))
        if not user_id:
            await websocket.send_text(json.dumps({"type": "error", "reason": "missing_userId"}))
            await websocket.close()
            return

        room = await rooms.get_or_create(room_id)
        participant = Participant(websocket=websocket, role=role, user_id=user_id)
        room.participants[user_id] = participant

        # Notify current roster
        roster = [
            {"userId": p.user_id, "role": p.role}
            for p in room.participants.values()
        ]
        await websocket.send_text(json.dumps({"type": "roster", "participants": roster}))

        # Broadcast join event
        join_event = {"type": "participant_joined", "userId": user_id, "role": role}
        for pid, p in room.participants.items():
            if pid != user_id:
                try:
                    await p.websocket.send_text(json.dumps(join_event))
                except RuntimeError:
                    pass
        
        # Auto-start mock AI analysis for candidates (if enabled and SFU mode)
        if role == "candidate" and SFU_ENABLED and AI_ANALYSIS_ENABLED:
            print(f"[AUTO] Checking auto-start for {user_id}, current tasks: {list(analysis_tasks.keys())}")
            if user_id not in analysis_tasks:
                print(f"[AUTO] Auto-starting mock analysis for candidate {user_id}")
                task = asyncio.create_task(_run_mock_analysis(room_id, user_id))
                analysis_tasks[user_id] = task
            else:
                print(f"[AUTO] Analysis already running for {user_id}")
        else:
            print(f"[AUTO] Not starting analysis: role={role}, SFU={SFU_ENABLED}, AI={AI_ANALYSIS_ENABLED}")

        # Main loop for signaling messages
        while True:
            text = await websocket.receive_text()
            msg = json.loads(text)
            mtype = msg.get("type")

            # Relay SDP/ICE/chat/messages to others in room
            if mtype in {"offer", "answer", "ice", "chat"}:
                # If SFU is enabled, handle WebRTC signaling via SFU
                if SFU_ENABLED and mtype == "offer":
                    track_info = msg.get("trackInfo", [])
                    print(f"[SFU] Received offer from {user_id} (role={role})")
                    
                    if role == "candidate":
                        # Candidate sending streams to backend
                        try:
                            print(f"[SFU] Handling candidate offer from {user_id}", flush=True)
                            print(f"[DEBUG] About to call handle_candidate_offer", flush=True)
                            print(f"[DEBUG] sfu_manager = {sfu_manager}", flush=True)
                            print(f"[DEBUG] offer_sdp type = {type(msg.get('sdp'))}", flush=True)
                            result = await sfu_manager.handle_candidate_offer(
                                room_id=room_id,
                                user_id=user_id,
                                offer_sdp=msg.get("sdp"),
                                track_info=track_info
                            )
                            
                            # Extract answer SDP
                            answer_sdp = {
                                "sdp": result["sdp"],
                                "type": result["type"]
                            }
                            
                            # Send answer back to candidate
                            await websocket.send_text(json.dumps({
                                "type": "answer",
                                "sdp": answer_sdp,
                                "from": "server"
                            }))
                            print(f"[SFU] Sent answer to candidate {user_id}", flush=True)
                            
                            # Check if there's a pending renegotiation (tracks received in on_track)
                            # Poll with longer intervals to give time for offer creation
                            print(f"[DEBUG] Polling for renegotiation offer...", flush=True)
                            await asyncio.sleep(0.4)  # Initial wait: 400ms
                            renegotiate_offer = sfu_manager.get_pending_renegotiate()
                            
                            # Poll multiple times with longer delays
                            poll_count = 1
                            while not renegotiate_offer and poll_count < 5:
                                print(f"[DEBUG] No offer yet, polling again (attempt {poll_count + 1}/5)...", flush=True)
                                await asyncio.sleep(0.3)  # 300ms between polls
                                renegotiate_offer = sfu_manager.get_pending_renegotiate()
                                poll_count += 1
                            
                            if renegotiate_offer:
                                proctor_id = renegotiate_offer.get("proctor_id")
                                print(f"[SFU] Renegotiating: sending new offer to proctor {proctor_id}")
                                
                                # Find proctor's websocket in room
                                room = await rooms.get_or_create(room_id)
                                proctor_participant = room.participants.get(proctor_id)
                                if proctor_participant:
                                    await proctor_participant.websocket.send_text(json.dumps({
                                        "type": "offer",
                                        "sdp": {
                                            "sdp": renegotiate_offer["sdp"],
                                            "type": renegotiate_offer["type"]
                                        },
                                        "from": "server",
                                        "renegotiate": True
                                    }))
                                    print(f"[SFU] Sent renegotiation offer to proctor {proctor_id}")
                                else:
                                    print(f"[SFU] Warning: Proctor {proctor_id} not found in room participants")
                            
                        except Exception as e:
                            print(f"[SFU] Candidate offer error: {e}")
                            import traceback
                            traceback.print_exc()
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "reason": f"sfu_error: {str(e)}"
                            }))
                    
                    elif role == "proctor":
                        # Proctor requesting streams from backend
                        try:
                            print(f"[SFU] Handling proctor offer from {user_id}")
                            answer = await sfu_manager.handle_proctor_offer(
                                room_id=room_id,
                                user_id=user_id,
                                offer_sdp=msg.get("sdp")
                            )
                            # Send answer back to proctor
                            await websocket.send_text(json.dumps({
                                "type": "answer",
                                "sdp": answer,
                                "from": "server"
                            }))
                            print(f"[SFU] Sent answer to proctor {user_id}")
                        except Exception as e:
                            print(f"[SFU] Proctor offer error: {e}")
                            import traceback
                            traceback.print_exc()
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "reason": f"sfu_error: {str(e)}"
                            }))
                
                elif SFU_ENABLED and mtype == "ice":
                    # Handle ICE candidate via SFU
                    is_proctor = (role == "proctor")
                    print(f"[SFU] Received ICE candidate from {user_id} (proctor={is_proctor})")
                    try:
                        await sfu_manager.add_ice_candidate(
                            room_id=room_id,
                            user_id=user_id,
                            candidate_dict=msg.get("candidate"),
                            is_proctor=is_proctor
                        )
                    except Exception as e:
                        print(f"[SFU] ICE error: {e}")
                
                elif SFU_ENABLED and mtype == "answer":
                    # Handle answer from proctor (renegotiation response)
                    if role == "proctor":
                        print(f"[SFU] Received answer from proctor {user_id} (renegotiation)")
                        try:
                            await sfu_manager.handle_proctor_answer(
                                room_id=room_id,
                                answer_sdp=msg.get("sdp")
                            )
                            print(f"[SFU] Applied proctor answer")
                        except Exception as e:
                            print(f"[SFU] Proctor answer error: {e}")
                            import traceback
                            traceback.print_exc()
                
                else:
                    # Fallback: P2P mode or chat - relay to others
                    await room.broadcast(sender_id=user_id, message=msg)
            elif mtype == "leave":
                break
            elif mtype == "incident":
                # {type:"incident", tag, level, note, ts, by}
                incident = {
                    "roomId": room.room_id,
                    "by": msg.get("by", user_id),
                    "tag": msg.get("tag"),
                    "level": msg.get("level"),
                    "note": msg.get("note"),
                    "ts": msg.get("ts"),
                }
                # Process through rules engine
                processed = rules_engine.process_incident(room.room_id, user_id, incident)
                room.incidents.append(processed)
                # fanout for live sync
                await room.broadcast(sender_id=user_id, message={"type": "incident", **processed})
            else:
                await websocket.send_text(json.dumps({"type": "error", "reason": "unknown_type"}))

    except WebSocketDisconnect:
        pass
    finally:
        if room and participant:
            # Clean up AI analysis tasks
            if AI_ANALYSIS_ENABLED and participant.role == "candidate":
                if user_id in analysis_tasks:
                    print(f"[AUTO] Auto-stopping mock analysis for candidate {user_id}")
                    task = analysis_tasks[user_id]
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                    del analysis_tasks[user_id]
            
            # Clean up SFU connections
            if SFU_ENABLED:
                try:
                    role = participant.role
                    if role == "candidate":
                        await sfu_manager._cleanup_candidate(room_id, user_id)
                        print(f"[SFU] Cleaned up candidate {user_id} connection", flush=True)
                    elif role == "proctor":
                        await sfu_manager._cleanup_proctor(room_id)
                        print(f"[SFU] Cleaned up proctor connection", flush=True)
                except Exception as e:
                    print(f"[SFU] Error during cleanup: {e}", flush=True)
            
            room.participants.pop(participant.user_id, None)
            # Notify others
            leave_event = {"type": "participant_left", "userId": participant.user_id}
            for p in list(room.participants.values()):
                try:
                    await p.websocket.send_text(json.dumps(leave_event))
                except RuntimeError:
                    pass
            await rooms.remove_if_empty(room.room_id)


@app.get("/rooms/{room_id}/incidents")
async def get_incidents(room_id: str):
    room = await rooms.get_or_create(room_id)
    return JSONResponse(room.incidents)


@app.post("/rooms/{room_id}/incidents")
async def post_incident(room_id: str, body: dict):
    room = await rooms.get_or_create(room_id)
    required = ["tag", "level", "note", "ts", "by"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=400, detail="missing fields")
    incident = {"roomId": room_id, **body}
    room.incidents.append(incident)
    return {"ok": True}


@app.get("/rooms/{room_id}/sessions/{user_id}/summary")
async def get_session_summary(room_id: str, user_id: str):
    """Lấy summary session từ rules engine"""
    summary = rules_engine.get_session_summary(room_id, user_id)
    return JSONResponse(summary)


@app.get("/rooms/{room_id}/sfu/stats")
async def get_sfu_stats(room_id: str):
    """Lấy thống kê SFU cho room"""
    if not SFU_ENABLED:
        raise HTTPException(status_code=503, detail="SFU not enabled")
    stats = sfu_manager.get_room_stats(room_id)
    return JSONResponse(stats)


# Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Note: Import ml_service may fail if dependencies missing - that's OK for MVP

