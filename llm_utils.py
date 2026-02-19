import os
import logging
import anthropic
from dotenv import load_dotenv

# Load Env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
if "#" in ANTHROPIC_API_KEY:
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY.split("#")[0].strip()

def is_valid_key(key):
    return key and key.startswith("sk-")

def count_tokens(text, model=None):
    """
    Counts tokens in a string.
    Anthropic doesn't use tiktoken, but for estimation we can use cl100k_base 
    or just simple character count / 4.
    """
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4

async def clean_text_with_llm(text: str, model: str = "claude-3-haiku-20240307") -> str:
    """
    Uses LLM to clean and repair text.
    """
    if not is_valid_key(ANTHROPIC_API_KEY):
        logger.warning("No valid ANTHROPIC_API_KEY found. Returning original text.")
        return text

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""
    You are a legal document assistant. Please clean and correct the following OCR text.
    Fix broken words, split concatenated words, and correct obvious typos.
    Do NOT summarize. Return ONLY the full cleaned text.
    
    TEXT:
    {text}
    """
    
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not found. Skipping LLM cleanup.")
        return text

    try:
        message = await client.messages.create(
            model=model,
            max_tokens=4000, # Adjust based on expected text length
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Anthropic cleanup failed: {e}")
        return text

async def generate_completion(prompt: str, model: str = "claude-3-haiku-20240307", max_tokens: int = 1000) -> str:
    """
    Generates a completion from the LLM.
    """
    if not is_valid_key(ANTHROPIC_API_KEY):
        logger.warning("No valid ANTHROPIC_API_KEY found. Returning mock response.")
        return "Resumen simulado: Este documento trata sobre acuerdos legales. (Mock LLM activo)"

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    try:
        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API Error: {e}")
        return f"Error generating completion: {e}"

# Compatibility adapter for PageIndex
async def PageIndex_LLM_Adapter(model, prompt, api_key=None):
    """
    Adapter to make PageIndex use Anthropic instead of OpenAI.
    Replaces pageindex.utils.ChatGPT_API_async
    """
    # Use environment key if passed key is None or the default dummy
    
    # Map OpenAI models to Anthropic models if needed
    anthropic_model = "claude-3-haiku-20240307" # Default fallback
    if "gpt-4" in model:
         anthropic_model = "claude-3-haiku-20240307" # Use haiku for speed/cost
    elif "claude" in model:
         anthropic_model = model

    return await generate_completion(prompt, model=anthropic_model)
