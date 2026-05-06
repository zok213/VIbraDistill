# CELL 4 — Phase 1A: SVM Baseline on Envelope Spectra
# svm_f1 defined here; referenced in Cell 9.
# ============================================================
print("\n=== PHASE 1A: SVM BASELINE ===")

X_train, y_train = train_dataset.windows, train_dataset.labels
X_test,  y_test  = test_dataset.windows,  test_dataset.labels

_u = np.unique(y_train)
assert len(_u) > 1, (
    f"FATAL: Only class {_u} in training set. "
    "Dataset loading failed — check CWRU path and directory naming."
)

svm_pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('svm',    SVC(kernel='rbf', C=10.0, gamma='scale',
                   class_weight='balanced', random_state=42)),
])
print("  Fitting SVM (RBF, C=10, gamma=scale)...")
# EXPERT FIX: 5-seed evaluation on strictly separated train/test splits.
# Concatenating X_train and X_test for CV causes data leakage because they are
# split by load severity (7-mil vs 14/21-mil). The SVM must be evaluated on the
# exact same cross-severity generalization task as the student.
svm_scores = []
for seed in [42, 123, 456, 789, 1024]:
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(kernel='rbf', C=10.0, gamma='scale',
                    class_weight='balanced', random_state=seed)),
    ])
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    svm_scores.append(f1_score(y_test, y_pred, average='weighted', zero_division=0))

svm_f1_mean = float(np.mean(svm_scores))
svm_f1_std  = float(np.std(svm_scores, ddof=1))
svm_f1 = svm_f1_mean

print(f"  SVM 5-seed (Strict Transfer): {svm_f1_mean*100:.2f}% \u00b1 {svm_f1_std*100:.2f}% F1")

# Also fit on full train for confusion matrix (using first seed 42)
svm_pipe.fit(X_train, y_train)

y_pred_svm = svm_pipe.predict(X_test)
svm_acc = (y_pred_svm == y_test).mean()

print(f"  Accuracy: {svm_acc*100:.2f}%  |  Weighted F1 (Mean): {svm_f1_mean*100:.2f}%")
print(classification_report(
    y_test, y_pred_svm,
    target_names=['Normal', 'InnerRace', 'OuterRace', 'Ball'],
    zero_division=0,
))

cm_svm = confusion_matrix(y_test, y_pred_svm)
fig, ax = plt.subplots(figsize=(5, 4))
ConfusionMatrixDisplay(
    cm_svm, display_labels=['Normal', 'InnerRace', 'OuterRace', 'Ball']
).plot(ax=ax, colorbar=False)
ax.set_title(f'SVM — F1={svm_f1:.3f}')
plt.tight_layout()
plt.savefig(os.path.join(WORK_DIR, 'svm_confusion.png'), dpi=100)
plt.close()
print("✓ SVM confusion matrix → svm_confusion.png")
