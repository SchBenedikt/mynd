import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def reset_training_system():
    """Setzt das Training-System zurück und startet neu"""
    
    # Backup erstellen
    backup_file = f"training_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    if os.path.exists("training_data.json"):
        try:
            with open("training_data.json", 'r', encoding='utf-8') as f:
                data = f.read()
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(data)
            
            logger.info(f"Backup created: {backup_file}")
        except Exception as e:
            logger.error(f"Backup failed: {e}")
    
    # Training-Datei zurücksetzen
    try:
        with open("training_data.json", 'w', encoding='utf-8') as f:
            f.write("[]")  # Leere JSON-Array
        
        logger.info("Training data reset successfully")
        
        # Modell-Info zurücksetzen
        model_info = {
            "model_name": "gemma3:latest",
            "training_version": "2.0",
            "last_reset": datetime.now().isoformat(),
            "context_window": 4096,
            "max_response_tokens": 2048,
            "metadata_extraction": True,
            "enhanced_search": True
        }
        
        with open("model_info.json", 'w', encoding='utf-8') as f:
            json.dump(model_info, f, indent=2)
        
        logger.info("Model info updated to version 2.0")
        
        return {
            "status": "success",
            "backup_file": backup_file,
            "training_version": "2.0",
            "features": [
                "Enhanced metadata extraction",
                "Improved context formatting", 
                "Better source attribution",
                "JSON-based training storage"
            ]
        }
        
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = reset_training_system()
    print(json.dumps(result, indent=2))
