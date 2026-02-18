# Fish Pond ML Model

This directory contains the extracted Machine Learning model and data for the Fish Pond application.

## Directory Structure

- `data/`: Contains the dataset used for training (`IoTPond6.xlsx`).
- `models/`: Contains the trained model artifacts (`classifier_v1.joblib`, `scaler_v1.joblib`, `metadata.json`).
- `ML/`: Source code package for feature engineering and prediction.
- `config.py`: Configuration file for paths.
- `demo.py`: A script to verify the model usage.

## Setup

1.  Create a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    # Activate:
    # Windows: .\venv\Scripts\activate
    # Linux/Mac: source venv/bin/activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

To run the demo script and verify the model:

```bash
python demo.py
```

To use the model in your application, ensure `ml` is in your Python path and import `Predictor` from `ML.predict`.

```python
import sys
import os
sys.path.append("/path/to/Fish_Pond_app/ml")

from ML.predict import Predictor

predictor = Predictor()
result = predictor.predict_with_proba(data)
```
