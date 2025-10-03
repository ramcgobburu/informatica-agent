# Informatica Agent - AskIt Chatbot

An AI-powered chatbot for Informatica PowerCenter workflow analysis and debugging, built with Azure AI services and designed to prevent RAG bleed issues.

## Features

- **Robust Workflow Search**: Find workflows by name with exact match validation
- **Table Debugging**: Analyze why tables might be empty or have issues
- **Component Analysis**: Search for specific components (tables, transformations, mappings)
- **Azure AI Integration**: Leverages Azure OpenAI and Azure Search for intelligent responses
- **Vector Database**: Uses ChromaDB for semantic search to prevent hallucinations
- **REST API**: Complete API for chatbot interaction and workflow management

## Architecture

### Core Components

1. **XML Parser** (`services/xml_parser.py`)
   - Parses PowerCenter exported XML metadata files
   - Extracts workflow, session, table, and transformation information
   - Handles multiple XML file formats and namespaces

2. **Vector Database Service** (`services/vector_database.py`)
   - Uses ChromaDB for semantic search
   - Indexes workflows and components for efficient retrieval
   - Prevents RAG bleed by validating search results

3. **Azure Integration** (`services/azure_integration.py`)
   - Integrates with Azure OpenAI for intelligent responses
   - Uses Azure Search for additional search capabilities
   - Supports Azure Blob Storage for XML file management

4. **Workflow Search Engine** (`services/workflow_search_engine.py`)
   - Provides robust workflow search with validation
   - Handles exact matches and semantic similarity
   - Prevents hallucinations by cross-referencing cached data

5. **Debugging Agent** (`services/debugging_agent.py`)
   - Analyzes table and workflow issues
   - Provides specific debugging recommendations
   - Uses pattern matching for common issues

## Setup

### Prerequisites

- Python 3.8+
- Azure OpenAI service
- Azure Search service (optional)
- Azure Storage account (optional)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd informatica-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create environment file:
```bash
cp .env.example .env
```

4. Configure environment variables in `.env`:
```env
# Azure Configuration
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name

# Azure Search Configuration (optional)
AZURE_SEARCH_ENDPOINT=your_azure_search_endpoint
AZURE_SEARCH_API_KEY=your_azure_search_api_key
AZURE_SEARCH_INDEX_NAME=informatica-metadata

# Azure Storage Configuration (optional)
AZURE_STORAGE_CONNECTION_STRING=your_azure_storage_connection_string
AZURE_STORAGE_CONTAINER_NAME=xml-files

# Application Configuration
XML_FILES_DIRECTORY=./xml_files
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True
```

### XML Files Setup

1. Create a directory for your XML files:
```bash
mkdir xml_files
```

2. Place your PowerCenter exported XML files in the directory:
```
xml_files/
├── set1.xml
├── set2.xml
├── set3.xml
└── ...
```

3. The system will automatically parse and index these files on startup.

## Usage

### Starting the Server

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

### Chatbot Interaction

#### Basic Workflow Search
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me workflow wf_customer_load"}'
```

#### Table Debugging
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Table customer_dim is empty, what might be the reason?"}'
```

#### Component Search
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find all transformations that use customer data"}'
```

### Direct API Endpoints

#### Search Workflows
```bash
curl "http://localhost:8000/workflows/search?query=wf_customer_load&exact_match=true"
```

#### Get Workflow Details
```bash
curl "http://localhost:8000/workflows/wf_customer_load?set_file=set30"
```

#### Find Table Workflows
```bash
curl "http://localhost:8000/tables/customer_dim/workflows"
```

#### Debug Table Issue
```bash
curl -X POST "http://localhost:8000/debug/table?table_name=customer_dim&issue_description=table is empty"
```

#### Upload XML File
```bash
curl -X POST "http://localhost:8000/upload/xml" \
  -F "file=@set30.xml"
```

## Solving RAG Bleed Issues

This system addresses RAG bleed through several mechanisms:

### 1. Exact Match Validation
- Performs exact name searches first
- Validates semantic search results against cached data
- Prevents hallucinations by cross-referencing results

### 2. Vector Database with Validation
- Uses ChromaDB for semantic search
- Validates results against actual workflow data
- Implements confidence scoring and thresholds

### 3. Structured Data Models
- Uses Pydantic models for data validation
- Ensures consistent data structure across the system
- Prevents type mismatches and data corruption

### 4. Multi-layered Search
- Combines exact match, semantic search, and pattern matching
- Validates results at multiple levels
- Provides fallback mechanisms for edge cases

### 5. Azure AI Integration
- Uses Azure OpenAI for intelligent response generation
- Provides context-aware responses based on validated data
- Implements prompt engineering to prevent hallucinations

## Deployment

### Local Development
```bash
python main.py
```

### Production Deployment
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Monitoring and Logging

The system includes comprehensive logging and monitoring:

- **Health Check**: `GET /health` - Check system status
- **Statistics**: `GET /statistics` - Get system statistics
- **Logging**: Structured logging with different levels

## Troubleshooting

### Common Issues

1. **XML Parsing Errors**
   - Check XML file format and encoding
   - Verify PowerCenter export format
   - Check file permissions

2. **Azure Service Issues**
   - Verify Azure credentials and endpoints
   - Check service availability and quotas
   - Review Azure service logs

3. **Search Issues**
   - Verify XML files are properly indexed
   - Check vector database initialization
   - Review search query format

4. **Performance Issues**
   - Monitor system resources
   - Check vector database performance
   - Review Azure service response times

### Debug Mode

Enable debug mode for detailed logging:
```env
DEBUG=True
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation

## Roadmap

- [ ] Enhanced NLP for query understanding
- [ ] Real-time workflow monitoring integration
- [ ] Advanced debugging patterns
- [ ] Workflow dependency visualization
- [ ] Performance optimization recommendations
- [ ] Integration with PowerCenter repository
- [ ] Automated testing and validation
- [ ] Enhanced security and authentication

