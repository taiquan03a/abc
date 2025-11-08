import React from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import Join from './pages/Join'
import Candidate from './pages/Candidate'
import Proctor from './pages/Proctor'

export default function App() {
  return (
    <div style={{ fontFamily: 'Inter, system-ui, Arial', padding: 16 }}>
      <header style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Proctoring</h2>
        <nav style={{ display: 'flex', gap: 12 }}>
          <Link to="/">Home</Link>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Join />} />
        <Route path="/candidate/:roomId/:userId" element={<Candidate />} />
        <Route path="/proctor/:roomId/:userId" element={<Proctor />} />
      </Routes>
    </div>
  )
}


