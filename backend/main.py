from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rules_engine import rules_engine

try:
    from ml_service import router as ml_router
except ImportError:
    ml_router = None


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

app = FastAPI(title="Proctoring Signaling Server", version="0.1.0")
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
    return {"ok": True}


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

        # Main loop for signaling messages
        while True:
            text = await websocket.receive_text()
            msg = json.loads(text)
            mtype = msg.get("type")

            # Relay SDP/ICE/chat/messages to others in room
            if mtype in {"offer", "answer", "ice", "chat"}:
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


# Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Note: Import ml_service may fail if dependencies missing - that's OK for MVP

