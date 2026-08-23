import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.abspath('backend/.env'))

# Tambahkan /backend ke sys.path agar import 'app...' berfungsi
sys.path.insert(0, os.path.abspath('backend'))

from app.pipeline.cv_csv_bridge import ingest, get_default_cross_path, get_default_density_path

def main():
    cross_path = get_default_cross_path()
    density_path = get_default_density_path()

    print(f"Ingesting CV output:")
    print(f"Cross CSV: {cross_path}")
    print(f"Density CSV: {density_path}")

    result = ingest(cross_path, density_path)
    print("Ingestion Result:")
    print(result)

if __name__ == "__main__":
    main()
