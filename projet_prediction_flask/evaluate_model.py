#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script d'évaluation visuelle du modèle BusArrivalPredictor
Génère plusieurs graphiques adaptés à la régression.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, learning_curve
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, accuracy_score

from bus_arrival_predictor import BusArrivalPredictor

# Configuration des plots
sns.set_style("whitegrid")
PLOT_DIR = "data/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

def ensure_model_ready(predictor):
    """S'assure que le modèle est chargé ou entraîné."""
    if predictor.model is not None and predictor.is_fitted:
        print("✅ Modèle déjà disponible.")
        return True
    print("⚠️ Modèle non trouvé ou non entraîné. Tentative de chargement...")
    if predictor.load_model():
        print("✅ Modèle chargé avec succès.")
        return True
    print("⚠️ Chargement échoué. Lancement d'un entraînement...")
    if predictor.train_model():
        print("✅ Entraînement terminé avec succès.")
        return True
    print("❌ Impossible de préparer le modèle. Vérifiez vos données.")
    return False

def plot_pred_vs_actual(predictor):
    """Graphique 1 : Prédictions vs valeurs réelles"""
    df = predictor.load_dataset()
    if df is None or len(df) == 0:
        print("❌ Aucune donnée chargée")
        return
    X, y = predictor.preprocess_data(df, fit_encoders=False)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = predictor.model.predict(X_test)

    plt.figure(figsize=(8, 8))
    plt.scatter(y_test, y_pred, alpha=0.5, edgecolors='k', s=30)
    lims = [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())]
    plt.plot(lims, lims, 'r--', lw=2, label="Idéal (y=x)")
    plt.xlabel("Temps réel (minutes)")
    plt.ylabel("Temps prédit (minutes)")
    plt.title("Prédictions vs Réalité")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOT_DIR, "pred_vs_actual.png"), dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Graphique sauvegardé : pred_vs_actual.png")

def plot_residuals(predictor):
    """Graphique 2 : Histogramme des erreurs (résidus)"""
    df = predictor.load_dataset()
    if df is None:
        return
    X, y = predictor.preprocess_data(df, fit_encoders=False)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = predictor.model.predict(X_test)
    residuals = y_pred - y_test

    plt.figure(figsize=(10, 5))
    sns.histplot(residuals, bins=40, kde=True, color='steelblue')
    plt.axvline(0, color='red', linestyle='--', label="Erreur nulle")
    plt.xlabel("Erreur de prédiction (minutes) – (prédit - réel)")
    plt.ylabel("Fréquence")
    plt.title("Distribution des erreurs (résidus)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOT_DIR, "residuals_hist.png"), dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Graphique sauvegardé : residuals_hist.png")

def plot_reliability_curve(predictor, threshold=5):
    """Graphique 3 : Courbe de fiabilité (calibration) pour la confiance"""
    df = predictor.load_dataset()
    if df is None:
        return
    X, y = predictor.preprocess_data(df, fit_encoders=False)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = predictor.model.predict(X_test)

    y_true_binary = (y_test > threshold).astype(int)
    errors = y_pred - y_test
    proba_clf = LogisticRegression().fit(errors.reshape(-1, 1), y_true_binary)
    prob_pos = proba_clf.predict_proba(errors.reshape(-1, 1))[:, 1]

    fraction_pos, mean_pred = calibration_curve(y_true_binary, prob_pos, n_bins=10)

    plt.figure(figsize=(8, 6))
    plt.plot(mean_pred, fraction_pos, marker='o', label="Modèle (basé sur l'erreur)")
    plt.plot([0, 1], [0, 1], linestyle='--', label="Parfaitement calibré")
    plt.xlabel(f"Probabilité prédite de retard > {threshold} min")
    plt.ylabel("Fréquence réelle de retard")
    plt.title(f"Courbe de fiabilité – Confiance du modèle (seuil {threshold} min)")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(PLOT_DIR, "reliability_curve.png"), dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Graphique sauvegardé : reliability_curve.png")

def plot_learning_curve(predictor):
    """Graphique 4 : Courbe d'apprentissage (MAE en fonction de la taille d'entraînement)"""
    df = predictor.load_dataset()
    if df is None:
        return
    X, y = predictor.preprocess_data(df, fit_encoders=False)
    model = predictor.model

    train_sizes, train_scores, test_scores = learning_curve(
        model, X, y, cv=5, scoring='neg_mean_absolute_error',
        train_sizes=np.linspace(0.1, 1.0, 10), n_jobs=-1
    )
    train_mae = -train_scores.mean(axis=1)
    test_mae = -test_scores.mean(axis=1)
    train_std = train_scores.std(axis=1)
    test_std = test_scores.std(axis=1)

    plt.figure(figsize=(8, 6))
    plt.plot(train_sizes, train_mae, 'o-', color='blue', label="Erreur entraînement")
    plt.fill_between(train_sizes, train_mae - train_std, train_mae + train_std, alpha=0.2, color='blue')
    plt.plot(train_sizes, test_mae, 'o-', color='red', label="Erreur validation")
    plt.fill_between(train_sizes, test_mae - test_std, test_mae + test_std, alpha=0.2, color='red')
    plt.xlabel("Taille de l'ensemble d'entraînement")
    plt.ylabel("MAE (minutes)")
    plt.title("Courbe d'apprentissage")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(PLOT_DIR, "learning_curve.png"), dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Graphique sauvegardé : learning_curve.png")

def plot_confusion_matrix_and_f1(predictor, threshold=5):
    """Graphique 5 : Matrice de confusion et score F1 (classification binaire)"""
    df = predictor.load_dataset()
    if df is None:
        return
    X, y = predictor.preprocess_data(df, fit_encoders=False)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = predictor.model.predict(X_test)

    y_true_class = (y_test > threshold).astype(int)
    y_pred_class = (y_pred > threshold).astype(int)

    cm = confusion_matrix(y_true_class, y_pred_class)
    f1 = f1_score(y_true_class, y_pred_class)
    acc = accuracy_score(y_true_class, y_pred_class)

    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=[f"≤{threshold} min", f">{threshold} min"],
                yticklabels=[f"≤{threshold} min", f">{threshold} min"])
    plt.xlabel("Prédiction")
    plt.ylabel("Réel")
    plt.title(f"Matrice de confusion (seuil = {threshold} min)\nF1 = {f1:.3f} | Accuracy = {acc:.3f}")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"confusion_matrix_thr{threshold}.png"), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Matrice de confusion sauvegardée (F1 = {f1:.3f})")

def main():
    print("=" * 60)
    print("Évaluation visuelle du modèle de prédiction de bus")
    print("=" * 60)

    predictor = BusArrivalPredictor()
    if not ensure_model_ready(predictor):
        print("❌ Impossible de continuer. Vérifiez votre environnement.")
        return

    print("\n📊 Génération des graphiques...\n")
    try:
        plot_pred_vs_actual(predictor)
    except Exception as e:
        print(f"Erreur sur pred_vs_actual : {e}")
    try:
        plot_residuals(predictor)
    except Exception as e:
        print(f"Erreur sur residuals : {e}")
    try:
        plot_reliability_curve(predictor, threshold=5)
    except Exception as e:
        print(f"Erreur sur reliability curve : {e}")
    try:
        plot_learning_curve(predictor)
    except Exception as e:
        print(f"Erreur sur learning curve : {e}")
    try:
        plot_confusion_matrix_and_f1(predictor, threshold=5)
    except Exception as e:
        print(f"Erreur sur confusion matrix : {e}")

    print(f"\n✅ Tous les graphiques disponibles sont dans : {PLOT_DIR}")

if __name__ == "__main__":
    main()