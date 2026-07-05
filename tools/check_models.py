"""
FightIQ - Gemini Model Checker (Updated to use google.genai)
Run: python tools/check_models.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from dotenv import load_dotenv
from google import genai

def check_available_models():
    print("=" * 60)
    print("GEMINI MODEL INVENTORY")
    print("=" * 60)

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env file")
        return

    client = genai.Client(api_key=api_key)

    print("\nQuerying available models...\n")

    text_models = []
    image_models = []
    other_models = []

    try:
        for model in client.models.list():
            model_name = model.name
            supported_methods = list(model.supported_actions) if hasattr(model, 'supported_actions') else []

            if 'generateContent' in supported_methods or 'generate_content' in supported_methods:
                text_models.append({
                    'name': model_name,
                    'display_name': getattr(model, 'display_name', model_name),
                })
            elif 'generateImages' in supported_methods or 'generate_images' in supported_methods or 'imagen' in model_name.lower():
                image_models.append({
                    'name': model_name,
                    'display_name': getattr(model, 'display_name', model_name),
                })
            else:
                other_models.append({'name': model_name, 'methods': supported_methods})

        print("TEXT GENERATION MODELS:")
        print("-" * 60)
        for i, m in enumerate(text_models, 1):
            print(f"  {i}. {m['name']}")
            if m['display_name'] != m['name']:
                print(f"     -> {m['display_name']}")
        if not text_models:
            print("  (none found with generateContent)")

        print("\nIMAGE GENERATION MODELS:")
        print("-" * 60)
        for i, m in enumerate(image_models, 1):
            print(f"  {i}. {m['name']}")
        if not image_models:
            print("  (none found with generateImages)")

        print("\nALL OTHER MODELS:")
        print("-" * 60)
        for m in other_models:
            print(f"  - {m['name']:50s}  actions={m['methods']}")

        # Check specific models by trying them
        print("\n" + "=" * 60)
        print("SPOT-CHECK: Testing key model names...")
        print("=" * 60)

        test_models = [
            "gemini-3.0-pro-preview",
            "gemini-3-pro-preview",
            "gemini-2.5-pro-preview-03-25",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-thinking-exp",
            "gemini-1.5-pro-latest",
        ]

        working = []
        for model_id in test_models:
            try:
                resp = client.models.generate_content(
                    model=model_id,
                    contents="Say: OK"
                )
                print(f"  WORKS: {model_id} -> {resp.text.strip()[:30]}")
                working.append(model_id)
            except Exception as e:
                err = str(e)[:60]
                print(f"  FAIL:  {model_id} ({err})")

        print("\n" + "=" * 60)
        print("RECOMMENDED CONFIG for core/config.py:")
        print("=" * 60)
        if working:
            print("\nGEMINI_MODELS = [")
            for m in working:
                print(f'    "{m}",')
            print("]")
        else:
            print("No models confirmed working - check API key and quota")

        # Save to file
        out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_recommendations.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("WORKING MODELS:\n")
            for m in working:
                f.write(f"  {m}\n")
        print(f"\nSaved to model_recommendations.txt")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_available_models()
