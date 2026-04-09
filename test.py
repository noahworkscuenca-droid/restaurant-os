import os
from dotenv import load_dotenv

load_dotenv(override=True)
API_KEY = os.getenv("GEMINI_API_KEY")

print(f"\n🔑 Llave detectada: ...{API_KEY[-4:] if API_KEY else 'NINGUNA'}")

try:
    from google import genai

    client = genai.Client(api_key=API_KEY)
    print("Enviando mensaje de prueba a Google (gemini-2.5-flash)...")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hola, responde solo con la palabra 'Conectado'.",
    )
    print(f"✅ ¡ÉXITO! Gemini dice: {response.text}")

except Exception as e:
    print(f"\n❌ EL ERROR REAL ES: {e}")
