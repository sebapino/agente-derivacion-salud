import streamlit as st
import pandas as pd
from groq import Groq
import json

# 1. Configuración de la Interfaz
st.set_page_config(page_title="Asistente de Derivación Salud", page_icon="🏥", layout="centered")

st.title("🏥 Asistente Inteligente de Derivación")
st.markdown("""
Esta herramienta ayuda a identificar el **Establecimiento Destino** según el Mapa de Derivación oficial. 
""")

# 2. Conexión con la IA (Modelo actualizado)
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    # Usamos un modelo vigente
    MODELO_IA = "llama-3.3-70b-versatile" 
except Exception:
    st.error("Error: Configura 'GROQ_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 3. Función para cargar y normalizar el CSV
@st.cache_data
def cargar_datos():
    file_path = 'derivaciones.csv'
    try:
        # Latin-1 para tildes de Excel, sep ';' por tu archivo
        df = pd.read_csv(file_path, sep=';', encoding='latin-1')
    except Exception:
        df = pd.read_csv(file_path, sep=';', encoding='utf-8')
    
    # Rellenar vacíos para evitar error de floats
    df = df.fillna("")
    
    # Limpieza: Mayúsculas, sin espacios y quitar puntos al final de nombres
    def limpiar(txt):
        return str(txt).upper().strip().rstrip('.')

    for col in df.columns:
        df[col] = df[col].apply(limpiar)
    
    return df

try:
    df_mapa = cargar_datos()

    # 4. Entrada del Usuario
    user_input = st.text_input("Ejemplo: 'Paciente de Casablanca para Endodoncia'", "")

    if user_input:
        with st.spinner("Analizando requerimiento..."):
            # Listas para que la IA sepa qué buscar
            comunas = sorted(df_mapa['Comuna_Origen'].unique().tolist())
            especialidades = sorted(df_mapa['Especialidad_Destino'].unique().tolist())
            tipos = sorted(df_mapa['Tipo_Especialidad'].unique().tolist())

            prompt_sistema = f"""
            Eres un asistente técnico de salud. Extrae los siguientes datos en JSON.
            
            COMUNAS: {comunas}
            ESPECIALIDADES: {especialidades}
            TIPOS: {tipos}
            
            Instrucciones:
            1. Retorna JSON con: "comuna", "especialidad", "tipo".
            2. Usa "NULL" si no encuentras el dato.
            3. El "tipo" se refiere a la categoría (ej: MÉDICA u ODONTOLÓGICA).
            """

            completion = client.chat.completions.create(
                model=MODELO_IA,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"}
            )

            res = json.loads(completion.choices[0].message.content)
            c_ia = res.get("comuna")
            e_ia = res.get("especialidad")
            t_ia = res.get("tipo")

            # 5. Lógica de Filtrado Dinámico
            if c_ia != "NULL" and e_ia != "NULL":
                # Filtro base
                query = (df_mapa['Comuna_Origen'] == c_ia) & (df_mapa['Especialidad_Destino'] == e_ia)
                
                # Si la IA detectó un tipo, lo sumamos al filtro
                if t_ia != "NULL":
                    query = query & (df_mapa['Tipo_Especialidad'] == t_ia)

                resultado = df_mapa[query]

                if not resultado.empty:
                    st.success(f"✅ Coincidencias para {e_ia} en {c_ia}")
                    for _, row in resultado.iterrows():
                        with st.expander(f"📍 {row['Establecimiento_Destino']}", expanded=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Tipo:** {row['Tipo_Especialidad']}")
                                st.write(f"**Rango Edad:** {row['Rango_Edad']}")
                            with col2:
                                st.write(f"**CIE-10:** {row['CIE-10']}")
                            
                            if row['Observacion']:
                                st.info(f"**Observación:** {row['Observacion']}")
                else:
                    st.warning("No se encontró una ruta exacta. Intenta especificar si es Médica u Odontológica.")
            else:
                st.info("Por favor, indica comuna y especialidad (ej: 'Niño de Valparaíso para Odontopediatría').")

except Exception as e:
    st.error(f"Se produjo un error al procesar la solicitud: {e}")