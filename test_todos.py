#!/usr/bin/env python3
"""Test-Skript für die Todo-Integration"""

import sys
sys.path.insert(0, '.')

from backend.features.tasks.manager import task_manager
from backend.features.knowledge.indexing import indexing_manager

print("\n" + "="*60)
print("TESTE NEXTCLOUD TODOS-INTEGRATION")
print("="*60 + "\n")

# Lade Nextcloud-Config zuerst
print("📂 Lade Nextcloud-Konfiguration aus Datei...")
indexing_manager.load_nextcloud_config()
print("  ✅ Geladen\n")

# Lade Nextcloud-Config
config = indexing_manager.get_config(mask_password=False)
print("📋 Nextcloud-Konfiguration:")
print(f"  URL: {config.get('url')}")
print(f"  Username: {config.get('username')}")
print(f"  Passwort: {'***' if config.get('password') else 'FEHLT'}")
print()

# Initialisiere Task-Manager
print("🔗 Initialisiere Task-Manager...")
success = task_manager.initialize(config['url'], config['username'], config['password'])
print(f"  Verbunden: {'✅ JA' if success else '❌ NEIN'}")
print()

# Lade Todos
if success:
    print("📝 Lade Todos...")
    tasks = task_manager.get_tasks(use_cache=False)
    print(f"  Todos gefunden: {len(tasks)}")
    for i, task in enumerate(tasks, 1):
        print(f"    {i}. {task.get('title')} (Priorität: {task.get('priority')})")
    print()
    
    # Test: Format für Chat
    print("💬 Formatiert für Chat:")
    print(task_manager.format_tasks_for_context(tasks))
else:
    print("❌ Konnte nicht mit Nextcloud verbinden")
    print("   Überprüfe URL und Zugangsdaten")

print("\n" + "="*60 + "\n")
