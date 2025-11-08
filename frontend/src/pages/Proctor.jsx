import React, { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { SignalingClient } from '../lib/signaling'
import { createPeer, addLocalStream, createAndSetAnswer, setRemoteDescription } from '../lib/webrtc'

// Component để render video với auto-update khi stream thay đổi
function CandidateVideo({ candidateId, stream, type, videoRefsRef, style }) {
  const videoRef = useRef(null)
  
  useEffect(() => {
    // Store ref
    if (!videoRefsRef.current.has(candidateId)) {
      videoRefsRef.current.set(candidateId, {})
    }
    const refs = videoRefsRef.current.get(candidateId)
    refs[type] = videoRef.current
    
    return () => {
      // Cleanup
      const refs = videoRefsRef.current.get(candidateId)
      if (refs) {
        delete refs[type]
      }
    }
  }, [candidateId, type, videoRefsRef])
  
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    
    if (stream) {
      const currentStream = video.srcObject
      // Check if stream has tracks
      const tracks = stream.getTracks()
      console.log(`Setting ${type} stream for ${candidateId}:`, {
        streamId: stream.id,
        tracks: tracks.length,
        trackIds: tracks.map(t => t.id),
        trackStates: tracks.map(t => t.readyState)
      })
      
      if (currentStream !== stream) {
        video.srcObject = stream
        // Force play
        video.play().then(() => {
          console.log(`${type} video playing for ${candidateId}`)
        }).catch(e => {
          console.warn(`Failed to play ${type} video for ${candidateId}:`, e)
        })
      } else {
        // Same stream but check if tracks are live
        const hasLiveTracks = tracks.some(t => t.readyState === 'live')
        if (!hasLiveTracks) {
          console.warn(`${type} stream for ${candidateId} has no live tracks`)
        }
      }
    } else {
      video.srcObject = null
      console.log(`Cleared ${type} stream for ${candidateId}`)
    }
  }, [stream, candidateId, type])
  
  return <video ref={videoRef} autoPlay playsInline style={style} />
}

const SIGNALING_BASE = (import.meta.env.VITE_SIGNALING_URL || 'http://localhost:8000')

const INCIDENT_TAGS = [
  { code: 'A1', name: 'Mất khuôn mặt', level: 'S1' },
  { code: 'A2', name: 'Nhiều khuôn mặt', level: 'S2' },
  { code: 'A3', name: 'Chuyển tab', level: 'S1' },
  { code: 'A4', name: 'Không chia sẻ màn hình', level: 'S2' },
  { code: 'A5', name: 'Tài liệu cấm (OCR)', level: 'S2' },
  { code: 'A6', name: 'Âm thanh hội thoại', level: 'S2' },
  { code: 'A7', name: 'Thiết bị phụ', level: 'S2' },
  { code: 'A8', name: 'VPN / IP lạ', level: 'S1' },
  { code: 'A9', name: 'Vi phạm Secure Browser', level: 'S2' },
  { code: 'A10', name: 'Nghi ngờ giả mạo', level: 'S3' },
  { code: 'A11', name: 'Không phản hồi', level: 'S1' }
]

