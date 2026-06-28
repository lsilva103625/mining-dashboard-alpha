# dashboard_umbral_40_8503.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from io import BytesIO
from pathlib import Path
import joblib

st.set_page_config(layout="wide", page_title="Análisis de Desgaste — Equipo Crítico", page_icon="⚙️")
st.title("📊 Análisis de Desgaste — Equipo Crítico")
st.caption(f"Versión 2.4 | Autor: Leonidas | {datetime.now().strftime('%Y-%m-%d')}")

# --- Paleta de colores ---
COLOR_MAP = {
    'Fe (ppm)': '#d32f2f',
    'Cu (ppm)': '#f57c00',
    'Si (ppm)': '#388e3c',
    'V100C': '#1976d2',
    'TBN (mgKOH/g)': '#7b1fa2',
    'OXI - (abs/0.1mm)': '#0288d1',
    'NIT - (abs/cm)': '#00796b',
    'REMAINING_LIFE': '#e91e63',
    'HORAS_TRABAJADAS': '#ff9800',
    'HORAS_AL_FALLO': '#ff9800',
    'BUDGET': '#4caf50'
}

# --- Función para guardar con timestamp ---
def save_plot(fig, prefix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0.1)
    buf.seek(0)
    return buf.getvalue(), f"{prefix}_{timestamp}.png"

# --- Cargar datos de análisis con rutas seguras ---
@st.cache_data
def load_analysis_data():
    root = Path(__file__).parent
    xls_path = root / "Sample_Reports_Mod_Test.xls"
    
    if not xls_path.exists():
        st.error("Archivo 'Sample_Reports_Mod_Test.xls' no encontrado en la raíz.")
        return pd.DataFrame(columns=['UNIT_ID', 'COMPONENT_TYPE', 'HOURS_OIL', 'DATE_ANALIZED'])

    try:
        xls = pd.ExcelFile(xls_path)
    except Exception as e:
        st.error(f"Error al abrir Excel: {e}")
        return pd.DataFrame(columns=['UNIT_ID', 'COMPONENT_TYPE', 'HOURS_OIL', 'DATE_ANALIZED'])

    dfs = []

    cols_idx = [1, 3, 8, 14, 22, 21, 29, 44, 41, 42, 55]
    cols_names = [
        'UNIT_ID', 'COMPONENT_LOCATION', 'HOURS_OIL', 'DATE_ANALIZED',
        'Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'TBN (mgKOH/g)',
        'OXI - (abs/0.1mm)', 'NIT - (abs/cm)', 'V100C'
    ]

    for sheet, comp_type in [
        ('DRILLS_ENG', 'MOTOR DIESEL'),
        ('DRILLS_COMP', 'COMPRESOR'),
        ('DRILLS_GEAR', None)
    ]:
        if sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, header=None, usecols=cols_idx, names=cols_names)
            df['UNIT_ID'] = df['UNIT_ID'].astype(str).str.strip()
            df['COMPONENT_LOCATION'] = df['COMPONENT_LOCATION'].astype(str).str.strip()
            if comp_type is not None:
                df['COMPONENT_TYPE'] = comp_type
            else:
                df['COMPONENT_TYPE'] = df['COMPONENT_LOCATION']
            dfs.append(df)

    if not dfs:
        return pd.DataFrame(columns=cols_names + ['COMPONENT_TYPE'])

    df_all = pd.concat(dfs, ignore_index=True)
    num_cols = ['HOURS_OIL', 'Fe (ppm)', 'Cu (ppm)', 'Si (ppm)', 'TBN (mgKOH/g)', 'OXI - (abs/0.1mm)', 'NIT - (abs/cm)', 'V100C']
    df_all[num_cols] = df_all[num_cols].apply(pd.to_numeric, errors='coerce')
    df_all = df_all.dropna(subset=['HOURS_OIL'])
    return df_all

