#!/usr/bin/env python3
"""Test tasks_enabled initialization"""

import logging
logging.basicConfig(level=logging.INFO)

from backend.features.tasks.manager import task_manager
from backend.features.knowledge.indexing import IndexingManager

indexing_manager = IndexingManager()
tasks_enabled = False

def initialize_tasks_from_config():
    global tasks_enabled
    try:
        config = None
        
        # Try indexing_manager
        try:
            config = indexing_manager.get_config(mask_password=False)
            if config and config.get('url'):
                print(f'✓ Config from indexing_manager')
        except Exception as e:
            print(f'✗ indexing_manager.get_config() failed: {e}')
        
        # Try fallback
        if not config or not config.get('url'):
            import json
            import os
            config_file = os.path.join(os.path.dirname(__file__), 'backend/config/indexing_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    print(f'✓ Config from file: {config_file}')
        
        print(f'Config loaded: {config is not None}')
        print(f'Config has url: {config.get("url") if config else "N/A"}')
        
        if config and config.get('url') and config.get('username') and config.get('password'):
            print(f'Calling task_manager.initialize...')
            success = task_manager.initialize(config['url'], config['username'], config['password'])
            print(f'task_manager.initialize() returned: {success}')
            tasks_enabled = success
            print(f'tasks_enabled set to: {tasks_enabled} (global)')
        else:
            print(f'Config invalid or incomplete')
            print(f'  - url: {config.get("url") if config else "missing"}')
            print(f'  - username: {config.get("username") if config else "missing"}')
            print(f'  - password: {config.get("password") if config else "missing"}')
            tasks_enabled = False
            
    except Exception as e:
        print(f'Exception in initialize_tasks_from_config: {e}')
        tasks_enabled = False

print(f'[TEST] Before: tasks_enabled = {tasks_enabled}')
initialize_tasks_from_config()
print(f'[TEST] After: tasks_enabled = {tasks_enabled}')
