# fuse_data_for_model.py
import pandas as pd
import os

print("🔍 Cargando HISTORICO_FALLAS_TEST.xls...")
df_hist = pd.read_excel('HISTORICO_FALLAS_TEST.xls')

# Asegurar REMAINING_LIFE
if 'REMAINING_LIFE' not in df_hist.columns:
    print("💡 Creando 'REMAINING_LIFE' = BUDGET - HORAS_TRABAJADAS")
    df_hist['REMAINING_LIFE'] = df_hist['BUDGET'] - df_hist['HORAS_TRABAJADAS']

print("📂 Cargando Sample_Reports_Mod_Test.xls...")
xls = pd.ExcelFile('Sample_Reports_Mod_Test.xls')

dfs_aceite = []
cols_idx = [1, 3, 8, 14, 22, 21, 29, 44, 41, 42, 55]
cols_names = [
    'UNIT_ID', 'COMPONENT_LOCATION', 'HOURS_OIL', 'DATE_ANALIZED',
    'Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'TBN (mgKOH/g)',
    'OXI - (abs/0.1mm)', 'NIT - (abs/cm)', 'V100C'
]

for sheet in ['DRILLS_ENG', 'DRILLS_COMP', 'DRILLS_GEAR']:
    if sheet in xls.sheet_names:
        print(f"  → Leyendo hoja: {sheet}")
        df = pd.read_excel(
            xls, sheet_name=sheet,
            header=None,
            usecols=cols_idx,
            names=cols_names
        )
        df['UNIT_ID'] = df['UNIT_ID'].astype(str).str.strip()
        df['COMPONENT_LOCATION'] = df['COMPONENT_LOCATION'].astype(str).str.strip()
        dfs_aceite.append(df)

if not dfs_aceite:
    raise RuntimeError("❌ No se encontraron hojas válidas en Sample_Reports_Mod_Test.xls")

df_aceite = pd.concat(dfs_aceite, ignore_index=True)
print(f"✅ Total de registros de aceite: {len(df_aceite)}")

# Obtener el último análisis por (UNIT_ID, COMPONENT_LOCATION)
# Asegurar que DATE_ANALIZED sea datetime
df_aceite['DATE_ANALIZED'] = pd.to_datetime(df_aceite['DATE_ANALIZED'], errors='coerce')

# Eliminar filas sin fecha válida
df_aceite = df_aceite.dropna(subset=['DATE_ANALIZED'])

# Ahora sí ordenar
df_aceite_latest = (
    df_aceite
    .sort_values('DATE_ANALIZED')
    .groupby(['UNIT_ID', 'COMPONENT_LOCATION'], as_index=False)
    .last()
)

print(f"✅ Último análisis único: {len(df_aceite_latest)}")

# Fusión: histórico (izq) + último análisis (der)
df_fused = pd.merge(
    df_hist,
    df_aceite_latest,
    on=['UNIT_ID', 'COMPONENT_LOCATION'],
    how='left',
    suffixes=('', '_LATEST')
)

# Guardar
output_path = 'data_fused_for_model.csv'
df_fused.to_csv(output_path, index=False)
print(f"\n✅ Fusión completada. Archivo guardado: {output_path}")
print(f"→ Filas: {len(df_fused)} | Columnas: {len(df_fused.columns)}")
print(f"→ Columnas clave: {[df_fused.columns[i] for i in range(min(10, len(df_fused.columns)))]}")