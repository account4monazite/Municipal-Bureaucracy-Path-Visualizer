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
    task: Optional[str] = None
    query: Optional[str] = None
    location: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


class ExtractRequest(BaseModel):
    message: str
    context: Optional[str] = None


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
        attach_to_node_id = json_data.get("attachToNodeId")
        
        if not query:
            await websocket.send_json({"type": "status", "message": "Query cannot be empty."})
            await websocket.close()
            return
            
        # 1. Search for URLs
        await websocket.send_json({"type": "status", "message": f"Searching for: {query}..."})
        urls = search_gov_sites(query, max_results=2)
        
        if not urls:
            await websocket.send_json({"type": "status", "message": "No government websites found for this query."})
            await websocket.close()
            return
            
        await websocket.send_json({
            "type": "status",
            "urls": urls,
            "message": f"Found {len(urls)} potential sources to check."
        })
            
        # 3. Scrape the top URL(s)
        combined_markdown = ""
        used_urls = []
        
        for url in urls:
            await websocket.send_json({
                "type": "status", 
                "url": url,
                "message": f"Extracting information from: {url}..."
            })
            md_content = scrape_url_with_firecrawl(url)
            if md_content:
                combined_markdown += f"\n\nSource: {url}\n{md_content}\n"
                used_urls.append(url)
                await websocket.send_json({
                    "type": "status", 
                    "url": url,
                    "message": f"Successfully extracted relevant info from {url}!"
                })
                break # Just take the first successful one
                
        if not combined_markdown:
            await websocket.send_json({"type": "status", "message": "Could not retrieve content from any of the URLs."})
            await websocket.close()
            return
            
        # 4. Generate Procedure
        await websocket.send_json({"type": "status", "message": "Analyzing content and generating procedure with Ollama..."})
        
        procedure_json_str = ""
        emitted_thoughts = set()
        
        for chunk in generate_procedure_with_ollama_stream(query, combined_markdown):
            if chunk is None:
                await websocket.send_json({"type": "status", "message": "Failed to stream procedure from Ollama."})
                await websocket.close()
                return
            procedure_json_str += chunk
            
            # Detect which section the LLM is currently generating and send a readable update
            if "process_type" in procedure_json_str and "process_type" not in emitted_thoughts:
                await websocket.send_json({"type": "status", "message": "Determining process type (online/offline)..."})
                emitted_thoughts.add("process_type")
            elif "prerequisites" in procedure_json_str and "prereq" not in emitted_thoughts:
                await websocket.send_json({"type": "status", "message": "Analyzing prerequisites and conditions..."})
                emitted_thoughts.add("prereq")
            elif "required_documentation" in procedure_json_str and "docs" not in emitted_thoughts:
                await websocket.send_json({"type": "status", "message": "Identifying required documents..."})
                emitted_thoughts.add("docs")
            elif "estimated_time" in procedure_json_str and "time" not in emitted_thoughts:
                await websocket.send_json({"type": "status", "message": "Calculating estimated timeline..."})
                emitted_thoughts.add("time")
            elif "step_by_step_procedure" in procedure_json_str and "steps" not in emitted_thoughts:
                await websocket.send_json({"type": "status", "message": "Formulating step-by-step procedure..."})
                emitted_thoughts.add("steps")
            
        # Parse the JSON string returned by Ollama back into a dict so it sends cleanly
        try:
            procedure = json.loads(procedure_json_str)
        except json.JSONDecodeError:
            procedure = {}
            
        # Transform the linear procedure into the ApiPayload graph structure expected by frontend
        nodes = {}
        initial_nodes = []
        initial_edges = []
        
        if isinstance(procedure, dict):
            prereq_node_ids = []
            prereqs = procedure.get("prerequisites", [])
            if prereqs and isinstance(prereqs, list):
                for k, prereq in enumerate(prereqs):
                    prereq_id = f"prereq_{k+1}"
                    title = str(prereq)[:30] + "..." if len(str(prereq)) > 30 else str(prereq)
                    nodes[prereq_id] = {
                        "id": prereq_id, "type": "process", "title": title,
                        "chatText": str(prereq), "prerequisites": []
                    }
                    prereq_node_ids.append(prereq_id)
                
            doc_node_ids = []
            docs = procedure.get("required_documentation", [])
            if docs and isinstance(docs, list):
                for j, doc in enumerate(docs):
                    doc_id = f"doc_{j+1}"
                    title = str(doc)[:30] + "..." if len(str(doc)) > 30 else str(doc)
                    nodes[doc_id] = {
                        "id": doc_id, "type": "document", "title": title,
                        "chatText": str(doc), "prerequisites": []
                    }
                    doc_node_ids.append(doc_id)
                
            steps = procedure.get("step_by_step_procedure", [])
            prev_node_id = None
            
            # Create a main Prerequisites node to hold all docs and prereqs
            if prereq_node_ids or doc_node_ids:
                nodes["node_prereqs_main"] = {
                    "id": "node_prereqs_main",
                    "type": "process",
                    "title": "Prerequisites & Docs",
                    "chatText": "Expand to see all requirements and documents needed before starting.",
                    "prerequisites": prereq_node_ids + doc_node_ids
                }
                initial_nodes.append("node_prereqs_main")
                prev_node_id = "node_prereqs_main"
                
            if steps and isinstance(steps, list):
                for i, step in enumerate(steps):
                    node_id = f"step_{i+1}"
                    title = f"Step {i+1}"
                    chat_text = str(step)
                    
                    if isinstance(step, dict):
                        title = step.get("title", title)
                        chat_text = step.get("description", step.get("text", chat_text))
                    elif isinstance(step, str):
                        first_sentence = step.split('.')[0] if '.' in step else step
                        if len(first_sentence) < 60:
                            title = first_sentence

                    nodes[node_id] = {
                        "id": node_id, "type": "process", "title": title,
                        "chatText": chat_text, "prerequisites": []
                    }
                    initial_nodes.append(node_id)
                    if prev_node_id:
                        initial_edges.append({"source": prev_node_id, "target": node_id})
                    prev_node_id = node_id

            process_type = procedure.get("process_type", "N/A")
            estimated_time = procedure.get("estimated_time", "N/A")
            narrative = f"Process Type: {process_type}. Estimated Time: {estimated_time}."
        else:
            narrative = "Could not parse procedure."

        payload = {
            "task": query,
            "narrative": narrative,
            "initialNodes": initial_nodes,
            "initialEdges": initial_edges,
            "nodes": nodes
        }
        
        # Save the final JSON to a local file for debugging
        try:
            with open("req_final.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save req_final.json: {e}")
            
        # 5. Send Final Result
        await websocket.send_json({
            "type": "complete",
            "attachToNodeId": attach_to_node_id,
            "payload": payload
        })
        
        await websocket.close()
        
    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        await websocket.send_json({"type": "status", "message": f"Error: {str(e)}"})
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
