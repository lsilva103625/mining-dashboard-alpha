# train_final.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
from pathlib import Path

root = Path(__file__).parent

# --- Cargar análisis ---
xls = pd.ExcelFile(root / "Sample_Reports_Mod_Test.xls")
dfs = []
cols_idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
cols_names = [
    'UNIT_ID', 'COMPONENT_LOCATION', 'HOURS_OIL', 'DATE_ANALIZED',
    'Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'TBN (mgKOH/g)',
    'OXI - (abs/0.1mm)', 'NIT - (abs/cm)', 'V100C'
]

for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet, usecols=cols_idx, names=cols_names, header=None)
    dfs.append(df)

df_analysis = pd.concat(dfs, ignore_index=True)
df_analysis = df_analysis.dropna(subset=['HOURS_OIL'])
numeric_cols = ['Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'TBN (mgKOH/g)', 'V100C', 'HOURS_OIL']
df_analysis[numeric_cols] = df_analysis[numeric_cols].apply(pd.to_numeric, errors='coerce')

# --- Cargar instalación ---
df_inst = pd.read_excel(root / "COMPONENTS_DRILLS_INSTALLED.xls", sheet_name='INSTALLED')
df_inst.columns = df_inst.columns.str.strip()
df_inst['UNIT_ID'] = df_inst['UNIT_ID'].astype(str).str.strip()
df_inst['COMPONENT_LOCATION'] = df_inst['COMPONENT_LOCATION'].astype(str).str.strip()

# --- Limpieza y diagnóstico ---
print("🔍 Diagnóstico de fusión:")
print("df_analysis UNIT_ID unicos:", df_analysis['UNIT_ID'].unique()[:5])
print("df_inst UNIT_ID unicos:", df_inst['UNIT_ID'].unique()[:5])
print("df_analysis COMPONENT unicos:", df_analysis['COMPONENT_LOCATION'].unique())
print("df_inst COMPONENT unicos:", df_inst['COMPONENT_LOCATION'].unique())

# --- Fusión ---
merged = pd.merge(
    df_analysis,
    df_inst[['UNIT_ID', 'COMPONENT_LOCATION', 'BUDGET', 'HORAS_VIDA_ACTUAL']],
    on=['UNIT_ID', 'COMPONENT_LOCATION'],
    how='inner'
)

print(f"✅ Filas tras fusión: {len(merged)}")
if len(merged) == 0:
    print("❌ ERROR: No hay coincidencias. Revisa los valores de UNIT_ID y COMPONENT_LOCATION.")
    exit(1)

# --- Objetivo ---
merged['REMAINING_LIFE'] = merged['BUDGET'] - merged['HORAS_VIDA_ACTUAL']
merged = merged[merged['REMAINING_LIFE'] >= 0].copy()

# --- Features ---
features_list = [
    'Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'V100C', 'TBN (mgKOH/g)',
    'HOURS_OIL', 'BUDGET', 'COMPONENT_LOCATION'
]

X = merged[features_list].copy()
y = merged['REMAINING_LIFE']

# Codificar
le = LabelEncoder()
X['COMPONENT_ENCODED'] = le.fit_transform(X['COMPONENT_LOCATION'])
X = X.drop('COMPONENT_LOCATION', axis=1)

# --- Entrenamiento ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
model.fit(X_train, y_train)

# --- Evaluación ---
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
print(f"🎯 MAE: {mae:.2f} | R²: {r2:.2f}")

# --- Guardar ---
joblib.dump(model, "model_remaining_life.joblib")
joblib.dump(le, "label_encoder_component.joblib")
print("✅ Modelos guardados: model_remaining_life.joblib, label_encoder_component.joblib")