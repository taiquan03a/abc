export class SignalingClient {
  constructor({ baseUrl, roomId, userId, role }) {
    this.baseUrl = baseUrl.replace(/^http/, 'ws')
    this.roomId = roomId
    this.userId = userId
    this.role = role
    this.ws = null
    this.listeners = new Map()
  }

  on(type, handler) {
    this.listeners.set(type, handler)
  }

  off(type) {
    this.listeners.delete(type)
  }

  async connect(maxRetries = 3, timeout = 5000) {
    for (let i = 0; i < maxRetries; i++) {
      try {
        this.ws = new WebSocket(`${this.baseUrl}/ws/${this.roomId}`)
        await new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            this.ws.close()
            reject(new Error('WebSocket connection timeout'))
          }, timeout)
          
          this.ws.onopen = () => {
            clearTimeout(timer)
            resolve()
          }
          this.ws.onerror = (e) => {
            clearTimeout(timer)
            reject(new Error('WebSocket connection error'))
          }
          this.ws.onclose = (e) => {
            clearTimeout(timer)
            if (e.code !== 1000) {
              reject(new Error(`WebSocket closed: ${e.code} ${e.reason}`))
            }
          }
        })
        
        // Setup message handler
        this.ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data)
            const handler = this.listeners.get(data.type)
            if (handler) handler(data)
          } catch (e) {
            console.error('Failed to parse message:', e)
          }
        }
        this.ws.onclose = () => {
          const handler = this.listeners.get('close')
          if (handler) handler()
        }
        
        // Send join message
        this.send({ type: 'join', userId: this.userId, role: this.role })
        return // Success
      } catch (error) {
        console.warn(`WebSocket connection attempt ${i + 1} failed:`, error)
        if (i === maxRetries - 1) {
          throw new Error(`Failed to connect after ${maxRetries} attempts: ${error.message}`)
        }
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1))) // Exponential backoff
      }
    }
  }

  send(obj) {
    if (this.ws?.readyState === 1) this.ws.send(JSON.stringify(obj))
  }

  close() {
    try { this.send({ type: 'leave' }) } catch {}
    this.ws?.close()
  }
}


