# create_model_for_cloud.py
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import numpy as np

# Cargar y limpiar AGRESIVAMENTE
df = pd.read_csv('data_fused_for_model.csv')

# Reemplazar strings no numéricos por NaN
for col in ['Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'V100C', 'TBN (mgKOH/g)', 'HOURS_OIL', 'BUDGET']:
    if col in df.columns:
        df[col] = df[col].replace({'--': np.nan, 'N/A': np.nan, '': np.nan, ' ': np.nan})
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Eliminar filas con NaN en features clave
cols_num = ['Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'V100C', 'TBN (mgKOH/g)', 'HOURS_OIL', 'BUDGET', 'REMAINING_LIFE']
df = df.dropna(subset=cols_num)

# Preparar
X = df[cols_num[:-1]].copy()
le = LabelEncoder()
X['COMPONENT_ENCODED'] = le.fit_transform(df['COMPONENT_LOCATION'])
y = df['REMAINING_LIFE']

# Entrenar
model = RandomForestRegressor(n_estimators=300, random_state=42)
model.fit(X, y)

# Guardar con protocolo seguro
joblib.dump(model, 'model_remaining_life.joblib', protocol=4)
joblib.dump(le, 'label_encoder_component.joblib', protocol=4)
print("✅ Modelos generados y listos para Streamlit Cloud.")