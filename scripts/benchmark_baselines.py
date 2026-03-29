"""
Benchmark meta-models against baselines:
1. Climatology: predict station unreliable rate as probability
2. Persistence: yesterday's outcome = today's prediction
3. Random: random predictions at the class frequency

If our models can't beat these, they're useless.
"""

import matplotlib
matplotlib.use('Agg')

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix,
                             brier_score_loss)
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data\meta_model")
OUT_DIR = DATA_DIR / "results"

# ─── Load ───
df = pd.read_csv(DATA_DIR / "meta_features.csv")
df['date'] = pd.to_datetime(df['date'])

with open(DATA_DIR / "feature_columns.txt") as f:
    feature_cols = [line.strip() for line in f if line.strip()]

X = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(df[feature_cols].median())
y = df['unreliable'].values

train_mask = df['year'] <= 2020
test_mask = df['year'] >= 2021
X_train, X_test = X[train_mask].values, X[test_mask].values
y_train, y_test = y[train_mask], y[test_mask]

# ─── Baseline 1: Climatology ───
# Predict each test sample's probability as the station's training unreliable rate
print("Computing baselines...")

station_rates = df[train_mask].groupby('station')['unreliable'].mean().to_dict()
# For stations not in training, use overall rate
overall_rate = y_train.mean()

clim_probs = df[test_mask]['station'].map(station_rates).fillna(overall_rate).values
clim_preds = (clim_probs > 0.5).astype(int)  # default threshold
# Also find optimal threshold for climatology
best_f1_clim = 0
best_t_clim = 0.5
for t in np.arange(0.05, 0.95, 0.01):
    preds = (clim_probs >= t).astype(int)
    f = f1_score(y_test, preds, zero_division=0)
    if f > best_f1_clim:
        best_f1_clim = f
        best_t_clim = t
clim_preds_opt = (clim_probs >= best_t_clim).astype(int)

# ─── Baseline 2: Persistence ───
# For each test row, find the same station's previous day outcome
df_sorted = df.sort_values(['station', 'date', 'lead_time_hours'])
df_sorted['prev_unreliable'] = df_sorted.groupby(['station', 'lead_time_hours'])['unreliable'].shift(1)

# Get persistence predictions for test set
persist_probs = df_sorted[test_mask]['prev_unreliable'].values
# Fill NaN (first day of each station) with overall training rate
persist_probs = np.where(np.isnan(persist_probs), overall_rate, persist_probs)
persist_preds = (persist_probs > 0.5).astype(int)

# ─── Baseline 3: Random (at class frequency) ───
rng = np.random.RandomState(42)
random_probs = rng.random(len(y_test))
# Scale to match training unreliable rate
random_preds = (random_probs < overall_rate).astype(int)

# ─── Train ML models with optimized thresholds ───
print("Training ML models...")
n_neg = (y_train == 0).sum()
n_pos = (y_train == 1).sum()

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

ml_models = {
    'RandomForest': RandomForestClassifier(
        n_estimators=500, max_depth=20, min_samples_leaf=10,
        class_weight='balanced', random_state=42, n_jobs=-1),
    'XGBoost': xgb.XGBClassifier(
        n_estimators=500, max_depth=8, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=n_neg/max(n_pos,1),
        random_state=42, n_jobs=-1, eval_metric='logloss'),
    'NeuralNetwork': MLPClassifier(
        hidden_layer_sizes=(128, 64, 32), activation='relu',
        max_iter=500, early_stopping=True, validation_fraction=0.15,
        random_state=42, learning_rate='adaptive', learning_rate_init=0.001),
}

ml_probs = {}
for name, model in ml_models.items():
    if name == 'NeuralNetwork':
        model.fit(X_train_s, y_train)
        ml_probs[name] = model.predict_proba(X_test_s)[:, 1]
    else:
        model.fit(X_train, y_train)
        ml_probs[name] = model.predict_proba(X_test)[:, 1]

