import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.abspath('backend/.env'))

# Tambahkan /backend ke sys.path agar import 'app...' berfungsi
sys.path.insert(0, os.path.abspath('backend'))

from app.services.traffic_ingestion_service import TrafficIngestionService
from app.pipeline.traffic_state_builder import getDefaultCrossPath, getDefaultDensityPath

def main():
    service = TrafficIngestionService()
    
    cross_path = getDefaultCrossPath()
    density_path = getDefaultDensityPath()
    
    print(f"Ingesting CV output:")
    print(f"Cross CSV: {cross_path}")
    print(f"Density CSV: {density_path}")
    
    result = service.ingestCvOutput(cross_path, density_path)
    print("Ingestion Result:")
    print(result)

if __name__ == "__main__":
    main()
