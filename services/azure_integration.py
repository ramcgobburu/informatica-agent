import openai
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio
from datetime import datetime

from config import Config
from models.workflow_models import Workflow, DebugResult, WorkflowSearchResult

logger = logging.getLogger(__name__)

class AzureIntegrationService:
    """Service for integrating with Azure AI services and tools"""
    
    def __init__(self):
        self.openai_client = None
        self.search_client = None
        self.blob_service_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure service clients"""
        try:
            # Initialize OpenAI client for Azure OpenAI
            if Config.AZURE_OPENAI_ENDPOINT and Config.AZURE_OPENAI_API_KEY:
                self.openai_client = openai.AzureOpenAI(
                    api_key=Config.AZURE_OPENAI_API_KEY,
                    api_version=Config.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
                )
                logger.info("Azure OpenAI client initialized")
            
            # Initialize Azure Search client
            if Config.AZURE_SEARCH_ENDPOINT and Config.AZURE_SEARCH_API_KEY:
                credential = AzureKeyCredential(Config.AZURE_SEARCH_API_KEY)
                self.search_client = SearchClient(
                    endpoint=Config.AZURE_SEARCH_ENDPOINT,
                    index_name=Config.AZURE_SEARCH_INDEX_NAME,
                    credential=credential
                )
                logger.info("Azure Search client initialized")
            
            # Initialize Azure Storage client
            if Config.AZURE_STORAGE_CONNECTION_STRING:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    Config.AZURE_STORAGE_CONNECTION_STRING
                )
                logger.info("Azure Storage client initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Azure clients: {e}")
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response using Azure OpenAI"""
        try:
            if not self.openai_client:
                return "Azure OpenAI service not configured"
            
            # Build system message
            system_message = self._build_system_message(context)
            
            # Build user message
            user_message = self._build_user_message(prompt, context)
            
            # Call Azure OpenAI
            response = self.openai_client.chat.completions.create(
                model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error generating response: {str(e)}"
    
    def _build_system_message(self, context: Dict[str, Any] = None) -> str:
        """Build system message for Azure OpenAI"""
        system_message = """You are an expert Informatica PowerCenter consultant and debugging specialist. 
        Your role is to help users understand their Informatica workflows, identify issues, and provide solutions.
        
        Key capabilities:
        1. Analyze workflow metadata to understand data flow
        2. Identify potential causes of data loading issues
        3. Provide specific recommendations for debugging
        4. Explain complex transformations and mappings
        5. Suggest best practices for workflow optimization
        
        Always provide:
        - Clear, actionable recommendations
        - Specific workflow and component names
        - Step-by-step debugging procedures
        - Alternative solutions when applicable
        
        Be precise and avoid hallucinations. If you don't have enough information, ask for clarification."""
        
        if context and context.get('workflow_results'):
            system_message += f"\n\nCurrent context includes {len(context['workflow_results'])} workflow search results."
        
        if context and context.get('debug_results'):
            system_message += f"\n\nCurrent context includes debugging analysis for table: {context['debug_results'].table_name}"
        
        return system_message
    
    def _build_user_message(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Build user message with context"""
        user_message = f"User question: {prompt}\n\n"
        
        if context:
            if context.get('workflow_results'):
                user_message += "Relevant workflows found:\n"
                for result in context['workflow_results'][:5]:  # Limit to top 5
                    user_message += f"- {result.workflow.name} (in {result.source_file}, confidence: {result.confidence_score:.2f})\n"
                user_message += "\n"
            
            if context.get('debug_results'):
                debug_result = context['debug_results']
                user_message += f"Debug analysis for table '{debug_result.table_name}':\n"
                user_message += f"Responsible workflows: {len(debug_result.responsible_workflows)}\n"
                user_message += f"Potential issues: {', '.join(debug_result.potential_issues)}\n"
                user_message += f"Recommendations: {', '.join(debug_result.recommendations)}\n\n"
            
            if context.get('table_search_results'):
                user_message += "Table search results:\n"
                for result in context['table_search_results'][:3]:  # Limit to top 3
                    user_message += f"- {result['component_name']} in {result['workflow_name']} ({result['component_type']})\n"
                user_message += "\n"
        
        return user_message
    
    async def search_azure_search(self, query: str, filters: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """Search using Azure Cognitive Search"""
        try:
            if not self.search_client:
                logger.warning("Azure Search not configured")
                return []
            
            # Build search parameters
            search_params = {
                "search_text": query,
                "top": 10,
                "include_total_count": True
            }
            
            if filters:
                # Build filter expression
                filter_parts = []
                for key, value in filters.items():
                    filter_parts.append(f"{key} eq '{value}'")
                search_params["filter"] = " and ".join(filter_parts)
            
            # Perform search
            results = self.search_client.search(**search_params)
            
            search_results = []
            for result in results:
                search_results.append({
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("@search.score", 0.0)
                })
            
            logger.info(f"Azure Search returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching Azure Search: {e}")
            return []
    
    async def upload_xml_to_blob(self, file_path: str, blob_name: str) -> bool:
        """Upload XML file to Azure Blob Storage"""
        try:
            if not self.blob_service_client:
                logger.warning("Azure Storage not configured")
                return False
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name
            )
            
            # Upload file
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            
            logger.info(f"Uploaded {file_path} to blob {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to blob storage: {e}")
            return False
    
    async def download_xml_from_blob(self, blob_name: str, local_path: str) -> bool:
        """Download XML file from Azure Blob Storage"""
        try:
            if not self.blob_service_client:
                logger.warning("Azure Storage not configured")
                return False
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name
            )
            
            # Download file
            with open(local_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            logger.info(f"Downloaded {blob_name} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from blob storage: {e}")
            return False
    
    async def list_blob_files(self) -> List[str]:
        """List all XML files in blob storage"""
        try:
            if not self.blob_service_client:
                logger.warning("Azure Storage not configured")
                return []
            
            container_client = self.blob_service_client.get_container_client(
                Config.AZURE_STORAGE_CONTAINER_NAME
            )
            
            blob_files = []
            for blob in container_client.list_blobs():
                if blob.name.endswith('.xml'):
                    blob_files.append(blob.name)
            
            logger.info(f"Found {len(blob_files)} XML files in blob storage")
            return blob_files
            
        except Exception as e:
            logger.error(f"Error listing blob files: {e}")
            return []
    
    async def create_azure_search_index(self, index_definition: Dict[str, Any]) -> bool:
        """Create Azure Search index for workflow metadata"""
        try:
            if not self.search_client:
                logger.warning("Azure Search not configured")
                return False
            
            # This would typically be done through the Azure Search management client
            # For now, we'll log the requirement
            logger.info("Azure Search index creation requires management client")
            logger.info(f"Index definition: {json.dumps(index_definition, indent=2)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating Azure Search index: {e}")
            return False
    
    async def index_workflows_to_azure_search(self, workflows: List[Workflow]) -> bool:
        """Index workflows to Azure Search"""
        try:
            if not self.search_client:
                logger.warning("Azure Search not configured")
                return False
            
            # Prepare documents for indexing
            documents = []
            for workflow in workflows:
                doc = {
                    "id": f"{workflow.set_file}_{workflow.name}",
                    "workflow_name": workflow.name,
                    "set_file": workflow.set_file,
                    "description": workflow.description or "",
                    "status": workflow.status.value,
                    "created_date": workflow.created_date.isoformat() if workflow.created_date else None,
                    "modified_date": workflow.modified_date.isoformat() if workflow.modified_date else None,
                    "session_count": len(workflow.sessions),
                    "source_table_count": len(workflow.source_tables),
                    "target_table_count": len(workflow.target_tables),
                    "transformation_count": len(workflow.transformations),
                    "content": self._create_searchable_content(workflow)
                }
                documents.append(doc)
            
            # Upload documents
            result = self.search_client.upload_documents(documents)
            
            logger.info(f"Indexed {len(documents)} workflows to Azure Search")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing to Azure Search: {e}")
            return False
    
    def _create_searchable_content(self, workflow: Workflow) -> str:
        """Create searchable content for Azure Search"""
        content_parts = [
            f"Workflow: {workflow.name}",
            f"Description: {workflow.description or 'No description'}",
            f"Status: {workflow.status.value}"
        ]
        
        # Add source tables
        for table in workflow.source_tables:
            content_parts.append(f"Source table: {table.name}")
            if table.schema:
                content_parts.append(f"Schema: {table.schema}")
            if table.database:
                content_parts.append(f"Database: {table.database}")
        
        # Add target tables
        for table in workflow.target_tables:
            content_parts.append(f"Target table: {table.name}")
            if table.schema:
                content_parts.append(f"Schema: {table.schema}")
            if table.database:
                content_parts.append(f"Database: {table.database}")
            if table.load_type:
                content_parts.append(f"Load type: {table.load_type}")
        
        # Add transformations
        for trans in workflow.transformations:
            content_parts.append(f"Transformation: {trans.name} (type: {trans.type})")
        
        return " ".join(content_parts)
    
    async def analyze_debugging_patterns(self, table_name: str, workflow_results: List[WorkflowSearchResult]) -> DebugResult:
        """Use Azure AI to analyze debugging patterns"""
        try:
            if not self.openai_client:
                return DebugResult(
                    table_name=table_name,
                    responsible_workflows=workflow_results,
                    potential_issues=["Azure OpenAI not configured"],
                    recommendations=["Configure Azure OpenAI service"],
                    confidence_score=0.0
                )
            
            # Build analysis prompt
            prompt = self._build_debug_analysis_prompt(table_name, workflow_results)
            
            # Get AI analysis
            response = self.openai_client.chat.completions.create(
                model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": "You are an expert Informatica debugging specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            analysis = response.choices[0].message.content
            
            # Extract structured information (this would be more sophisticated in production)
            potential_issues = self._extract_issues_from_analysis(analysis)
            recommendations = self._extract_recommendations_from_analysis(analysis)
            
            return DebugResult(
                table_name=table_name,
                responsible_workflows=workflow_results,
                potential_issues=potential_issues,
                recommendations=recommendations,
                confidence_score=0.8  # This would be calculated based on analysis quality
            )
            
        except Exception as e:
            logger.error(f"Error analyzing debugging patterns: {e}")
            return DebugResult(
                table_name=table_name,
                responsible_workflows=workflow_results,
                potential_issues=[f"Analysis error: {str(e)}"],
                recommendations=["Check Azure OpenAI configuration"],
                confidence_score=0.0
            )
    
    def _build_debug_analysis_prompt(self, table_name: str, workflow_results: List[WorkflowSearchResult]) -> str:
        """Build prompt for debugging analysis"""
        prompt = f"""Analyze why the table '{table_name}' might be empty and provide debugging recommendations.

Workflows that load this table:
"""
        
        for result in workflow_results:
            prompt += f"- {result.workflow.name} (in {result.source_file}, confidence: {result.confidence_score:.2f})\n"
        
        prompt += """
Please provide:
1. Potential causes for the table being empty
2. Specific debugging steps to identify the root cause
3. Recommendations for fixing the issue

Focus on common Informatica issues like:
- Session failures
- Source data issues
- Transformation errors
- Target connection problems
- Workflow scheduling issues
"""
        
        return prompt
    
    def _extract_issues_from_analysis(self, analysis: str) -> List[str]:
        """Extract potential issues from AI analysis"""
        # Simple extraction - in production, this would be more sophisticated
        issues = []
        lines = analysis.split('\n')
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['issue', 'problem', 'error', 'failure', 'cause']):
                if line.strip() and not line.strip().startswith('#'):
                    issues.append(line.strip())
        
        return issues[:5]  # Limit to 5 issues
    
    def _extract_recommendations_from_analysis(self, analysis: str) -> List[str]:
        """Extract recommendations from AI analysis"""
        # Simple extraction - in production, this would be more sophisticated
        recommendations = []
        lines = analysis.split('\n')
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'check', 'verify', 'fix']):
                if line.strip() and not line.strip().startswith('#'):
                    recommendations.append(line.strip())
        
        return recommendations[:5]  # Limit to 5 recommendations

