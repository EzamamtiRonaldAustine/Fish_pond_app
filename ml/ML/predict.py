import os
import sys
import joblib
import json
import pandas as pd

# Ensure project root is importable when running as a script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ml_config import MODEL_PATH, METADATA_PATH, SCALER_PATH
from ML.features import build_features


class Predictor:
    """
    Lightweight prediction helper for offline/batch use.

    Ensures the same feature engineering and scaling used in training
    are applied before calling the model.
    """

    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)

        with open(METADATA_PATH) as f:
            metadata = json.load(f)

        self.feature_cols = metadata["features"]
        self.labels = metadata.get("labels", ["Low", "Medium", "High"])

    def _prepare_features(self, data):
        df = pd.DataFrame(data)
        df, _ = build_features(df)

        if df.empty:
            raise ValueError("Not enough historical data for prediction.")

        missing = set(self.feature_cols) - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing engineered feature columns for prediction: {sorted(missing)}"
            )

        X = df[self.feature_cols]
        X_scaled = self.scaler.transform(X)
        return X_scaled

    def predict(self, data):
        """
        Return only the predicted risk level for the most recent row.
        """
        X_scaled = self._prepare_features(data)
        prediction = self.model.predict(X_scaled)
        return prediction[-1]

    def predict_with_proba(self, data):
        """
        Return the predicted risk level and class probabilities
        for the most recent row.
        """
        X_scaled = self._prepare_features(data)
        x_last = X_scaled[-1:]
        pred = self.model.predict(x_last)[0]

        probs = {}
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(x_last)[0]
            # Map probabilities using the model's actual classes (prevents mismatches
            # when the trained model only contains 2 of the 3 expected labels).
            model_classes = getattr(self.model, "classes_", None)
            if model_classes is None:
                model_classes = list(range(len(proba)))
            probs = {str(c): float(p) for c, p in zip(model_classes, proba)}

        return {"predicted_level": str(pred), "probabilities": probs}

