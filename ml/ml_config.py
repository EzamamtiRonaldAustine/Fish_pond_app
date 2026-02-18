import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_RAW_DIR = os.path.join(BASE_DIR, "data")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data") # utilizing same dir for simplicity if needed
MODEL_DIR = os.path.join(BASE_DIR, "models")

MODEL_PATH = os.path.join(MODEL_DIR, "classifier_v1.joblib")
METADATA_PATH = os.path.join(MODEL_DIR, "metadata.json")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler_v1.joblib")

RANDOM_STATE = 42