# --- Cargar datos de instalación ---
@st.cache_data
def load_installed_data():
    root = Path(__file__).parent
    inst_path = root / "COMPONENTS_DRILLS_INSTALLED.xls"
    
    if not inst_path.exists():
        st.warning("Archivo 'COMPONENTS_DRILLS_INSTALLED.xls' no encontrado en la raíz.")
        return pd.DataFrame(columns=['UNIT_ID', 'COMPONENT_LOCATION', 'FECHA_INSTALACION', 'HORAS_VIDA_ACTUAL', 'BUDGET'])

    try:
        df_inst = pd.read_excel(inst_path, sheet_name='INSTALLED')
        df_inst['UNIT_ID'] = df_inst['UNIT_ID'].astype(str).str.strip()
        df_inst['COMPONENT_LOCATION'] = df_inst['COMPONENT_LOCATION'].astype(str).str.strip()
        return df_inst
    except Exception as e:
        st.error(f"Error al abrir COMPONENTS_DRILLS_INSTALLED.xls: {e}")
        return pd.DataFrame(columns=['UNIT_ID', 'COMPONENT_LOCATION', 'FECHA_INSTALACION', 'HORAS_VIDA_ACTUAL', 'BUDGET'])

# --- Cargar datos ---
df_analysis = load_analysis_data()
df_installed = load_installed_data()

# --- Filtros ---
st.sidebar.header("🔍 Filtros")

if df_analysis.empty:
    st.stop()

unit_options = sorted(df_analysis['UNIT_ID'].unique())
unit_sel = st.sidebar.selectbox("Unidad", options=unit_options)

comp_options = sorted(df_analysis['COMPONENT_TYPE'].unique())
component_sel = st.sidebar.selectbox("Componente", options=comp_options)

df_comp = df_analysis[
    (df_analysis['UNIT_ID'] == unit_sel) & 
    (df_analysis['COMPONENT_TYPE'] == component_sel)
]

# --- Buscar datos de instalación para el componente actual ---
row_inst = None
if not df_installed.empty:
    row_inst = df_installed[
        (df_installed['UNIT_ID'] == unit_sel) & 
        (df_installed['COMPONENT_LOCATION'] == component_sel)
    ]
    if not row_inst.empty:
        row_inst = row_inst.iloc[0]
    else:
        row_inst = None

# --- Obtener último análisis ---
last_hour = "N/A"
last_date = "N/A"

if not df_comp.empty:
    df_valid = df_comp.dropna(subset=['DATE_ANALIZED'])
    if not df_valid.empty:
        df_latest = df_valid.loc[df_valid['DATE_ANALIZED'].idxmax()]
        last_hour = df_latest['HOURS_OIL']
        if pd.notna(df_latest['DATE_ANALIZED']):
            month_names = {
                1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
            }
            dt = df_latest['DATE_ANALIZED']
            last_date = f"{month_names[dt.month]}-{dt.day:02d}-{dt.year}"
        else:
            last_date = "N/A"
    else:
        last_hour, last_date = "N/A", "N/A"
else:
    last_hour, last_date = "N/A", "N/A"

# --- Barra de metadata ---
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(
        f"**Unidad:** `{unit_sel}` | **Componente:** `{component_sel}` | "
        f"**Horas aceite último cambio:** `{last_hour} h` | "
        f"**Fecha último cambio aceite:** `{last_date}`",
        unsafe_allow_html=True
    )

# --- Contexto operativo (CORREGIDO: usa COMPONENTS_DRILLS_INSTALLED.xls, formato fecha, color dinámico) ---
st.markdown("### 📋 Contexto operativo")
col1, col2, col3, col4 = st.columns(4)

# Helper seguro
def safe_float(x, default=np.nan):
    if pd.isna(x) or x is None:
        return default
    try:
        return float(x)
    except:
        return default

def safe_str(x, default="N/A"):
    if pd.isna(x) or x is None:
        return default
    return str(x)

# Extraer valores desde df_inst (no desde df_comp)
serial = safe_str(unit_sel)
component = safe_str(component_sel)

# Formatear fecha: AGOSTO-15-2021
inst_date = "N/A"
if row_inst is not None and 'FECHA_INSTALACION' in row_inst.index:
    val = row_inst['FECHA_INSTALACION']
    if pd.notna(val):
        try:
            if isinstance(val, str):
                val = pd.to_datetime(val)
            month_names = {
                1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
                5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
                9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
            }
            inst_date = f"{month_names[val.month]}-{val.day:02d}-{val.year}"
        except:
            inst_date = safe_str(val)

