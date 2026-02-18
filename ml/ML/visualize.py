"""
Visualization utilities for model analysis and presentation.
"""
import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from joblib import load

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import MODEL_PATH, METADATA_PATH, SCALER_PATH
from ML.features import engineer

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)


def plot_feature_importance(top_n=15, save_path=None):
    """
    Plot feature importance from the trained RandomForest model.
    """
    model = load(MODEL_PATH)
    
    if not hasattr(model, 'feature_importances_'):
        print("Model does not support feature importance.")
        return
    
    with open(METADATA_PATH) as f:
        metadata = json.load(f)
    
    feature_cols = metadata['features']
    importances = model.feature_importances_
    
    # Sort by importance
    indices = np.argsort(importances)[::-1][:top_n]
    
    plt.figure(figsize=(10, 8))
    plt.title(f'Top {top_n} Feature Importances', fontsize=16, fontweight='bold')
    plt.barh(range(top_n), importances[indices])
    plt.yticks(range(top_n), [feature_cols[i] for i in indices])
    plt.xlabel('Importance', fontsize=12)
    plt.gca().invert_yaxis()
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved feature importance plot to {save_path}")
    else:
        plt.show()


def plot_confusion_matrix(y_true, y_pred, labels=None, save_path=None):
    """
    Plot confusion matrix with better formatting.
    """
    from sklearn.metrics import confusion_matrix
    
    if labels is None:
        labels = ['Low', 'Medium', 'High']
    
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=labels,
        yticklabels=labels,
        cbar_kws={'label': 'Count'}
    )
    plt.title('Confusion Matrix', fontsize=16, fontweight='bold')
    plt.ylabel('True Label', fontsize=12)
    plt.xlabel('Predicted Label', fontsize=12)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved confusion matrix to {save_path}")
    else:
        plt.show()


def plot_class_distribution(y, save_path=None):
    """
    Plot the distribution of risk levels in the dataset.
    """
    counts = pd.Series(y).value_counts().sort_index()
    
    plt.figure(figsize=(8, 6))
    bars = plt.bar(counts.index, counts.values, color=['#2ecc71', '#f39c12', '#e74c3c'])
    plt.title('Risk Level Distribution', fontsize=16, fontweight='bold')
    plt.xlabel('Risk Level', fontsize=12)
    plt.ylabel('Count', fontsize=12)
    
    # Add count labels on bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved class distribution plot to {save_path}")
    else:
        plt.show()


def plot_sensor_timeseries(df, sensors=None, save_path=None):
    """
    Plot time series of key sensor readings.
    """
    if sensors is None:
        sensors = ['Temperature(C)', 'Turbidity(NTU)', 'PH', 'Ammonia(g/ml)', 'Nitrate(g/ml)']
    
    if 'created_at' not in df.columns:
        print("DataFrame must have 'created_at' column for time series plot.")
        return
    
    df_plot = df.copy()
    df_plot['created_at'] = pd.to_datetime(df_plot['created_at'])
    df_plot = df_plot.sort_values('created_at')
    
    n_sensors = len(sensors)
    fig, axes = plt.subplots(n_sensors, 1, figsize=(14, 3*n_sensors), sharex=True)
    
    if n_sensors == 1:
        axes = [axes]
    
    for idx, sensor in enumerate(sensors):
        if sensor in df_plot.columns:
            axes[idx].plot(df_plot['created_at'], df_plot[sensor], linewidth=1.5)
            axes[idx].set_ylabel(sensor, fontsize=10)
            axes[idx].grid(True, alpha=0.3)
    
    axes[-1].set_xlabel('Time', fontsize=12)
    plt.suptitle('Sensor Readings Over Time', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved time series plot to {save_path}")
    else:
        plt.show()


def plot_risk_over_time(df, save_path=None):
    """
    Plot risk levels over time (if risk_level column exists).
    """
    if 'risk_level' not in df.columns or 'created_at' not in df.columns:
        print("DataFrame must have 'risk_level' and 'created_at' columns.")
        return
    
    df_plot = df.copy()
    df_plot['created_at'] = pd.to_datetime(df_plot['created_at'])
    df_plot = df_plot.sort_values('created_at')
    
    # Map risk levels to numeric for plotting
    risk_map = {'Low': 0, 'Medium': 1, 'High': 2}
    df_plot['risk_numeric'] = df_plot['risk_level'].map(risk_map)
    
    plt.figure(figsize=(14, 6))
    colors = {'Low': '#2ecc71', 'Medium': '#f39c12', 'High': '#e74c3c'}
    
    for level in ['Low', 'Medium', 'High']:
        mask = df_plot['risk_level'] == level
        plt.scatter(
            df_plot.loc[mask, 'created_at'],
            df_plot.loc[mask, 'risk_numeric'],
            label=level,
            color=colors[level],
            alpha=0.6,
            s=50
        )
    
    plt.ylabel('Risk Level', fontsize=12)
    plt.xlabel('Time', fontsize=12)
    plt.title('Risk Level Over Time', fontsize=16, fontweight='bold')
    plt.yticks([0, 1, 2], ['Low', 'Medium', 'High'])
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved risk over time plot to {save_path}")
    else:
        plt.show()


if __name__ == "__main__":
    # Example usage - uncomment and modify as needed
    # from config import DATA_RAW_DIR
    # import pandas as pd
    # 
    # df = pd.read_excel(os.path.join(DATA_RAW_DIR, "IoTPond6.xlsx"), sheet_name="IoTPond6")
    # df, _ = engineer(df)
    # 
    # plot_class_distribution(df['risk_level'], save_path='class_distribution.png')
    # plot_feature_importance(top_n=15, save_path='feature_importance.png')
    # plot_sensor_timeseries(df, save_path='sensor_timeseries.png')
    # plot_risk_over_time(df, save_path='risk_over_time.png')
    pass
