import pandas as pd

def test_merge():
    cross_df = pd.read_csv("cv/output/crossing_simpang.csv")
    density_df = pd.read_csv("cv/output/percobaan_logic_simpang.csv")
    
    # 1. Standardize Timestamps
    cross_df["timestamp"] = pd.to_datetime(cross_df["timestamp"], errors="coerce")
    density_df["timestamp"] = pd.to_datetime(density_df["timestamp"], errors="coerce")
    
    # 2. Map Kamera to Approach
    camera_map = {
        "CCTV_1": "south",
        "CCTV_2": "west",
        "CCTV_3": "east",
        "CCTV_4": "north",
    }
    
    cross_df["approach"] = cross_df["kamera"].map(camera_map)
    density_df["approach"] = density_df["kamera"].map(camera_map)
    
    # Drop rows without known camera
    cross_df = cross_df.dropna(subset=["approach"])
    density_df = density_df.dropna(subset=["approach"])
    
    # 3. Aggregate crossing per timestamp & approach
    # Since CCTV_2 might have MAGELANG and DIPONEGORO labels, we sum them up per camera
    cross_agg = cross_df.groupby(["timestamp", "approach"], as_index=False).agg({
        "jumlah_crossing": "sum",
        "motor_crossing": "sum",
        "mobil_crossing": "sum",
        "truk_crossing": "sum",
        "bus_crossing": "sum",
    })
    
    # Aggregate density per timestamp & approach (just in case of multiple rows)
    density_agg = density_df.groupby(["timestamp", "approach"], as_index=False).agg({
        "total_di_zona": "mean",
    })
    
    # 4. Merge them
    merged = pd.merge(cross_agg, density_agg, on=["timestamp", "approach"], how="outer").fillna(0)
    
    # Add required columns to simulate old behavior
    merged["intersectionId"] = "simpang4-pingit"
    merged["laneId"] = "all_lanes"
    
    # Rename columns to match old schema so TrafficStateBuilder doesn't need huge changes
    merged = merged.rename(columns={
        "jumlah_crossing": "vehicleCount",
        "mobil_crossing": "carCount",
        "motor_crossing": "motorcycleCount",
        "bus_crossing": "busCount",
        "truk_crossing": "truckCount",
        "total_di_zona": "densityIndex",
    })
    
    merged["queueLengthVeh"] = 0
    merged["queueLengthMEst"] = 0.0
    
    print(merged.head(10))

if __name__ == "__main__":
    test_merge()
