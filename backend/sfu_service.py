"""
SFU (Selective Forwarding Unit) Service - Phase 1
Forward WebRTC streams from candidates to single proctor
"""
import asyncio
import logging
from typing import Dict, Optional
from dataclasses import dataclass

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate
    from aiortc.sdp import candidate_from_sdp
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    MediaStreamTrack = None
    RTCIceCandidate = None
    candidate_from_sdp = None

logger = logging.getLogger(__name__)


@dataclass
class CandidateConnection:
    """Represents a candidate's WebRTC connection"""
    pc: 'RTCPeerConnection'
    user_id: str
    room_id: str
    camera_track: Optional['MediaStreamTrack'] = None
    screen_track: Optional['MediaStreamTrack'] = None
    audio_track: Optional['MediaStreamTrack'] = None
    track_labels: dict = None  # trackId -> label mapping
    
    def __post_init__(self):
        if self.track_labels is None:
            self.track_labels = {}


@dataclass
class ProctorConnection:
    """Represents the proctor's WebRTC connection"""
    pc: 'RTCPeerConnection'
    user_id: str
    room_id: str


class SFUManager:
    """
    Manages WebRTC connections for stream forwarding
    
    Flow:
    1. Candidates connect → Backend receives their tracks
    2. Proctor connects → Backend forwards all candidate tracks to proctor
    3. New candidates join → Renegotiate with proctor to add new tracks
    """
    
    def __init__(self):
        if not AIORTC_AVAILABLE:
            logger.warning("aiortc not available - SFU disabled")
        
        # room_id -> candidate_user_id -> CandidateConnection
        self._candidates: Dict[str, Dict[str, CandidateConnection]] = {}
        
        # room_id -> ProctorConnection (single proctor per room)
        self._proctors: Dict[str, ProctorConnection] = {}
        
        self._lock = asyncio.Lock()
        
        # Track metadata: track_id -> label (camera/screen/audio)
        self._track_labels: Dict[str, str] = {}
        
        # Pending renegotiation offer (for delivery to proctor)
        self._pending_renegotiate = None
        
        # Renegotiation debounce: track_count per candidate to batch multiple tracks
        self._renegotiate_pending = {}  # room_id -> bool
        
        # Callback for renegotiation ready (to notify main.py immediately)
        self._renegotiate_callback = None
    
    def set_renegotiate_callback(self, callback):
        """Set callback to be called when renegotiation offer is ready"""
        self._renegotiate_callback = callback
    
    async def handle_candidate_offer(
        self, 
        room_id: str, 
        user_id: str, 
        offer_sdp: dict,
        track_info: list = None
    ) -> dict:
        """
        Handle offer from candidate
        Returns answer SDP
        
        If candidate already has a connection, this is a renegotiation (e.g., screen share added)
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available")
        
        print(f"[DEBUG] Starting handle_candidate_offer for {user_id}", flush=True)
        
        async with self._lock:
            print(f"[DEBUG] Acquired lock for {user_id}", flush=True)
            
            # Check if this is a renegotiation (candidate already connected)
            existing_candidates = self._candidates.get(room_id, {})
            existing_conn = existing_candidates.get(user_id)
            
            if existing_conn:
                print(f"[RENEGOTIATE] Candidate {user_id} is renegotiating (e.g., added screen share)", flush=True)
                # This is a renegotiation - update existing connection
                pc = existing_conn.pc
                
                # Update track info
                if track_info:
                    for info in track_info:
                        track_id = info.get('trackId')
                        label = info.get('label')
                        if track_id and label:
                            existing_conn.track_labels[track_id] = label
                            self._track_labels[track_id] = label
                
                print(f"[RENEGOTIATE] Updated track info: {existing_conn.track_labels}", flush=True)
                
                # Set new remote description (new offer from candidate)
                await pc.setRemoteDescription(RTCSessionDescription(
                    sdp=offer_sdp['sdp'],
                    type=offer_sdp['type']
                ))
                
                print(f"[RENEGOTIATE] Set new remote description, creating answer", flush=True)
                
                # Create new answer
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                
                print(f"[RENEGOTIATE] Created answer for {user_id}, tracks will fire in on_track", flush=True)
                
                return {
                    "sdp": pc.localDescription.sdp,
                    "type": pc.localDescription.type
                }
            
            # Not a renegotiation - create new connection
            print(f"[DEBUG] Creating new connection for {user_id}", flush=True)
            
            # Create peer connection for candidate
            pc = RTCPeerConnection()
            print(f"[DEBUG] Created RTCPeerConnection for {user_id}", flush=True)
            
            # Prepare track labels
            track_labels = {}
            if track_info:
                for info in track_info:
                    track_id = info.get('trackId')
                    label = info.get('label')
                    if track_id and label:
                        track_labels[track_id] = label
                        self._track_labels[track_id] = label
            
            candidate_conn = CandidateConnection(
                pc=pc,
                user_id=user_id,
                room_id=room_id,
                track_labels=track_labels
            )
            print(f"[DEBUG] Created CandidateConnection for {user_id}", flush=True)
            
            print(f"Candidate {user_id} track info: {track_labels}")
            
            print(f"[DEBUG] About to setup track handlers for {user_id}", flush=True)
            
            # Handle incoming tracks from candidate
            @pc.on("track")
            async def on_track(track):
                print(f"[TRACK] Received track from candidate {user_id}: kind={track.kind}, id={track.id}", flush=True)
                
                # Identify track type using track_info stored in candidate_conn
                track_label = candidate_conn.track_labels.get(track.id, '')
                print(f"[TRACK] Track label for {track.id}: '{track_label}'", flush=True)
                
                if track.kind == "video":
                    if track_label == "camera":
                        candidate_conn.camera_track = track
                        print(f"Set camera track for candidate {user_id}")
                    elif track_label == "screen":
                        candidate_conn.screen_track = track
                        print(f"Set screen track for candidate {user_id}")
                    else:
                        # Fallback: first video = camera, second = screen
                        if not candidate_conn.camera_track:
                            candidate_conn.camera_track = track
                            print(f"Set camera track (fallback) for {user_id}")
                        else:
                            candidate_conn.screen_track = track
                            print(f"Set screen track (fallback) for {user_id}")
                
                elif track.kind == "audio":
                    candidate_conn.audio_track = track
                    print(f"Set audio track for candidate {user_id}")
                
                # Forward track to proctor if connected
                # Run renegotiation in background to avoid blocking on_track
                proctor_conn = self._proctors.get(room_id)
                print(f"[DEBUG] on_track: proctor_conn={proctor_conn}, renegotiate_pending={self._renegotiate_pending.get(room_id)}", flush=True)
                
                # Always allow renegotiation for new tracks (screen share can be added later)
                if proctor_conn:
                    # Check if we should trigger renegotiation
                    should_renegotiate = False
                    
                    if not self._renegotiate_pending.get(room_id):
                        # Not currently renegotiating
                        should_renegotiate = True
                    elif track.kind == "video" and track_label == "screen":
                        # Screen share is being added - force renegotiation even if pending
                        print(f"[RENEGOTIATE] Screen track detected, forcing renegotiation", flush=True)
                        should_renegotiate = True
                        # Wait for any pending renegotiation to complete
                        await asyncio.sleep(0.3)
                    
                    if should_renegotiate:
                        self._renegotiate_pending[room_id] = True
                        print(f"[RENEGOTIATE] Triggering renegotiation for {user_id} (track: {track_label or track.kind})", flush=True)
                        
                        # Schedule renegotiation as background task with direct WebSocket access
                        asyncio.create_task(self._do_renegotiation(
                            room_id=room_id,
                            user_id=user_id,
                            candidate_conn=candidate_conn,
                            proctor_conn=proctor_conn,
                            is_screen_track=(track.kind == "video" and track_label == "screen"),
                            rooms_manager=True  # Flag to enable direct sending
                        ))
            
            @pc.on("connectionstatechange")
            async def on_connection_state():
                print(f"[CONNSTATE] Candidate {user_id} connection state: {pc.connectionState}", flush=True)
                if pc.connectionState in ["failed", "closed"]:
                    await self._cleanup_candidate(room_id, user_id)
            
            print(f"[DEBUG] About to setRemoteDescription for {user_id}", flush=True)
            
            # Set remote description (offer from candidate)
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=offer_sdp['sdp'],
                type=offer_sdp['type']
            ))
            
            print(f"[DEBUG] Set remote description for candidate {user_id}", flush=True)
            print(f"[DEBUG] Transceivers: {len(pc.getTransceivers())}", flush=True)
            for idx, transceiver in enumerate(pc.getTransceivers()):
                print(f"[DEBUG]   Transceiver {idx}: mid={transceiver.mid}, direction={transceiver.direction}, kind={transceiver.receiver.track.kind if transceiver.receiver.track else 'None'}", flush=True)
            
            print(f"[DEBUG] About to createAnswer for {user_id}", flush=True)
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            print(f"[DEBUG] Created and set answer for {user_id}", flush=True)
            
            # Store connection
            if room_id not in self._candidates:
                self._candidates[room_id] = {}
            self._candidates[room_id][user_id] = candidate_conn
            
            print(f"Created answer for candidate {user_id} in room {room_id}")
            
            # Note: Renegotiation with proctor will happen automatically in on_track handler
            # when tracks are received
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
    
    async def handle_proctor_offer(
        self,
        room_id: str,
        user_id: str,
        offer_sdp: dict
    ) -> dict:
        """
        Handle offer from proctor
        Returns answer SDP with all candidate tracks (or recvonly if no candidates yet)
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available")
        
        async with self._lock:
            # Create peer connection for proctor
            pc = RTCPeerConnection()
            
            proctor_conn = ProctorConnection(
                pc=pc,
                user_id=user_id,
                room_id=room_id
            )
            
            @pc.on("connectionstatechange")
            async def on_connection_state():
                print(f"Proctor {user_id} connection state: {pc.connectionState}")
                if pc.connectionState in ["failed", "closed"]:
                    await self._cleanup_proctor(room_id)
            
            # Set remote description (offer from proctor)
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=offer_sdp['sdp'],
                type=offer_sdp['type']
            ))
            
            # Add all existing candidate tracks to proctor's PC
            candidates = self._candidates.get(room_id, {})
            track_count = 0
            
            for candidate_id, candidate_conn in candidates.items():
                if candidate_conn.camera_track:
                    pc.addTrack(candidate_conn.camera_track)
                    track_count += 1
                    print(f"Added camera track from {candidate_id} to proctor")
                
                if candidate_conn.screen_track:
                    pc.addTrack(candidate_conn.screen_track)
                    track_count += 1
                    print(f"Added screen track from {candidate_id} to proctor")
                
                if candidate_conn.audio_track:
                    pc.addTrack(candidate_conn.audio_track)
                    track_count += 1
                    print(f"Added audio track from {candidate_id} to proctor")
            
            print(f"Added {track_count} tracks to proctor {user_id}")
            
            # If no tracks yet, we need to add dummy transceivers to be able to receive tracks later
            if track_count == 0:
                logger.warning(f"No candidates yet, proctor will connect with no tracks initially")
                # Don't add dummy transceivers - just create answer as-is
                # Renegotiation will add tracks when candidates join
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            # Store proctor connection
            self._proctors[room_id] = proctor_conn
            
            print(f"Created answer for proctor {user_id} in room {room_id}")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
    
    async def _do_renegotiation(
        self,
        room_id: str,
        user_id: str,
        candidate_conn: CandidateConnection,
        proctor_conn: ProctorConnection,
        is_screen_track: bool = False,
        rooms_manager = None  # Pass RoomManager to send directly
    ):
        """
        Perform renegotiation in background task to avoid blocking on_track
        """
        try:
            # Wait briefly for all tracks to arrive
            # For screen share (single track), wait less time
            if is_screen_track:
                await asyncio.sleep(0.05)  # 50ms for screen share
            else:
                await asyncio.sleep(0.2)   # 200ms for initial connection (multiple tracks)
            
            print(f"[RENEGOTIATE] Checking tracks from {user_id} to add to proctor", flush=True)
            
            # Get existing track IDs in proctor connection
            existing_track_ids = set()
            for sender in proctor_conn.pc.getSenders():
                if sender.track:
                    existing_track_ids.add(sender.track.id)
            
            print(f"[RENEGOTIATE] Existing tracks in proctor: {existing_track_ids}", flush=True)
            
            # Add only NEW tracks from this candidate
            track_count = 0
            if candidate_conn.camera_track and candidate_conn.camera_track.id not in existing_track_ids:
                proctor_conn.pc.addTrack(candidate_conn.camera_track)
                print(f"  - Added camera track (id={candidate_conn.camera_track.id})", flush=True)
                track_count += 1
            elif candidate_conn.camera_track:
                print(f"  - Skipped camera track (already added)", flush=True)
                
            if candidate_conn.screen_track and candidate_conn.screen_track.id not in existing_track_ids:
                proctor_conn.pc.addTrack(candidate_conn.screen_track)
                print(f"  - Added screen track (id={candidate_conn.screen_track.id})", flush=True)
                track_count += 1
            elif candidate_conn.screen_track:
                print(f"  - Skipped screen track (already added)", flush=True)
                
            if candidate_conn.audio_track and candidate_conn.audio_track.id not in existing_track_ids:
                proctor_conn.pc.addTrack(candidate_conn.audio_track)
                print(f"  - Added audio track (id={candidate_conn.audio_track.id})", flush=True)
                track_count += 1
            elif candidate_conn.audio_track:
                print(f"  - Skipped audio track (already added)", flush=True)
            
            print(f"[RENEGOTIATE] Total NEW tracks added: {track_count}", flush=True)
            
            # Only create offer if we added new tracks
            if track_count > 0:
                print(f"[RENEGOTIATE] Starting createOffer()...", flush=True)
                # Create new offer for renegotiation
                offer = await proctor_conn.pc.createOffer()
                print(f"[RENEGOTIATE] createOffer() completed, setting local description...", flush=True)
                await proctor_conn.pc.setLocalDescription(offer)
                print(f"[RENEGOTIATE] setLocalDescription() completed", flush=True)
                
                # Store for delivery to proctor
                self._pending_renegotiate = {
                    "sdp": proctor_conn.pc.localDescription.sdp,
                    "type": proctor_conn.pc.localDescription.type,
                    "room_id": room_id,
                    "proctor_id": proctor_conn.user_id,
                    "candidate_id": user_id
                }
                print(f"[RENEGOTIATE] Created offer, stored for delivery to proctor", flush=True)
                
                # If rooms_manager is provided, send offer directly to proctor
                if rooms_manager:
                    print(f"[RENEGOTIATE] Sending offer directly to proctor via WebSocket", flush=True)
                    try:
                        import json
                        # Import at runtime to avoid circular dependency
                        import sys
                        main_module = sys.modules.get('main')
                        if main_module and hasattr(main_module, 'rooms'):
                            rooms = main_module.rooms
                            room = await rooms.get_or_create(room_id)
                            proctor_participant = room.participants.get(proctor_conn.user_id)
                            if proctor_participant:
                                await proctor_participant.websocket.send_text(json.dumps({
                                    "type": "offer",
                                    "sdp": {
                                        "sdp": self._pending_renegotiate["sdp"],
                                        "type": self._pending_renegotiate["type"]
                                    },
                                    "from": "server",
                                    "renegotiate": True
                                }))
                                print(f"[SFU] Sent renegotiation offer to proctor {proctor_conn.user_id}", flush=True)
                            else:
                                print(f"[SFU] Warning: Proctor {proctor_conn.user_id} not found in room participants", flush=True)
                        else:
                            print(f"[RENEGOTIATE] main module not loaded yet, falling back to polling", flush=True)
                    except Exception as e:
                        print(f"[RENEGOTIATE] Error sending offer directly: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
            else:
                print(f"[RENEGOTIATE] No new tracks to add, skipping offer creation", flush=True)
            
            self._renegotiate_pending[room_id] = False
            
        except Exception as e:
            print(f"[RENEGOTIATE] Error during renegotiation: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self._renegotiate_pending[room_id] = False
    
    async def handle_proctor_answer(self, room_id: str, answer_sdp: dict):
        """
        Handle answer from proctor (response to renegotiation offer)
        """
        if not AIORTC_AVAILABLE:
            return
        
        async with self._lock:
            proctor_conn = self._proctors.get(room_id)
            if not proctor_conn:
                logger.warning(f"Proctor connection not found for room {room_id}")
                return
            
            pc = proctor_conn.pc
            
            # Set remote description (answer from proctor)
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=answer_sdp['sdp'],
                type=answer_sdp['type']
            ))
            
            print(f"Applied answer from proctor in room {room_id}, state: {pc.signalingState}")
    
    def get_pending_renegotiate(self):
        """
        Get and clear pending renegotiation offer
        """
        renegotiate = self._pending_renegotiate
        self._pending_renegotiate = None
        return renegotiate
    
    async def add_candidate_tracks_to_proctor(
        self, 
        room_id: str, 
        candidate_id: str,
        camera_track=None,
        screen_track=None,
        audio_track=None
    ):
        """
        Add tracks from a newly joined candidate to the proctor's peer connection.
        Triggers renegotiation by creating a new offer.
        """
        if not AIORTC_AVAILABLE:
            return
        
        async with self._lock:
            proctor_conn = self._proctors.get(room_id)
            if not proctor_conn:
                logger.warning(f"No proctor in room {room_id} to forward tracks from {candidate_id}")
                return
            
            pc = proctor_conn.pc
            added_count = 0
            
            # Add new tracks
            if camera_track:
                pc.addTrack(camera_track)
                added_count += 1
                print(f"[RENEGOTIATE] Added camera track from {candidate_id} to proctor")
            
            if screen_track:
                pc.addTrack(screen_track)
                added_count += 1
                print(f"[RENEGOTIATE] Added screen track from {candidate_id} to proctor")
            
            if audio_track:
                pc.addTrack(audio_track)
                added_count += 1
                print(f"[RENEGOTIATE] Added audio track from {candidate_id} to proctor")
            
            print(f"[RENEGOTIATE] Added {added_count} tracks, creating new offer for proctor")
            
            # Create new offer to trigger renegotiation
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Return the offer so main.py can send it to proctor via WebSocket
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
                "room_id": room_id,
                "proctor_id": proctor_conn.user_id
            }
    
    async def _forward_track_to_proctor(
        self,
        room_id: str,
        track: 'MediaStreamTrack',
        candidate_id: str,
        track_label: str
    ):
        """Forward new track from candidate to proctor (requires renegotiation)"""
        proctor = self._proctors.get(room_id)
        
        if not proctor:
            print(f"No proctor connected to room {room_id}, track will be added when proctor joins")
            return
        
        try:
            # Add track to proctor's peer connection
            proctor.pc.addTrack(track)
            print(f"Added {track_label} track from {candidate_id} to proctor, need renegotiation")
            
            # Note: Renegotiation needs to be triggered via WebSocket
            # The main WebSocket handler will need to send a "renegotiate" message to proctor
            
        except Exception as e:
            logger.error(f"Failed to forward track to proctor: {e}")
    
    async def add_ice_candidate(
        self, 
        room_id: str, 
        user_id: str, 
        candidate_dict: dict, 
        is_proctor: bool = False
    ):
        """Add ICE candidate to peer connection"""
        try:
            if is_proctor:
                conn = self._proctors.get(room_id)
                if not conn:
                    logger.warning(f"Proctor connection not found for room {room_id}")
                    return
                pc = conn.pc
            else:
                candidates = self._candidates.get(room_id, {})
                conn = candidates.get(user_id)
                if not conn:
                    logger.warning(f"Candidate {user_id} connection not found in room {room_id}")
                    return
                pc = conn.pc
            
            # Check if connection is still open
            if pc.connectionState in ["closed", "failed"]:
                logger.warning(f"Connection for {user_id} is {pc.connectionState}, skipping ICE candidate")
                return
            
            if pc and candidate_dict:
                # Parse ICE candidate from browser format to aiortc format
                candidate_str = candidate_dict.get('candidate', '')
                sdp_mid = candidate_dict.get('sdpMid')
                sdp_mline_index = candidate_dict.get('sdpMLineIndex')
                
                if candidate_str and candidate_str != '':
                    # Parse candidate string using aiortc's parser
                    ice_candidate = candidate_from_sdp(candidate_str.split(':', 1)[1])
                    ice_candidate.sdpMid = sdp_mid
                    ice_candidate.sdpMLineIndex = sdp_mline_index
                    
                    await pc.addIceCandidate(ice_candidate)
                    print(f"Added ICE candidate for {user_id} (proctor={is_proctor})")
                else:
                    logger.warning(f"Empty ICE candidate from {user_id}")
        
        except Exception as e:
            # Ignore errors during cleanup phase
            if "NoneType" not in str(e) and "call_exception_handler" not in str(e):
                logger.error(f"Failed to add ICE candidate for {user_id}: {e}")
                import traceback
                traceback.print_exc()
    
    async def _cleanup_candidate(self, room_id: str, user_id: str):
        """Clean up candidate connection"""
        async with self._lock:
            candidates = self._candidates.get(room_id, {})
            if user_id in candidates:
                candidate_conn = candidates[user_id]
                try:
                    # Stop all tracks first to avoid cleanup issues
                    if candidate_conn.camera_track:
                        candidate_conn.camera_track.stop()
                    if candidate_conn.screen_track:
                        candidate_conn.screen_track.stop()
                    if candidate_conn.audio_track:
                        candidate_conn.audio_track.stop()
                    
                    # Close peer connection
                    if candidate_conn.pc.connectionState not in ["closed"]:
                        await candidate_conn.pc.close()
                except Exception as e:
                    logger.error(f"Error closing candidate PC for {user_id}: {e}")
                
                del candidates[user_id]
                
                # Clean up room if no candidates left
                if not candidates and room_id in self._candidates:
                    del self._candidates[room_id]
                
                print(f"Cleaned up candidate {user_id} from room {room_id}")
    
    async def _cleanup_proctor(self, room_id: str):
        """Clean up proctor connection"""
        async with self._lock:
            if room_id in self._proctors:
                proctor_conn = self._proctors[room_id]
                try:
                    # Close peer connection
                    if proctor_conn.pc.connectionState not in ["closed"]:
                        await proctor_conn.pc.close()
                except Exception as e:
                    logger.error(f"Error closing proctor PC: {e}")
                
                del self._proctors[room_id]
                
                print(f"Cleaned up proctor from room {room_id}")
    
    def get_room_stats(self, room_id: str) -> dict:
        """Get statistics for a room"""
        candidates = list(self._candidates.get(room_id, {}).keys())
        proctor = self._proctors.get(room_id)
        proctor_id = proctor.user_id if proctor else None
        
        return {
            "room_id": room_id,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "proctor": proctor_id,
            "has_proctor": proctor is not None
        }
    
    def is_available(self) -> bool:
        """Check if SFU is available (aiortc installed)"""
        return AIORTC_AVAILABLE


# Global SFU manager instance
sfu_manager = SFUManager()
