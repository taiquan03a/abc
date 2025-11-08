export async function createPeer({ onTrack, onIce, onDataMessage }) {
  const pc = new RTCPeerConnection({
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' }
    ]
  })

  pc.ontrack = (ev) => {
    if (onTrack) onTrack(ev) // Pass full event, not just stream
  }
  pc.onicecandidate = (ev) => {
    if (ev.candidate && onIce) onIce(ev.candidate)
  }

  const dc = pc.createDataChannel('chat')
  dc.onmessage = (ev) => onDataMessage && onDataMessage(ev.data)

  return { pc, dc }
}

export async function addLocalStream(pc, stream, label = null) {
  // Store track label mapping in peer connection for identification
  if (!pc._trackLabels) {
    pc._trackLabels = new Map()
  }
  
  for (const track of stream.getTracks()) {
    pc.addTrack(track, stream)
    // Store label mapping by track ID
    if (label && track.kind === 'video') {
      pc._trackLabels.set(track.id, label)
    }
  }
  
  return pc
}

export async function setRemoteDescription(pc, desc) {
  await pc.setRemoteDescription(new RTCSessionDescription(desc))
}

export async function createAndSetOffer(pc) {
  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  return offer
}

export async function createAndSetAnswer(pc) {
  const answer = await pc.createAnswer()
  await pc.setLocalDescription(answer)
  return answer
}


