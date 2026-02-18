import joblib
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report
from config import MODEL_PATH
from ml.features import build_features


def evaluate(data_path):

    model = joblib.load(MODEL_PATH)

    df = pd.read_csv(data_path)

    df, feature_cols = build_features(df)

    X = df[feature_cols]
    y = df["risk_level"]

    y_pred = model.predict(X)

    print(confusion_matrix(y, y_pred))
    print(classification_report(y, y_pred))
