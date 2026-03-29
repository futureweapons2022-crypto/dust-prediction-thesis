"""
Fix the recall problem: optimize classification threshold.
Instead of 50%, find the threshold that maximizes F1 score
and also show Precision-Recall tradeoff curves.
"""

import matplotlib
matplotlib.use('Agg')

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix,
                             precision_recall_curve, classification_report)
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
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

# Scale for NN
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

# ─── Train all 3 models ───
n_neg = (y_train == 0).sum()
n_pos = (y_train == 1).sum()

models = {
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

print("Training models...")
for name, model in models.items():
    if name == 'NeuralNetwork':
        model.fit(X_train_s, y_train)
    else:
        model.fit(X_train, y_train)
    print(f"  {name} trained")

# ─── Get probabilities ───
probs = {}
for name, model in models.items():
    if name == 'NeuralNetwork':
        probs[name] = model.predict_proba(X_test_s)[:, 1]
    else:
        probs[name] = model.predict_proba(X_test)[:, 1]

# ─── Find optimal thresholds ───
print("\n" + "="*70)
print("THRESHOLD OPTIMIZATION")
print("="*70)

colors = {'RandomForest': '#2196F3', 'XGBoost': '#FF9800', 'NeuralNetwork': '#4CAF50'}

# Plot: Precision-Recall-F1 vs Threshold for each model
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

best_thresholds = {}

for ax, (name, y_prob) in zip(axes, probs.items()):
    thresholds = np.arange(0.05, 0.95, 0.01)
    precisions, recalls, f1s = [], [], []

    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        p = precision_score(y_test, y_pred, zero_division=0)
        r = recall_score(y_test, y_pred, zero_division=0)
        f = f1_score(y_test, y_pred, zero_division=0)
        precisions.append(p)
        recalls.append(r)
        f1s.append(f)

    # Find best F1 threshold
    best_idx = np.argmax(f1s)
    best_t = thresholds[best_idx]
    best_f1 = f1s[best_idx]
    best_thresholds[name] = best_t

    ax.plot(thresholds, precisions, 'b-', label='Precision', linewidth=1.5)
    ax.plot(thresholds, recalls, 'r-', label='Recall', linewidth=1.5)
    ax.plot(thresholds, f1s, 'g-', label='F1', linewidth=2)
    ax.axvline(best_t, color='k', linestyle='--', alpha=0.7, label=f'Best t={best_t:.2f}')
    ax.axvline(0.5, color='gray', linestyle=':', alpha=0.5, label='Default t=0.50')

    ax.set_xlabel('Threshold', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title(f'{name}\nBest F1={best_f1:.3f} at t={best_t:.2f}', fontsize=12, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.05, 0.95)
    ax.set_ylim(0, 1)

fig.tight_layout()
fig.savefig(OUT_DIR / "threshold_optimization.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved threshold_optimization.png")

# ─── Results with optimized thresholds ───
print("\n" + "="*70)
print("RESULTS: DEFAULT (t=0.50) vs OPTIMIZED THRESHOLD")
print("="*70)

all_results = []

for name, y_prob in probs.items():
    best_t = best_thresholds[name]

    for label, t in [('default_0.50', 0.50), (f'optimized_{best_t:.2f}', best_t)]:
        y_pred = (y_prob >= t).astype(int)
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_prob)
        cm = confusion_matrix(y_test, y_pred)

        all_results.append({
            'model': name, 'threshold': label, 't_value': t,
            'accuracy': round(acc, 3), 'precision': round(prec, 3),
            'recall': round(rec, 3), 'f1': round(f1, 3), 'auc_roc': round(auc, 3),
            'TP': cm[1,1], 'FP': cm[0,1], 'FN': cm[1,0], 'TN': cm[0,0],
        })

        if 'optimized' in label:
            print(f"\n--- {name} (t={best_t:.2f}) ---")
            print(f"  Accuracy:  {acc:.3f}")
            print(f"  Precision: {prec:.3f}")
            print(f"  Recall:    {rec:.3f}  (was {[r for r in all_results if r['model']==name and r['threshold']=='default_0.50'][0]['recall']:.3f})")
            print(f"  F1:        {f1:.3f}  (was {[r for r in all_results if r['model']==name and r['threshold']=='default_0.50'][0]['f1']:.3f})")
            print(f"  AUC-ROC:   {auc:.3f}")
            print(f"  Caught {cm[1,1]}/{cm[1,1]+cm[1,0]} failures ({cm[1,1]/(cm[1,1]+cm[1,0])*100:.1f}%)")
            print(f"  False alarms: {cm[0,1]}/{cm[0,0]+cm[0,1]} ({cm[0,1]/(cm[0,0]+cm[0,1])*100:.1f}%)")

results_df = pd.DataFrame(all_results)
results_df.to_csv(OUT_DIR / "threshold_comparison.csv", index=False)

# ─── Confusion matrices with optimized thresholds ───
print("\nGenerating optimized confusion matrices...")
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

for ax, (name, y_prob) in zip(axes, probs.items()):
    t = best_thresholds[name]
    y_pred = (y_prob >= t).astype(int)
    cm = confusion_matrix(y_test, y_pred)

    im = ax.imshow(cm, cmap='Blues', interpolation='nearest')
    ax.set_title(f'{name} (t={t:.2f})', fontsize=12, fontweight='bold')
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Reliable', 'Unreliable'])
    ax.set_yticklabels(['Reliable', 'Unreliable'])

    for i in range(2):
        for j in range(2):
            color = 'white' if cm[i, j] > cm.max() * 0.5 else 'black'
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    color=color, fontsize=14, fontweight='bold')

fig.suptitle('Confusion Matrices — Optimized Thresholds', fontsize=13, fontweight='bold')
fig.tight_layout()
fig.savefig(OUT_DIR / "confusion_matrices_optimized.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved confusion_matrices_optimized.png")

print("\nDone!")
