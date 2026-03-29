"""
Phase 2 Step 2: Train Meta-Models (RF, XGBoost, NN)
=====================================================
Binary classification: Reliable vs Unreliable CAMS forecasts.

Train: 2015-2020 | Test: 2021-2024
Also: Leave-One-Station-Out cross-validation
SHAP analysis for interpretability

Outputs in data/meta_model/:
  - model performance metrics (CSV + printed)
  - ROC curves
  - confusion matrices
  - SHAP summary plots
  - feature importance rankings
"""

import matplotlib
matplotlib.use('Agg')  # non-interactive backend — no tkinter crash

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix,
                             classification_report, roc_curve)
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# Try importing xgboost and shap
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("WARNING: xgboost not installed. Will skip XGBoost.")

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False
    print("WARNING: shap not installed. Will skip SHAP analysis.")

DATA_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data\meta_model")
OUT_DIR = DATA_DIR / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Load data ───
print("Loading meta_features.csv...")
df = pd.read_csv(DATA_DIR / "meta_features.csv")
df['date'] = pd.to_datetime(df['date'])
print(f"  Total: {len(df)} rows")

# Feature columns
with open(DATA_DIR / "feature_columns.txt") as f:
    feature_cols = [line.strip() for line in f if line.strip()]

print(f"  Features: {len(feature_cols)}")

# Handle any NaN/inf in features
X = df[feature_cols].copy()
X = X.replace([np.inf, -np.inf], np.nan)
nan_cols = X.columns[X.isna().any()].tolist()
if nan_cols:
    print(f"  Columns with NaN: {nan_cols}")
    X = X.fillna(X.median())

y = df['unreliable'].values

# ─── Train/Test Split (temporal) ───
train_mask = df['year'] <= 2020
test_mask = df['year'] >= 2021

X_train, X_test = X[train_mask].values, X[test_mask].values
y_train, y_test = y[train_mask], y[test_mask]

print(f"\n  Train: {len(X_train)} rows ({y_train.mean()*100:.1f}% unreliable)")
print(f"  Test:  {len(X_test)} rows ({y_test.mean()*100:.1f}% unreliable)")

# Scale features (needed for NN, doesn't hurt RF/XGB)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ─── Define models ───
models = {}

# 1. Random Forest
models['RandomForest'] = RandomForestClassifier(
    n_estimators=500,
    max_depth=20,
    min_samples_leaf=10,
    class_weight='balanced',  # handle imbalance
    random_state=42,
    n_jobs=-1,
)

# 2. XGBoost
if HAS_XGB:
    # Compute scale_pos_weight for imbalance
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos = n_neg / max(n_pos, 1)

    models['XGBoost'] = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos,
        random_state=42,
        n_jobs=-1,
        eval_metric='logloss',
    )

# 3. Neural Network
models['NeuralNetwork'] = MLPClassifier(
    hidden_layer_sizes=(128, 64, 32),
    activation='relu',
    max_iter=500,
    early_stopping=True,
    validation_fraction=0.15,
    random_state=42,
    learning_rate='adaptive',
    learning_rate_init=0.001,
)

# ─── Train and evaluate ───
print("\n" + "="*70)
print("TRAINING MODELS")
print("="*70)

results = []

for name, model in models.items():
    print(f"\n--- {name} ---")

    # Use scaled data for NN, raw for tree models
    if name == 'NeuralNetwork':
        X_tr, X_te = X_train_scaled, X_test_scaled
    else:
        X_tr, X_te = X_train, X_test

    # Train
    print(f"  Training on {len(X_tr)} samples...", flush=True)
    model.fit(X_tr, y_train)

    # Predict
    y_pred = model.predict(X_te)
    y_prob = model.predict_proba(X_te)[:, 1]

    # Metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob)

    results.append({
        'model': name, 'accuracy': acc, 'precision': prec,
        'recall': rec, 'f1': f1, 'auc_roc': auc,
    })

    print(f"  Accuracy:  {acc:.3f}")
    print(f"  Precision: {prec:.3f}")
    print(f"  Recall:    {rec:.3f}")
    print(f"  F1 Score:  {f1:.3f}")
    print(f"  AUC-ROC:   {auc:.3f}")

    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=['Reliable', 'Unreliable'], digits=3))

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print(f"  Confusion Matrix:")
    print(f"    TN={cm[0,0]}  FP={cm[0,1]}")
    print(f"    FN={cm[1,0]}  TP={cm[1,1]}")