export default function Proctor() {
  const { roomId, userId } = useParams()
  const [msgs, setMsgs] = useState([])
  const [chat, setChat] = useState('')
  const [incidents, setIncidents] = useState([])
  const [note, setNote] = useState('')
  const [focusedId, setFocusedId] = useState(null)
  const [filterIncidents, setFilterIncidents] = useState(false)
  const [viewMode, setViewMode] = useState('grid') // grid, timeline
  const [selectedCandidate, setSelectedCandidate] = useState(null)

  const localVideoRef = useRef(null)
  const pcsRef = useRef(new Map()) // candidateUserId -> RTCPeerConnection
  const streamMapsRef = useRef(new Map()) // candidateUserId -> { camera: stream, screen: stream }
  const [remoteStreams, setRemoteStreams] = useState({}) // userId -> { camera: stream, screen: stream }
  const videoRefsRef = useRef(new Map()) // candidateId -> { camera: videoElement, screen: videoElement }
  const sigRef = useRef(null)

  useEffect(() => {
    const init = async () => {
      const signaling = new SignalingClient({ baseUrl: SIGNALING_BASE, roomId, userId, role: 'proctor' })
      sigRef.current = signaling
      signaling.on('offer', async (data) => {
        const candidateId = data.from
        const trackInfo = data.trackInfo || [] // Track metadata from candidate
        let pc = pcsRef.current.get(candidateId)
        
        // Store track info for this candidate
        if (!streamMapsRef.current.has(candidateId)) {
          streamMapsRef.current.set(candidateId, { camera: null, screen: null, trackInfo: {} })
        }
        
        // Build trackInfo map: trackId -> label
        const trackInfoMap = {}
        trackInfo.forEach(info => {
          trackInfoMap[info.trackId] = info.label
        })
        const streamMap = streamMapsRef.current.get(candidateId)
        streamMap.trackInfo = trackInfoMap
        console.log('Received offer with trackInfo:', trackInfo, 'Map:', trackInfoMap)
        
        // Create per-candidate PC if not exists
        if (!pc) {
          // Initialize stream map for this candidate
          streamMapsRef.current.set(candidateId, { camera: null, screen: null })
          
          // Create PC first
          const peer = await createPeer({
            onTrack: (ev) => {
              console.log('=== onTrack CALLED ===', { candidateId, ev })
              // Handle multiple tracks (camera and screen)
              const track = ev.track
              console.log('onTrack event:', { 
                candidateId, 
                trackId: track.id, 
                trackKind: track.kind,
                trackLabel: track.label,
                streamId: ev.streams?.[0]?.id 
              })
              
              // Get stream map for this candidate
              let streamMap = streamMapsRef.current.get(candidateId)
              if (!streamMap) {
                streamMap = { camera: null, screen: null }
                streamMapsRef.current.set(candidateId, streamMap)
              }
              
              // Get the peer connection from ref (should be set by now)
              const candidatePc = pcsRef.current.get(candidateId)
              if (!candidatePc) {
                console.warn('PC not found for candidate', candidateId, 'in onTrack - will retry')
                // Store track temporarily and retry after PC is set
                setTimeout(() => {
                  const retryPc = pcsRef.current.get(candidateId)
                  if (retryPc && track.readyState === 'live') {
                    // Retry processing
                    console.log('Retrying track processing for', candidateId)
                  }
                }, 500)
                return
              }
              
              // Identify track using trackInfo from candidate (if available)
              let isScreen = false
              let isCamera = false
              
              const trackLabel = track.label || ''
              
              // Get trackInfo map for this candidate (reuse streamMap from above)
              const trackInfoMap = streamMap?.trackInfo || {}
              
              console.log('Track received:', { 
                trackLabel, 
                trackId: track.id, 
                candidateId,
                trackKind: track.kind,
                trackInfoLabel: trackInfoMap[track.id]
              })
              
              if (track.kind === 'video') {
                // First, try to use trackInfo from candidate
                const infoLabel = trackInfoMap[track.id]
                
                if (infoLabel === 'camera') {
                  isCamera = true
                } else if (infoLabel === 'screen') {
                  isScreen = true
                } else {
                  // Fallback: use transceiver order
                  const transceivers = candidatePc.getTransceivers()
                  const currentTransceiver = transceivers.find(t => 
                    t.receiver.track && t.receiver.track.id === track.id
                  )
                  
                  if (currentTransceiver) {
                    // Get all video transceivers sorted by mid
                    const videoTransceivers = transceivers
                      .filter(t => t.receiver.track && t.receiver.track.kind === 'video')
                      .sort((a, b) => {
                        const midA = parseInt(a.mid) || 0
                        const midB = parseInt(b.mid) || 0
                        return midA - midB
                      })
                    
                    const index = videoTransceivers.findIndex(t => t.receiver.track.id === track.id)
                    
                    console.log('Video transceiver analysis (fallback):', {
                      candidateId,
                      trackId: track.id,
                      currentMid: currentTransceiver.mid,
                      index,
                      totalVideoTransceivers: videoTransceivers.length,
                      allMids: videoTransceivers.map(t => t.mid)
                    })
                    
                    // First video track (index 0) = camera
                    // Second video track (index 1) = screen
                    if (index === 0) {
                      isCamera = true
                    } else if (index >= 1) {
                      isScreen = true
                    }
                  } else {
                    console.warn('Could not find transceiver for track', track.id)
                    // Last fallback: check if we already have camera
                    const hasCamera = streamMap.camera !== null
                    if (!hasCamera) {
                      isCamera = true
                    } else {
                      isScreen = true
                    }
                  }
                }
              }
              
              console.log('Track identified:', { 
                trackLabel, 
                isScreen, 
                isCamera, 
                trackId: track.id, 
                candidateId
              })
              
              if (isScreen) {
                // Screen track - create new stream or update existing
                let screenStream = streamMap.screen
                if (!screenStream) {
                  screenStream = new MediaStream([track])
                } else {
                  // Add track to existing stream if not already there
                  const existingTrack = screenStream.getVideoTracks().find(t => t.id === track.id)
                  if (!existingTrack) {
                    screenStream.addTrack(track)
                  }
                }
                streamMap.screen = screenStream
                streamMapsRef.current.set(candidateId, streamMap)
                console.log('Screen stream updated for', candidateId, 'track:', track.id)
                
                // Update video element immediately
                const videoRefs = videoRefsRef.current.get(candidateId)
                if (videoRefs?.screen) {
                  videoRefs.screen.srcObject = screenStream
                  videoRefs.screen.play().catch(e => console.warn('Screen video play failed:', e))
                }
              } else if (isCamera) {
                // Camera track - create new stream or update existing
                let cameraStream = streamMap.camera
                if (!cameraStream) {
                  cameraStream = new MediaStream([track])
                } else {
                  // Add track to existing stream if not already there
                  const existingTrack = cameraStream.getVideoTracks().find(t => t.id === track.id)
                  if (!existingTrack) {
                    cameraStream.addTrack(track)
                  }
                }
                streamMap.camera = cameraStream
                streamMapsRef.current.set(candidateId, streamMap)
                console.log('Camera stream updated for', candidateId, 'track:', track.id)
                
                // Update video element immediately
                const videoRefs = videoRefsRef.current.get(candidateId)
                if (videoRefs?.camera) {
                  videoRefs.camera.srcObject = cameraStream
                  videoRefs.camera.play().catch(e => console.warn('Camera video play failed:', e))
                }
              }
              
              // Update state with current streams (trigger re-render)
              setRemoteStreams((curr) => {
                const currentMap = streamMapsRef.current.get(candidateId) || { camera: null, screen: null }
                const updated = {
                  ...curr,
                  [candidateId]: {
                    camera: currentMap.camera || curr[candidateId]?.camera,
                    screen: currentMap.screen || curr[candidateId]?.screen
                  }
                }
                console.log('Updated remoteStreams for', candidateId, updated[candidateId])
                return updated
              })
            },
            onIce: (candidate) => sigRef.current?.send({ type: 'ice', candidate, to: candidateId })
          })
          pc = peer.pc
          
          // Monitor connection state
          pc.onconnectionstatechange = () => {
            console.log(`PC connection state for ${candidateId}:`, pc.connectionState)
            if (pc.connectionState === 'connected') {
              // Check for existing tracks
              const transceivers = pc.getTransceivers()
              transceivers.forEach(transceiver => {
                if (transceiver.receiver.track && transceiver.receiver.track.readyState === 'live') {
                  console.log('Found existing track after connection:', {
                    trackId: transceiver.receiver.track.id,
                    kind: transceiver.receiver.track.kind,
                    label: transceiver.receiver.track.label
                  })
                  // Process existing tracks manually
                  const track = transceiver.receiver.track
                  const ev = { 
                    track: track, 
                    streams: transceiver.receiver.track.streams?.length > 0 
                      ? transceiver.receiver.track.streams 
                      : [new MediaStream([track])]
                  }
                  // Re-use the onTrack handler logic
                  if (peer.pc.ontrack) {
                    peer.pc.ontrack(ev)
                  }
                }
              })
            }
          }
          
          // Monitor ICE connection state
          pc.oniceconnectionstatechange = () => {
            console.log(`ICE connection state for ${candidateId}:`, pc.iceConnectionState)
          }
          
          // Store PC immediately BEFORE handling offer, so onTrack can access it
          pcsRef.current.set(candidateId, pc)
        }
        
        // Handle offer (initial or renegotiation)
        console.log('Processing offer from', candidateId)
        await setRemoteDescription(pc, data.sdp)
        const answer = await createAndSetAnswer(pc)
        signaling.send({ type: 'answer', sdp: answer, to: candidateId })
        console.log('Sent answer to', candidateId, 'transceivers:', pc.getTransceivers().length)
        
        // Log transceivers after answer and check for tracks
        setTimeout(() => {
          const transceivers = pc.getTransceivers()
          console.log('Transceivers after answer for', candidateId, ':', transceivers.map(t => ({
            mid: t.mid,
            kind: t.receiver.track?.kind,
            trackId: t.receiver.track?.id,
            trackLabel: t.receiver.track?.label,
            trackState: t.receiver.track?.readyState
          })))
          
          // Check if we have tracks but streams not set
          transceivers.forEach(transceiver => {
            if (transceiver.receiver.track && transceiver.receiver.track.readyState === 'live') {
              const track = transceiver.receiver.track
              const streamMap = streamMapsRef.current.get(candidateId)
              if (streamMap) {
                // Process this track
                console.log('Processing existing track:', track.id)
              }
            }
          })
        }, 1000)
      })
      signaling.on('ice', async (data) => {
        const candidateId = data.from
        const pc = pcsRef.current.get(candidateId)
        if (pc) {
          try { await pc.addIceCandidate(data.candidate) } catch {}
        }
      })
      signaling.on('chat', (data) => {
        setMsgs(m => [...m, { from: data.from, text: data.text }])
      })
      signaling.on('incident', (data) => {
        setIncidents(list => [...list, { ...data, id: Date.now() + Math.random() }])
      })
      await signaling.connect()

      // Optional: Proctor can also send mic for talk-back on each pc created later
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true })
        localVideoRef.current.textContent = 'Mic live'
        // Attach to future PCs upon creation
        pcsRef.current.__talkbackStream = stream
      } catch {}
    }
    init()
    return () => {
      try { sigRef.current?.close() } catch {}
      for (const pc of pcsRef.current.values()) {
        try { pc.close() } catch {}
      }
      pcsRef.current.clear()
    }
  }, [roomId, userId])

  // Hotkeys
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.ctrlKey || e.metaKey) {
        const macros = {
          S1: 'Đây là nhắc nhở cấp S1, vui lòng tuân thủ ngay.',
          S2: 'Đây là cảnh báo cấp S2. Nếu tái diễn sẽ tạm dừng/kết thúc phiên.',
          S3: 'Phiên có thể bị kết thúc do vi phạm nghiêm trọng.'
        }
        if (e.key === '1') { 
          e.preventDefault()
          const text = macros.S1
          sigRef.current?.send({ type: 'chat', text })
          setMsgs(m => [...m, { from: userId, text }])
        }
        if (e.key === '2') { 
          e.preventDefault()
          const text = macros.S2
          sigRef.current?.send({ type: 'chat', text })
          setMsgs(m => [...m, { from: userId, text }])
        }
        if (e.key === '3') { 
          e.preventDefault()
          const text = macros.S3
          sigRef.current?.send({ type: 'chat', text })
          setMsgs(m => [...m, { from: userId, text }])
        }
      }
    }
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [userId])

  const sendChat = () => {
    if (!chat) return
    sigRef.current?.send({ type: 'chat', text: chat })
    setMsgs(m => [...m, { from: userId, text: chat }])
    setChat('')
  }

  const tagIncident = (tag) => {
    const payload = { type: 'incident', tag: tag.code, level: tag.level, note, ts: Date.now(), by: userId }
    sigRef.current?.send(payload)
    setIncidents(list => [...list, { ...payload, roomId }])
    setNote('')
  }

  const macros = {
    S1: 'Đây là nhắc nhở cấp S1, vui lòng tuân thủ ngay.',
    S2: 'Đây là cảnh báo cấp S2. Nếu tái diễn sẽ tạm dừng/kết thúc phiên.',
    S3: 'Phiên có thể bị kết thúc do vi phạm nghiêm trọng.'
  }

  const sendMacro = (level) => {
    const text = macros[level]
    if (!text) return
    sigRef.current?.send({ type: 'chat', text })
    setMsgs(m => [...m, { from: userId, text }])
  }

  const controlCandidate = (candidateId, action) => {
    sigRef.current?.send({ type: 'control', action, to: candidateId })
  }

  const getSeverityColor = (level) => {
    if (level === 'S3') return '#dc3545'
    if (level === 'S2') return '#ffc107'
    return '#17a2b8'
  }

  const getIncidentsByCandidate = (candidateId) => {
    return incidents.filter(it => it.from === candidateId || it.by === candidateId)
  }

  const groupedIncidents = Object.keys(remoteStreams).reduce((acc, uid) => {
    acc[uid] = getIncidentsByCandidate(uid)
    return acc
  }, {})

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      <div>
        <h3>Proctor: {userId}</h3>
        {focusedId ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: remoteStreams[focusedId]?.screen ? '1fr 1fr' : '1fr', gap: 12, marginBottom: 12 }}>
              {/* Camera View */}
              <div>
                <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>Camera - {focusedId}</div>
                <CandidateVideo 
                  candidateId={focusedId}
                  stream={remoteStreams[focusedId]?.camera}
                  type="camera"
                  videoRefsRef={videoRefsRef}
                  style={{ width: '100%', background: '#000', minHeight: 320, borderRadius: 4 }}
                />
                {!remoteStreams[focusedId]?.camera && (
                  <div style={{ 
                    width: '100%', 
                    minHeight: 320, 
                    background: '#111', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    color: '#999',
                    borderRadius: 4
                  }}>
                    Chưa nhận được camera stream
                  </div>
                )}
              </div>
              {/* Screen View */}
              {remoteStreams[focusedId]?.screen && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 4, color: '#666' }}>Screen Share</div>
                  <CandidateVideo 
                    candidateId={focusedId}
                    stream={remoteStreams[focusedId]?.screen}
                    type="screen"
                    videoRefsRef={videoRefsRef}
                    style={{ width: '100%', background: '#000', minHeight: 320, borderRadius: 4 }}
                  />
                </div>
              )}
            </div>
            <div style={{ margin: '6px 0' }}>
              <button onClick={() => controlCandidate(focusedId, 'pause')}>Pause</button>
              <button onClick={() => controlCandidate(focusedId, 'end')} style={{ marginLeft: 8 }}>End</button>
              <button onClick={() => setFocusedId(null)} style={{ marginLeft: 8 }}>Unpin</button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
            {Object.entries(remoteStreams)
              .filter(([uid]) => !filterIncidents || incidents.some(it => it.from === uid || it.by === uid))
              .map(([uid, streams]) => {
                const candIncidents = groupedIncidents[uid] || []
                const s3Count = candIncidents.filter(i => i.level === 'S3').length
                const s2Count = candIncidents.filter(i => i.level === 'S2').length
                const cameraStream = streams?.camera || null
                const screenStream = streams?.screen || null
                
                return (
                  <div key={uid} style={{ position: 'relative', border: selectedCandidate === uid ? '2px solid #007bff' : '1px solid #ddd', borderRadius: 8, padding: 8, background: '#f8f9fa' }}>
                    <div style={{ marginBottom: 4, fontSize: 12, fontWeight: 'bold' }}>Candidate: {uid}</div>
                    <div style={{ display: 'grid', gridTemplateColumns: screenStream ? '1fr 1fr' : '1fr', gap: 8 }}>
                      {/* Camera View */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ fontSize: 11, marginBottom: 4, color: '#666' }}>Camera</div>
                        <CandidateVideo 
                          candidateId={uid}
                          stream={cameraStream}
                          type="camera"
                          videoRefsRef={videoRefsRef}
                          style={{ width: '100%', background: '#000', minHeight: 150, borderRadius: 4 }}
                        />
                        {!cameraStream && (
                          <div style={{ 
                            width: '100%', 
                            minHeight: 150, 
                            background: '#111', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            color: '#999',
                            fontSize: 12,
                            borderRadius: 4,
                            position: 'absolute',
                            top: 20,
                            left: 0,
                            right: 0
                          }}>
                            Chờ camera...
                          </div>
                        )}
                      </div>
                      {/* Screen Share View */}
                      {screenStream ? (
                        <div style={{ position: 'relative' }}>
                          <div style={{ fontSize: 11, marginBottom: 4, color: '#666' }}>Screen</div>
                          <CandidateVideo 
                            candidateId={uid}
                            stream={screenStream}
                            type="screen"
                            videoRefsRef={videoRefsRef}
                            style={{ width: '100%', background: '#000', minHeight: 150, borderRadius: 4 }}
                          />
                        </div>
                      ) : (
                        <div style={{ position: 'relative' }}>
                          <div style={{ fontSize: 11, marginBottom: 4, color: '#666' }}>Screen</div>
                          <div style={{ 
                            width: '100%', 
                            minHeight: 150, 
                            background: '#111', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            color: '#666',
                            fontSize: 11,
                            borderRadius: 4
                          }}>
                            Chưa share
                          </div>
                        </div>
                      )}
                    </div>
                    <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 4, zIndex: 10 }}>
                      {s3Count > 0 && <span style={{ background: '#dc3545', color: 'white', padding: '2px 6px', borderRadius: 3, fontSize: 10 }}>S3:{s3Count}</span>}
                      {s2Count > 0 && <span style={{ background: '#ffc107', color: 'black', padding: '2px 6px', borderRadius: 3, fontSize: 10 }}>S2:{s2Count}</span>}
                    </div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                      <button onClick={() => setFocusedId(uid)} style={{ flex: 1, fontSize: 11, padding: '4px 8px' }}>Pin</button>
                      <button onClick={() => setSelectedCandidate(uid === selectedCandidate ? null : uid)} style={{ flex: 1, fontSize: 11, padding: '4px 8px' }}>Select</button>
                    </div>
                  </div>
                )
              })}
            {Object.keys(remoteStreams).length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: '#666' }}>
                Chưa có thí sinh nào kết nối
              </div>
            )}
          </div>
        )}
        <div style={{ marginTop: 8, fontSize: 12, color: '#666' }} ref={localVideoRef}></div>
        <div style={{ marginTop: 12 }}>
          <div style={{ height: 160, overflow: 'auto', border: '1px solid #ddd', padding: 8 }}>
            {msgs.map((m,i) => (<div key={i}><b>{m.from}:</b> {m.text}</div>))}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <input value={chat} onChange={e=>setChat(e.target.value)} placeholder="Chat" style={{ flex: 1 }} />
            <button onClick={sendChat}>Send</button>
            <button onClick={() => sendMacro('S1')} title="Ctrl+1">S1</button>
            <button onClick={() => sendMacro('S2')} title="Ctrl+2">S2</button>
            <button onClick={() => sendMacro('S3')} title="Ctrl+3">S3</button>
          </div>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
            <input type="checkbox" checked={filterIncidents} onChange={e=>setFilterIncidents(e.target.checked)} />
            Only candidates with incidents
          </label>
        </div>
      </div>
      <div>
        <h4>Incidents</h4>
        <textarea placeholder="Ghi chú" value={note} onChange={e=>setNote(e.target.value)} style={{ width: '100%', height: 64 }} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {INCIDENT_TAGS.map(t => (
            <button key={t.code} onClick={() => tagIncident(t)}>{t.code}</button>
          ))}
        </div>
        <div style={{ marginBottom: 8 }}>
          <button onClick={() => setViewMode('grid')} style={{ marginRight: 4, background: viewMode === 'grid' ? '#007bff' : '#f0f0f0' }}>Grid</button>
          <button onClick={() => setViewMode('timeline')} style={{ background: viewMode === 'timeline' ? '#007bff' : '#f0f0f0' }}>Timeline</button>
        </div>
        {viewMode === 'timeline' ? (
          <div style={{ height: 300, overflow: 'auto', border: '1px solid #eee', padding: 8 }}>
            {incidents
              .sort((a, b) => b.ts - a.ts)
              .map((it) => (
                <div key={it.id || it.ts} style={{ 
                  padding: 8, 
                  marginBottom: 8, 
                  borderLeft: `4px solid ${getSeverityColor(it.level)}`,
                  background: '#f9f9f9'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{it.tag}</strong> <span style={{ color: getSeverityColor(it.level), fontWeight: 'bold' }}>({it.level})</span>
                      <div style={{ fontSize: 11, color: '#666' }}>by {it.by || it.from}</div>
                    </div>
                    <div style={{ fontSize: 11, color: '#999' }}>{new Date(it.ts).toLocaleTimeString()}</div>
                  </div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>{it.note}</div>
                  {it.escalated && <div style={{ fontSize: 11, color: '#999' }}>Escalated: {it.escalated}x</div>}
                </div>
              ))}
          </div>
        ) : (
          <div style={{ height: 300, overflow: 'auto', border: '1px solid #eee', padding: 8 }}>
            {incidents
              .filter(it => !selectedCandidate || it.from === selectedCandidate || it.by === selectedCandidate)
              .map((it) => (
                <div key={it.id || it.ts} style={{ 
                  padding: 6, 
                  borderBottom: '1px solid #f0f0f0',
                  borderLeft: `3px solid ${getSeverityColor(it.level)}`
                }}>
                  <div><b>{it.tag}</b> <span style={{ color: getSeverityColor(it.level), fontWeight: 'bold' }}>({it.level})</span> by {it.by || it.from}</div>
                  <div style={{ fontSize: 12, color: '#555' }}>{new Date(it.ts).toLocaleTimeString()} - {it.note}</div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  )
}


