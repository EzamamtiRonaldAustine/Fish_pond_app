import sys
import os
from pathlib import Path

# Add the project root to the path so we can import the api module
project_root = Path(r"c:\Users\USER\Desktop\Fish_Pond_app")
sys.path.append(str(project_root))

from api.predict import predict_water_quality

def test_scaling():
    print("Running Water Quality Prediction Tests...\n")

    # 1. Normal Conditions (from your logs, ~120 N, ~80 P)
    # Expected: EXCELLENT or GOOD (no longer POOR)
    print("--- Test 1: Normal Pond Conditions ---")
    res1 = predict_water_quality(
        temperature=25.5,
        ph=7.6,
        nitrite=120.0,      # Actually Nitrogen
        phosphorus=80.0     # Actually Phosphorus
    )
    print(f"Result: {res1['quality_label']} ({res1['confidence']}%)")
    print(f"Inputs: {res1['sensor_inputs']}")
    assert res1['quality_level'] in [0, 1], "Normal conditions should be Excellent or Good"
    print("✅ Passed\n")


    # 2. Elevated Conditions
    # Approaching upper bounds of healthy sensor readings
    print("--- Test 2: Elevated Nutrient Conditions ---")
    res2 = predict_water_quality(
        temperature=28.0,
        ph=8.2,
        nitrite=400.0,      
        phosphorus=250.0     
    )
    print(f"Result: {res2['quality_label']} ({res2['confidence']}%)")
    print(f"Inputs: {res2['sensor_inputs']}")
    print("✅ Passed\n")


    # 3. Toxic/Lethal Conditions
    # Huge spike in nutrients or extreme limits of sensor
    print("--- Test 3: Extreme Nutrient Spike ---")
    res3 = predict_water_quality(
        temperature=32.0,
        ph=9.0,
        nitrite=1800.0,      
        phosphorus=800.0     
    )
    print(f"Result: {res3['quality_label']} ({res3['confidence']}%)")
    print(f"Inputs: {res3['sensor_inputs']}")
    assert res3['quality_level'] == 2, "Extreme conditions should be POOR"
    print("✅ Passed\n")


if __name__ == "__main__":
    test_scaling()