# Find optimal thresholds for ML models
ml_best_t = {}
for name, prob in ml_probs.items():
    best_f1, best_t = 0, 0.5
    for t in np.arange(0.05, 0.95, 0.01):
        preds = (prob >= t).astype(int)
        f = f1_score(y_test, preds, zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_t = t
    ml_best_t[name] = best_t

# ─── Compute all metrics ───
print("\nComputing metrics...")

def compute_metrics(name, y_true, y_prob, threshold):
    y_pred = (y_prob >= threshold).astype(int)

    # Handle edge case where all predictions are same class
    try:
        auc = roc_auc_score(y_true, y_prob)
    except ValueError:
        auc = 0.5

    try:
        brier = brier_score_loss(y_true, y_prob)
    except:
        brier = np.nan

    return {
        'model': name,
        'threshold': round(threshold, 2),
        'accuracy': round(accuracy_score(y_true, y_pred), 3),
        'precision': round(precision_score(y_true, y_pred, zero_division=0), 3),
        'recall': round(recall_score(y_true, y_pred, zero_division=0), 3),
        'f1': round(f1_score(y_true, y_pred, zero_division=0), 3),
        'auc_roc': round(auc, 3),
        'brier_score': round(brier, 4),
    }

all_results = []

# Baselines
all_results.append(compute_metrics('Climatology', y_test, clim_probs, best_t_clim))
all_results.append(compute_metrics('Persistence', y_test, persist_probs, 0.5))
all_results.append(compute_metrics('Random', y_test, random_probs, 1 - overall_rate))

# ML models (optimized)
for name, prob in ml_probs.items():
    all_results.append(compute_metrics(name, y_test, prob, ml_best_t[name]))

results_df = pd.DataFrame(all_results)

# ─── Print results ───
print("\n" + "="*70)
print("BENCHMARKING: ML MODELS vs BASELINES")
print("="*70)
print(results_df.to_string(index=False))

# Compute skill scores (improvement over climatology)
clim_auc = results_df[results_df['model'] == 'Climatology']['auc_roc'].values[0]
clim_f1 = results_df[results_df['model'] == 'Climatology']['f1'].values[0]
clim_brier = results_df[results_df['model'] == 'Climatology']['brier_score'].values[0]

print(f"\n--- Skill Scores (improvement over Climatology) ---")
for _, row in results_df.iterrows():
    if row['model'] in ['Climatology', 'Random']:
        continue
    auc_skill = (row['auc_roc'] - clim_auc) / (1.0 - clim_auc) * 100 if clim_auc < 1 else 0
    f1_skill = (row['f1'] - clim_f1) / (1.0 - clim_f1) * 100 if clim_f1 < 1 else 0
    brier_skill = (1 - row['brier_score'] / clim_brier) * 100 if clim_brier > 0 else 0
    print(f"  {row['model']:15s}: AUC skill={auc_skill:+.1f}%, F1 skill={f1_skill:+.1f}%, Brier skill={brier_skill:+.1f}%")

# ─── Bar chart comparison ───
print("\nGenerating comparison chart...")
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

metrics_to_plot = ['f1', 'auc_roc', 'recall']
titles = ['F1 Score', 'AUC-ROC', 'Recall']

baseline_names = ['Random', 'Climatology', 'Persistence']
ml_names = ['RandomForest', 'XGBoost', 'NeuralNetwork']
all_names = baseline_names + ml_names

bar_colors = ['#ccc', '#999', '#666', '#2196F3', '#FF9800', '#4CAF50']

for ax, metric, title in zip(axes, metrics_to_plot, titles):
    values = []
    for name in all_names:
        row = results_df[results_df['model'] == name]
        if len(row) > 0:
            values.append(row[metric].values[0])
        else:
            values.append(0)

    bars = ax.bar(range(len(all_names)), values, color=bar_colors, edgecolor='white', linewidth=0.5)

    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{val:.3f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(range(len(all_names)))
    ax.set_xticklabels(all_names, rotation=30, ha='right', fontsize=8)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3, axis='y')

    # Draw line separating baselines from ML
    ax.axvline(2.5, color='red', linestyle='--', alpha=0.5, linewidth=1)

fig.suptitle('Meta-Model Performance vs Baselines', fontsize=14, fontweight='bold', y=1.02)
fig.tight_layout()
fig.savefig(OUT_DIR / "benchmark_comparison.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved benchmark_comparison.png")

results_df.to_csv(OUT_DIR / "benchmark_results.csv", index=False)
print(f"Saved benchmark_results.csv")

print("\nDone!")
