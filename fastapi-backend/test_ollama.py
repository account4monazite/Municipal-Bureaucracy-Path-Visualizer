import asyncio
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ollama():
    system_prompt = """You are a helpful assistant that extracts information from user messages for government services.
Extract the user's intended task (intent), location (city, state, district), and any other relevant details from the user's message.
Return a valid JSON object with the following keys:
- "intent": The civic task the user wants to accomplish (e.g., "aadhaar_update", "income_certificate", "birth_certificate", "passport_application", "driving_license", "business_registration"). If the task is unclear, use "unknown" or invent a concise snake_case name for it.
- "location": A JSON object containing "city", "state", and "district". Set values to null if not provided in the text.
- "details": A JSON object with any other relevant details (e.g., "business_type", "document_type", etc).

Ensure your output is strictly a JSON object."""

    user_message = "Senior citizen card apply Mumbai Maharashtra"
    prompt = f"User Message: {user_message}"

    payload = {
        "model": "llama3",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("http://localhost:11434/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content")
            print("RAW OLLAMA OUTPUT:", content)
            if content:
                result = json.loads(content)
                print("PARSED:", result)
    except Exception as exc:
        logger.warning("Failed to extract task with Ollama: %s", exc)

if __name__ == "__main__":
    asyncio.run(test_ollama())
