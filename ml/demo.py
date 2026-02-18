import sys
import os
import pandas as pd

# Add current directory to path so we can import config and ML package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ML.predict import Predictor
    print("Successfully imported Predictor.")
except ImportError as e:
    print(f"Error importing Predictor: {e}")
    sys.exit(1)

def run_demo():
    print("Initializing Predictor...")
    try:
        predictor = Predictor()
        print("Model and Scaler loaded successfully.")
    except Exception as e:
        print(f"Failed to load artifacts: {e}")
        return

    # The model uses lag features (up to 12 steps back), so we need 
    # historical data to generate a prediction for the latest timestamp.
    # Generating a sequence of 20 data points (simulating 1-hour intervals)
    
    base_time = pd.Timestamp("2021-10-12T00:00:00Z")
    sample_data = []
    
    for i in range(20):
        # Create slightly varying data to simulate realistic readings
        row = {
            "created_at": (base_time + pd.Timedelta(hours=i)).isoformat(),
            "Temperature(C)": 26.0 + (i * 0.1),  
            "Turbidity(NTU)": 15.0 + (i % 5),
            "PH": 8.1 + (i * 0.01),
            "Ammonia(g/ml)": 0.03,
            "Nitrate(g/ml)": 120.0
        }
        sample_data.append(row)

    print(f"\nRunning prediction on sample data:\n{sample_data}")
    try:
        result = predictor.predict_with_proba(sample_data)
        print("\nPrediction Result:")
        print(result)
    except Exception as e:
        print(f"Prediction failed: {e}")

if __name__ == "__main__":
    run_demo()
