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
from pandas.tseries.offsets import DateOffset

st.set_page_config(layout="wide", page_title="Análisis de Desgaste — Equipo Crítico", page_icon="⚙️")
st.title("📊 Análisis de Desgaste — Equipo Crítico")
st.caption(f"Versión 2.8 | Autor: Leonidas | {datetime.now().strftime('%Y-%m-%d')}")

# --- Estilo personalizado para pestañas (fuente grande) ---
st.markdown(
    """
    <style>
    .stTabs [role="tab"] {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.2rem !important;
        min-height: 44px !important;
    }
    .stMetric {
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

# --- Helper seguro ---
def safe_float(x, default=np.nan):
    if pd.isna(x) or x is None:
        return default
    try:
        return float(x)
    except:
        return default

def format_fecha(val):
    if pd.isna(val):
        return "N/A"
    try:
        if isinstance(val, str):
            val = pd.to_datetime(val)
        month_names = {
            1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
            5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
            9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
        }
        return f"{month_names[val.month]}-{val.day:02d}-{val.year}"
    except:
        return str(val)

# --- Pestañas principales ---
tab1, tab2 = st.tabs(["📊 Modelo Predictivo", "📈 Serie Temporal"])

# --- Contenido de la pestaña 1: Modelo Predictivo ---
with tab1:
    # --- Barra de metadata ---
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(
            f"**Unidad:** `{unit_sel}` | **Componente:** `{component_sel}` | "
            f"**Horas aceite último cambio:** `{last_hour} h` | "
            f"**Fecha último cambio aceite:** `{last_date}`",
            unsafe_allow_html=True
        )

    # --- Pre-calcular predicción ---
    pred_value = "N/A"
    risk_label = "📁 Falta modelo"
    risk_color = "#6c757d"

    try:
        root = Path(__file__).parent
        model_path = root / "model_remaining_life_v4.joblib"
        encoder_path = root / "label_encoder_component_v4.joblib"
        
        if model_path.exists() and encoder_path.exists():
            model = joblib.load(model_path)
            le = joblib.load(encoder_path)
            
            if not df_comp.empty:
                row = df_comp.iloc[0]
                features = {
                    'Fe (ppm)': safe_float(row.get('Fe (ppm)', 0)),
                    'Cu (ppm)': safe_float(row.get('Cu (ppm)', 0)),
                    'Si (ppm)': safe_float(row.get('Si (ppm)', 0)),
                    'V100C': safe_float(row.get('V100C', 0)),
                    'TBN (mgKOH/g)': safe_float(row.get('TBN (mgKOH/g)', 0)),
                    'HOURS_OIL': safe_float(row.get('HOURS_OIL', 0)),
                    'BUDGET': safe_float(row.get('BUDGET', 
                        row_inst['BUDGET'] if row_inst is not None else 15000)),
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
    except Exception:
        pred_value, risk_label = "Error", "💥 Falló carga"
        risk_color = "#6c757d"

    # --- Cuadro destacado de predicción ---
    st.markdown(
        f"""
        <div style="
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-top: 16px;
            margin-bottom: 16px;
        ">
            <p style="color: #e6edf3; font-size: 0.8rem; margin: 4px 0;">Predicción basada en modelo de Random Forest</p>
            <p style="color: #c9d1d9; font-size: 0.75rem; margin: 2px 0;">entrenado con historial de fallas</p>
            <h3 style="color: #c9d1d9; font-size: 1.1rem; margin: 8px 0 4px 0;">Vida restante estimada</h3>
            <p style="font-size: 2.0rem; font-weight: bold; color: {risk_color}; margin: 4px 0;">{pred_value}</p>
            <div style="display: inline-block; background-color: #161b22; padding: 3px 10px; border-radius: 5px; font-size: 0.85rem;">
                <span style="color: {risk_color};">{risk_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- Contexto operativo (4 columnas, gap="small") ---
    st.markdown("### 📋 Contexto operativo", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1], gap="small")

    serial = str(unit_sel) if unit_sel else "N/A"
    component = str(component_sel) if component_sel else "N/A"
    inst_date = format_fecha(row_inst['FECHA_INSTALACION'] if row_inst is not None else None)
    horas_act = safe_float(row_inst['HORAS_VIDA_ACTUAL'] if row_inst is not None else None, default=np.nan)
    budget_val = safe_float(row_inst['BUDGET'] if row_inst is not None else None, default=np.nan)

    # Restante (determinista) con color dinámico
    restante_det_text = "N/A"
    restante_color = "#6c757d"
    restante_label = ""
    if not np.isnan(horas_act) and not np.isnan(budget_val):
        restante_det = int(budget_val - horas_act)
        if restante_det > 0:
            restante_color = "#10b981"
            restante_label = "✓ Bajo riesgo"
        elif restante_det == 0:
            restante_color = "#f59e0b"
            restante_label = "⚠️ En límite"
        else:
            restante_color = "#dc2626"
            restante_label = "❗ Crítico"
        restante_det_text = f"{restante_det:,} h"

    with col1:
        st.metric("Serial", serial, delta=None, delta_color="off")
        st.metric("Componente", component, delta=None, delta_color="off")
    with col2:
        st.metric("Instalación", inst_date, delta=None, delta_color="off")
        st.metric("Horas actuales", f"{horas_act:.1f} h" if not np.isnan(horas_act) else "N/A", delta=None, delta_color="off")
    with col3:
        st.metric("Budget", f"{budget_val:.0f} h" if not np.isnan(budget_val) else "N/A", delta=None, delta_color="off")
        # Restante (determinista)
        if not np.isnan(horas_act) and not np.isnan(budget_val):
            st.markdown(
                f"<div style='font-size:1.1rem; font-weight:bold; color:{restante_color};'>Restante (determinista)</div>"
                f"<div style='font-size:1.4rem; font-weight:bold; color:{restante_color};'>{restante_det_text}</div>"
                f"<div style='font-size:0.8rem; color:{restante_color};'>{restante_label}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div style='font-size:1.1rem; font-weight:bold; color:#6c757d;'>Restante (determinista)</div>"
                "<div style='font-size:1.4rem; font-weight:bold; color:#6c757d;'>N/A</div>",
                unsafe_allow_html=True
            )
    with col4:
        st.write("")
        st.write("")

    # --- Alerta de umbrales críticos (contextual) ---
    umbrales_violados = []

    if not df_comp.empty:
        fe = safe_float(df_comp['Fe (ppm)'].iloc[0] if 'Fe (ppm)' in df_comp.columns else None)
        cu = safe_float(df_comp['Cu (ppm)'].iloc[0] if 'Cu (ppm)' in df_comp.columns else None)
        si = safe_float(df_comp['Si (ppm)'].iloc[0] if 'Si (ppm)' in df_comp.columns else None)
        v100c = safe_float(df_comp['V100C'].iloc[0] if 'V100C' in df_comp.columns else None)  # ✅ minúscula
        tbn = safe_float(df_comp['TBN (mgKOH/g)'].iloc[0] if 'TBN (mgKOH/g)' in df_comp.columns else None)

        if component_sel == "MOTOR DIESEL":
            if not np.isnan(fe) and fe > 40:
                umbrales_violados.append("Fe > 40 ppm")
            if not np.isnan(tbn) and tbn < 5:
                umbrales_violados.append("TBN < 5 mgKOH/g")
            if not np.isnan(v100c) and (v100c < 12 or v100c > 16):
                umbrales_violados.append("V100C fuera de rango (<12 o >16)")
            if not np.isnan(cu) and cu > 20:
                umbrales_violados.append("Cu > 20 ppm")
            if not np.isnan(si) and si > 20:
                umbrales_violados.append("Si > 20 ppm")

        elif component_sel == "COMPRESOR":
            if not np.isnan(fe) and fe > 40:
                umbrales_violados.append("Fe > 40 ppm")
            if not np.isnan(v100c) and (v100c < 12 or v100c > 16):
                umbrales_violados.append("V100C fuera de rango (<12 o >16)")
            if not np.isnan(cu) and cu > 20:
                umbrales_violados.append("Cu > 20 ppm")
            if not np.isnan(si) and si > 20:
                umbrales_violados.append("Si > 20 ppm")
            # ⚠️ TBN NO se evalúa para COMPRESOR

        elif component_sel == "ENGRANAJE":
            if not np.isnan(cu) and cu > 15:
                umbrales_violados.append("Cu > 15 ppm")
            if not np.isnan(si) and si > 25:
                umbrales_violados.append("Si > 25 ppm")
            if not np.isnan(v100c) and (v100c < 13 or v100c > 15.5):
                umbrales_violados.append("V100C fuera de rango")

    if umbrales_violados:
        st.warning(f"⚠️ Umbrales críticos superados: {', '.join(umbrales_violados)}")

    # --- Elementos ---
    with st.expander("🔬 Elementos", expanded=False):
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

# --- Contenido de la pestaña 2: Serie Temporal ---
with tab2:
    st.subheader("Evolución temporal de elementos críticos")
    st.caption("Últimos 6 meses — datos por inspección")

    if df_analysis.empty:
        st.warning("No hay datos para mostrar.")
        st.stop()

    # Filtrar por unidad y componente
    df_temp = df_analysis[
        (df_analysis['UNIT_ID'] == unit_sel) & 
        (df_analysis['COMPONENT_TYPE'] == component_sel)
    ].copy()

    if df_temp.empty:
        st.info("No hay datos históricos para esta unidad y componente.")
        st.stop()

    # Asegurar DATE_ANALIZED como datetime
    df_temp['DATE_ANALIZED'] = pd.to_datetime(df_temp['DATE_ANALIZED'], errors='coerce')
    df_temp = df_temp.dropna(subset=['DATE_ANALIZED'])

    # Filtro de rango de fechas
    today = pd.Timestamp.today()
    six_months_ago = today - DateOffset(months=6)
    date_range = st.date_input(
        "Rango de fechas",
        value=(six_months_ago.date(), today.date()),
        min_value=df_temp['DATE_ANALIZED'].min().date(),
        max_value=today.date()
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df_temp['DATE_ANALIZED'].dt.date >= start_date) & (df_temp['DATE_ANALIZED'].dt.date <= end_date)
        df_filtered = df_temp[mask].sort_values('DATE_ANALIZED')
    else:
        df_filtered = df_temp.sort_values('DATE_ANALIZED')

    if df_filtered.empty:
        st.warning("No hay datos en el rango seleccionado.")
        st.stop()

    # --- Sección 1: Evolución de Desgaste y Contaminación ---
    st.subheader("🔹 Evolución de Desgaste y Contaminación")
    st.caption("Fe, Cu, Si, V100C — indicadores de desgaste mecánico y contaminación")

    desgaste_cols = ["Fe (ppm)", "Cu (ppm)", "Si (ppm)", "V100C"]
    cols_desgaste = [col for col in desgaste_cols if col in df_filtered.columns]

    if cols_desgaste:
        fig1, ax1 = plt.subplots(figsize=(10, 5))
        for col in cols_desgaste:
            data = pd.to_numeric(df_filtered[col], errors='coerce')
            valid_mask = data.notna()
            ax1.plot(
                df_filtered.loc[valid_mask, 'DATE_ANALIZED'],
                data[valid_mask],
                marker='o',
                label=col,
                linewidth=2
            )

            # Umbrales específicos (sin TBN aquí — ya está en salud)
            if col == "Fe (ppm)":
                ax1.axhline(40, color='crimson', ls='--', lw=1.2, label='Umbral crítico: 40 ppm')
            elif col == "Cu (ppm)":
                ax1.axhline(20, color='darkorange', ls='--', lw=1.2, label='>20 ppm')
            elif col == "Si (ppm)":
                ax1.axhline(20, color='purple', ls='--', lw=1.2, label='>20 ppm')
            elif col == "V100C":
                ax1.axhline(12, color='steelblue', ls='--', lw=1.2, label='<12')
                ax1.axhline(16, color='steelblue', ls='--', lw=1.2, label='>16')

        ax1.set_xlabel("Fecha de análisis", fontsize=10)
        ax1.set_ylabel("Valor", fontsize=10)
        ax1.set_title(f"Desgaste & Contaminación — {unit_sel} | {component_sel}", fontsize=12)
        ax1.grid(True, linestyle=':', alpha=0.7)
        ax1.legend(fontsize=9)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig1)

        plot_bytes, fname = save_plot(fig1, f"desgaste_{unit_sel}_{component_sel}")
        st.download_button("💾 Guardar gráfico", plot_bytes, file_name=fname, mime="image/png")

    # --- Sección 2: Salud del Aceite (TBN solo para MOTOR DIESEL) ---
    st.subheader("🔹 Salud del Aceite")
    st.caption("TBN, OXI, NIT — indicadores de degradación química del aceite")

    salud_cols = ["TBN (mgKOH/g)", "OXI - (abs/0.1mm)", "NIT - (abs/cm)"]
    cols_salud = [col for col in salud_cols if col in df_filtered.columns]

    if cols_salud:
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        for col in cols_salud:
            data = pd.to_numeric(df_filtered[col], errors='coerce')
            valid_mask = data.notna()
            ax2.plot(
                df_filtered.loc[valid_mask, 'DATE_ANALIZED'],
                data[valid_mask],
                marker='s',
                label=col,
                linewidth=2
            )

            # ✅ TBN solo si es MOTOR DIESEL
            if col == "TBN (mgKOH/g)" and component_sel == "MOTOR DIESEL":
                ax2.axhline(5, color='crimson', ls='--', lw=1.2, label='Umbral: <5 mgKOH/g')
            elif col == "OXI - (abs/0.1mm)":
                ax2.axhline(0.1, color='green', ls='--', lw=1.2, label='>0.1 (oxidación)')
            elif col == "NIT - (abs/cm)":
                ax2.axhline(0.05, color='teal', ls='--', lw=1.2, label='>0.05 (nitración)')

        ax2.set_xlabel("Fecha de análisis", fontsize=10)
        ax2.set_ylabel("Valor", fontsize=10)
        ax2.set_title(f"Salud del Aceite — {unit_sel} | {component_sel}", fontsize=12)
        ax2.grid(True, linestyle=':', alpha=0.7)
        ax2.legend(fontsize=9)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig2)

        plot_bytes, fname = save_plot(fig2, f"salud_aceite_{unit_sel}_{component_sel}")
        st.download_button("💾 Guardar gráfico", plot_bytes, file_name=fname, mime="image/png")

    # --- Si no hay datos ---
    if not cols_desgaste and not cols_salud:
        st.info("No hay elementos de desgaste ni salud del aceite para graficar en este componente.")

st.caption("💡 Reporte generado automáticamente desde análisis de aceite (SOS). Umbral Fe > 40 ppm aplicable a equipos críticos. Validar con inspección física.")

# 🔍 Diagnóstico rápido — ejecuta esto en tu terminal/local
print("=== Sample_Reports_Mod_Test.xls ===")
print(df_analysis.columns.tolist())

print("\n=== COMPONENTS_DRILLS_INSTALLED.xls ===")
print(df_installed.columns.tolist())

print("\n=== Primer registro de df_comp ===")
if not df_comp.empty:
    print(df_comp.iloc[0])
