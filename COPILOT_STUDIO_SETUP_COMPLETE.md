# Informatica Agent - Copilot Studio Setup Complete

## Overview
This document contains the complete setup process for building an Informatica Agent using Microsoft Copilot Studio, Azure Functions, and Azure AI Search. This is a low-code/no-code solution that works with personal Microsoft accounts.

## Architecture
```
User Query → Copilot Studio → Azure Function API → Azure AI Search → Response
```

## Current Status
- ✅ **Copilot Studio Agent Created**: "Ask-Inf-Expert"
- ✅ **Azure Function App Created**: "informatica-agent" (Canada Central)
- ✅ **Azure AI Search Created**: "informatica-search-service"
- ✅ **Environment Variables Configured**: All Azure services connected
- ✅ **Function URL Obtained**: Ready for Copilot Studio integration

## Services Created

### 1. Copilot Studio Agent
- **Name**: Ask-Inf-Expert
- **Description**: AI-powered chatbot for Informatica PowerCenter workflow analysis and debugging
- **Instructions**: Configured with expert system prompt
- **Status**: Created and ready for Tools integration

### 2. Azure Function App
- **Name**: informatica-agent
- **Location**: Canada Central
- **Resource Group**: DefaultResourceGroup-EUS
- **Plan**: Flex Consumption
- **Function**: HttpTrigger (with custom code for Informatica processing)
- **Status**: Deployed and running

### 3. Azure AI Search
- **Name**: informatica-search-service
- **Location**: Canada Central
- **Pricing Tier**: Standard
- **Status**: Created and running
- **Endpoint**: https://informatica-search-service.search.windows.net

## Environment Variables (Configured)
```
AZURE_SEARCH_ENDPOINT=https://informatica-search-service.search.windows.net
AZURE_SEARCH_API_KEY=[CONFIGURED]
AZURE_SEARCH_INDEX_NAME=informatica-workflows
```

## Function URL (Saved)
**Note**: The actual function URL with key should be retrieved from Azure Portal when needed:
- **Function App**: informatica-agent
- **Location**: Canada Central
- **Resource Group**: DefaultResourceGroup-EUS
- **To get URL**: Azure Portal → Function App → Functions → Get Function URL

## Next Steps Required

### Step 1: Access Copilot Studio (Not Microsoft 365 Copilot)
- **URL**: https://copilotstudio.microsoft.com
- **Note**: Microsoft 365 Copilot ≠ Copilot Studio
- **Action**: Navigate to Copilot Studio specifically

### Step 2: Add Tools to Copilot Studio
1. **Open your agent** "Ask-Inf-Expert"
2. **Go to Tools** (or Actions/Connectors)
3. **Import OpenAPI** or create custom connector
4. **Get the function URL** from Azure Portal (Function App → Functions → Get Function URL)
5. **Configure the connector**

### Step 3: Create Topics
1. **Workflow Search Topic**:
   - Trigger phrases: "show me workflow", "find workflow", "search for workflow"
   - Action: Call the Azure Function API
   - Map user input to query parameter

2. **Table Debug Topic**:
   - Trigger phrases: "table is empty", "debug table", "table issue"
   - Action: Call the Azure Function API
   - Extract table name from user input

### Step 4: Test and Publish
1. **Test your copilot** with sample queries
2. **Publish** the copilot
3. **Get the web chat URL**
4. **Share with your team**

## Code Files Available

### Azure Function Code (Deployed)
The functions are deployed with the following capabilities:
- **Search workflows** by name
- **Debug table issues** with recommendations
- **Connect to Azure AI Search** for metadata lookup
- **Return structured responses** for Copilot Studio

### XML Parser (Available)
- **Location**: `services/xml_parser.py`
- **Purpose**: Parse PowerCenter XML metadata
- **Features**: Extract workflows, sessions, tables, transformations

### Vector Database Service (Available)
- **Location**: `services/vector_database.py`
- **Purpose**: Semantic search to prevent RAG bleed
- **Integration**: ChromaDB (can be replaced with Azure AI Search)

## Troubleshooting

### Common Issues
1. **"Microsoft 365 Copilot" vs "Copilot Studio"**: Make sure you're in Copilot Studio
2. **Region restrictions**: Use Canada Central (allowed for your subscription)
3. **Function deployment**: Functions are already deployed and running
4. **Environment variables**: All configured correctly

### Verification Steps
1. **Azure Function App**: Running in Canada Central
2. **Azure AI Search**: Running with endpoint accessible
3. **Environment variables**: All three configured
4. **Function URL**: Available from Azure Portal

## Important Notes

### Subscription Details
- **Subscription**: Azure for Students
- **Resource Group**: DefaultResourceGroup-EUS
- **Location**: Canada Central (required due to restrictions)

### Security
- **Function Key**: Configured in Azure, retrieve when needed
- **Search API Key**: Configured in environment variables
- **Access**: Personal Microsoft account (no company credentials needed)

### Scalability
- **Consumption Plan**: Pay-per-use, scales automatically
- **Free Tier**: Available for testing
- **Production Ready**: Can scale to Standard/Premium tiers

## Support Files

### Documentation
- `README.md`: Complete project documentation
- `azure_search_setup.md`: Azure AI Search setup guide
- `copilot_studio_guide.md`: Copilot Studio implementation guide
- `azure_bot_guide.md`: Alternative Azure Bot Service approach

### Sample Data
- `xml_files/sample_set1.xml`: Sanitized PowerCenter XML sample
- `models/workflow_models.py`: Data models for workflows

## Contact Information
- **Repository**: https://github.com/ramcgobburu/informatica-agent
- **User**: ramcgobburu@andrew.cmu.edu
- **Organization**: Andrew CMU

## Last Updated
- **Date**: October 3, 2025
- **Status**: Ready for Copilot Studio Tools integration
- **Next Action**: Complete Copilot Studio setup with Tools and Topics

---

**IMPORTANT**: When starting a new chat session, reference this document to understand the current state and continue from the next required step.