horas_act = safe_float(row_inst['HORAS_VIDA_ACTUAL'] if row_inst is not None else None, default=np.nan)
budget_val = safe_float(row_inst['BUDGET'] if row_inst is not None else None, default=np.nan)

with col1:
    st.metric("Serial", serial)
    st.metric("Componente", component)
with col2:
    st.metric("Instalación", inst_date)
    st.metric("Horas actuales", f"{horas_act:.1f} h" if not np.isnan(horas_act) else "N/A")
with col3:
    st.metric("Budget", f"{budget_val:.0f} h" if not np.isnan(budget_val) else "N/A")
    # --- Restante (determinista) con color dinámico ---
    if not np.isnan(horas_act) and not np.isnan(budget_val):
        restante_det = int(budget_val - horas_act)
        if restante_det > 0:
            color = "#10b981"
            label = "✓ Bajo riesgo"
        elif restante_det == 0:
            color = "#f59e0b"
            label = "⚠️ En límite"
        else:
            color = "#dc2626"
            label = "❗ Crítico"
        
        st.markdown(
            f"<div style='font-size:1.1rem; font-weight:bold; color:{color};'>Restante (determinista)</div>"
            f"<div style='font-size:1.4rem; font-weight:bold; color:{color};'>{restante_det:,} h</div>",
            unsafe_allow_html=True
        )
        st.caption(f"<span style='color:{color};'>{label}</span>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='font-size:1.1rem; font-weight:bold; color:#6c757d;'>Restante (determinista)</div>"
            "<div style='font-size:1.4rem; font-weight:bold; color:#6c757d;'>N/A</div>",
            unsafe_allow_html=True
        )
with col4:
    # Modelo (igual que antes — sin cambios)
    pred_value = "N/A"
    risk_label = "📁 Falta modelo"
    risk_color = "#6c757d"
    
    try:
        root = Path(__file__).parent
        model_path = root / "model_remaining_life.joblib"
        encoder_path = root / "label_encoder_component.joblib"
        
        if model_path.exists() and encoder_path.exists():
            model = joblib.load(model_path)
            le = joblib.load(encoder_path)
            
            # Para el modelo, usamos df_comp (datos de inspección actual)
            row = df_comp.iloc[0] if not df_comp.empty else None
            if row is not None:
                features = {
                    'Fe (ppm)': safe_float(row.get('Fe (ppm)', 0)),
                    'Cu (ppm)': safe_float(row.get('Cu (ppm)', 0)),
                    'Si (ppm)': safe_float(row.get('Si (ppm)', 0)),
                    'V100C': safe_float(row.get('V100C', 0)),
                    'TBN (mgKOH/g)': safe_float(row.get('TBN (mgKOH/g)', 0)),
                    'HOURS_OIL': safe_float(row.get('HOURS_OIL', 0)),  # ← horas desde último cambio
                    'BUDGET': safe_float(row.get('BUDGET', budget_val)),  # ← usa el budget de df_inst si está disponible
                }
                comp_encoded = le.transform([row['COMPONENT_TYPE']])[0] if row['COMPONENT_TYPE'] in le.classes_ else 0
                features['COMPONENT_ENCODED'] = comp_encoded
                
                X_pred = pd.DataFrame([features])
                pred = float(model.predict(X_pred)[0])
                pred_value = f"{int(pred):,} h"
                
                if pred < 0:
                    risk_label = "❗ Crítico"
                    risk_color = "#dc2626"
                elif pred < 500:
                    risk_label = "⚠️ Alto"
                    risk_color = "#f59e0b"
                elif pred < 1500:
                    risk_label = "🟡 Medio"
                    risk_color = "#f59e0b"
                else:
                    risk_label = "✓ Bajo"
                    risk_color = "#10b981"
            else:
                pred_value, risk_label = "N/A", "Sin datos de inspección"
        else:
            pred_value, risk_label = "N/A", "📁 Falta modelo"
            
    except Exception as e:
        pred_value, risk_label = "Error", f"💥 {type(e).__name__[:10]}"

    st.metric("Restante (modelo)", pred_value, delta_color="inverse")
    st.caption(f"Estado: {risk_label}")

