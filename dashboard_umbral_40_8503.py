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
import os

st.set_page_config(layout="wide", page_title="Análisis de Desgaste — Equipo Crítico", page_icon="⚙️")
st.title("📊 Análisis de Desgaste — Equipo Crítico")
st.caption(f"Versión 2.3 | Autor: Leonidas | {datetime.now().strftime('%Y-%m-%d')}")

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

# --- Cargar datos con rutas seguras ---
@st.cache_data
def load_all_data():
    base_dir = Path(__file__).parent
    xls_path = base_dir / "Sample_Reports_Mod_Test.xls"
    
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

# --- Cargar datos ---
df_all = load_all_data()

# --- Filtros ---
st.sidebar.header("🔍 Filtros")

if df_all.empty:
    st.stop()

unit_options = sorted(df_all['UNIT_ID'].unique())
unit_sel = st.sidebar.selectbox("Unidad", options=unit_options)

comp_options = sorted(df_all['COMPONENT_TYPE'].unique())
component_sel = st.sidebar.selectbox("Componente", options=comp_options)

df_comp = df_all[
    (df_all['UNIT_ID'] == unit_sel) & 
    (df_all['COMPONENT_TYPE'] == component_sel)
]

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

# --- Barra de metadata + predicción ---
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(
        f"**Unidad:** `{unit_sel}` | **Componente:** `{component_sel}` | "
        f"**Horas aceite último cambio:** `{last_hour} h` | "
        f"**Fecha último cambio aceite:** `{last_date}`",
        unsafe_allow_html=True
    )

with col2:
    # Cargar modelo con ruta robusta
    pred_value = "N/A"
    risk_label = "📁 Falta modelo"
    risk_color = "#6c757d"
    
    try:
        root = Path(__file__).parent
        model_path = root / "model_remaining_life.joblib"
        encoder_path = root / "label_encoder_component.joblib"
        
        if model_path.exists() and encoder_path.exists():
            try:
                model = joblib.load(model_path)
                le = joblib.load(encoder_path)
                
                row = df_comp.iloc[0]
                
                def safe_float(x):
                    return float(x) if pd.notna(x) and str(x).replace('.', '').replace('-', '').isdigit() else 0.0
                
                features = {
                    'Fe (ppm)': safe_float(row.get('Fe (ppm)', 0)),
                    'Cu (ppm)': safe_float(row.get('Cu (ppm)', 0)),
                    'Si (ppm)': safe_float(row.get('Si (ppm)', 0)),
                    'V100C': safe_float(row.get('V100C', 0)),
                    'TBN (mgKOH/g)': safe_float(row.get('TBN (mgKOH/g)', 0)),
                    'HOURS_OIL': safe_float(row.get('HOURS_OIL', 0)),
                    'BUDGET': safe_float(row.get('BUDGET', 8000)),
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
            except Exception as e:
                pred_value = "Error"
                risk_label = f"💥 {type(e).__name__[:10]}"
                risk_color = "#6c757d"
        else:
            # st.warning(f"Modelos no encontrados en: {root}")
            pred_value, risk_label, risk_color = "N/A", "📁 Falta modelo", "#6c757d"
            
    except Exception as e:
        pred_value, risk_label, risk_color = "Error", f"⚠️ {type(e).__name__}", "#6c757d"

    st.markdown(
        f"""
        <div style="
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            <p style="color: #e6edf3; font-size: 0.8rem; margin: 4px 0;">Predicción basada en modelo de Random Forest</p>
            <p style="color: #c9d1d9; font-size: 0.75rem; margin: 2px 0;">entrenado con historial de fallas</p>
            <h3 style="color: #c9d1d9; font-size: 1.1rem; margin: 8px 0 4px 0;">Vida restante estimada</h3>
            <p style="font-size: 1.8rem; font-weight: bold; color: {risk_color}; margin: 4px 0;">{pred_value}</p>
            <div style="display: inline-block; background-color: #161b22; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">
                <span style="color: {risk_color};">{risk_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

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

# --- Datos operativos ---
with st.expander("📋 Datos Operativos", expanded=False):
    if not df_comp.empty:
        latest = df_comp.sort_values('HOURS_OIL', ascending=False).iloc[0]
        st.write(f"**Horas aceite (ciclo):** {latest['HOURS_OIL']:.0f} h")
        try:
            inst_path = Path(__file__).parent / "COMPONENTS_DRILLS_INSTALLED.xls"
            if inst_path.exists():
                df_inst = pd.read_excel(inst_path, sheet_name='INSTALLED')
                df_inst['UNIT_ID'] = df_inst['UNIT_ID'].astype(str).str.strip()
                df_inst['COMPONENT_LOCATION'] = df_inst['COMPONENT_LOCATION'].astype(str).str.strip()
                row = df_inst[
                    (df_inst['UNIT_ID'] == unit_sel) & 
                    (df_inst['COMPONENT_LOCATION'] == component_sel)
                ]
                if not row.empty:
                    r = row.iloc[0]
                    st.write(f"- Budget: {r['BUDGET']:.0f} h")
                    st.write(f"- Restante: {r['REMAINING_LIFE']:.0f} h")
        except Exception as e:
            st.write(f"- Error cargando COMPONENTS_DRILLS_INSTALLED.xls: {type(e).__name__}")
    else:
        st.write("No hay datos")

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
