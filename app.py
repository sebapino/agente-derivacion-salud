import streamlit as st
import pandas as pd
from groq import Groq
import json

# 1. Configuración de la Interfaz
st.set_page_config(page_title="Asistente de Derivación Salud", page_icon="🏥", layout="centered")

st.title("🏥 Asistente Inteligente de Derivación")
st.markdown("""
Esta herramienta ayuda a identificar el **Establecimiento Destino** según el Mapa de Derivación oficial. 
La decisión clínica final es siempre del profesional tratante.
""")

# 2. Conexión con la IA (Debes poner tu API Key de Groq aquí o en Secrets)
# Para pruebas locales puedes usar: client = Groq(api_key="TU_LLAVE_AQUI")
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Falta la configuración de la API Key. Por favor, configúrala en Streamlit Secrets.")

# 3. Función para cargar y normalizar el CSV
@st.cache_data
def cargar_datos():
    df = pd.read_csv('derivaciones.csv', sep=None, engine='python')
    # Normalización: Todo a mayúsculas y sin espacios extra para evitar errores de "match"
    df = df.apply(lambda x: x.astype(str).str.upper().str.strip())
    return df

try:
    df_mapa = cargar_datos()

    # 4. Entrada del Operador (Lenguaje Natural)
    user_input = st.text_input("Ejemplo: 'Paciente de Maipú necesita derivación a Oftalmología'", "")

    if user_input:
        with st.spinner("Analizando mapa de red..."):
            # 5. El Cerebro (IA) extrae los filtros
            prompt_sistema = f"""
            Eres un extractor de datos técnicos de salud. 
            Tu objetivo es extraer: Comuna_Origen y Especialidad_Destino del texto.
            
            Opciones válidas de Comuna: {df_mapa['Comuna_Origen'].unique().tolist()}
            Opciones válidas de Especialidad: {df_mapa['Especialidad_Destino'].unique().tolist()}
            
            Responde ÚNICAMENTE en formato JSON:
            {{"comuna": "VALOR", "especialidad": "VALOR"}}
            Si no encuentras el dato, pon "NULL".
            """
            
            completion = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"}
            )
            
            filtros = json.loads(completion.choices[0].message.content)
            comuna = filtros.get("comuna")
            especialidad = filtros.get("especialidad")

            # 6. Lógica de Búsqueda Estricta
            if comuna != "NULL" and especialidad != "NULL":
                resultado = df_mapa[
                    (df_mapa['Comuna_Origen'] == comuna) & 
                    (df_mapa['Especialidad_Destino'] == especialidad)
                ]

                if not resultado.empty:
                    st.success(f"📍 **Destino Encontrado para {especialidad} desde {comuna}:**")
                    for i, row in resultado.iterrows():
                        with st.container():
                            st.info(f"### {row['Establecimiento_Destino']}")
                            st.write(f"**Rango Etario:** {row['Rango_Edad']}")
                            st.write(f"**CIE-10 Asociado:** {row['CIE-10']}")
                            st.write(f"**Observaciones:** {row['Observacion']}")
                            st.divider()
                else:
                    st.warning(f"No se encontró una ruta específica en el mapa para {especialidad} en {comuna}.")
            else:
                st.info("Por favor, indica claramente la comuna y la especialidad requerida.")

except Exception as e:
    st.warning("Asegúrate de haber subido el archivo 'derivaciones.csv' correctamente.")
