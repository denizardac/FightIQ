import google.generativeai as genai
import os
import sys
from dotenv import load_dotenv

# ==========================================
# 🔍 FIGHTIQ: GEMINI MODEL CHECKER
# ==========================================

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

def check_available_models():
    print("=" * 60)
    print("🤖 GEMINI MODEL INVENTORY")
    print("=" * 60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ ERROR: GEMINI_API_KEY not found in .env file")
        return
    
    genai.configure(api_key=api_key)
    
    print("\n📋 Querying available models...\n")
    
    # Categories
    text_models = []
    image_models = []
    other_models = []
    
    try:
        for model in genai.list_models():
            model_name = model.name
            supported_methods = [m for m in model.supported_generation_methods]
            
            # Categorize
            if 'generateContent' in supported_methods:
                text_models.append({
                    'name': model_name,
                    'display_name': model.display_name,
                    'description': model.description[:60] + "..." if len(model.description) > 60 else model.description
                })
            elif 'generateImage' in supported_methods or 'imagen' in model_name.lower():
                image_models.append({
                    'name': model_name,
                    'display_name': model.display_name,
                    'description': model.description[:60] + "..." if len(model.description) > 60 else model.description
                })
            else:
                other_models.append({
                    'name': model_name,
                    'methods': supported_methods
                })
        
        # Display results
        print("🧠 TEXT GENERATION MODELS (Fight Brain):")
        print("-" * 60)
        if text_models:
            for i, model in enumerate(text_models, 1):
                print(f"{i}. {model['name']}")
                print(f"   Display: {model['display_name']}")
                print(f"   Info: {model['description']}")
                print()
        else:
            print("❌ No text generation models found")
        
        print("\n🎨 IMAGE GENERATION MODELS (Nano Banana):")
        print("-" * 60)
        if image_models:
            for i, model in enumerate(image_models, 1):
                print(f"{i}. {model['name']}")
                print(f"   Display: {model['display_name']}")
                print(f"   Info: {model['description']}")
                print()
        else:
            print("⚠️ No image generation models found")
            print("   (Image generation may not be available in your API tier)")
        
        if other_models:
            print("\n📦 OTHER MODELS:")
            print("-" * 60)
            for model in other_models[:5]:  # Show first 5
                print(f"- {model['name']}: {model['methods']}")
        
        # Recommendations
        print("\n" + "=" * 60)
        print("💡 RECOMMENDATIONS:")
        print("=" * 60)
        
        # Check for specific models we want
        model_names = [m['name'] for m in text_models]
        
        recommended_text = None
        priority_models = [
            "models/gemini-2.0-flash-exp",
            "models/gemini-exp-1206",
            "models/gemini-2.5-pro",
            "models/gemini-1.5-pro-002",
            "models/gemini-1.5-pro-latest",
            "models/gemini-1.5-pro",
            "models/gemini-pro"
        ]
        
        for model in priority_models:
            if model in model_names:
                recommended_text = model
                break
        
        if recommended_text:
            print(f"✅ FIGHT BRAIN: Use '{recommended_text}'")
            print(f"   (Best available from your priority list)")
        else:
            print(f"⚠️ FIGHT BRAIN: None of the priority models found")
            if text_models:
                print(f"   Fallback to: {text_models[0]['name']}")
        
        if image_models:
            print(f"✅ NANO BANANA: Image generation available!")
            print(f"   Use: {image_models[0]['name']}")
        else:
            print(f"❌ NANO BANANA: No image generation models detected")
            print(f"   Recommendation: Use stock backgrounds or manual design")
        
        # Save recommendations to file
        with open("model_recommendations.txt", "w", encoding="utf-8") as f:
            f.write("GEMINI MODEL RECOMMENDATIONS\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"PRIMARY TEXT MODEL: {recommended_text or 'Not found'}\n")
            f.write(f"IMAGE MODEL: {image_models[0]['name'] if image_models else 'Not available'}\n\n")
            f.write("ALL TEXT MODELS:\n")
            for model in text_models:
                f.write(f"  - {model['name']}\n")
        
        print(f"\n📁 Saved to 'model_recommendations.txt'")
        
    except Exception as e:
        print(f"❌ Error querying models: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_available_models()
