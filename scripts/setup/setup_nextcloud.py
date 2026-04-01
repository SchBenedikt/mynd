#!/usr/bin/env python3
"""
Interactive Nextcloud Configuration Setup Wizard
Helps user configure Nextcloud connection with Login Flow v2
"""

import os
import json
import sys
import time
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict, Any

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Print a header with formatting"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_status(message: str, status: str = 'info'):
    """Print a status message with color"""
    colors = {
        'info': Colors.BLUE,
        'success': Colors.GREEN,
        'warning': Colors.YELLOW,
        'error': Colors.RED,
    }
    color = colors.get(status, Colors.BLUE)
    print(f"{color}➜{Colors.END} {message}")

def print_step(step_num: int, total: int, text: str):
    """Print a step indicator"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[{step_num}/{total}]{Colors.END} {text}")

def validate_nextcloud_url(url: str) -> Optional[str]:
    """Validate and normalize Nextcloud URL"""
    url = url.strip()
    
    if not url:
        print_status("URL darf nicht leer sein", 'error')
        return None
    
    # Add https:// if protocol is missing
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Basic URL validation
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            print_status("Ungültige URL format", 'error')
            return None
    except:
        print_status("URL parsing fehlgeschlagen", 'error')
        return None
    
    return url

def test_nextcloud_connection(url: str) -> bool:
    """Test if Nextcloud instance is reachable"""
    try:
        import requests
        print_status(f"Teste Verbindung zu {url}...", 'info')
        
        # Test status endpoint
        response = requests.get(
            f"{url}/status.php",
            timeout=5,
            verify=True
        )
        
        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'unknown')
            installed = data.get('installed', False)
            
            if installed:
                print_status(f"✓ Nextcloud {version} gefunden und installiert", 'success')
                return True
            else:
                print_status("Nextcloud ist nicht installiert", 'error')
                return False
        else:
            print_status(f"Server antwortet mit Status {response.status_code}", 'error')
            return False
            
    except requests.exceptions.ConnectionError:
        print_status("Verbindung fehlgeschlagen - URL erreichbar?", 'error')
        return False
    except requests.exceptions.Timeout:
        print_status("Verbindung timed out", 'error')
        return False
    except Exception as e:
        print_status(f"Fehler beim Test: {str(e)}", 'error')
        return False

def get_nextcloud_url() -> Optional[str]:
    """Interactive prompt for Nextcloud URL"""
    attempts = 0
    max_attempts = 3
    
    while attempts < max_attempts:
        print(f"\n{Colors.CYAN}Gib deine Nextcloud-URL ein:{Colors.END}")
        print(f"  {Colors.YELLOW}Beispiele:{Colors.END}")
        print(f"    • https://nextcloud.example.com")
        print(f"    • https://myserver.de/nextcloud")
        print(f"    • nextcloud.local (wird zu https://nextcloud.local)")
        
        url = input(f"\n{Colors.BLUE}➜ Nextcloud URL: {Colors.END}").strip()
        
        validated_url = validate_nextcloud_url(url)
        if validated_url:
            # Test connection
            if test_nextcloud_connection(validated_url):
                return validated_url
            else:
                attempts += 1
                if attempts < max_attempts:
                    print_status(f"Noch {max_attempts - attempts} Versuche übrig", 'warning')
                    print(f"\n{Colors.YELLOW}Tipp: Überprüfe, ob die URL korrekt ist und Nextcloud läuft{Colors.END}")
        else:
            attempts += 1
    
    print_status("Zu viele fehlgeschlagene Versuche", 'error')
    return None

def save_nextcloud_config(nextcloud_url: str) -> bool:
    """Save Nextcloud URL to config"""
    try:
        config_dir = Path(__file__).parent.parent / "backend" / "config"
        config_file = config_dir / "nextcloud_config.json"
        
        # Create config directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config = {
            "nextcloud_url": nextcloud_url,
            "username": "USE_ENV_VARIABLE_NEXTCLOUD_USERNAME",
            "password": "USE_ENV_VARIABLE_NEXTCLOUD_PASSWORD",
            "auth_type": "login_flow_v2",
            "display_name": "USE_ENV_VARIABLE_NEXTCLOUD_DISPLAY_NAME"
        }
        
        # Write config atomically with secure permissions
        tmp_file = f"{config_file}.tmp"
        with open(tmp_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, config_file)
        
        print_status(f"Konfiguration gespeichert: {config_file}", 'success')
        return True
        
    except Exception as e:
        print_status(f"Fehler beim Speichern: {str(e)}", 'error')
        return False

def setup_env_variables():
    """Prompt user to set up environment variables"""
    print_step(2, 4, "Umgebungsvariablen einrichten")
    
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        print_status("Erstelle .env Datei aus .env.example...", 'info')
        example_file = Path(__file__).parent.parent / ".env.example"
        
        if example_file.exists():
            with open(example_file, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            os.chmod(env_file, 0o600)
            print_status(".env Datei erstellt", 'success')
        else:
            print_status(".env.example nicht gefunden", 'warning')
    else:
        print_status(".env Datei existiert bereits", 'info')
    
    print(f"\n{Colors.YELLOW}WICHTIG: Folgende Umgebungsvariablen in .env setzen:{Colors.END}")
    print(f"  • NEXTCLOUD_USERNAME=dein_benutzername")
    print(f"  • NEXTCLOUD_PASSWORD=dein_passwort")
    print(f"  • NEXTCLOUD_DISPLAY_NAME=dein_anzeigename")
    
    # Optional: Ask user if they want to edit the file
    response = input(f"\n{Colors.BLUE}➜ .env Datei automatisch öffnen? (y/n): {Colors.END}").lower()
    
    if response == 'y':
        try:
            if sys.platform == 'darwin':  # macOS
                os.system(f'open -e "{env_file}"')
            elif sys.platform == 'linux':
                os.system(f'nano "{env_file}"')
            elif sys.platform == 'win32':
                os.system(f'notepad "{env_file}"')
        except Exception as e:
            print_status(f"Konnte Editor nicht öffnen: {str(e)}", 'warning')

def test_backend_connection():
    """Test if backend is running and accessible"""
    print_step(3, 4, "Backend-Verbindung testen")
    
    try:
        import requests
        
        print_status("Teste Backend auf http://localhost:5001...", 'info')
        response = requests.get("http://localhost:5001/api/health", timeout=2)
        
        if response.status_code == 200:
            print_status("✓ Backend läuft und antwortet", 'success')
            return True
        else:
            print_status(f"Backend antwortet mit Status {response.status_code}", 'warning')
            print_status("Backend läuft wahrscheinlich nicht", 'error')
            return False
            
    except Exception as e:
        print_status("Backend nicht erreichbar", 'error')
        print(f"\n{Colors.YELLOW}Starte Backend mit:{Colors.END}")
        print(f"  cd backend/core && python3 app.py")
        return False

def open_frontend():
    """Prompt to open frontend"""
    print_step(4, 4, "Frontend öffnen und testen")
    
    print(f"\n{Colors.GREEN}✓ Setup abgeschlossen!{Colors.END}\n")
    print(f"{Colors.CYAN}Öffne dein Frontend:{Colors.END}")
    print(f"  {Colors.BOLD}http://localhost:3000{Colors.END}")
    
    print(f"\n{Colors.YELLOW}In der UI:{Colors.END}")
    print(f"  1. Gehe zu 'Dokumente' oder 'Integrationen'")
    print(f"  2. Klicke auf 'Mit Nextcloud verbinden'")
    print(f"  3. Gib deine Nextcloud-URL ein")
    print(f"  4. Melde dich an und autorisiere MYND")
    print(f"  5. Die Verbindung wird hergestellt")
    
    response = input(f"\n{Colors.BLUE}➜ Frontend jetzt öffnen? (y/n): {Colors.END}").lower()
    
    if response == 'y':
        try:
            if sys.platform == 'darwin':  # macOS
                os.system('open http://localhost:3000')
            elif sys.platform == 'linux':
                os.system('xdg-open http://localhost:3000')
            elif sys.platform == 'win32':
                os.system('start http://localhost:3000')
        except Exception as e:
            print_status(f"Konnte Browser nicht öffnen: {str(e)}", 'warning')

def main():
    """Main setup wizard"""
    print_header("MYND Nextcloud Integration Setup")
    
    print(f"{Colors.CYAN}Willkommen zum MYND Nextcloud Setup!{Colors.END}")
    print(f"\nDieser Wizard hilft dir, MYND mit deiner Nextcloud-Instanz zu verbinden.")
    print(f"Es werden {Colors.BOLD}4 Schritte{Colors.END} durchlaufen.")
    
    # Step 1: Get Nextcloud URL
    print_step(1, 4, "Nextcloud-URL konfigurieren")
    nextcloud_url = get_nextcloud_url()
    
    if not nextcloud_url:
        print_status("Setup abgebrochen", 'error')
        sys.exit(1)
    
    # Save configuration
    if not save_nextcloud_config(nextcloud_url):
        print_status("Setup abgebrochen", 'error')
        sys.exit(1)
    
    # Step 2: Setup environment variables
    setup_env_variables()
    
    # Step 3: Test backend
    test_backend_connection()
    
    # Step 4: Open frontend
    open_frontend()
    
    print_header("Setup abgeschlossen!")
    print(f"{Colors.GREEN}✓ Deine Nextcloud-Instanz ist konfiguriert!{Colors.END}\n")
    print(f"Nächste Schritte:")
    print(f"  1. Stelle sicher, dass Backend und Frontend laufen")
    print(f"  2. Öffne http://localhost:3000")
    print(f"  3. Verbinde MYND mit deiner Nextcloud-Instanz\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup durch Benutzer abgebrochen{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Fehler: {str(e)}{Colors.END}")
        sys.exit(1)
