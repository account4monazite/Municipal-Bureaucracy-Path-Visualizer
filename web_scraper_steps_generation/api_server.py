from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import json
import logging

# Import the functions from your existing scraper script
from gov_procedure_scraper import (
    build_search_query_from_json,
    search_gov_sites,
    scrape_url_with_firecrawl,
    generate_procedure_with_ollama,
    generate_procedure_with_ollama_stream,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Gov Procedure & NLP Service API")


# Define expected JSON request bodies
class TaskRequest(BaseModel):
    task: str
    location: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


class ExtractRequest(BaseModel):
    message: str
    context: Optional[str] = None


@app.post("/internal/nlp/extract")
async def extract_task(request: ExtractRequest):
    """
    Lightweight intent and location extractor for chat messages.
    """
    msg = request.message.lower()
    intent = None
    location = None
    details: Dict[str, Any] = {}

    if any(w in msg for w in ["register", "registration", "business", "company", "firm"]):
        intent = "business_registration"
    elif any(w in msg for w in ["passport"]):
        intent = "passport_application"
    elif any(w in msg for w in ["driving", "licence", "license", "dl"]):
        intent = "driving_license"
    elif any(w in msg for w in ["birth certificate"]):
        intent = "birth_certificate"
    elif any(w in msg for w in ["aadhaar", "aadhar", "uidai"]):
        intent = "aadhaar_update"
    elif any(w in msg for w in ["income certificate", "income cert", "income proof"]):
        intent = "income_certificate"

    cities = {
        "mumbai": ("Mumbai", "Maharashtra"),
        "delhi": ("Delhi", "Delhi"),
        "bangalore": ("Bangalore", "Karnataka"),
        "bengaluru": ("Bangalore", "Karnataka"),
        "chennai": ("Chennai", "Tamil Nadu"),
        "hyderabad": ("Hyderabad", "Telangana"),
        "pune": ("Pune", "Maharashtra"),
        "kolkata": ("Kolkata", "West Bengal"),
    }
    for keyword, (city, state) in cities.items():
        if keyword in msg:
            location = {"city": city, "state": state}
            break

    if any(name in msg for name in ["seawoods darave", "seawoods", "darave", "belapur"]):
        location = {"city": "Navi Mumbai", "district": "Thane", "state": "Maharashtra"}

    if "restaurant" in msg:
        details["business_type"] = "restaurant"
    elif "shop" in msg or "store" in msg:
        details["business_type"] = "retail_shop"
    elif "cafe" in msg or "coffee" in msg:
        details["business_type"] = "cafe"

    return {"intent": intent, "location": location, "details": details}


@app.post("/internal/government/search")
async def government_search(request: TaskRequest):
    """
    Search official gov sites and return structured Civic Task Graph requirements.
    """
    json_data = request.model_dump()
    base_query = build_search_query_from_json(json_data)

    urls = search_gov_sites(base_query, max_results=2)
    combined_markdown = ""
    used_urls = []
    if urls:
        for url in urls:
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                used_urls.append(url)
                break

    procedure_text = None
    if combined_markdown:
        procedure_text = generate_procedure_with_ollama(json_data, combined_markdown)

    # Try parsing procedure_text as JSON if Ollama returned JSON
    if procedure_text:
        cleaned = procedure_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "nodes" in parsed and "initialNodes" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    # Build fallback Civic Task Graph if non-JSON procedure or scrape failed
    formatted_task = request.task.replace("_", " ").title() if request.task else "Civic Task"
    return {
        "task": formatted_task,
        "initialNodes": ["step_1", "step_2"],
        "initialEdges": [{"source": "step_1", "target": "step_2"}],
        "nodes": {
            "step_1": {
                "id": "step_1",
                "type": "process",
                "title": f"Initiate {formatted_task}",
                "chatText": procedure_text or f"Initial step to begin application for {formatted_task}.",
                "actionLink": used_urls[0] if used_urls else None,
                "prerequisites": ["step_1_doc"],
            },
            "step_1_doc": {
                "id": "step_1_doc",
                "type": "document",
                "title": "Required Documentation",
                "chatText": "Identity and address proof required for verification.",
                "actionLink": None,
                "prerequisites": [],
            },
            "step_2": {
                "id": "step_2",
                "type": "process",
                "title": "Verification & Issuance",
                "chatText": f"Final stage for processing and completing {formatted_task}.",
                "actionLink": None,
                "prerequisites": [],
            },
        },
        "sources": [{"source_url": u, "source_title": "Official Portal"} for u in used_urls],
    }


@app.post("/generate-procedure")
async def generate_procedure(request: TaskRequest):
    try:
        # Convert the Pydantic model to a standard dictionary
        json_data = request.model_dump()
        
        # 1. Build Query
        base_query = build_search_query_from_json(json_data)
        
        # 2. Search for URLs
        urls = search_gov_sites(base_query, max_results=2)
        if not urls:
            raise HTTPException(status_code=404, detail="No government websites found for this query.")
            
        # 3. Scrape the top URL(s)
        combined_markdown = ""
        used_urls = []
        for url in urls:
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                used_urls.append(url)
                break # Just take the first successful one
                
        if not combined_markdown:
            raise HTTPException(status_code=500, detail="Could not retrieve content from any of the URLs.")
            
        # 4. Generate Procedure
        procedure = generate_procedure_with_ollama(json_data, combined_markdown)
        
        if not procedure:
            raise HTTPException(status_code=500, detail="Failed to generate procedure with Ollama.")
            
        return {
            "query_used": base_query,
            "urls_scraped": used_urls,
            "procedure": procedure
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/generate-procedure")
async def websocket_generate_procedure(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait for the client to send the JSON payload
        data = await websocket.receive_text()
        json_data = json.loads(data)
        
        # 1. Build Query
        await websocket.send_json({"status": "progress", "message": "Building search query..."})
        base_query = build_search_query_from_json(json_data)
        
        # 2. Search for URLs
        await websocket.send_json({"status": "progress", "message": f"Searching for: {base_query}..."})
        urls = search_gov_sites(base_query, max_results=2)
        
        if not urls:
            await websocket.send_json({"status": "error", "message": "No government websites found for this query."})
            await websocket.close()
            return
            
        await websocket.send_json({
            "status": "sources_found",
            "urls": urls,
            "message": f"Found {len(urls)} potential sources to check."
        })
            
        # 3. Scrape the top URL(s)
        combined_markdown = ""
        used_urls = []
        
        for url in urls:
            await websocket.send_json({
                "status": "checking_source", 
                "url": url,
                "message": f"Extracting information from: {url}..."
            })
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                used_urls.append(url)
                await websocket.send_json({
                    "status": "source_success", 
                    "url": url,
                    "message": f"Successfully extracted relevant info from {url}!"
                })
                break # Just take the first successful one
                
        if not combined_markdown:
            await websocket.send_json({"status": "error", "message": "Could not retrieve content from any of the URLs."})
            await websocket.close()
            return
            
        # 4. Generate Procedure
        await websocket.send_json({"status": "progress", "message": "Analyzing content and generating procedure with Ollama..."})
        
        procedure_json_str = ""
        emitted_thoughts = set()
        
        for chunk in generate_procedure_with_ollama_stream(json_data, combined_markdown):
            if chunk is None:
                await websocket.send_json({"status": "error", "message": "Failed to stream procedure from Ollama."})
                await websocket.close()
                return
            procedure_json_str += chunk
            
            # Detect which section the LLM is currently generating and send a readable update
            if "process_type" in procedure_json_str and "type" not in emitted_thoughts:
                await websocket.send_json({"status": "llm_thinking", "message": "Determining process type (online/offline)..."})
                emitted_thoughts.add("type")
            elif "prerequisites" in procedure_json_str and "prereq" not in emitted_thoughts:
                await websocket.send_json({"status": "llm_thinking", "message": "Analyzing prerequisites and conditions..."})
                emitted_thoughts.add("prereq")
            elif "required_documentation" in procedure_json_str and "docs" not in emitted_thoughts:
                await websocket.send_json({"status": "llm_thinking", "message": "Identifying required documents..."})
                emitted_thoughts.add("docs")
            elif "estimated_time" in procedure_json_str and "time" not in emitted_thoughts:
                await websocket.send_json({"status": "llm_thinking", "message": "Calculating estimated timeline..."})
                emitted_thoughts.add("time")
            elif "step_by_step_procedure" in procedure_json_str and "steps" not in emitted_thoughts:
                await websocket.send_json({"status": "llm_thinking", "message": "Formulating step-by-step procedure..."})
                emitted_thoughts.add("steps")
            
        # Parse the JSON string returned by Ollama back into a dict so it sends cleanly
        try:
            procedure = json.loads(procedure_json_str)
        except json.JSONDecodeError:
            procedure = procedure_json_str # Fallback if it didn't return valid JSON
            
        # 5. Send Final Result
        await websocket.send_json({
            "status": "completed",
            "query_used": base_query,
            "urls_scraped": used_urls,
            "procedure": procedure
        })
        
        await websocket.close()
        
    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
