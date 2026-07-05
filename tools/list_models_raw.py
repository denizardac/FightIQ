"""
FightIQ - Gemini Model Lister: dumps all model names raw.
Run: python tools/list_models_raw.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("ALL MODELS AVAILABLE ON THIS KEY:")
print("=" * 70)
for m in client.models.list():
    actions = list(m.supported_actions) if hasattr(m, 'supported_actions') else []
    print(f"{m.name:55s}  {actions}")