# ─── Save results table ───
results_df = pd.DataFrame(results)
results_df.to_csv(OUT_DIR / "model_comparison.csv", index=False)
print("\n" + "="*70)
print("MODEL COMPARISON")
print("="*70)
print(results_df.to_string(index=False))

# ─── ROC Curves ───
print("\nGenerating ROC curves...")
fig, ax = plt.subplots(figsize=(8, 6))
colors = {'RandomForest': '#2196F3', 'XGBoost': '#FF9800', 'NeuralNetwork': '#4CAF50'}

for name, model in models.items():
    if name == 'NeuralNetwork':
        y_prob = model.predict_proba(X_test_scaled)[:, 1]
    else:
        y_prob = model.predict_proba(X_test)[:, 1]

    fpr, tpr, _ = roc_curve(y_test, y_prob)
    auc = roc_auc_score(y_test, y_prob)
    ax.plot(fpr, tpr, color=colors.get(name, 'gray'), linewidth=2,
            label=f'{name} (AUC={auc:.3f})')

ax.plot([0, 1], [0, 1], 'k--', linewidth=1, alpha=0.5)
ax.set_xlabel('False Positive Rate', fontsize=12)
ax.set_ylabel('True Positive Rate', fontsize=12)
ax.set_title('ROC Curves — Meta-Model Comparison', fontsize=13, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT_DIR / "roc_curves.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("  Saved roc_curves.png")

# ─── Confusion Matrix plots ───
print("Generating confusion matrices...")
fig, axes = plt.subplots(1, len(models), figsize=(5*len(models), 4.5))
if len(models) == 1:
    axes = [axes]

for ax, (name, model) in zip(axes, models.items()):
    if name == 'NeuralNetwork':
        y_pred = model.predict(X_test_scaled)
    else:
        y_pred = model.predict(X_test)

    cm = confusion_matrix(y_test, y_pred)
    im = ax.imshow(cm, cmap='Blues', interpolation='nearest')
    ax.set_title(name, fontsize=12, fontweight='bold')
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

fig.tight_layout()
fig.savefig(OUT_DIR / "confusion_matrices.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("  Saved confusion_matrices.png")

# ─── Feature Importance (RF + XGBoost) ───
print("\nGenerating feature importance plots...")
for name in ['RandomForest', 'XGBoost']:
    if name not in models:
        continue

    model = models[name]
    importances = model.feature_importances_
    idx = np.argsort(importances)[-20:]  # top 20

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(range(len(idx)), importances[idx], color=colors.get(name, 'gray'), alpha=0.8)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([feature_cols[i] for i in idx], fontsize=9)
    ax.set_xlabel('Feature Importance', fontsize=11)
    ax.set_title(f'{name} — Top 20 Features', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"feature_importance_{name}.png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved feature_importance_{name}.png")

# ─── SHAP Analysis ───
if HAS_SHAP:
    print("\nRunning SHAP analysis (this may take a minute)...")

    # Use the best tree model for SHAP (faster than NN)
    best_tree = 'XGBoost' if 'XGBoost' in models else 'RandomForest'
    model = models[best_tree]

    # Use a sample for speed
    shap_sample_size = min(2000, len(X_test))
    shap_idx = np.random.RandomState(42).choice(len(X_test), shap_sample_size, replace=False)
    X_shap = X_test[shap_idx]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_shap)

    # For binary classification, shap_values may be a list [class0, class1]
    if isinstance(shap_values, list):
        shap_vals = shap_values[1]  # class 1 = unreliable
    else:
        shap_vals = shap_values

    # Summary plot
    fig, ax = plt.subplots(figsize=(12, 10))
    shap.summary_plot(shap_vals, X_shap, feature_names=feature_cols,
                      show=False, max_display=20)
    plt.title(f'SHAP Summary — {best_tree}', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"shap_summary_{best_tree}.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved shap_summary_{best_tree}.png")

    # Bar plot (mean |SHAP|)
    fig, ax = plt.subplots(figsize=(10, 8))
    shap.summary_plot(shap_vals, X_shap, feature_names=feature_cols,
                      plot_type='bar', show=False, max_display=20)
    plt.title(f'Mean |SHAP| — {best_tree}', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"shap_bar_{best_tree}.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved shap_bar_{best_tree}.png")
else:
    print("\nSkipping SHAP (not installed). Install with: pip install shap")

# ─── Leave-One-Station-Out Cross-Validation ───
print("\n" + "="*70)
print("LEAVE-ONE-STATION-OUT CROSS-VALIDATION")
print("="*70)

stations = sorted(df['station'].unique())
# Use RF for LOSO (fastest)
loso_results = []

for held_out in stations:
    train_idx = df['station'] != held_out
    test_idx = df['station'] == held_out

    if test_idx.sum() == 0 or train_idx.sum() == 0:
        continue

    X_tr_loso = X[train_idx].values
    X_te_loso = X[test_idx].values
    y_tr_loso = y[train_idx]
    y_te_loso = y[test_idx]

    # Handle case where test set has only one class
    if len(np.unique(y_te_loso)) < 2:
        print(f"  {held_out}: only one class in test — skipping AUC")
        continue

    rf_loso = RandomForestClassifier(
        n_estimators=300, max_depth=20, min_samples_leaf=10,
        class_weight='balanced', random_state=42, n_jobs=-1)
    rf_loso.fit(X_tr_loso, y_tr_loso)

    y_pred_loso = rf_loso.predict(X_te_loso)
    y_prob_loso = rf_loso.predict_proba(X_te_loso)[:, 1]

    acc = accuracy_score(y_te_loso, y_pred_loso)
    f1 = f1_score(y_te_loso, y_pred_loso, zero_division=0)
    auc = roc_auc_score(y_te_loso, y_prob_loso)

    loso_results.append({
        'held_out_station': held_out,
        'n_test': len(y_te_loso),
        'unreliable_rate': y_te_loso.mean(),
        'accuracy': acc, 'f1': f1, 'auc_roc': auc,
    })

    print(f"  {held_out}: N={len(y_te_loso)}, Acc={acc:.3f}, F1={f1:.3f}, AUC={auc:.3f}")

loso_df = pd.DataFrame(loso_results)
loso_df.to_csv(OUT_DIR / "loso_results.csv", index=False)
print(f"\n  Mean LOSO AUC: {loso_df['auc_roc'].mean():.3f} (+/- {loso_df['auc_roc'].std():.3f})")

# ─── Per-station test performance (temporal split) ───
print("\n" + "="*70)
print("PER-STATION TEST PERFORMANCE (RF, temporal split)")
print("="*70)

rf_model = models['RandomForest']
test_stations = df[df['year'] >= 2021]['station'].unique()

for st in sorted(test_stations):
    mask = (df['station'] == st) & (df['year'] >= 2021)
    if mask.sum() == 0:
        continue
    X_st = X[mask].values
    y_st = y[mask]

    y_pred_st = rf_model.predict(X_st)
    y_prob_st = rf_model.predict_proba(X_st)[:, 1]

    acc = accuracy_score(y_st, y_pred_st)
    f1 = f1_score(y_st, y_pred_st, zero_division=0)
    if len(np.unique(y_st)) >= 2:
        auc = roc_auc_score(y_st, y_prob_st)
    else:
        auc = float('nan')

    print(f"  {st}: N={len(y_st)}, Acc={acc:.3f}, F1={f1:.3f}, AUC={auc:.3f}")

print("\nAll outputs saved to:", OUT_DIR)
print("Done!")
