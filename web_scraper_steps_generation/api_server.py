from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import json
from pydantic import BaseModel
from typing import Dict, Any

# Import the functions from your existing scraper script
from gov_procedure_scraper import build_search_query_from_json, search_gov_sites, scrape_url_with_firecrawl, generate_procedure_with_ollama

app = FastAPI(title="Gov Procedure API")

# Define the expected JSON body format (can accept any arbitrary JSON)
class TaskRequest(BaseModel):
    task: str
    location: Dict[str, str]
    details: Dict[str, Any]

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
        for url in urls:
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                break # Just take the first successful one
                
        if not combined_markdown:
            raise HTTPException(status_code=500, detail="Could not retrieve content from any of the URLs.")
            
        # 4. Generate Procedure
        procedure = generate_procedure_with_ollama(json_data, combined_markdown)
        
        if not procedure:
            raise HTTPException(status_code=500, detail="Failed to generate procedure with Ollama.")
            
        return {
            "query_used": base_query,
            "urls_scraped": urls,
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
            
        # 3. Scrape the top URL(s)
        await websocket.send_json({"status": "progress", "message": f"Found {len(urls)} URLs. Scraping content..."})
        combined_markdown = ""
        for url in urls:
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                break # Just take the first successful one
                
        if not combined_markdown:
            await websocket.send_json({"status": "error", "message": "Could not retrieve content from any of the URLs."})
            await websocket.close()
            return
            
        # 4. Generate Procedure
        await websocket.send_json({"status": "progress", "message": "Analyzing content and generating procedure with Ollama..."})
        procedure_json_str = generate_procedure_with_ollama(json_data, combined_markdown)
        
        if not procedure_json_str:
            await websocket.send_json({"status": "error", "message": "Failed to generate procedure with Ollama."})
            await websocket.close()
            return
            
        # Parse the JSON string returned by Ollama back into a dict so it sends cleanly
        try:
            procedure = json.loads(procedure_json_str)
        except json.JSONDecodeError:
            procedure = procedure_json_str # Fallback if it didn't return valid JSON
            
        # 5. Send Final Result
        await websocket.send_json({
            "status": "completed",
            "query_used": base_query,
            "urls_scraped": urls,
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
