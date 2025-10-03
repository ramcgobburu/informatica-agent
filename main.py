from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import logging
import asyncio
from pathlib import Path
import uuid
from datetime import datetime

from models.workflow_models import ChatRequest, ChatResponse, WorkflowSearchResult, DebugResult
from services.workflow_search_engine import WorkflowSearchEngine
from services.debugging_agent import DebuggingAgent
from services.azure_integration import AzureIntegrationService
from services.xml_parser import PowerCenterXMLParser
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Informatica Agent API",
    description="AI-powered chatbot for Informatica PowerCenter workflow analysis and debugging",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
search_engine: Optional[WorkflowSearchEngine] = None
debugging_agent: Optional[DebuggingAgent] = None
azure_service: Optional[AzureIntegrationService] = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global search_engine, debugging_agent, azure_service
    
    try:
        # Initialize Azure service
        azure_service = AzureIntegrationService()
        
        # Initialize search engine
        search_engine = WorkflowSearchEngine()
        
        # Initialize debugging agent
        debugging_agent = DebuggingAgent(search_engine, azure_service)
        
        # Initialize from XML files if directory exists
        xml_dir = Path(Config.XML_FILES_DIRECTORY)
        if xml_dir.exists() and xml_dir.is_dir():
            logger.info(f"Initializing from XML files in {xml_dir}")
            success = await search_engine.initialize_from_xml_files(str(xml_dir))
            if success:
                logger.info("Successfully initialized search engine from XML files")
            else:
                logger.warning("Failed to initialize search engine from XML files")
        else:
            logger.warning(f"XML directory not found: {xml_dir}")
        
        logger.info("Services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Informatica Agent API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        stats = search_engine.get_search_statistics() if search_engine else {}
        return {
            "status": "healthy",
            "search_engine": "initialized" if search_engine else "not_initialized",
            "debugging_agent": "initialized" if debugging_agent else "not_initialized",
            "azure_service": "initialized" if azure_service else "not_initialized",
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chatbot endpoint"""
    try:
        if not search_engine or not debugging_agent:
            raise HTTPException(status_code=500, detail="Services not initialized")
        
        session_id = request.session_id or str(uuid.uuid4())
        user_message = request.message.lower()
        
        # Initialize response
        response_data = {
            "response": "",
            "debug_results": None,
            "workflow_results": None,
            "confidence_score": 0.0,
            "source_files": [],
            "session_id": session_id
        }
        
        # Determine intent and process accordingly
        if "workflow" in user_message and ("show" in user_message or "find" in user_message or "get" in user_message):
            # Workflow search intent
            workflow_results = await _handle_workflow_search(user_message, search_engine)
            response_data["workflow_results"] = workflow_results
            response_data["source_files"] = [result.source_file for result in workflow_results]
            response_data["confidence_score"] = max([r.confidence_score for r in workflow_results]) if workflow_results else 0.0
            
            # Generate response using Azure AI
            context = {"workflow_results": workflow_results}
            response_data["response"] = await azure_service.generate_response(request.message, context)
            
        elif "table" in user_message and ("empty" in user_message or "issue" in user_message or "problem" in user_message):
            # Table debugging intent
            table_name = _extract_table_name(user_message)
            if table_name:
                debug_result = await debugging_agent.analyze_table_issue(table_name, user_message)
                response_data["debug_results"] = debug_result
                response_data["source_files"] = [result.source_file for result in debug_result.responsible_workflows]
                response_data["confidence_score"] = debug_result.confidence_score
                
                # Generate response using Azure AI
                context = {"debug_results": debug_result}
                response_data["response"] = await azure_service.generate_response(request.message, context)
            else:
                response_data["response"] = "I couldn't identify the table name in your message. Please specify which table you're having issues with."
                
        elif "component" in user_message or "transformation" in user_message or "mapping" in user_message:
            # Component search intent
            component_results = await _handle_component_search(user_message, search_engine)
            response_data["workflow_results"] = component_results
            response_data["source_files"] = list(set([result.source_file for result in component_results]))
            response_data["confidence_score"] = max([r.confidence_score for r in component_results]) if component_results else 0.0
            
            # Generate response using Azure AI
            context = {"workflow_results": component_results}
            response_data["response"] = await azure_service.generate_response(request.message, context)
            
        else:
            # General query - try workflow search first
            workflow_results = await _handle_workflow_search(user_message, search_engine)
            if workflow_results:
                response_data["workflow_results"] = workflow_results
                response_data["source_files"] = [result.source_file for result in workflow_results]
                response_data["confidence_score"] = max([r.confidence_score for r in workflow_results])
                
                context = {"workflow_results": workflow_results}
                response_data["response"] = await azure_service.generate_response(request.message, context)
            else:
                # No specific results found
                response_data["response"] = "I couldn't find specific information about your query. Please try rephrasing your question or be more specific about the workflow, table, or component you're asking about."
        
        return ChatResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

@app.get("/workflows/search")
async def search_workflows(
    query: str,
    exact_match: bool = False,
    limit: int = 10
):
    """Search for workflows by name"""
    try:
        if not search_engine:
            raise HTTPException(status_code=500, detail="Search engine not initialized")
        
        results = await search_engine.search_workflow_by_name(query, exact_match)
        return {
            "query": query,
            "results": results[:limit],
            "total_count": len(results),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Workflow search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/workflows/{workflow_name}")
async def get_workflow_details(workflow_name: str, set_file: Optional[str] = None):
    """Get detailed information about a specific workflow"""
    try:
        if not search_engine:
            raise HTTPException(status_code=500, detail="Search engine not initialized")
        
        if set_file:
            workflow = await search_engine.get_workflow_details(workflow_name, set_file)
        else:
            # Search for the workflow first
            results = await search_engine.search_workflow_by_name(workflow_name, exact_match=True)
            if not results:
                raise HTTPException(status_code=404, detail="Workflow not found")
            workflow = results[0].workflow
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return {
            "workflow": workflow,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get workflow details error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting workflow details: {str(e)}")

@app.get("/tables/{table_name}/workflows")
async def get_table_workflows(table_name: str):
    """Get workflows that load a specific table"""
    try:
        if not search_engine:
            raise HTTPException(status_code=500, detail="Search engine not initialized")
        
        results = await search_engine.search_table_workflows(table_name)
        return {
            "table_name": table_name,
            "workflows": results,
            "total_count": len(results),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Table workflows search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.post("/debug/table")
async def debug_table_issue(table_name: str, issue_description: str = ""):
    """Debug why a table might be empty or have issues"""
    try:
        if not debugging_agent:
            raise HTTPException(status_code=500, detail="Debugging agent not initialized")
        
        debug_result = await debugging_agent.analyze_table_issue(table_name, issue_description)
        return {
            "debug_result": debug_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Table debug error: {e}")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")

@app.post("/debug/workflow")
async def debug_workflow_issue(workflow_name: str, issue_description: str = ""):
    """Debug a specific workflow issue"""
    try:
        if not debugging_agent:
            raise HTTPException(status_code=500, detail="Debugging agent not initialized")
        
        debug_result = await debugging_agent.debug_workflow_issue(workflow_name, issue_description)
        return {
            "debug_result": debug_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Workflow debug error: {e}")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")

@app.post("/upload/xml")
async def upload_xml_file(file: UploadFile = File(...)):
    """Upload and process an XML file"""
    try:
        if not file.filename.endswith('.xml'):
            raise HTTPException(status_code=400, detail="File must be an XML file")
        
        # Save file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Parse XML file
        parser = PowerCenterXMLParser()
        workflows = parser.parse_xml_file(str(temp_path))
        
        # Index workflows if search engine is available
        if search_engine and workflows:
            # Add to cache
            set_name = temp_path.stem
            search_engine.workflow_cache[set_name] = workflows
            
            # Index in vector database
            search_engine.vector_db.index_workflows(workflows)
        
        # Clean up temp file
        temp_path.unlink()
        
        return {
            "filename": file.filename,
            "workflows_parsed": len(workflows),
            "workflow_names": [w.name for w in workflows],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"XML upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.post("/refresh")
async def refresh_xml_files(xml_directory: str = Config.XML_FILES_DIRECTORY):
    """Refresh the search engine from XML files"""
    try:
        if not search_engine:
            raise HTTPException(status_code=500, detail="Search engine not initialized")
        
        success = await search_engine.refresh_from_xml_files(xml_directory)
        if success:
            return {
                "status": "success",
                "message": "Search engine refreshed successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to refresh search engine")
        
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh error: {str(e)}")

@app.get("/statistics")
async def get_statistics():
    """Get system statistics"""
    try:
        stats = {}
        
        if search_engine:
            stats["search_engine"] = search_engine.get_search_statistics()
        
        if debugging_agent:
            stats["debugging_agent"] = await debugging_agent.get_debugging_statistics()
        
        return {
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=f"Statistics error: {str(e)}")

# Helper functions
async def _handle_workflow_search(query: str, search_engine: WorkflowSearchEngine) -> List[WorkflowSearchResult]:
    """Handle workflow search requests"""
    # Extract workflow name from query
    workflow_name = _extract_workflow_name(query)
    if workflow_name:
        return await search_engine.search_workflow_by_name(workflow_name)
    else:
        # Try general search
        return await search_engine.search_workflow_by_name(query, exact_match=False)

async def _handle_component_search(query: str, search_engine: WorkflowSearchEngine) -> List[WorkflowSearchResult]:
    """Handle component search requests"""
    # For now, treat as workflow search
    return await search_engine.search_workflow_by_name(query, exact_match=False)

def _extract_workflow_name(query: str) -> Optional[str]:
    """Extract workflow name from query"""
    # Simple extraction - can be improved with NLP
    words = query.split()
    for i, word in enumerate(words):
        if word.lower() in ["workflow", "wf", "mapping"]:
            if i + 1 < len(words):
                return words[i + 1]
    return None

def _extract_table_name(query: str) -> Optional[str]:
    """Extract table name from query"""
    # Simple extraction - can be improved with NLP
    words = query.split()
    for i, word in enumerate(words):
        if word.lower() in ["table", "tbl"]:
            if i + 1 < len(words):
                return words[i + 1]
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG
    )

