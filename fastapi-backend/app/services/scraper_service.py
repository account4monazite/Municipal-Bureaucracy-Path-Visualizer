import json
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(
        self,
        firecrawl_api_url: str = "http://localhost:3002/v1/scrape",
        firecrawl_api_key: str = "fc-YOUR_API_KEY",
        ollama_api_url: str = "http://localhost:11434/api/chat",
        ollama_model: str = "llama3"
    ):
        self.firecrawl_api_url = firecrawl_api_url
        self.firecrawl_api_key = firecrawl_api_key
        self.ollama_api_url = ollama_api_url
        self.ollama_model = ollama_model

    def _build_search_query(self, task: str, location: Dict[str, Any], details: Dict[str, Any]) -> str:
        """Extract terms to build a meaningful search query."""
        task_str = task.replace("_", " ")
        
        city = location.get("city", "")
        state = location.get("state", "")
        loc_str = f"{city} {state}".strip()
        
        details_str = " ".join(str(v).replace("_", " ") for v in details.values())
        
        query_parts = [task_str, details_str, loc_str]
        base_query = " ".join(part for part in query_parts if part).strip()
        return base_query

    async def search_gov_sites(self, query: str, max_results: int = 3, max_retries: int = 2) -> List[str]:
        import asyncio
        search_query = f"{query} official government website India"
        logger.info(f"Searching Firecrawl for: '{search_query}'")
        
        headers = {"Content-Type": "application/json"}
        if self.firecrawl_api_key and self.firecrawl_api_key != "fc-YOUR_API_KEY":
            headers["Authorization"] = f"Bearer {self.firecrawl_api_key}"
            
        payload = {"query": search_query}
        search_url = self.firecrawl_api_url.replace("/scrape", "/search")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    logger.info(f"Retry {attempt}/{max_retries} for search query...")
                    await asyncio.sleep(2)
                    
                results = []
                try:
                    response = await client.post(search_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    if data.get("success") and "data" in data and len(data["data"]) > 0:
                        for item in data["data"][:max_results]:
                            if "url" in item:
                                results.append(item["url"])
                                logger.info(f"Found URL: {item['url']}")
                        return results
                    else:
                        logger.warning(f"No search results found in attempt {attempt + 1}.")
                except Exception as e:
                    logger.error(f"Firecrawl search failed on attempt {attempt + 1}: {e}")
                    
        logger.error("After all retries, Firecrawl failed to find any results.")
        return []

    async def scrape_url(self, url: str) -> Optional[str]:
        logger.info(f"Scraping URL with Firecrawl: {url}")
        headers = {"Content-Type": "application/json"}
        if self.firecrawl_api_key and self.firecrawl_api_key != "fc-YOUR_API_KEY":
            headers["Authorization"] = f"Bearer {self.firecrawl_api_key}"
            
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.firecrawl_api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    return data["data"]["markdown"]
                else:
                    logger.warning(f"Firecrawl failed to scrape {url}: {data.get('error')}")
            except httpx.RequestError as e:
                logger.error(f"Request to Firecrawl failed: {e}")
        return None

    async def generate_procedure(self, task_profile: Dict[str, Any], context_text: str) -> Optional[str]:
        logger.info(f"Generating procedure using Ollama ({self.ollama_model})")
        task_desc = json.dumps(task_profile, indent=2)
        
        prompt = f"""You are a helpful assistant for Indian citizens. Based on the following official government information, provide a comprehensive guide for the user's task.

User's Task Profile:
{task_desc}

Official Information Context:
{context_text}

Please structure your response with the following sections:
1. **Process Type**: State whether the process is completely online, completely offline, or hybrid.
2. **Prerequisites**: List any conditions or requirements that must be met before starting.
3. **Required Documentation**: List all documents needed for this task.
4. **Estimated Time**: Provide the general time it takes to get this work done (if mentioned).
5. **Step-by-Step Procedure**: A clear, sequential guide specific to the user's location and details.

Instructions:
- Only use the information provided in the Official Information Context.
- If the context does not contain enough information for a specific section (e.g., Estimated Time), explicitly state "Information not available in the provided context."
"""

        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.ollama_api_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]
            except httpx.RequestError as e:
                logger.error(f"Request to Ollama failed: {e}")
        return None
