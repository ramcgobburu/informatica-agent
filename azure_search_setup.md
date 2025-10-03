# Azure Cognitive Search Setup Guide

## Step 1: Create Azure Cognitive Search Service

### 1.1 Navigate to Azure Portal
1. Go to [Azure Portal](https://portal.azure.com)
2. Click "Create a resource"
3. Search for "Azure Cognitive Search"
4. Click "Create"

### 1.2 Configure Basic Settings
- **Subscription**: Select your subscription
- **Resource Group**: Select existing or create new (e.g., "informatica-agent-rg")
- **Service Name**: Choose a unique name (e.g., "informatica-search-service")
- **Location**: Select your preferred region
- **Pricing Tier**: Choose "Basic" or "Standard" (Basic is sufficient for testing)

### 1.3 Create the Service
1. Click "Review + create"
2. Click "Create"
3. Wait for deployment to complete (5-10 minutes)

### 1.4 Get Connection Details
Once created, go to your search service:
1. Click on "Keys" in the left menu
2. Copy the following:
   - **Endpoint**: e.g., `https://your-service-name.search.windows.net`
   - **Primary admin key**: Copy this key

## Step 2: Create Search Index

### 2.1 Navigate to Search Explorer
1. In your search service, click "Search explorer"
2. Click "Create index"

### 2.2 Define Index Schema
Use this JSON schema for the index:

```json
{
  "name": "informatica-workflows",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "workflow_name",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "set_file",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "description",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "status",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "created_date",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "modified_date",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "component_type",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": false,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "component_name",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": false,
      "retrievable": true
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "facetable": false,
      "retrievable": true
    }
  ]
}
```

### 2.3 Create the Index
1. Paste the JSON schema
2. Click "Create"

## Step 3: Test the Index
1. In Search Explorer, select your "informatica-workflows" index
2. Click "Search" to test (should return empty results initially)

## Step 4: Update Configuration
Once you have the search service set up, update your `.env` file with:

```env
AZURE_SEARCH_ENDPOINT=https://your-service-name.search.windows.net
AZURE_SEARCH_API_KEY=your-primary-admin-key
AZURE_SEARCH_INDEX_NAME=informatica-workflows
```

## Next Steps
After completing this setup, we'll move to Azure Database configuration.
