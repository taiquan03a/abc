import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Join() {
  const nav = useNavigate()
  const [roomId, setRoomId] = useState('demo-room')
  const [userId, setUserId] = useState(() => Math.random().toString(36).slice(2,8))
  const [role, setRole] = useState('candidate')

  const go = () => {
    if (!roomId || !userId) return
    if (role === 'proctor') nav(`/proctor/${roomId}/${userId}`)
    else nav(`/candidate/${roomId}/${userId}`)
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <h3>Join Session</h3>
      <label>Room ID</label>
      <input value={roomId} onChange={e=>setRoomId(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
      <label>User ID</label>
      <input value={userId} onChange={e=>setUserId(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
      <label>Role</label>
      <select value={role} onChange={e=>setRole(e.target.value)} style={{ width: '100%', marginBottom: 12 }}>
        <option value="candidate">Candidate</option>
        <option value="proctor">Proctor</option>
      </select>
      <button onClick={go}>Join</button>
      <p style={{ color: '#666' }}>Pro tip: Open two tabs, one proctor, one candidate, same room.</p>
    </div>
  )
}


