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
    .author-text { text-align: center; color: #666666; font-size: 0.9em; margin-top: -10px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- SECCIÓN DE LOGO Y TÍTULO ---
if os.path.exists('logo.png'):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image('logo.png', use_container_width=True)
else:
    st.title("🏥 Asistente Inteligente de Derivación")

st.markdown("<h3 style='text-align: center; margin-bottom: 0;'>Red de Derivación SSVSA</h3>", unsafe_allow_html=True)
st.markdown("<p class='author-text'>Autoría: Sebastián Pino Rivera</p>", unsafe_allow_html=True)
st.markdown("---")

# 2. Conexión con la IA
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("⚠️ Error: Configura la 'GROQ_API_KEY' en los Secrets de Streamlit.")

# 3. Función para cargar y normalizar el CSV
@st.cache_data
def cargar_datos():
    archivo = 'derivaciones.csv'
    if not os.path.exists(archivo):
        return None
    
    encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    df = None
    
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(archivo, sep=None, engine='python', encoding=encoding)
            break
        except:
            continue
            
    if df is None:
        st.error("❌ No se pudo leer el archivo CSV.")
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
        st.error(f"❌ Error al procesar columnas: {e}")
        return None

df_mapa = cargar_datos()

if df_mapa is not None:
    # Botón de limpieza
    if st.button("🔄 Nueva Consulta / Limpiar"):
        st.rerun()

    # Filtro por tipo de especialidad
    if 'TIPO_ESPECIALIDAD' in df_mapa.columns:
        tipos_disponibles = sorted(df_mapa['TIPO_ESPECIALIDAD'].unique().tolist())
        tipo_seleccionado = st.selectbox("1. Selecciona el Tipo de Especialidad (Opcional):", ["TODOS"] + tipos_disponibles)
    else:
        tipo_seleccionado = "TODOS"

    # Entrada del Operador
    user_input = st.text_input("2. Consulta (Comuna + Especialidad o Código CIE-10):", key="input_query", placeholder="Ej: Destino para N40 en San Antonio")

    if user_input:
        df_filtrado = df_mapa.copy()
        if tipo_seleccionado != "TODOS":
            df_filtrado = df_mapa[df_mapa['TIPO_ESPECIALIDAD'] == tipo_seleccionado]

        with st.spinner("Analizando mapa de red..."):
            try:
                # 5. IA Extrae Filtros (COMUNA, ESPECIALIDAD Y CIE-10)
                comunas_validas = df_filtrado['COMUNA_ORIGEN'].unique().tolist()
                especialidades_validas = df_filtrado['ESPECIALIDAD_DESTINO'].unique().tolist()

                prompt_sistema = f"""
                Eres un experto en derivaciones del SSVSA. 
                Tu objetivo es extraer: COMUNA_ORIGEN, ESPECIALIDAD_DESTINO y un CODIGO_CIE10 (si se menciona).
                
                Opciones Comuna: {comunas_validas}
                Opciones Especialidad: {especialidades_validas}
                
                Responde ÚNICAMENTE en JSON: 
                {{"comuna": "VALOR", "especialidad": "VALOR", "cie10": "VALOR"}}
                """
                
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": user_input}],
                    response_format={"type": "json_object"}
                )
                
                filtros = json.loads(completion.choices[0].message.content)
                comuna = filtros.get("comuna")
                especialidad = filtros.get("especialidad")
                cie10_user = filtros.get("cie10")

                # 6. Lógica de Búsqueda Híbrida
                if comuna != "NULL":
                    # Filtro base por comuna
                    mask_comuna = (df_filtrado['COMUNA_ORIGEN'] == comuna)
                    
                    # Prioridad 1: Búsqueda por CIE-10 si existe
                    if cie10_user != "NULL":
                        # Limpiamos el código detectado para búsqueda parcial
                        cie10_clean = cie10_user.replace(".", "").strip()
                        resultado = df_filtrado[mask_comuna & (df_filtrado['CIE-10'].str.contains(cie10_clean, na=False))]
                    
                    # Prioridad 2: Búsqueda por Especialidad
                    elif especialidad != "NULL":
                        resultado = df_filtrado[mask_comuna & (df_filtrado['ESPECIALIDAD_DESTINO'] == especialidad)]
                    
                    else:
                        resultado = pd.DataFrame()

                    if not resultado.empty:
                        # Agrupación para visualización limpia
                        cols_agrupar = ['ESTABLECIMIENTO_DESTINO', 'RANGO_EDAD']
                        if 'TIPO_ESPECIALIDAD' in df_mapa.columns: cols_agrupar.append('TIPO_ESPECIALIDAD')

                        agrupado = resultado.groupby(cols_agrupar).agg({
                            'CIE-10': lambda x: ', '.join(sorted(set(x))),
                            'OBSERVACION': lambda x: ' | '.join(sorted(set(x)))
                        }).reset_index()

                        st.success(f"📍 Resultados encontrados en {comuna}:")
                        
                        for i, row in agrupado.iterrows():
                            with st.expander(f"🏥 {row['ESTABLECIMIENTO_DESTINO']}", expanded=True):
                                c1, c2 = st.columns(2)
                                with c1: st.write(f"**Edad:** {row['RANGO_EDAD']}")
                                with c2: 
                                    if 'TIPO_ESPECIALIDAD' in row: st.write(f"**Tipo:** {row['TIPO_ESPECIALIDAD']}")
                                st.markdown(f"**CIE-10 Cubiertos:** `{row['CIE-10']}`")
                                st.info(f"**Observación:** {row['OBSERVACION']}")
                    else:
                        st.warning(f"No se encontró información para los criterios ingresados en {comuna}.")
                else:
                    st.info("Por favor, indica al menos la comuna de origen del paciente.")
            except Exception as e:
                st.error(f"Error en la consulta: {e}")
else:
    st.warning("⚠️ Sube el archivo 'derivaciones.csv' a tu repositorio.")
