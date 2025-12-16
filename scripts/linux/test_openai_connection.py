import os
import sys
import time
from decouple import config

# Add project root to path to ensure we can import if needed, though we rely mostly on installed packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_openai_connection():
    print("----------------------------------------------------------------")
    print("Testing OpenAI API Connectivity (Actual Network Request)")
    print("----------------------------------------------------------------")

    try:
        import openai
        print(f"[INFO] OpenAI library version: {openai.__version__}")
    except ImportError:
        print("[ERROR] openai library not installed.")
        return

    # Try to get API Key from env or .env file
    api_key = os.environ.get('OPENAI_API_KEY') or config('OPENAI_API_KEY', default=None)

    if not api_key:
        print("[ERROR] OPENAI_API_KEY not found in environment variables or .env file.")
        return

    # Mask key for display
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"[INFO] Using API Key: {masked_key}")

    client = openai.OpenAI(api_key=api_key)

    print("[INFO] Attempting to list models (simple GET request)...")
    start_time = time.time()
    try:
        # Set a timeout to avoid hanging indefinitely if that's the issue
        # Note: older versions of openai lib might use different timeout setting, 
        # but modern client supports timeout in request or client init.
        # We'll try standard call.
        models = client.models.list()
        duration = time.time() - start_time
        
        model_ids = [m.id for m in models.data]
        print(f"[SUCCESS] Successfully retrieved {len(model_ids)} models in {duration:.2f} seconds.")
        print(f"[INFO] First 5 models: {model_ids[:5]}")
        
    except openai.AuthenticationError:
        print("[ERROR] Authentication failed. Check your API Key.")
    except openai.APIConnectionError as e:
        print(f"[ERROR] Connection error: {e}")
        print("       Check your network settings, firewall, or DNS.")
    except openai.APITimeoutError:
        print("[ERROR] Request timed out.")
        print("       The request took too long to complete. Possible network restrictions.")
    except openai.RateLimitError:
        print("[ERROR] Rate limit exceeded.")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

    print("----------------------------------------------------------------")

    # Also test Embedding call since that's what the stuck process is likely doing first
    print("[INFO] Attempting to create a test embedding...")
    try:
        start_time = time.time()
        resp = client.embeddings.create(
            input="Teste de conexao",
            model="text-embedding-3-small"
        )
        duration = time.time() - start_time
        print(f"[SUCCESS] Embedding created in {duration:.2f} seconds.")
    except Exception as e:
        print(f"[ERROR] Embedding creation failed: {e}")

if __name__ == "__main__":
    test_openai_connection()
