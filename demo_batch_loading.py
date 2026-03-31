#!/usr/bin/env python3
"""
Demo: Task Batch-Loading System
Zeigt wie die neuen DB-basierten Tasks funktionieren
"""

import requests
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5001"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def demo():
    print_header("🚀 TASK BATCH-LOADING DEMO")
    
    # 1. Task Status prüfen
    print("1️⃣  Checking task status...")
    response = requests.get(f"{BASE_URL}/api/tasks/status")
    if response.status_code == 200:
        status = response.json()
        print(f"   ✅ Tasks enabled: {status.get('enabled')}")
        print(f"   ✅ Connected: {status.get('connected')}")
    else:
        print(f"   ❌ Error: {response.status_code}")
        return
    
    # 2. DB Stats BEFORE loading
    print("\n2️⃣  Checking initial DB stats (before loading)...")
    response = requests.get(f"{BASE_URL}/api/tasks/db-stats")
    if response.status_code == 200:
        stats = response.json()
        print(f"   Tasks in DB: {stats.get('total', 0)}")
        print(f"   Open: {stats.get('open', 0)}")
        print(f"   Completed: {stats.get('completed', 0)}")
    
    # 3. START THE BATCH LOAD!
    print("\n3️⃣  ⏳ STARTING BATCH-LOAD (this will run in background!)...")
    response = requests.post(
        f"{BASE_URL}/api/tasks/sync",
        json={'list_name': 'todo', 'batch_size': 100},
        timeout=5
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ {result.get('message')}")
        print(f"   Status: {result.get('status')}")
    else:
        print(f"   ❌ Error: {response.json()}")
        return
    
    # 4. MONITOR PROGRESS
    print("\n4️⃣  📊 MONITORING SYNC PROGRESS...")
    print("   (Checking every 2 seconds, max 60 seconds)...\n")
    
    max_polls = 30
    poll_count = 0
    last_loaded = 0
    
    while poll_count < max_polls:
        response = requests.get(f"{BASE_URL}/api/tasks/sync-status")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', {})
            is_loading = data.get('is_loading')
            
            total = status.get('total', 0)
            open_count = status.get('open', 0)
            completed = status.get('completed', 0)
            
            if total > last_loaded or is_loading:
                print(f"   [{poll_count*2:3d}s] Total: {total:4d} | Open: {open_count:3d} | Completed: {completed:4d} | Loading: {is_loading}")
                last_loaded = total
            
            # Sync complete?
            if not is_loading and total > 0:
                print(f"\n   ✅ SYNC COMPLETE! Loaded {total} tasks in {poll_count*2} seconds!")
                break
        
        poll_count += 1
        time.sleep(2)
    
    # 5. FINAL STATS
    print("\n5️⃣  📈 FINAL STATISTICS:")
    response = requests.get(f"{BASE_URL}/api/tasks/db-stats")
    if response.status_code == 200:
        stats = response.json()
        print(f"   Total Tasks: {stats.get('total', 0)}")
        print(f"   Open Tasks: {stats.get('open', 0)}")
        print(f"   Completed: {stats.get('completed', 0)}")
        
        if stats.get('by_priority'):
            print(f"\n   By Priority:")
            for priority, count in sorted(stats.get('by_priority', {}).items()):
                priority_names = {0: 'Low', 5: 'Medium', 1-4: 'High'}
                print(f"      Priority {priority}: {count} tasks")
    
    # 6. TEST CHAT WITH TODOS
    print("\n6️⃣  💬 TESTING CHAT WITH TODOS...")
    response = requests.post(
        f"{BASE_URL}/api/agent/query",
        json={
            'prompt': 'welche todos habe ich?',
            'language': 'de',
            'preferred_source': 'auto',
            'context': ''
        },
        timeout=10
    )
    
    if response.status_code == 200:
        chat = response.json()
        response_text = chat.get('response', '')[:150]
        context_used = chat.get('context_used', False)
        print(f"   ✅ Chat responded (context_used: {context_used})")
        print(f"   Response: {response_text}...")
    else:
        print(f"   ❌ Chat failed: {response.status_code}")
    
    print_header("🎉 DEMO COMPLETE!")
    print("""
    What you demonstrated:
    ✅ Nextcloud tasks loaded INTO SQLite database
    ✅ Background batch-processing (100 tasks at a time)
    ✅ Chat now queries the database (ultra-fast!)
    ✅ No more WebDAV timeouts!
    
    Next steps:
    1. Use the UI to ask about todos
    2. Chat will now respond instantly (no hangs!)
    3. You can sync more tasks anytime with /api/tasks/sync
    """)

if __name__ == "__main__":
    try:
        demo()
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
