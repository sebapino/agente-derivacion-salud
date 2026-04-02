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

# 2. Conexión con la IA (Groq)
try:
    # Intenta obtener la API KEY desde los secrets de Streamlit
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Error: Configura 'GROQ_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 3. Función para cargar y normalizar el CSV (Soluciona Encoding y Separador)
@st.cache_data
def cargar_datos():
    file_path = 'derivaciones.csv'
    try:
        # Intentamos con latin-1 que es el estándar de Excel en español
        df = pd.read_csv(file_path, sep=';', encoding='latin-1')
    except UnicodeDecodeError:
        # Si falla, intentamos con utf-8
        df = pd.read_csv(file_path, sep=';', encoding='utf-8')
    except FileNotFoundError:
        st.error(f"No se encontró el archivo {file_path}")
        st.stop()

    # REGLA DE ORO: Completar vacíos con texto para evitar errores de tipo "float"
    df = df.fillna("")

    # Normalización: Todo a mayúsculas, sin espacios y quitamos el punto final (ej: "VALPARAÍSO.")
    def limpiar_texto(txt):
        return str(txt).upper().strip().rstrip('.')

    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto)
    
    return df

try:
    df_mapa = cargar_datos()

    # 4. Entrada del Operador (Lenguaje Natural)
    user_input = st.text_input("Ejemplo: 'Paciente de Casablanca necesita Endodoncia'", "")

    if user_input:
        with st.spinner("Consultando mapa de red..."):
            # Obtenemos listas únicas para el prompt del sistema
            comunas_validas = sorted(df_mapa['Comuna_Origen'].unique().tolist())
            especialidades_validas = sorted(df_mapa['Especialidad_Destino'].unique().tolist())

            prompt_sistema = f"""
            Eres un experto en redes de salud chilena. Tu tarea es extraer la Comuna y la Especialidad.
            
            COMUNAS VÁLIDAS: {", ".join(comunas_validas)}
            ESPECIALIDADES VÁLIDAS: {", ".join(especialidades_validas)}
            
            Instrucciones:
            1. Devuelve un JSON con llaves "comuna" y "especialidad".
            2. El valor debe ser EXACTAMENTE igual a los nombres de las listas de arriba.
            3. Si el dato no está o es ambiguo, usa "NULL".
            
            Responde SOLO el JSON.
            """

            completion = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"}
            )

            # 5. Parsear respuesta de la IA
            filtros = json.loads(completion.choices[0].message.content)
            comuna_ia = filtros.get("comuna")
            especialidad_ia = filtros.get("especialidad")

            # 6. Lógica de Búsqueda y Visualización
            if comuna_ia != "NULL" and especialidad_ia != "NULL":
                resultado = df_mapa[
                    (df_mapa['Comuna_Origen'] == comuna_ia) & 
                    (df_mapa['Especialidad_Destino'] == especialidad_ia)
                ]

                if not resultado.empty:
                    st.success(f"✅ Se encontraron {len(resultado)} coincidencia(s) para {especialidad_ia} en {comuna_ia}")
                    
                    for _, row in resultado.iterrows():
                        with st.expander(f"📍 {row['Establecimiento_Destino']}", expanded=True):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"**Rango Edad:** {row['Rango_Edad']}")
                                st.write(f"**Tipo:** {row['Tipo_Especialidad']}")
                            with c2:
                                st.write(f"**CIE-10:** {row['CIE-10']}")
                            
                            if row['Observacion']:
                                st.info(f"**Observación:** {row['Observacion']}")
                else:
                    st.warning(f"No hay una ruta directa registrada para {especialidad_ia} en {comuna_ia}.")
            else:
                st.info("No se logró identificar la comuna o la especialidad. Por favor intenta de nuevo.")

except Exception as e:
    st.error(f"Se produjo un error al procesar la solicitud: {e}")