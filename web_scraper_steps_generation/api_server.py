from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import json
from pydantic import BaseModel
from typing import Dict, Any

# Import the functions from your existing scraper script
from gov_procedure_scraper import build_search_query_from_json, search_gov_sites, scrape_url_with_firecrawl, generate_procedure_with_ollama, generate_procedure_with_ollama_stream

app = FastAPI(title="Gov Procedure API")

# Define the expected JSON body format
class TaskRequest(BaseModel):
    query: str

@app.post("/generate-procedure")
async def generate_procedure(request: TaskRequest):
    try:
        query = request.query
        
        # 1. Search for URLs
        urls = search_gov_sites(query, max_results=2)
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
            
        # 3. Generate Procedure
        procedure = generate_procedure_with_ollama(query, combined_markdown)
        
        if not procedure:
            raise HTTPException(status_code=500, detail="Failed to generate procedure with Ollama.")
            
        return {
            "query_used": query,
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
        query = json_data.get("query", "")
        
        if not query:
            await websocket.send_json({"status": "error", "message": "Query cannot be empty."})
            await websocket.close()
            return
            
        # 1. Search for URLs
        await websocket.send_json({"status": "progress", "message": f"Searching for: {query}..."})
        urls = search_gov_sites(query, max_results=2)
        
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
        
        for chunk in generate_procedure_with_ollama_stream(query, combined_markdown):
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
            "query_used": query,
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
