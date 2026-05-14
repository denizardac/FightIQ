"""Quick test of Imagen API"""
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("Testing Imagen API with new google.genai package...")
print(f"API Key: {api_key[:20]}...")

try:
    client = genai.Client(api_key=api_key)
    
    # Try simple generation
    print("\nAttempting image generation...")
    response = client.models.generate_images(
        model="imagen-4.0-generate-preview-06-06",
        prompt="A simple red square",
        config=types.GenerateImagesConfig(
            number_of_images=1
        )
    )
    
    if response.generated_images:
        print("✅ SUCCESS! Imagen API works!")
        print(f"Generated {len(response.generated_images)} image(s)")
    else:
        print("❌ No images generated")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"\nError type: {type(e)}")
    import traceback
    traceback.print_exc()
