import streamlit as st
import pandas as pd
from groq import Groq
import json
import os

# 1. Configuración de la Interfaz
st.set_page_config(page_title="Asistente de Derivación Salud", page_icon="🏥", layout="centered")

st.title("🏥 Asistente Inteligente de Derivación")
st.markdown("""
Esta herramienta ayuda a identificar el **Establecimiento Destino** según el Mapa de Derivación oficial. 
La decisión clínica final es siempre del profesional tratante.
""")

# 2. Conexión con la IA
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("⚠️ Error de configuración: No se encontró la API Key en Streamlit Secrets.")

# 3. Función para cargar y normalizar el CSV
@st.cache_data
def cargar_datos():
    archivo = 'derivaciones.csv'
    
    # Verificación de existencia de archivo
    if not os.path.exists(archivo):
        archivos_en_carpeta = os.listdir('.')
        st.error(f"❌ No se encontró '{archivo}'. En el repositorio veo: {archivos_en_carpeta}")
        return None

    try:
        # Cargamos detectando automáticamente el separador (coma o punto y coma)
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8')
        
        # --- NORMALIZACIÓN CRÍTICA ---
        # 1. Quitamos espacios y pasamos nombres de columnas a MAYÚSCULAS sin tildes para el código
        df.columns = (df.columns.str.strip()
                      .str.upper()
                      .str.replace('Ó', 'O')
                      .str.replace('Á', 'A')
                      .str.replace('É', 'E')
                      .str.replace('Í', 'I')
                      .str.replace('Ú', 'U'))
        
        # 2. Limpiamos los datos de las celdas
        df = df.apply(lambda x: x.astype(str).str.upper().str.strip())
        return df
    except Exception as e:
        st.error(f"❌ Error al leer el CSV: {e}")
        return None

# Intentar cargar la base de datos
df_mapa = cargar_datos()

# Si los datos cargaron, habilitamos la búsqueda
if df_mapa is not None:
    # 4. Entrada del Operador
    user_input = st.text_input("Haz tu consulta (ej: Paciente de Maipú para Oftalmología):", "")

    if user_input:
        with st.spinner("Analizando mapa de red..."):
            try:
                # 5. El Cerebro (IA) extrae los filtros
                prompt_sistema = f"""
                Eres un extractor de datos técnicos de salud. 
                Tu objetivo es extraer: COMUNA_ORIGEN y ESPECIALIDAD_DESTINO.
                
                Opciones válidas de Comuna: {df_mapa['COMUNA_ORIGEN'].unique().tolist()}
                Opciones válidas de Especialidad: {df_mapa['ESPECIALIDAD_DESTINO'].unique().tolist()}
                
                Responde ÚNICAMENTE en formato JSON:
                {{"comuna": "VALOR", "especialidad": "VALOR"}}
                Si el valor no está en las opciones, pon "NULL".
                """
                
                completion = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[
                        {"role": "system", "content": prompt_sistema},
                        {"role": "user", "content": user_input}
                    ],
                    response_format={"type": "json_object"}
                )
                
                filtros = json.loads(completion.choices[0].message.content)
                comuna = filtros.get("comuna")
                especialidad = filtros.get("especialidad")

                # 6. Lógica de Búsqueda
                if comuna != "NULL" and especialidad != "NULL":
                    resultado = df_mapa[
                        (df_mapa['COMUNA_ORIGEN'] == comuna) & 
                        (df_mapa['ESPECIALIDAD_DESTINO'] == especialidad)
                    ]

                    if not resultado.empty:
                        st.success(f"📍 Resultado para {especialidad} desde {comuna}:")
                        for i, row in resultado.iterrows():
                            with st.container():
                                # Usamos los nombres de columna normalizados (MAYÚSCULAS Y SIN TILDES)
                                st.info(f"### {row['ESTABLECIMIENTO_DESTINO']}")
                                st.write(f"**Rango Etario:** {row['RANGO_EDAD']}")
                                st.write(f"**CIE-10:** {row['CIE-10']}")
                                st.write(f"**Observación:** {row['OBSERVACION']}")
                                st.divider()
                    else:
                        st.warning(f"No existe una ruta directa para {especialidad} en {comuna}.")
                else:
                    st.info("No logré identificar la comuna o especialidad. Intenta ser más específico.")
            except Exception as e:
                st.error(f"Hubo un error al procesar la consulta con la IA: {e}")
else:
    st.info("Esperando que el archivo de datos esté disponible...")
