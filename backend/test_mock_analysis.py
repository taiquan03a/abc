"""
Quick test script for Mock AI Analysis
Run this to verify the mock analyzer works correctly
"""

from ai_analysis import MockAIAnalyzer
import json

def test_mock_analyzer():
    """Test basic mock analyzer functionality"""
    print("=" * 60)
    print("TESTING MOCK AI ANALYZER")
    print("=" * 60)
    
    analyzer = MockAIAnalyzer()
    
    # Generate 10 mock analyses
    for i in range(10):
        result = analyzer.analyze_frame(
            candidate_id="test_candidate_1",
            room_id="test_room"
        )
        
        print(f"\n--- Analysis #{i+1} ---")
        print(f"Scenario: {result['scenario']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Number of analyses: {len(result['analyses'])}")
        
        # Check for alerts
        alerts_found = []
        for analysis in result['analyses']:
            alert = analysis.get('result', {}).get('alert')
            if alert:
                alerts_found.append({
                    "type": alert['type'],
                    "level": alert['level'],
                    "message": alert['message']
                })
        
        if alerts_found:
            print(f"🚨 ALERTS DETECTED: {len(alerts_found)}")
            for alert in alerts_found:
                print(f"   - [{alert['type']}] ({alert['level']}) {alert['message']}")
        else:
            print("✅ No alerts (normal scenario)")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


def test_incident_types():
    """Test incident type definitions"""
    from ai_analysis import IncidentTypes, INCIDENT_DEFINITIONS, get_incident_info
    
    print("\n" + "=" * 60)
    print("INCIDENT TYPE DEFINITIONS")
    print("=" * 60)
    
    for incident_type, info in INCIDENT_DEFINITIONS.items():
        print(f"\n{incident_type}: {info['name']}")
        print(f"  Level: {info['default_level']}")
        print(f"  Message: {info['message']}")


if __name__ == "__main__":
    test_mock_analyzer()
    test_incident_types()
