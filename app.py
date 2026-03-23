import streamlit as st
import pandas as pd
from groq import Groq
import json
import os

# 1. Configuración de la Interfaz
st.set_page_config(page_title="Asistente de Derivación SSVSA", page_icon="🏥", layout="centered")

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #f0f2f6; }
    .stExpander { border: 1px solid #e6e9ef; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_content_html=True)

# --- SECCIÓN DE LOGO Y TÍTULO ---
if os.path.exists('logo.png'):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image('logo.png', use_container_width=True)
else:
    st.title("🏥 Asistente Inteligente de Derivación")

st.markdown("<h3 style='text-align: center;'>Red de Derivación SSVSA</h3>", unsafe_content_html=True)
st.markdown("---")

# 2. Conexión con la IA
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("⚠️ Error: Configura la 'GROQ_API_KEY' en los Secrets de Streamlit.")

# 3. Función para cargar y normalizar el CSV (MEJORADA CON AUTO-DECODIFICACIÓN)
@st.cache_data
def cargar_datos():
    archivo = 'derivaciones.csv'
    if not os.path.exists(archivo):
        return None
    
    # Intentamos diferentes codificaciones para evitar el error de 'utf-8'
    encodigs_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    df = None
    
    for encoding in encodigs_to_try:
        try:
            df = pd.read_csv(archivo, sep=None, engine='python', encoding=encoding)
            break # Si funciona, salimos del bucle
        except (UnicodeDecodeError, Exception):
            continue
            
    if df is None:
        st.error("❌ No se pudo leer el archivo CSV. Revisa el formato y la codificación.")
        return None

    try:
        # Normalización de nombres de columnas
        df.columns = (df.columns.str.strip().str.upper()
                      .str.replace('Ó', 'O').str.replace('Á', 'A')
                      .str.replace('É', 'E').str.replace('Í', 'I')
                      .str.replace('Ú', 'U').str.replace(' ', '_'))
        
        # Limpieza de datos en las celdas
        df = df.apply(lambda x: x.astype(str).str.upper().str.strip())
        return df
    except Exception as e:
        st.error(f"❌ Error al procesar las columnas: {e}")
        return None

df_mapa = cargar_datos()

if df_mapa is not None:
    # --- BOTÓN NUEVA CONSULTA (Limpia el estado) ---
    if st.button("🔄 Nueva Consulta / Limpiar"):
        st.rerun()

    # --- FILTRO POR TIPO ---
    if 'TIPO_ESPECIALIDAD' in df_mapa.columns:
        tipos_disponibles = sorted(df_mapa['TIPO_ESPECIALIDAD'].unique().tolist())
        tipo_seleccionado = st.selectbox("1. Selecciona el Tipo de Especialidad:", ["TODOS"] + tipos_disponibles)
    else:
        tipo_seleccionado = "TODOS"

    # 4. Entrada del Operador
    user_input = st.text_input("2. Describe la consulta (ej: Paciente de Casablanca para Endodoncia):", key="input_query")

    if user_input:
        df_filtrado = df_mapa.copy()
        if tipo_seleccionado != "TODOS":
            df_filtrado = df_mapa[df_mapa['TIPO_ESPECIALIDAD'] == tipo_seleccionado]

        with st.spinner("Analizando mapa de red..."):
            try:
                # 5. IA Extrae Filtros
                comunas_validas = df_filtrado['COMUNA_ORIGEN'].unique().tolist()
                especialidades_validas = df_filtrado['ESPECIALIDAD_DESTINO'].unique().tolist()

                prompt_sistema = f"""
                Eres un experto en derivaciones del SSVSA. Extrae: COMUNA_ORIGEN y ESPECIALIDAD_DESTINO.
                Opciones Comuna: {comunas_validas}
                Opciones Especialidad: {especialidades_validas}
                Responde ÚNICAMENTE en JSON: {{"comuna": "VALOR", "especialidad": "VALOR"}}
                """
                
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": user_input}],
                    response_format={"type": "json_object"}
                )
                
                filtros = json.loads(completion.choices[0].message.content)
                comuna = filtros.get("comuna")
                especialidad = filtros.get("especialidad")

                # 6. Lógica de Búsqueda y Agrupación
                if comuna != "NULL" and especialidad != "NULL":
                    resultado = df_filtrado[
                        (df_filtrado['COMUNA_ORIGEN'] == comuna) & 
                        (df_filtrado['ESPECIALIDAD_DESTINO'] == especialidad)
                    ]

                    if not resultado.empty:
                        cols_agrupar = ['ESTABLECIMIENTO_DESTINO', 'RANGO_EDAD']
                        if 'TIPO_ESPECIALIDAD' in df_mapa.columns: cols_agrupar.append('TIPO_ESPECIALIDAD')

                        agrupado = resultado.groupby(cols_agrupar).agg({
                            'CIE-10': lambda x: ', '.join(sorted(set(x))),
                            'OBSERVACION': lambda x: ' | '.join(sorted(set(x)))
                        }).reset_index()

                        st.success(f"📍 Resultados para {especialidad} en {comuna}:")
                        
                        for i, row in agrupado.iterrows():
                            with st.expander(f"🏥 {row['ESTABLECIMIENTO_DESTINO']}", expanded=True):
                                c1, c2 = st.columns(2)
                                with c1: st.write(f"**Edad:** {row['RANGO_EDAD']}")
                                with c2: 
                                    if 'TIPO_ESPECIALIDAD' in row: st.write(f"**Tipo:** {row['TIPO_ESPECIALIDAD']}")
                                st.markdown(f"**CIE-10:** `{row['CIE-10']}`")
                                st.info(f"**Observación:** {row['OBSERVACION']}")
                    else:
                        st.warning(f"No hay ruta para {especialidad} en {comuna} categoría {tipo_seleccionado}.")
                else:
                    st.info("No identifiqué la comuna o especialidad. Intenta ser más específico.")
            except Exception as e:
                st.error(f"Error: {e}")
else:
    st.warning("⚠️ Sube el archivo 'derivaciones.csv' a tu repositorio.")
