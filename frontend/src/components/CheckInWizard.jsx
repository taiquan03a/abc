import React, { useState, useEffect } from 'react'

/**
 * Pre-exam Check-in Wizard (T-15' checklist)
 * Theo thiết kế: media probe, screen share probe, secure browser check
 */
export default function CheckInWizard({ onComplete, onCancel }) {
  const [checks, setChecks] = useState({
    camera: { ok: false, detail: '' },
    mic: { ok: false, detail: '' },
    screen: { ok: false, detail: '' },
    brightness: { ok: false, detail: '' },
    network: { ok: false, detail: '' },
    battery: { ok: false, detail: '' },
    secureBrowser: { ok: false, detail: '' }
  })
  const [running, setRunning] = useState(false)

  const runChecks = async () => {
    setRunning(true)
    const results = { ...checks }

    // Camera check
    try {
      const camStream = await navigator.mediaDevices.getUserMedia({ video: true })
      const track = camStream.getVideoTracks()[0]
      const settings = track.getSettings()
      results.camera = { ok: true, detail: `${settings.width}x${settings.height} @ ${settings.frameRate}fps` }
      camStream.getTracks().forEach(t => t.stop())
    } catch (e) {
      results.camera = { ok: false, detail: e.message }
    }

    // Mic check
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      results.mic = { ok: true, detail: 'OK' }
      micStream.getTracks().forEach(t => t.stop())
    } catch (e) {
      results.mic = { ok: false, detail: e.message }
    }

    // Screen share check (simulate)
    try {
      // Check if API available
      if (navigator.mediaDevices.getDisplayMedia) {
        results.screen = { ok: true, detail: 'API available' }
      } else {
        results.screen = { ok: false, detail: 'Not supported' }
      }
    } catch (e) {
      results.screen = { ok: false, detail: e.message }
    }

    // Brightness check (mock - would need camera analysis)
    results.brightness = { ok: true, detail: 'Adequate (mock)' }

    // Network check
    try {
      const start = performance.now()
      await fetch('https://www.google.com/favicon.ico', { mode: 'no-cors', cache: 'no-cache' })
      const latency = performance.now() - start
      results.network = { ok: latency < 1000, detail: `Latency: ${latency.toFixed(0)}ms` }
    } catch (e) {
      results.network = { ok: false, detail: 'Offline' }
    }

    // Battery check
    if (navigator.getBattery) {
      try {
        const battery = await navigator.getBattery()
        results.battery = { 
          ok: battery.level > 0.2 || battery.charging, 
          detail: `${(battery.level * 100).toFixed(0)}% ${battery.charging ? '(charging)' : ''}` 
        }
      } catch {
        results.battery = { ok: true, detail: 'N/A' }
      }
    } else {
      results.battery = { ok: true, detail: 'N/A' }
    }

    // Secure browser check (mock - would check extension)
    results.secureBrowser = { ok: true, detail: 'Extension active (mock)' }

    setChecks(results)
    setRunning(false)
  }

  useEffect(() => {
    runChecks()
  }, [])

  const allOk = Object.values(checks).every(c => c.ok)

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: 24 }}>
      <h2>Check-in kỹ thuật (T-15')</h2>
      <div style={{ marginBottom: 16 }}>
        {Object.entries(checks).map(([key, check]) => (
          <div key={key} style={{ 
            padding: 12, 
            marginBottom: 8, 
            border: '1px solid #ddd', 
            borderRadius: 4,
            background: check.ok ? '#d4edda' : '#f8d7da'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{key.charAt(0).toUpperCase() + key.slice(1)}</strong>
                <div style={{ fontSize: 12, color: '#666' }}>{check.detail}</div>
              </div>
              <div>{check.ok ? '✓' : '✗'}</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={runChecks} disabled={running}>
          {running ? 'Đang kiểm tra...' : 'Chạy lại kiểm tra'}
        </button>
        {allOk && (
          <button onClick={() => onComplete?.(checks)} style={{ background: '#28a745', color: 'white' }}>
            Hoàn tất
          </button>
        )}
        {onCancel && <button onClick={onCancel}>Hủy</button>}
      </div>
    </div>
  )
}

