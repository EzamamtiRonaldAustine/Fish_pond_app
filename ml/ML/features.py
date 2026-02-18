"""Re-export feature engineering for algae risk model (ML.features)."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "features_engineering",
    os.path.join(os.path.dirname(__file__), "features-engineering.py"),
)
_features_engineering = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_features_engineering)

engineer = _features_engineering.engineer
build_features = _features_engineering.build_features
