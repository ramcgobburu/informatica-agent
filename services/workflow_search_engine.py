import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import asyncio
from datetime import datetime

from models.workflow_models import (
    Workflow, WorkflowSearchResult, DebugResult, 
    ComponentType, ComponentStatus
)
from services.xml_parser import PowerCenterXMLParser
from services.vector_database import VectorDatabaseService
from services.azure_integration import AzureIntegrationService

logger = logging.getLogger(__name__)

class WorkflowSearchEngine:
    """Robust workflow search engine to prevent RAG bleed and ensure accurate results"""
    
    def __init__(self):
        self.xml_parser = PowerCenterXMLParser()
        self.vector_db = VectorDatabaseService()
        self.azure_service = AzureIntegrationService()
        self.workflow_cache = {}
        self.search_history = []
    
    async def initialize_from_xml_files(self, xml_directory: str) -> bool:
        """Initialize the search engine by parsing all XML files"""
        try:
            xml_path = Path(xml_directory)
            if not xml_path.exists():
                logger.error(f"XML directory not found: {xml_directory}")
                return False
            
            all_workflows = []
            xml_files = list(xml_path.glob("*.xml"))
            
            logger.info(f"Found {len(xml_files)} XML files to process")
            
            for xml_file in xml_files:
                try:
                    logger.info(f"Processing {xml_file.name}")
                    workflows = self.xml_parser.parse_xml_file(str(xml_file))
                    
                    # Cache workflows by set file
                    set_name = xml_file.stem
                    self.workflow_cache[set_name] = workflows
                    
                    all_workflows.extend(workflows)
                    
                    logger.info(f"Parsed {len(workflows)} workflows from {xml_file.name}")
                    
                except Exception as e:
                    logger.error(f"Error processing {xml_file.name}: {e}")
                    continue
            
            # Index all workflows in vector database
            if all_workflows:
                success = self.vector_db.index_workflows(all_workflows)
                if success:
                    logger.info(f"Successfully indexed {len(all_workflows)} workflows")
                else:
                    logger.error("Failed to index workflows in vector database")
                    return False
            
            # Index to Azure Search if configured
            if self.azure_service.search_client:
                await self.azure_service.index_workflows_to_azure_search(all_workflows)
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing search engine: {e}")
            return False
    
    async def search_workflow_by_name(self, workflow_name: str, exact_match: bool = True) -> List[WorkflowSearchResult]:
        """Search for a workflow by name with exact match validation"""
        try:
            results = []
            
            # First, try exact match in cache
            if exact_match:
                exact_results = self._exact_name_search(workflow_name)
                if exact_results:
                    return exact_results
            
            # Then, try semantic search
            semantic_results = self.vector_db.search_workflows(workflow_name, limit=10)
            
            # Validate semantic results against exact matches
            validated_results = self._validate_search_results(workflow_name, semantic_results)
            
            # Add to search history
            self.search_history.append({
                "query": workflow_name,
                "timestamp": datetime.now(),
                "results_count": len(validated_results),
                "exact_match": exact_match
            })
            
            return validated_results
            
        except Exception as e:
            logger.error(f"Error searching workflow by name: {e}")
            return []
    
    def _exact_name_search(self, workflow_name: str) -> List[WorkflowSearchResult]:
        """Perform exact name search in cached workflows"""
        exact_results = []
        
        for set_name, workflows in self.workflow_cache.items():
            for workflow in workflows:
                if workflow.name.lower() == workflow_name.lower():
                    result = WorkflowSearchResult(
                        workflow=workflow,
                        confidence_score=1.0,
                        match_reason=f"Exact name match in {set_name}",
                        source_file=set_name
                    )
                    exact_results.append(result)
        
        return exact_results
    
    def _validate_search_results(self, query: str, semantic_results: List[WorkflowSearchResult]) -> List[WorkflowSearchResult]:
        """Validate semantic search results to prevent hallucinations"""
        validated_results = []
        
        for result in semantic_results:
            # Check if the workflow actually exists in our cache
            if self._workflow_exists_in_cache(result.workflow):
                # Validate the match makes sense
                if self._is_reasonable_match(query, result.workflow):
                    validated_results.append(result)
                else:
                    # Lower confidence for questionable matches
                    result.confidence_score *= 0.5
                    if result.confidence_score > 0.3:  # Minimum threshold
                        validated_results.append(result)
        
        return validated_results
    
    def _workflow_exists_in_cache(self, workflow: Workflow) -> bool:
        """Check if workflow exists in our cache"""
        if workflow.set_file in self.workflow_cache:
            for cached_workflow in self.workflow_cache[workflow.set_file]:
                if cached_workflow.name == workflow.name:
                    return True
        return False
    
    def _is_reasonable_match(self, query: str, workflow: Workflow) -> bool:
        """Check if the match is reasonable to prevent hallucinations"""
        query_lower = query.lower()
        workflow_name_lower = workflow.name.lower()
        
        # Exact match
        if query_lower == workflow_name_lower:
            return True
        
        # Contains match
        if query_lower in workflow_name_lower or workflow_name_lower in query_lower:
            return True
        
        # Fuzzy match for common variations
        # Remove common prefixes/suffixes and compare
        query_clean = re.sub(r'^(wf_|workflow_|mapping_)', '', query_lower)
        workflow_clean = re.sub(r'^(wf_|workflow_|mapping_)', '', workflow_name_lower)
        
        if query_clean == workflow_clean:
            return True
        
        # Check if query is a significant part of workflow name
        if len(query_clean) > 3 and query_clean in workflow_clean:
            return True
        
        return False
    
    async def search_table_workflows(self, table_name: str) -> List[WorkflowSearchResult]:
        """Search for workflows that load a specific table"""
        try:
            # Use vector database to find table-related workflows
            table_results = self.vector_db.find_table_workflows(table_name)
            
            # Validate results
            validated_results = []
            for result in table_results:
                if self._workflow_exists_in_cache(result.workflow):
                    # Check if the table actually exists in this workflow
                    if self._table_exists_in_workflow(table_name, result.workflow):
                        validated_results.append(result)
            
            # Sort by confidence score
            validated_results.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return validated_results
            
        except Exception as e:
            logger.error(f"Error searching table workflows: {e}")
            return []
    
    def _table_exists_in_workflow(self, table_name: str, workflow: Workflow) -> bool:
        """Check if table exists in workflow (source or target)"""
        table_name_lower = table_name.lower()
        
        # Check source tables
        for source_table in workflow.source_tables:
            if source_table.name.lower() == table_name_lower:
                return True
        
        # Check target tables
        for target_table in workflow.target_tables:
            if target_table.name.lower() == table_name_lower:
                return True
        
        return False
    
    async def search_components(self, component_name: str, component_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for specific components (tables, transformations, etc.)"""
        try:
            # Use vector database for component search
            component_results = self.vector_db.search_components(
                component_name, 
                component_type, 
                limit=20
            )
            
            # Validate results
            validated_results = []
            for result in component_results:
                if self._component_exists_in_cache(result):
                    validated_results.append(result)
            
            return validated_results
            
        except Exception as e:
            logger.error(f"Error searching components: {e}")
            return []
    
    def _component_exists_in_cache(self, result: Dict[str, Any]) -> bool:
        """Check if component exists in our cache"""
        workflow_name = result['workflow_name']
        set_file = result['set_file']
        
        if set_file in self.workflow_cache:
            for workflow in self.workflow_cache[set_file]:
                if workflow.name == workflow_name:
                    return True
        return False
    
    async def debug_table_issue(self, table_name: str) -> DebugResult:
        """Debug why a table might be empty or have issues"""
        try:
            # Find workflows that load this table
            workflow_results = await self.search_table_workflows(table_name)
            
            if not workflow_results:
                return DebugResult(
                    table_name=table_name,
                    responsible_workflows=[],
                    potential_issues=["No workflows found that load this table"],
                    recommendations=["Verify table name and check if workflows exist"],
                    confidence_score=0.0
                )
            
            # Use Azure AI to analyze the issue
            debug_result = await self.azure_service.analyze_debugging_patterns(
                table_name, workflow_results
            )
            
            return debug_result
            
        except Exception as e:
            logger.error(f"Error debugging table issue: {e}")
            return DebugResult(
                table_name=table_name,
                responsible_workflows=[],
                potential_issues=[f"Debug analysis error: {str(e)}"],
                recommendations=["Check system configuration and try again"],
                confidence_score=0.0
            )
    
    async def get_workflow_details(self, workflow_name: str, set_file: str) -> Optional[Workflow]:
        """Get detailed information about a specific workflow"""
        try:
            if set_file in self.workflow_cache:
                for workflow in self.workflow_cache[set_file]:
                    if workflow.name == workflow_name:
                        return workflow
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting workflow details: {e}")
            return None
    
    async def get_workflow_dependencies(self, workflow_name: str) -> List[Workflow]:
        """Get workflows that depend on the specified workflow"""
        try:
            dependencies = []
            
            for set_name, workflows in self.workflow_cache.items():
                for workflow in workflows:
                    # Check if this workflow depends on the specified workflow
                    if self._workflow_depends_on(workflow, workflow_name):
                        dependencies.append(workflow)
            
            return dependencies
            
        except Exception as e:
            logger.error(f"Error getting workflow dependencies: {e}")
            return []
    
    def _workflow_depends_on(self, workflow: Workflow, target_workflow: str) -> bool:
        """Check if a workflow depends on another workflow"""
        # Check if target workflow is in dependencies
        if target_workflow in workflow.dependencies:
            return True
        
        # Check if any source tables come from the target workflow
        for source_table in workflow.source_tables:
            if self._table_comes_from_workflow(source_table.name, target_workflow):
                return True
        
        return False
    
    def _table_comes_from_workflow(self, table_name: str, workflow_name: str) -> bool:
        """Check if a table comes from a specific workflow"""
        for set_name, workflows in self.workflow_cache.items():
            for workflow in workflows:
                if workflow.name == workflow_name:
                    for target_table in workflow.target_tables:
                        if target_table.name == table_name:
                            return True
        return False
    
    async def search_with_filters(self, query: str, filters: Dict[str, Any]) -> List[WorkflowSearchResult]:
        """Search workflows with additional filters"""
        try:
            # Get base results
            results = await self.search_workflow_by_name(query, exact_match=False)
            
            # Apply filters
            filtered_results = []
            for result in results:
                if self._matches_filters(result.workflow, filters):
                    filtered_results.append(result)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error searching with filters: {e}")
            return []
    
    def _matches_filters(self, workflow: Workflow, filters: Dict[str, Any]) -> bool:
        """Check if workflow matches the given filters"""
        for filter_key, filter_value in filters.items():
            if filter_key == "status":
                if workflow.status.value != filter_value:
                    return False
            elif filter_key == "set_file":
                if workflow.set_file != filter_value:
                    return False
            elif filter_key == "has_source_table":
                if not any(table.name == filter_value for table in workflow.source_tables):
                    return False
            elif filter_key == "has_target_table":
                if not any(table.name == filter_value for table in workflow.target_tables):
                    return False
            elif filter_key == "min_sessions":
                if len(workflow.sessions) < filter_value:
                    return False
            elif filter_key == "max_sessions":
                if len(workflow.sessions) > filter_value:
                    return False
        
        return True
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get search engine statistics"""
        total_workflows = sum(len(workflows) for workflows in self.workflow_cache.values())
        total_sets = len(self.workflow_cache)
        
        return {
            "total_workflows": total_workflows,
            "total_sets": total_sets,
            "search_history_count": len(self.search_history),
            "cache_status": "loaded" if self.workflow_cache else "empty",
            "vector_db_status": "initialized",
            "azure_integration_status": "configured" if self.azure_service.openai_client else "not_configured"
        }
    
    def clear_cache(self):
        """Clear the workflow cache"""
        self.workflow_cache.clear()
        self.search_history.clear()
        logger.info("Workflow cache cleared")
    
    async def refresh_from_xml_files(self, xml_directory: str) -> bool:
        """Refresh the search engine from XML files"""
        try:
            # Clear existing cache
            self.clear_cache()
            
            # Reinitialize from XML files
            return await self.initialize_from_xml_files(xml_directory)
            
        except Exception as e:
            logger.error(f"Error refreshing from XML files: {e}")
            return False

