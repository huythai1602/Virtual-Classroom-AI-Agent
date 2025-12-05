
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

# Load env
load_dotenv()

print("Attempting to import app and agent...")

try:
    from config.settings import settings
    print(f"Settings loaded: Model={settings.OPENAI_MODEL}")
    
    from core.agent import agent
    print("Agent imported successfully.")
    
    from app import app
    print("FastAPI app imported successfully.")
    
    print("Startup check passed!")
except Exception as e:
    print(f"CRITICAL ERROR STARTING APP: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
