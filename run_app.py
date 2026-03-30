#!/usr/bin/env python
"""
Entry point to run the MYND application.
This script loads and runs the Flask app from the backend.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == '__main__':
    from backend.core.app import app
    
    # Run the Flask app
    print("\n🚀 MYND AI-Chat-Anwendung wird gestartet...")
    print("📍 Öffne http://localhost:5001 im Browser\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
