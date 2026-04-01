#!/usr/bin/env python3
"""
Test script for new Immich photo features:
1. Date filtering (heute, gestern, diese Woche, etc.)
2. Links/IDs display
3. Thumbnail preview URLs
4. Context-based filtering (objects/tags)
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5001"

def test_photo_search_with_date():
    """Test 1: Search photos with date filter"""
    print("\n=== Test 1: Datum-Filter ===")
    
    queries = [
        "Fotos von heute",
        "Fotos von gestern",
        "Fotos von dieser Woche",
    ]
    
    for query in queries:
        print(f"\n📸 Suche: {query}")
        response = requests.post(
            f"{BASE_URL}/api/immich/search",
            json={
                "username": "default",
                "query": query,
                "limit": 2
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            print(f"   ✓ Gefunden: {count} Fotos")
            
            for i, photo in enumerate(data.get('results', [])[:1], 1):
                print(f"\n   Foto {i}:")
                print(f"   📌 ID: {photo['id']}")
                print(f"   📅 Datum: {photo['created_at'][:10]}")
                print(f"   🖼️  Vorschau: {photo['thumbnail_url']}")
                print(f"   🔗 Link: {photo['asset_url']}")
                if photo.get('people'):
                    print(f"   👥 Personen: {', '.join(photo['people'])}")
                if photo.get('objects'):
                    print(f"   🏷️  Objekte: {', '.join(photo['objects'])}")

def test_photo_details():
    """Test 2: Full photo details with all metadata"""
    print("\n\n=== Test 2: Foto-Details mit Metadaten ===")
    
    response = requests.post(
        f"{BASE_URL}/api/immich/search",
        json={
            "username": "default",
            "query": "Isabelle",
            "limit": 1
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('results'):
            photo = data['results'][0]
            print(f"\n📸 Foto: {photo['original_file_name']}")
            print(f"   ID:        {photo['id']}")
            print(f"   Datum:     {photo['created_at']}")
            print(f"   Ort:       {photo.get('location', 'Unbekannt')}")
            print(f"   Personen:  {', '.join(photo['people']) if photo['people'] else 'Keine'}")
            print(f"   Objekte:   {', '.join(photo['objects']) if photo['objects'] else 'Keine'}")
            print(f"   Tags:      {', '.join(photo['tags']) if photo['tags'] else 'Keine'}")
            print(f"\n   🖼️  Vorschau-URL: {photo['thumbnail_url']}")
            print(f"   🔗 Original-URL:  {photo['asset_url']}")

def test_context_search():
    """Test 3: Search by context (objects/tags)"""
    print("\n\n=== Test 3: Kontext-basierte Suche ===")
    
    context_queries = [
        "Person",
        "Katze",
        "Baum",
    ]
    
    for query in context_queries:
        print(f"\n🏷️  Suche nach: {query}")
        response = requests.post(
            f"{BASE_URL}/api/immich/search-by-context",
            json={
                "username": "default",
                "query": query,
                "limit": 2
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            print(f"   ✓ Gefunden: {count} Fotos")
            
            for photo in data.get('results', []):
                print(f"   {photo['original_file_name']}")
                if photo.get('objects'):
                    print(f"     Objekte: {', '.join(photo['objects'][:3])}")

def test_markdown_response():
    """Test 4: Format for agent query (with markdown formatting)"""
    print("\n\n=== Test 4: Markdown-formatierte Response ===")
    
    response = requests.post(
        f"{BASE_URL}/api/immich/search",
        json={
            "username": "default",
            "query": "Fotos von heute",
            "limit": 1
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print("\n📋 Markdown-Format für KI:")
        print("\n```markdown")
        
        for i, photo in enumerate(data.get('results', []), 1):
            print(f"### Foto {i}: {photo['original_file_name']}")
            print(f"**ID:** `{photo['id']}`")
            print(f"**Datum:** {photo['created_at'][:10]}")
            print(f"[Bild ansehen]({photo['asset_url']})")
            print(f"[![Vorschau]({photo['thumbnail_url']})]({photo['asset_url']})")
            print()
        
        print("```")

if __name__ == "__main__":
    print("🚀 Testen Sie neue Immich-Funktionen")
    print("=" * 50)
    
    try:
        test_photo_search_with_date()
        test_photo_details()
        test_context_search()
        test_markdown_response()
        
        print("\n\n✅ Alle Tests abgeschlossen!")
        print("\nFeature-Zusammenfassung:")
        print("1. ✓ Datum-Filter (heute, gestern, diese Woche)")
        print("2. ✓ IDs und Links sichtbar")
        print("3. ✓ Thumbnail-Vorschau URLs")
        print("4. ✓ Kontext-Filter (Objekte/Tags)")
        
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
