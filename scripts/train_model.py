# RUTA: server_py/scripts/train_model.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_auc_score
import joblib
import os
import traceback

# --- Configuración ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models', 'win_probability')
os.makedirs(MODELS_DIR, exist_ok=True)

# *** Usar FEATURES_FILE que definimos aquí ***
FEATURES_FILE = os.path.join(DATA_DIR, "nba_game_features.csv")
MODEL_FILE = os.path.join(MODELS_DIR, "logistic_regression_model.joblib")
SCALER_FILE = os.path.join(MODELS_DIR, "scaler.joblib")

# --- Columnas (sin cambios) ---
FEATURE_COLUMNS = [ 'H_WPCT', 'V_WPCT', 'DIFF_WPCT', 'H_LOC_WPCT', 'V_LOC_WPCT', 'DIFF_LOC_WPCT', 'H_L10_WPCT', 'V_L10_WPCT', 'DIFF_L10_WPCT', 'H_OFF_RTG', 'V_OFF_RTG', 'DIFF_OFF_RTG', 'H_DEF_RTG', 'V_DEF_RTG', 'DIFF_DEF_RTG_INV', 'H_NET_RTG', 'V_NET_RTG', 'DIFF_NET_RTG', 'H_PACE', 'V_PACE', 'DIFF_PACE' ]
TARGET_COLUMN = 'HOME_WIN'

# --- Función Principal de Entrenamiento ---
def train_logistic_regression():
    print("Starting model training process...")

    # 1. Cargar Datos
    try:
        print(f"Loading data from '{FEATURES_FILE}'...")
        # *** CORRECCIÓN: Usar FEATURES_FILE ***
        df = pd.read_csv(FEATURES_FILE)
        print(f"Data loaded successfully. Shape: {df.shape}")
        df.replace([float('inf'), -float('inf')], float('nan'), inplace=True)
        # Asegurarse que las columnas existen antes de dropear NaN
        cols_to_check = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN] if col in df.columns]
        df.dropna(subset=cols_to_check, inplace=True)
        print(f"Shape after dropping NaN/Inf in relevant columns: {df.shape}")
        if df.empty: print("ERROR: No valid data remaining."); return
        if TARGET_COLUMN not in df.columns: print(f"ERROR: Target column '{TARGET_COLUMN}' not found in CSV."); return
        missing_features = [col for col in FEATURE_COLUMNS if col not in df.columns]
        if missing_features: print(f"ERROR: Missing feature columns in CSV: {missing_features}"); return

    except FileNotFoundError: print(f"ERROR: File not found at '{FEATURES_FILE}'. Run build_features.py?"); return
    except Exception as e: print(f"ERROR: Failed to load/process file: {e}"); traceback.print_exc(); return

    # 2. Seleccionar Features (X) y Target (y)
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    print(f"Features (X) shape: {X.shape}"); print(f"Target (y) shape: {y.shape}")

    # 3. Dividir Datos
    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        print("Data split."); print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")
    except Exception as e: print(f"ERROR: Failed to split data: {e}"); traceback.print_exc(); return

    # 4. Escalar Features
    try:
        print("Scaling features..."); scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train) # Fit y transform en train
        X_test_scaled = scaler.transform(X_test) # Solo transform en test
        print("Features scaled.")
    except Exception as e: print(f"ERROR: Failed to scale features: {e}"); traceback.print_exc(); return

    # 5. Entrenar Modelo
    try:
        print("Training Logistic Regression model..."); model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X_train_scaled, y_train); print("Model training completed.")
    except Exception as e: print(f"ERROR: Failed during model training: {e}"); traceback.print_exc(); return

    # 6. Evaluar Modelo
    try:
        print("\n--- Model Evaluation ---")
        y_pred_train = model.predict(X_train_scaled); y_pred_test = model.predict(X_test_scaled)
        y_prob_train = model.predict_proba(X_train_scaled)[:, 1]; y_prob_test = model.predict_proba(X_test_scaled)[:, 1]
        train_accuracy = accuracy_score(y_train, y_pred_train); test_accuracy = accuracy_score(y_test, y_pred_test)
        train_auc = roc_auc_score(y_train, y_prob_train); test_auc = roc_auc_score(y_test, y_prob_test)
        print(f"Training Accuracy: {train_accuracy:.4f}"); print(f"Testing Accuracy: {test_accuracy:.4f}")
        print(f"Training AUC: {train_auc:.4f}"); print(f"Testing AUC: {test_auc:.4f}")
        print("\nClassification Report (Test Set):"); print(classification_report(y_test, y_pred_test, target_names=['Visitor Win', 'Home Win'], zero_division=0)) # Añadido zero_division
        print("\nConfusion Matrix (Test Set):"); print(confusion_matrix(y_test, y_pred_test))
    except Exception as e: print(f"ERROR: Failed during model evaluation: {e}"); traceback.print_exc()

    # 7. Guardar Modelo y Scaler
    try:
        print("\nSaving model and scaler...")
        joblib.dump(model, MODEL_FILE); joblib.dump(scaler, SCALER_FILE)
        print(f"Model saved to: {MODEL_FILE}"); print(f"Scaler saved to: {SCALER_FILE}")
        print("--- Training process finished successfully! ---")
    except Exception as e: print(f"ERROR: Failed to save model or scaler: {e}"); traceback.print_exc()

if __name__ == '__main__':
    # pip install scikit-learn joblib pandas
    train_logistic_regression()