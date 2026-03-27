import sys
from pathlib import Path

BASE_DIR = Path(r"c:\Users\USER\Desktop\Fish_Pond_app\api")
sys.path.append(str(BASE_DIR.parent))

# We only need to check the math of the feature engineering to see if it brings it down
def engineer_features(temperature, ph, nitrite, phosphorus):
    N_TO_NO2_SCALE = 0.0005
    scaled_nitrite = nitrite * N_TO_NO2_SCALE
    
    P_TO_P_SCALE   = 0.002
    surrogate_p    = min(phosphorus * P_TO_P_SCALE, 8.0)
    
    print(f"Inputs: N={nitrite}, P={phosphorus}")
    print(f"Scaled NO2: {scaled_nitrite:.4f} mg/L (Target: < 2.0 mg/L)")
    print(f"Scaled P:   {surrogate_p:.4f} mg/L (Target: < 5.0 mg/L)")
    print("-" * 40)

if __name__ == "__main__":
    print("--- 1. Normal/Healthy Pond (120 N, 80 P) ---")
    engineer_features(25.5, 7.6, 120.0, 80.0)

    print("--- 2. Elevated Pond (400 N, 250 P) ---")
    engineer_features(25.5, 7.6, 400.0, 250.0)

    print("--- 3. Extreme Spike (2000 N, 1000 P) ---")
    engineer_features(25.5, 7.6, 2000.0, 1000.0)
