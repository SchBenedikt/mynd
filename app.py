#!/usr/bin/env python3
"""MYND Flask backend — entry point.

The application is defined in the `app` package. This module
creates the Flask app, loads plugins, starts the scheduler, and
runs the development server.
"""

import os
import threading

from app import flask_app as app
from app.config import SERVER_PORT, logger
from app.helpers import knowledge_base
from app.ollama_client import ollama_client
from app.scheduler import _start_indexing_scheduler, automation_engine


def _warm_up_model():
    """Pre-load the LLM in the background so the first real request is fast.

    Runs in a daemon thread; never blocks server startup.
    """
    try:
        from app.ollama_client import load_ai_config
        from core.llm import chat_with_tools

        config = load_ai_config()
        messages = [{'role': 'user', 'content': 'Reply only with: OK'}]
        if config.get('provider') == 'ollama':
            _warm = ollama_client.chat(messages)
        else:
            _warm = chat_with_tools(config['model'], messages, [])
        if 'error' in _warm:
            logger.warning(f'Model warm-up: {_warm["error"]}')
    except Exception as _we:
        logger.warning(f'Model warm-up failed: {_we}')


if __name__ == '__main__':
    print('=' * 50)
    print('  MYND – local-first AI workspace')
    print('=' * 50)
    print(f'  Ollama:     {ollama_client.base_url}')
    print(f'  Model:      {ollama_client.model}')
    print(f'  Chunks:     {len(knowledge_base.chunks)}')
    print(f'  Backend:    http://127.0.0.1:{SERVER_PORT}/api/')
    print('  Frontend:   cd frontend && npm run dev')
    print(f'  Automations: {len(automation_engine.load_automations())} active')
    print('=' * 50)
    automation_engine.start()
    _start_indexing_scheduler()

    # Warm-up model in a background thread so server start is not blocked
    threading.Thread(target=_warm_up_model, daemon=True, name='model-warmup').start()

    app.run(
        debug=False,
        host=os.getenv('MYND_HOST', '127.0.0.1'),
        port=SERVER_PORT,
        use_reloader=False,
        threaded=True,
    )
