#!/usr/bin/env python3
"""MYND Flask backend — entry point.

The application is defined in the `app` package. This module
creates the Flask app, loads plugins, starts the scheduler, and
runs the development server.
"""
from app import flask_app as app
from app.config import logger
from app.helpers import knowledge_base
from app.ollama_client import ollama_client
from app.scheduler import _start_indexing_scheduler, automation_engine

if __name__ == '__main__':
    print("=" * 50)
    print("  MYND – local-first AI workspace")
    print("=" * 50)
    print(f"  Ollama:     {ollama_client.base_url}")
    print(f"  Model:      {ollama_client.model}")
    print(f"  Chunks:     {len(knowledge_base.chunks)}")
    print("  Backend:    http://127.0.0.1:5001/api/")
    print("  Frontend:   cd frontend && npm run dev")
    print(f"  Automations: {len(automation_engine.load_automations())} active")
    print("=" * 50)
    automation_engine.start()
    _start_indexing_scheduler()

    # Warm-up model
    try:
        _warm = ollama_client.chat([{"role": "user", "content": "Reply only with: OK"}])
        if 'error' in _warm:
            logger.warning(f"Model warm-up: {_warm['error']}")
    except Exception as _we:
        logger.warning(f"Model warm-up failed: {_we}")

    app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False, threaded=True)
