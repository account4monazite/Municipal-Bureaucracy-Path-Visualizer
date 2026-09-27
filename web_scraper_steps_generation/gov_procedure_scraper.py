import requests
import json
import argparse
import time
import sys

import requests
import json
import argparse
import time
import sys
import os

# Configuration
FIRECRAWL_API_URL = os.environ.get("FIRECRAWL_API_URL", "http://localhost:3002/v1/scrape")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "fc-YOUR_API_KEY") 
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

def build_search_query_from_json(json_data: dict) -> str:
    """Extract terms from the JSON to build a meaningful search query."""
    task = json_data.get("task", "").replace("_", " ")
    
    loc_dict = json_data.get("location", {})
    city = loc_dict.get("city", "")
    state = loc_dict.get("state", "")
    location = f"{city} {state}".strip()
    
    details_dict = json_data.get("details", {})
    details = " ".join(str(v).replace("_", " ") for v in details_dict.values())
    
    # Construct a query like "sir registration voter verification Mumbai Maharashtra"
    query_parts = [task, details, location]
    base_query = " ".join(part for part in query_parts if part).strip()
    return base_query

def search_gov_sites(query: str, max_results: int = 3, max_retries: int = 2):
    """Search for relevant .gov.in websites using Firecrawl Search."""
    search_query = f"{query} official government website India"
    print(f"[*] Searching for: '{search_query}'...")
    
    headers = {"Content-Type": "application/json"}
    if FIRECRAWL_API_KEY and FIRECRAWL_API_KEY != "fc-YOUR_API_KEY":
        headers["Authorization"] = f"Bearer {FIRECRAWL_API_KEY}"
        
    payload = {"query": search_query}
    search_url = FIRECRAWL_API_URL.replace("/scrape", "/search")
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[*] Retry {attempt}/{max_retries} for search query...")
            time.sleep(2)
            
        results = []
        try:
            response = requests.post(search_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get("success") and "data" in data and len(data["data"]) > 0:
                for item in data["data"][:max_results]:
                    if "url" in item:
                        results.append(item["url"])
                        print(f"    Found URL: {item['url']}")
                return results
            else:
                print(f"[-] No search results found in attempt {attempt + 1}.")
        except Exception as e:
            print(f"[-] Firecrawl search failed on attempt {attempt + 1}: {e}")
            
    print("[-] After all retries, Firecrawl failed to find any results.")
    return []

def scrape_url_with_firecrawl(url: str):
    """Scrape the content of a URL using Firecrawl."""
    print(f"[*] Scraping URL with Firecrawler: {url}")
    
    headers = {
        "Content-Type": "application/json",
    }
    if FIRECRAWL_API_KEY and FIRECRAWL_API_KEY != "fc-YOUR_API_KEY":
        headers["Authorization"] = f"Bearer {FIRECRAWL_API_KEY}"
        
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True
    }
    
    try:
        response = requests.post(FIRECRAWL_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            return data["data"]["markdown"]
        else:
            print(f"[-] Firecrawl failed to scrape {url}: {data.get('error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[-] Request to Firecrawl failed: {e}")
        return None

def generate_procedure_with_ollama(json_data: dict, context_text: str):
    """Ask Ollama (llama3) to generate a step-by-step procedure based on the context."""
    print(f"[*] Generating step-by-step procedure using Ollama ({OLLAMA_MODEL})...")
    
    task_desc = json.dumps(json_data, indent=2)
    
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
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"[-] Request to Ollama failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Gov Procedure Scraper & Generator")
    parser.add_argument("input_json", type=str, help="JSON string or path to a JSON file representing the task")
    args = parser.parse_args()
    
    # Try reading as a file first
    import os
    if os.path.exists(args.input_json):
        with open(args.input_json, "r", encoding="utf-8") as f:
            try:
                json_data = json.load(f)
            except json.JSONDecodeError:
                print("[-] Invalid JSON file provided.")
                sys.exit(1)
    else:
        try:
            json_data = json.loads(args.input_json)
        except json.JSONDecodeError:
            print("[-] Invalid JSON input provided. Ensure it is valid JSON or a valid file path.")
            sys.exit(1)
        
    base_query = build_search_query_from_json(json_data)
    print(f"--- Starting Flow for: '{base_query}' ---")
    
    # 1. Search for URLs
    urls = search_gov_sites(base_query, max_results=2)
    if not urls:
        print("[-] No government websites found for this query.")
        return
        
    # 2. Scrape the top URL(s)
    combined_markdown = ""
    for url in urls:
        md_content = scrape_url_with_firecrawl(url)
        if md_content:
            combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
            print(f"[+] Successfully scraped {len(md_content)} characters from {url}")
            break # Just take the first successful one
            
    if not combined_markdown:
        print("[-] Could not retrieve content from any of the URLs.")
        return
        
    # 3. Generate Procedure
    procedure = generate_procedure_with_ollama(json_data, combined_markdown)
    
    if procedure:
        print("\n" + "="*50)
        print("FINAL STEP-BY-STEP PROCEDURE:")
        print("="*50)
        print(procedure)
        print("="*50)

if __name__ == "__main__":
    main()
