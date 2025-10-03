#!/usr/bin/env python3
"""
Startup script for Informatica Agent
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from main import app
from config import Config

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('informatica_agent.log')
        ]
    )

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_DEPLOYMENT_NAME'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment")
        print("The application will start but some features may not work properly")
    
    return len(missing_vars) == 0

def create_directories():
    """Create required directories if they don't exist"""
    directories = [
        Config.XML_FILES_DIRECTORY,
        Config.CHROMA_PERSIST_DIRECTORY,
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

def main():
    """Main startup function"""
    print("Starting Informatica Agent...")
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Create required directories
    create_directories()
    
    # Check environment
    env_ok = check_environment()
    
    # Print startup information
    print(f"API Host: {Config.API_HOST}")
    print(f"API Port: {Config.API_PORT}")
    print(f"Debug Mode: {Config.DEBUG}")
    print(f"XML Files Directory: {Config.XML_FILES_DIRECTORY}")
    print(f"Vector DB Directory: {Config.CHROMA_PERSIST_DIRECTORY}")
    print(f"Environment OK: {env_ok}")
    
    # Check if XML files exist
    xml_dir = Path(Config.XML_FILES_DIRECTORY)
    xml_files = list(xml_dir.glob("*.xml"))
    print(f"XML Files Found: {len(xml_files)}")
    
    if xml_files:
        print("XML Files:")
        for xml_file in xml_files:
            print(f"  - {xml_file.name}")
    else:
        print("No XML files found. Please place your PowerCenter XML files in the xml_files directory.")
    
    print("\nStarting FastAPI server...")
    print(f"API Documentation: http://{Config.API_HOST}:{Config.API_PORT}/docs")
    print(f"Health Check: http://{Config.API_HOST}:{Config.API_PORT}/health")
    print("\nPress Ctrl+C to stop the server")
    
    # Start the server
    import uvicorn
    uvicorn.run(
        app,
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG,
        log_level="info"
    )

if __name__ == "__main__":
    main()

