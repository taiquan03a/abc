try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.rtciceccandidate import RTCIceCandidate
    print('✅ All aiortc imports successful')
    print('✅ SFU should be available')
except Exception as e:
    print('❌ Import error:', e)
    import traceback
    traceback.print_exc()