# --- Alerta de umbrales superados ---
umbrales_violados = []
if not df_comp.empty:
    fe = safe_float(df_comp['Fe (ppm)'].iloc[0] if 'Fe (ppm)' in df_comp.columns else None)
    tbn = safe_float(df_comp['TBN (mgKOH/g)'].iloc[0] if 'TBN (mgKOH/g)' in df_comp.columns else None)
    v100c = safe_float(df_comp['V100C'].iloc[0] if 'V100C' in df_comp.columns else None)
    
    if not np.isnan(fe) and fe > 40:
        umbrales_violados.append("Fe > 40 ppm")
    if not np.isnan(tbn) and tbn < 5:
        umbrales_violados.append("TBN < 5 mgKOH/g")
    if not np.isnan(v100c):
        if v100c < 12 or v100c > 16:
            umbrales_violados.append("V100C fuera de rango (<12 o >16)")

if umbrales_violados:
    st.warning(f"⚠️ Umbrales críticos superados: {', '.join(umbrales_violados)}")

# --- Elementos ---
with st.sidebar.expander("🔬 Elementos", expanded=False):
    st.caption("Seleccione los elementos para analizar:")
    
    all_elements = [
        ("Fe (ppm)", "Fe (ppm)"),
        ("Cu (ppm)", "Cu (ppm)"),
        ("Si (ppm)", "Si (ppm)"),
        ("V100C", "V100C"),
        ("TBN (mgKOH/g)", "TBN (mgKOH/g)"),
        ("OXI - (abs/0.1mm)", "OXI - (abs/0.1mm)"),
        ("NIT - (abs/cm)", "NIT - (abs/cm)")
    ]
    
    element_labels = [label for _, label in all_elements]
    default_selection = ["Fe (ppm)", "V100C", "TBN (mgKOH/g)"]
    selected_elements = st.multiselect(
        "Elementos:",
        options=element_labels,
        default=default_selection,
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Todos"):
            selected_elements = element_labels
    with col2:
        if st.button("❌ Limpiar"):
            selected_elements = []
    
    st.session_state.selected_elements = selected_elements

cols = st.session_state.get('selected_elements', default_selection)

st.subheader(f"Análisis: {unit_sel} — {component_sel}")
st.caption("⚠️ Umbral crítico: Fe > 40 ppm")

# --- Gráficos ---
if cols:
    n = len(cols)
    fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 3.8))
    if n == 1:
        axes = [axes]
    
    for i, col in enumerate(cols):
        ax = axes[i]
        data = df_comp[col].dropna()
        if len(data) > 0:
            color = COLOR_MAP.get(col, '#5D8AA8')
            sns.histplot(data, ax=ax, color=color, alpha=0.85, kde=False)
            sns.kdeplot(data, ax=ax, color='#1A1A1A', linewidth=1.5, fill=False)
            ax.set_title(f"{col} — {unit_sel} | {component_sel}", fontsize=10, pad=10)
            ax.set_xlabel(col, fontsize=9)
            
            if col == 'Fe (ppm)':
                ax.axvline(40, color='crimson', ls='--', lw=1.2, label='40 ppm')
                ax.legend(fontsize=8)
            elif col == 'V100C':
                ax.axhline(12, color='crimson', ls='--', lw=1.2, label='<12')
                ax.axhline(16, color='crimson', ls='--', lw=1.2, label='>16')
                ax.legend(fontsize=8)
            elif col == 'TBN (mgKOH/g)':
                ax.axhline(5, color='crimson', ls='--', lw=1.2, label='<5')
                ax.legend(fontsize=8)
            
            ax.text(0.02, 0.02, f"n={len(df_comp)}", transform=ax.transAxes, fontsize=7, color='gray')
        else:
            ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', fontsize=9)
    
    plt.tight_layout(pad=1.4)
    fig.subplots_adjust(top=0.82)
    st.pyplot(fig)
    
    plot_bytes, fname = save_plot(fig, f"distrib_{unit_sel}_{component_sel}")
    st.download_button("💾 Save", plot_bytes, file_name=fname, mime="image/png")

