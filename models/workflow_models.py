from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ComponentType(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    TRANSFORMATION = "transformation"
    MAPPING = "mapping"
    WORKFLOW = "workflow"
    SESSION = "session"

class ComponentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"

class WorkflowComponent(BaseModel):
    name: str
    type: ComponentType
    status: ComponentStatus
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SourceTable(BaseModel):
    name: str
    schema: Optional[str] = None
    database: Optional[str] = None
    connection: Optional[str] = None
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    filters: List[str] = Field(default_factory=list)

class TargetTable(BaseModel):
    name: str
    schema: Optional[str] = None
    database: Optional[str] = None
    connection: Optional[str] = None
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    load_type: Optional[str] = None  # insert, update, upsert, etc.

class Transformation(BaseModel):
    name: str
    type: str
    input_ports: List[str] = Field(default_factory=list)
    output_ports: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    expression: Optional[str] = None

class Session(BaseModel):
    name: str
    workflow_name: str
    mapping_name: str
    source_connections: List[str] = Field(default_factory=list)
    target_connections: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    last_run_status: Optional[str] = None
    last_run_time: Optional[datetime] = None

class Workflow(BaseModel):
    name: str
    set_file: str  # e.g., "set30"
    description: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    status: ComponentStatus
    sessions: List[Session] = Field(default_factory=list)
    source_tables: List[SourceTable] = Field(default_factory=list)
    target_tables: List[TargetTable] = Field(default_factory=list)
    transformations: List[Transformation] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WorkflowSearchResult(BaseModel):
    workflow: Workflow
    confidence_score: float
    match_reason: str
    source_file: str

class DebugResult(BaseModel):
    table_name: str
    responsible_workflows: List[WorkflowSearchResult]
    potential_issues: List[str]
    recommendations: List[str]
    confidence_score: float

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    debug_results: Optional[DebugResult] = None
    workflow_results: Optional[List[WorkflowSearchResult]] = None
    confidence_score: float
    source_files: List[str]
    session_id: str

