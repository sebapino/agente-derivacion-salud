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

# 2. Conexión con la IA
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Falta la configuración de la API Key en Streamlit Secrets.")

# 3. Función para cargar y normalizar el CSV (CORREGIDA)
@st.cache_data
def cargar_datos():
    # Especificamos el separador ';' y el nombre exacto del archivo
    df = pd.read_csv('derivaciones.csv', sep=';')
    
    # Rellenamos los vacíos con un texto vacío para evitar el error de "float found"
    df = df.fillna("")
    
    # Normalización profunda:
    # 1. Convertir todo a String
    # 2. A Mayúsculas
    # 3. Eliminar espacios al inicio/final
    # 4. Eliminar el punto final en los nombres (como en 'VALPARAÍSO.')
    df = df.apply(lambda x: x.astype(str).str.upper().str.strip().str.rstrip('.'))
    
    return df

try:
    df_mapa = cargar_datos()

    # 4. Entrada del Operador
    user_input = st.text_input("Ejemplo: 'Paciente de Casablanca para Endodoncia'", "")

    if user_input:
        with st.spinner("Analizando mapa de red..."):
            # 5. Preparamos las opciones para la IA (asegurando que sean solo strings)
            comunas_lista = sorted(df_mapa['Comuna_Origen'].unique().tolist())
            especialidades_lista = sorted(df_mapa['Especialidad_Destino'].unique().tolist())
            
            prompt_sistema = f"""
            Eres un extractor de datos técnicos de salud. 
            Tu objetivo es extraer: Comuna_Origen y Especialidad_Destino del texto del usuario.
            
            Opciones válidas de Comuna: {", ".join(comunas_lista)}
            Opciones válidas de Especialidad: {", ".join(especialidades_lista)}
            
            Responde ÚNICAMENTE en formato JSON:
            {{"comuna": "VALOR", "especialidad": "VALOR"}}
            
            REGLAS:
            1. El VALOR debe coincidir EXACTAMENTE con uno de las listas de arriba.
            2. Si no encuentras el dato, pon "NULL".
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

            # 6. Lógica de Búsqueda
            if comuna != "NULL" and especialidad != "NULL":
                # Aplicamos el filtro (ambos en mayúsculas por seguridad)
                resultado = df_mapa[
                    (df_mapa['Comuna_Origen'] == comuna.upper()) & 
                    (df_mapa['Especialidad_Destino'] == especialidad.upper())
                ]

                if not resultado.empty:
                    st.success(f"📍 **Destino Encontrado para {especialidad} desde {comuna}:**")
                    for i, row in resultado.iterrows():
                        with st.container():
                            st.info(f"### {row['Establecimiento_Destino']}")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Rango Etario:** {row['Rango_Edad']}")
                                st.write(f"**CIE-10:** {row['CIE-10']}")
                            with col2:
                                st.write(f"**Tipo:** {row['Tipo_Especialidad']}")
                            
                            if row['Observacion']:
                                st.warning(f"**Observaciones:** {row['Observacion']}")
                            st.divider()
                else:
                    st.warning(f"No se encontró una ruta específica para {especialidad} en {comuna}.")
            else:
                st.info("No pudimos identificar la comuna o especialidad. Intenta ser más específico.")

except FileNotFoundError:
    st.error("No se encontró el archivo 'derivaciones.csv'. Asegúrate de que el nombre sea exacto.")
except Exception as e:
    st.error(f"Ocurrió un error inesperado: {e}")