# --- V100C vs Horas ---
if 'V100C' in cols and 'HOURS_OIL' in df_comp.columns:
    st.subheader("V100C vs Horas de Aceite")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    color = COLOR_MAP.get('V100C', '#5D8AA8')
    sns.scatterplot(data=df_comp, x='HOURS_OIL', y='V100C', ax=ax, color=color, s=35, alpha=0.8)
    ax.axhline(12, color='crimson', ls='--', lw=1.2, label='<12')
    ax.axhline(16, color='crimson', ls='--', lw=1.2, label='>16')
    ax.set_title(f"V100C vs Horas — {unit_sel} | {component_sel}", fontsize=10, pad=10)
    ax.set_xlabel('Horas de Aceite', fontsize=9)
    ax.set_ylabel('V100C', fontsize=9)
    ax.legend(fontsize=8)
    ax.text(0.02, 0.02, f"n={len(df_comp)}", transform=ax.transAxes, fontsize=7, color='gray')
    plt.tight_layout(pad=1.4)
    st.pyplot(fig)
    
    plot_bytes, fname = save_plot(fig, f"v100c_{unit_sel}_{component_sel}")
    st.download_button("💾 Save", plot_bytes, file_name=fname, mime="image/png")

# --- TBN vs Horas (solo MOTOR DIESEL) ---
if 'TBN (mgKOH/g)' in cols and component_sel == 'MOTOR DIESEL':
    st.subheader("TBN vs Horas de Aceite")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    color = COLOR_MAP.get('TBN (mgKOH/g)', '#5D8AA8')
    sns.scatterplot(data=df_comp, x='HOURS_OIL', y='TBN (mgKOH/g)', ax=ax, color=color, s=35, alpha=0.8)
    ax.axhline(5, color='crimson', ls='--', lw=1.2, label='<5')
    ax.set_title(f"TBN vs Horas — {unit_sel} | {component_sel}", fontsize=10, pad=10)
    ax.set_xlabel('Horas de Aceite', fontsize=9)
    ax.set_ylabel('TBN (mgKOH/g)', fontsize=9)
    ax.legend(fontsize=8)
    ax.text(0.02, 0.02, f"n={len(df_comp)}", transform=ax.transAxes, fontsize=7, color='gray')
    plt.tight_layout(pad=1.4)
    st.pyplot(fig)
    
    plot_bytes, fname = save_plot(fig, f"tbn_{unit_sel}_{component_sel}")
    st.download_button("💾 Save", plot_bytes, file_name=fname, mime="image/png")

# --- Datos operativos (viejo, pero opcionalmente redundante) ---
with st.expander("📋 Datos Operativos (desde instalación)", expanded=False):
    if row_inst is not None:
        st.write(f"**Horas actuales (total):** {row_inst['HORAS_VIDA_ACTUAL']:.0f} h")
        st.write(f"**Budget (máx.):** {row_inst['BUDGET']:.0f} h")
        st.write(f"**Restante (determinista):** {row_inst['BUDGET'] - row_inst['HORAS_VIDA_ACTUAL']:.0f} h")
    else:
        st.write("No hay datos de instalación.")

# --- Umbrales ---
with st.expander("🔍 Umbrales técnicos", expanded=False):
    st.caption("""
    • Fe > 40 ppm → desgaste severo  
    • Cu > 20 ppm → cojinetes/bombas  
    • Si > 20 ppm → contaminación  
    • V100C < 12 o > 16 → viscosidad fuera de rango  
    • TBN < 5 mgKOH/g → cambio inminente (MOTOR DIESEL)
    """)

st.markdown("---")
st.caption("💡 Reporte generado automáticamente desde análisis de aceite (SOS). Umbral Fe > 40 ppm aplicable a equipos críticos. Validar con inspección física.")
