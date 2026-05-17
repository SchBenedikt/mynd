#!/usr/bin/env python3
"""
Debug Immich Photo Search
"""
import os
import sys
import json
import logging
from datetime import date, timedelta

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.features.integration.immich_client import ImmichClient

def test_immich_connection():
    """Test basic Immich connection"""
    logger.info("="*60)
    logger.info("Testing Immich Connection")
    logger.info("="*60)
    
    # Try to get config from environment first
    immich_url = os.getenv('IMMICH_URL', '').strip()
    immich_api_key = os.getenv('IMMICH_API_KEY', '').strip()
    
    # Fallback to config file
    if not immich_url or not immich_api_key:
        config_file = os.path.join(os.path.dirname(__file__), 'backend/config/ai_config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                immich_url = config.get('immich_url_default', '').strip()
                immich_api_key = config.get('immich_api_key_default', '').strip()
                logger.info(f"Loaded Immich config from {config_file}")
    
    if not immich_url or not immich_api_key:
        logger.error("Immich URL and API KEY not configured!")
        logger.info("Set IMMICH_URL and IMMICH_API_KEY environment variables or configure ai_config.json")
        return False
    
    logger.info(f"Immich URL: {immich_url}")
    logger.info(f"API Key: {'*' * 10}")
    
    try:
        client = ImmichClient(immich_url, immich_api_key)
        logger.info("ImmichClient created")
        
        # Test connection
        if client.test_connection():
            logger.info("✓ Connection successful!")
            return client
        else:
            logger.error(f"✗ Connection failed: {client.last_error}")
            return None
    except Exception as e:
        logger.error(f"✗ Error creating client: {e}")
        return None


def test_photo_search(client, query):
    """Test photo search"""
    logger.info("="*60)
    logger.info(f"Testing Photo Search: '{query}'")
    logger.info("="*60)
    
    try:
        result = client.search_photos_intelligent(query, limit=5)
        logger.info(f"Search result: {json.dumps(result, indent=2, default=str)}")
        return result
    except Exception as e:
        logger.error(f"Error in search: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    # Test connection
    client = test_immich_connection()
    if not client:
        logger.error("Cannot proceed without Immich connection")
        return
    
    # Test queries from the error report
    test_queries = [
        "Kannst du mir bitte Fotos zeigen, die heute aufgenommen worden sind?",
        "Zeig mir bitte Fotos von dieser Woche"
    ]
    
    for query in test_queries:
        result = test_photo_search(client, query)
        logger.info("")


if __name__ == '__main__':
    main()
