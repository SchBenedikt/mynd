#!/usr/bin/env python3
"""
Test: Chat-Integration mit Todo-Abfrage
Simuliert: User fragt "welche todos habe ich?" -> Backend lädt Todos -> Keine Crashes
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5001"

def test_chat_with_todos():
    """Test the chat endpoint with a todo query"""
    
    print("=" * 60)
    print("TEST: Chat mit Todo-Frage")
    print("=" * 60)
    
    # Test-Nachrichten
    test_cases = [
        ("welche todos habe ich?", "Deutsch - Alle todos"),
        ("what todos do I have?", "English - All todos"),
        ("zeige meine aufgaben für diese woche", "Deutsch - Wöchentliche Aufgaben"),
    ]
    
    for message, description in test_cases:
        print(f"\n[TEST] {description}")
        print(f"Message: '{message}'")
        print("-" * 40)
        
        try:
            start_time = time.time()
            
            # Chat API aufrufen
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json={"message": message},
                timeout=30
            )
            
            elapsed = time.time() - start_time
            
            print(f"Status: {response.status_code}")
            print(f"Response time: {elapsed:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS - Response received")
                print(f"Response: {data.get('response', 'N/A')[:200]}...")
                
                # Prüfe ob Todos in Context waren
                if 'TODO' in data.get('response', '').upper():
                    print(f"✅ Todos wurden im Response gefunden")
                else:
                    print(f"⚠️  Keine Todos im Response erwähnt")
                    
            else:
                print(f"❌ ERROR - Status {response.status_code}")
                print(f"Response: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"❌ TIMEOUT - Request took too long (>30s)")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ CONNECTION ERROR - Backend crashed or unreachable")
            print(f"Error: {str(e)[:100]}")
        except Exception as e:
            print(f"❌ ERROR - {type(e).__name__}: {str(e)[:100]}")
    
    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)

if __name__ == "__main__":
    test_chat_with_todos()
