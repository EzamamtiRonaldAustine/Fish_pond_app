import os
import numpy as np
import pandas as pd
def normalize(series, min_val=None, max_val=None):
    if min_val is None:
        min_val = series.min()
    if max_val is None:
        max_val = series.max()
    return ((series - min_val) / (max_val - min_val)).clip(0, 1)
def engineer(df):
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
        df = df.dropna(subset=['created_at']).copy()
        df = df.sort_values('created_at').reset_index(drop=True)
    if 'entry_id' in df.columns:
        df = df.dropna(subset=['entry_id']).copy()
    if 'Ammonia(g/ml)' in df.columns:
        df['Ammonia(g/ml)'] = df['Ammonia(g/ml)'].replace([np.inf, -np.inf], np.nan)
    df.interpolate(method='linear', inplace=True)
    df.ffill(inplace=True)
    df.bfill(inplace=True)
    # Clip extreme sensor values to plausible physical ranges to reduce outlier impact
    sensor_ranges = {
        'Temperature(C)': (0, 40),
        'Turbidity(NTU)': (0, 1000),
        'PH': (5, 10),
        'Ammonia(g/ml)': (0, 0.5),
        'Nitrate(g/ml)': (0, 1000),
    }
    for col, (lo, hi) in sensor_ranges.items():
        if col in df.columns:
            df[col] = df[col].clip(lower=lo, upper=hi)
    if {'Temperature(C)','PH','Turbidity(NTU)','Ammonia(g/ml)','Nitrate(g/ml)'} <= set(df.columns):
        temp_risk = normalize(df['Temperature(C)'], 24, 28)
        ph_risk = 1 - np.abs(df['PH'] - 8.2) / 4.0
        turb_risk = normalize(df['Turbidity(NTU)'], 0, 100)
        ammo_risk = normalize(df['Ammonia(g/ml)'], 0, 0.1)
        nitr_risk = normalize(df['Nitrate(g/ml)'], 0, 500)
        df['algae_risk_score'] = (ammo_risk * 0.30 + nitr_risk * 0.30 + turb_risk * 0.20 + temp_risk * 0.15 + ph_risk * 0.05) * 100
        df['algae_risk_score'] = df['algae_risk_score'].rolling(window=3, min_periods=1).mean()
        bins = [0, 50, 75, 100]
        labels = ['Low', 'Medium', 'High']
        df['risk_level'] = pd.cut(df['algae_risk_score'], bins=bins, labels=labels, include_lowest=True)
    df['hour'] = df['created_at'].dt.hour if 'created_at' in df.columns else 0
    df['is_daytime'] = ((df['hour'] >= 6) & (df['hour'] <= 18)).astype(int)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    cols = [c for c in ['Temperature(C)', 'Turbidity(NTU)', 'PH', 'Ammonia(g/ml)', 'Nitrate(g/ml)'] if c in df.columns]
    for col in cols:
        for lag in [1, 3, 6, 12]:
            df[f'{col}_lag_{lag}'] = df[col].shift(lag)
        df[f'{col}_diff_1'] = df[col] - df[col].shift(1)
    for col in cols:
        df[f'{col}_roll_mean_12'] = df[col].rolling(12, min_periods=1).mean()
        df[f'{col}_roll_std_12'] = df[col].rolling(12, min_periods=1).std()
        df[f'{col}_roll_max_12'] = df[col].rolling(12, min_periods=1).max()
    if {'Ammonia(g/ml)','Nitrate(g/ml)','Temperature(C)','PH'} <= set(df.columns):
        df['nutrient_ratio'] = df['Ammonia(g/ml)'] / (df['Nitrate(g/ml)'] + 1e-6)
        df['temp_ph_interact'] = df['Temperature(C)'] * df['PH']
        df['un_ionized_ammonia'] = df['Ammonia(g/ml)'] * (10 ** (df['PH'] - 7)) / (1 + 10 ** (df['PH'] - 7))
        df['bloom_risk_proxy'] = 0.4 * df['Turbidity(NTU)'] + 0.3 * df['Nitrate(g/ml)'] + 0.2 * (df['Temperature(C)'] > 25).astype(int) + 0.1 * (df['PH'] > 8.5).astype(int)
    df = df.dropna().reset_index(drop=True)
    exclude = ['created_at', 'algae_risk_score', 'risk_level', 'Turbidity(NTU)', 'entry_id']
    feature_cols = [c for c in df.columns if c not in exclude]
    return df, feature_cols
def build_features(df):
    return engineer(df)
