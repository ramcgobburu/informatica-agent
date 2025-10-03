import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional, Tuple
import logging
import json
import hashlib
from pathlib import Path

from models.workflow_models import Workflow, WorkflowSearchResult, DebugResult
from config import Config

logger = logging.getLogger(__name__)

class VectorDatabaseService:
    """Service for managing vector database operations to prevent RAG bleed"""
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize sentence transformer for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Collection names
        self.workflow_collection_name = "workflows"
        self.component_collection_name = "components"
        self.debug_collection_name = "debug_patterns"
        
        # Initialize collections
        self._initialize_collections()
    
    def _initialize_collections(self):
        """Initialize ChromaDB collections"""
        try:
            # Workflow collection
            self.workflow_collection = self.client.get_or_create_collection(
                name=self.workflow_collection_name,
                metadata={"description": "Workflow metadata and descriptions"}
            )
            
            # Component collection (tables, transformations, etc.)
            self.component_collection = self.client.get_or_create_collection(
                name=self.component_collection_name,
                metadata={"description": "Individual components within workflows"}
            )
            
            # Debug patterns collection
            self.debug_collection = self.client.get_or_create_collection(
                name=self.debug_collection_name,
                metadata={"description": "Common debugging patterns and solutions"}
            )
            
            logger.info("Vector database collections initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing vector database: {e}")
            raise
    
    def index_workflows(self, workflows: List[Workflow]) -> bool:
        """Index workflows in the vector database"""
        try:
            workflow_documents = []
            workflow_metadatas = []
            workflow_ids = []
            
            component_documents = []
            component_metadatas = []
            component_ids = []
            
            for workflow in workflows:
                # Create workflow document
                workflow_doc = self._create_workflow_document(workflow)
                workflow_id = f"{workflow.set_file}_{workflow.name}"
                
                workflow_documents.append(workflow_doc)
                workflow_metadatas.append({
                    "name": workflow.name,
                    "set_file": workflow.set_file,
                    "type": "workflow",
                    "created_date": workflow.created_date.isoformat() if workflow.created_date else None,
                    "modified_date": workflow.modified_date.isoformat() if workflow.modified_date else None,
                    "status": workflow.status.value,
                    "session_count": len(workflow.sessions),
                    "source_table_count": len(workflow.source_tables),
                    "target_table_count": len(workflow.target_tables),
                    "transformation_count": len(workflow.transformations)
                })
                workflow_ids.append(workflow_id)
                
                # Index individual components
                for source_table in workflow.source_tables:
                    component_doc = self._create_source_table_document(source_table, workflow)
                    component_id = f"{workflow.set_file}_{workflow.name}_source_{source_table.name}"
                    
                    component_documents.append(component_doc)
                    component_metadatas.append({
                        "workflow_name": workflow.name,
                        "set_file": workflow.set_file,
                        "component_name": source_table.name,
                        "component_type": "source_table",
                        "schema": source_table.schema,
                        "database": source_table.database,
                        "connection": source_table.connection
                    })
                    component_ids.append(component_id)
                
                for target_table in workflow.target_tables:
                    component_doc = self._create_target_table_document(target_table, workflow)
                    component_id = f"{workflow.set_file}_{workflow.name}_target_{target_table.name}"
                    
                    component_documents.append(component_doc)
                    component_metadatas.append({
                        "workflow_name": workflow.name,
                        "set_file": workflow.set_file,
                        "component_name": target_table.name,
                        "component_type": "target_table",
                        "schema": target_table.schema,
                        "database": target_table.database,
                        "connection": target_table.connection,
                        "load_type": target_table.load_type
                    })
                    component_ids.append(component_id)
                
                for transformation in workflow.transformations:
                    component_doc = self._create_transformation_document(transformation, workflow)
                    component_id = f"{workflow.set_file}_{workflow.name}_trans_{transformation.name}"
                    
                    component_documents.append(component_doc)
                    component_metadatas.append({
                        "workflow_name": workflow.name,
                        "set_file": workflow.set_file,
                        "component_name": transformation.name,
                        "component_type": "transformation",
                        "transformation_type": transformation.type,
                        "input_ports": transformation.input_ports,
                        "output_ports": transformation.output_ports
                    })
                    component_ids.append(component_id)
            
            # Add to collections
            if workflow_documents:
                self.workflow_collection.add(
                    documents=workflow_documents,
                    metadatas=workflow_metadatas,
                    ids=workflow_ids
                )
            
            if component_documents:
                self.component_collection.add(
                    documents=component_documents,
                    metadatas=component_metadatas,
                    ids=component_ids
                )
            
            logger.info(f"Indexed {len(workflows)} workflows and {len(component_documents)} components")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing workflows: {e}")
            return False
    
    def search_workflows(self, query: str, limit: int = 10) -> List[WorkflowSearchResult]:
        """Search for workflows using semantic similarity"""
        try:
            # Search in workflow collection
            workflow_results = self.workflow_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            search_results = []
            
            if workflow_results['documents'] and workflow_results['documents'][0]:
                for i, doc in enumerate(workflow_results['documents'][0]):
                    metadata = workflow_results['metadatas'][0][i]
                    distance = workflow_results['distances'][0][i]
                    
                    # Convert distance to confidence score (0-1, higher is better)
                    confidence_score = max(0, 1 - distance)
                    
                    # Create workflow object from metadata
                    workflow = self._reconstruct_workflow_from_metadata(metadata)
                    
                    if workflow:
                        search_result = WorkflowSearchResult(
                            workflow=workflow,
                            confidence_score=confidence_score,
                            match_reason=f"Semantic match in {metadata['set_file']}",
                            source_file=metadata['set_file']
                        )
                        search_results.append(search_result)
            
            # Sort by confidence score
            search_results.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching workflows: {e}")
            return []
    
    def search_components(self, query: str, component_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for specific components (tables, transformations, etc.)"""
        try:
            # Build query with filters
            where_clause = {}
            if component_type:
                where_clause["component_type"] = component_type
            
            # Search in component collection
            component_results = self.component_collection.query(
                query_texts=[query],
                where=where_clause if where_clause else None,
                n_results=limit
            )
            
            results = []
            
            if component_results['documents'] and component_results['documents'][0]:
                for i, doc in enumerate(component_results['documents'][0]):
                    metadata = component_results['metadatas'][0][i]
                    distance = component_results['distances'][0][i]
                    
                    confidence_score = max(0, 1 - distance)
                    
                    result = {
                        "component_name": metadata['component_name'],
                        "workflow_name": metadata['workflow_name'],
                        "set_file": metadata['set_file'],
                        "component_type": metadata['component_type'],
                        "confidence_score": confidence_score,
                        "metadata": metadata
                    }
                    
                    results.append(result)
            
            # Sort by confidence score
            results.sort(key=lambda x: x['confidence_score'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching components: {e}")
            return []
    
    def find_table_workflows(self, table_name: str) -> List[WorkflowSearchResult]:
        """Find workflows that load a specific table"""
        try:
            # Search for target tables with the given name
            table_results = self.search_components(
                query=f"target table {table_name}",
                component_type="target_table",
                limit=20
            )
            
            # Also search for source tables
            source_results = self.search_components(
                query=f"source table {table_name}",
                component_type="source_table",
                limit=20
            )
            
            # Combine and deduplicate results
            all_results = table_results + source_results
            unique_workflows = {}
            
            for result in all_results:
                workflow_key = f"{result['set_file']}_{result['workflow_name']}"
                if workflow_key not in unique_workflows or result['confidence_score'] > unique_workflows[workflow_key]['confidence_score']:
                    unique_workflows[workflow_key] = result
            
            # Convert to WorkflowSearchResult objects
            search_results = []
            for result in unique_workflows.values():
                if result['confidence_score'] > 0.3:  # Minimum confidence threshold
                    workflow = self._reconstruct_workflow_from_metadata({
                        'name': result['workflow_name'],
                        'set_file': result['set_file']
                    })
                    
                    if workflow:
                        search_result = WorkflowSearchResult(
                            workflow=workflow,
                            confidence_score=result['confidence_score'],
                            match_reason=f"Table '{table_name}' found in {result['component_type']}",
                            source_file=result['set_file']
                        )
                        search_results.append(search_result)
            
            # Sort by confidence score
            search_results.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error finding table workflows: {e}")
            return []
    
    def add_debug_patterns(self, patterns: List[Dict[str, Any]]) -> bool:
        """Add common debugging patterns to the database"""
        try:
            documents = []
            metadatas = []
            ids = []
            
            for pattern in patterns:
                doc = pattern.get('description', '') + ' ' + pattern.get('solution', '')
                pattern_id = hashlib.md5(doc.encode()).hexdigest()
                
                documents.append(doc)
                metadatas.append(pattern)
                ids.append(pattern_id)
            
            if documents:
                self.debug_collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
            
            logger.info(f"Added {len(patterns)} debug patterns")
            return True
            
        except Exception as e:
            logger.error(f"Error adding debug patterns: {e}")
            return False
    
    def search_debug_patterns(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant debug patterns"""
        try:
            debug_results = self.debug_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            results = []
            
            if debug_results['documents'] and debug_results['documents'][0]:
                for i, doc in enumerate(debug_results['documents'][0]):
                    metadata = debug_results['metadatas'][0][i]
                    distance = debug_results['distances'][0][i]
                    
                    confidence_score = max(0, 1 - distance)
                    
                    result = {
                        "pattern": metadata,
                        "confidence_score": confidence_score
                    }
                    
                    results.append(result)
            
            # Sort by confidence score
            results.sort(key=lambda x: x['confidence_score'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching debug patterns: {e}")
            return []
    
    def _create_workflow_document(self, workflow: Workflow) -> str:
        """Create a searchable document for a workflow"""
        doc_parts = [
            f"Workflow: {workflow.name}",
            f"Description: {workflow.description or 'No description'}",
            f"Status: {workflow.status.value}",
            f"Set file: {workflow.set_file}"
        ]
        
        # Add session information
        if workflow.sessions:
            doc_parts.append("Sessions:")
            for session in workflow.sessions:
                doc_parts.append(f"- {session.name} (mapping: {session.mapping_name})")
        
        # Add source tables
        if workflow.source_tables:
            doc_parts.append("Source tables:")
            for table in workflow.source_tables:
                table_info = f"- {table.name}"
                if table.schema:
                    table_info += f" ({table.schema})"
                if table.database:
                    table_info += f" in {table.database}"
                doc_parts.append(table_info)
        
        # Add target tables
        if workflow.target_tables:
            doc_parts.append("Target tables:")
            for table in workflow.target_tables:
                table_info = f"- {table.name}"
                if table.schema:
                    table_info += f" ({table.schema})"
                if table.database:
                    table_info += f" in {table.database}"
                if table.load_type:
                    table_info += f" (load type: {table.load_type})"
                doc_parts.append(table_info)
        
        # Add transformations
        if workflow.transformations:
            doc_parts.append("Transformations:")
            for trans in workflow.transformations:
                doc_parts.append(f"- {trans.name} (type: {trans.type})")
        
        return " ".join(doc_parts)
    
    def _create_source_table_document(self, table: SourceTable, workflow: Workflow) -> str:
        """Create a searchable document for a source table"""
        doc_parts = [
            f"Source table: {table.name}",
            f"Workflow: {workflow.name}",
            f"Set file: {workflow.set_file}"
        ]
        
        if table.schema:
            doc_parts.append(f"Schema: {table.schema}")
        
        if table.database:
            doc_parts.append(f"Database: {table.database}")
        
        if table.connection:
            doc_parts.append(f"Connection: {table.connection}")
        
        if table.columns:
            doc_parts.append("Columns:")
            for col in table.columns:
                col_info = f"- {col.get('name', 'unknown')}"
                if col.get('data_type'):
                    col_info += f" ({col['data_type']})"
                doc_parts.append(col_info)
        
        return " ".join(doc_parts)
    
    def _create_target_table_document(self, table: TargetTable, workflow: Workflow) -> str:
        """Create a searchable document for a target table"""
        doc_parts = [
            f"Target table: {table.name}",
            f"Workflow: {workflow.name}",
            f"Set file: {workflow.set_file}"
        ]
        
        if table.schema:
            doc_parts.append(f"Schema: {table.schema}")
        
        if table.database:
            doc_parts.append(f"Database: {table.database}")
        
        if table.connection:
            doc_parts.append(f"Connection: {table.connection}")
        
        if table.load_type:
            doc_parts.append(f"Load type: {table.load_type}")
        
        if table.columns:
            doc_parts.append("Columns:")
            for col in table.columns:
                col_info = f"- {col.get('name', 'unknown')}"
                if col.get('data_type'):
                    col_info += f" ({col['data_type']})"
                doc_parts.append(col_info)
        
        return " ".join(doc_parts)
    
    def _create_transformation_document(self, transformation: Transformation, workflow: Workflow) -> str:
        """Create a searchable document for a transformation"""
        doc_parts = [
            f"Transformation: {transformation.name}",
            f"Type: {transformation.type}",
            f"Workflow: {workflow.name}",
            f"Set file: {workflow.set_file}"
        ]
        
        if transformation.input_ports:
            doc_parts.append(f"Input ports: {', '.join(transformation.input_ports)}")
        
        if transformation.output_ports:
            doc_parts.append(f"Output ports: {', '.join(transformation.output_ports)}")
        
        if transformation.expression:
            doc_parts.append(f"Expression: {transformation.expression}")
        
        return " ".join(doc_parts)
    
    def _reconstruct_workflow_from_metadata(self, metadata: Dict[str, Any]) -> Optional[Workflow]:
        """Reconstruct a minimal workflow object from metadata"""
        try:
            return Workflow(
                name=metadata['name'],
                set_file=metadata['set_file'],
                status=ComponentStatus.ACTIVE
            )
        except Exception as e:
            logger.error(f"Error reconstructing workflow: {e}")
            return None
    
    def clear_database(self) -> bool:
        """Clear all data from the vector database"""
        try:
            self.client.delete_collection(self.workflow_collection_name)
            self.client.delete_collection(self.component_collection_name)
            self.client.delete_collection(self.debug_collection_name)
            
            # Reinitialize collections
            self._initialize_collections()
            
            logger.info("Vector database cleared successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing vector database: {e}")
            return False

