/**
 * Recording Service: Ghi video camera + screen
 * Client-side MediaRecorder API
 */
export class RecordingService {
  constructor() {
    this.recorders = new Map() // streamId -> MediaRecorder
    this.chunks = new Map() // streamId -> chunks[]
    this.startTime = null
  }

  async startRecording(stream, streamId = 'main') {
    if (this.recorders.has(streamId)) {
      console.warn(`Recording ${streamId} already started`)
      return
    }

    const options = { mimeType: 'video/webm;codecs=vp9,opus' }
    const recorder = new MediaRecorder(stream, options)
    const chunks = []

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: 'video/webm' })
      this.chunks.set(streamId, blob)
    }

    this.recorders.set(streamId, recorder)
    this.chunks.set(streamId, chunks)
    recorder.start(1000) // chunk every 1s
    if (!this.startTime) this.startTime = Date.now()
  }

  async stopRecording(streamId = 'main') {
    const recorder = this.recorders.get(streamId)
    if (!recorder) return null

    return new Promise((resolve) => {
      recorder.onstop = () => {
        const chunks = this.chunks.get(streamId) || []
        const blob = new Blob(chunks, { type: 'video/webm' })
        this.recorders.delete(streamId)
        this.chunks.delete(streamId)
        resolve(blob)
      }
      recorder.stop()
    })
  }

  async stopAll() {
    const results = {}
    for (const streamId of this.recorders.keys()) {
      results[streamId] = await this.stopRecording(streamId)
    }
    this.startTime = null
    return results
  }

  getDuration() {
    if (!this.startTime) return 0
    return Date.now() - this.startTime
  }

  download(blob, filename) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `recording-${Date.now()}.webm`
    a.click()
    URL.revokeObjectURL(url)
  }
}

