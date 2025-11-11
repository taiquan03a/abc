"""
Test WebSocket AI Analysis flow
"""
import asyncio
import websockets
import json

async def test_proctor():
    """Test as proctor"""
    uri = "ws://localhost:8000/ws/test-room"
    
    print("🎭 Connecting as PROCTOR...")
    async with websockets.connect(uri) as websocket:
        # Send join as proctor
        await websocket.send(json.dumps({
            "type": "join",
            "userId": "proctor123",
            "role": "proctor"
        }))
        print("✅ Proctor joined")
        
        # Listen for messages
        print("👂 Listening for AI analysis messages...")
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(message)
                print(f"📨 Received: {data.get('type')}")
                
                if data.get('type') == 'ai_analysis':
                    print(f"🤖 AI ANALYSIS: {data}")
                    print(f"   Scenario: {data.get('data', {}).get('scenario')}")
                    print(f"   Candidate: {data.get('data', {}).get('candidate_id')}")
                    break
        except asyncio.TimeoutError:
            print("⏰ Timeout - no AI analysis received in 30s")

async def test_candidate():
    """Test as candidate"""
    uri = "ws://localhost:8000/ws/test-room"
    
    print("👤 Connecting as CANDIDATE...")
    async with websockets.connect(uri) as websocket:
        # Send join as candidate
        await websocket.send(json.dumps({
            "type": "join",
            "userId": "candidate456",
            "role": "candidate"
        }))
        print("✅ Candidate joined - should trigger auto-start AI analysis")
        
        # Keep connection alive
        await asyncio.sleep(15)
        print("👤 Candidate disconnecting...")

async def main():
    """Run proctor in background, then candidate"""
    proctor_task = asyncio.create_task(test_proctor())
    await asyncio.sleep(2)  # Let proctor connect first
    
    candidate_task = asyncio.create_task(test_candidate())
    
    # Wait for both
    await asyncio.gather(proctor_task, candidate_task, return_exceptions=True)

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING WEBSOCKET AI ANALYSIS FLOW")
    print("=" * 60)
    asyncio.run(main())
