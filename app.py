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

# 2. Conexión con la IA (Modelo actualizado y vigente)
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    MODELO_IA = "llama-3.3-70b-versatile" 
except Exception:
    st.error("Error: Configura 'GROQ_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# 3. Función para cargar y normalizar el CSV
@st.cache_data
def cargar_datos():
    file_path = 'derivaciones.csv'
    try:
        # Usamos latin-1 por los caracteres especiales de Excel y sep ';' por tu archivo
        df = pd.read_csv(file_path, sep=';', encoding='latin-1')
    except Exception:
        df = pd.read_csv(file_path, sep=';', encoding='utf-8')
    
    # REGLA ORO: Rellenar vacíos para evitar errores de floats en el prompt
    df = df.fillna("")
    
    # Normalización: Mayúsculas, sin espacios y quitar puntos finales (ej: "VALPARAÍSO.")
    def limpiar(txt):
        return str(txt).upper().strip().rstrip('.')

    for col in df.columns:
        df[col] = df[col].apply(limpiar)
    
    return df

try:
    df_mapa = cargar_datos()

    # --- NUEVO: SELECTOR DE TIPO (Alimentado del CSV) ---
    tipos_disponibles = sorted(df_mapa['Tipo_Especialidad'].unique().tolist())
    tipo_seleccionado = st.selectbox("Seleccione Tipo de Especialidad:", tipos_disponibles)

    # 4. Entrada del Usuario
    user_input = st.text_input("Describa la necesidad del paciente:", placeholder="Ej: Paciente de Casablanca para Endodoncia")

    if user_input:
        with st.spinner("Analizando requerimiento..."):
            # Filtramos las opciones que le pasamos a la IA según el TIPO seleccionado
            # Esto hace que la IA sea mucho más precisa
            df_filtrado_tipo = df_mapa[df_mapa['Tipo_Especialidad'] == tipo_seleccionado]
            
            comunas = sorted(df_filtrado_tipo['Comuna_Origen'].unique().tolist())
            especialidades = sorted(df_filtrado_tipo['Especialidad_Destino'].unique().tolist())

            prompt_sistema = f"""
            Eres un experto en derivaciones de salud. Tu tarea es extraer la Comuna y la Especialidad del texto.
            
            CONTEXTO DEL TIPO: {tipo_seleccionado}
            COMUNAS VÁLIDAS: {comunas}
            ESPECIALIDADES VÁLIDAS: {especialidades}
            
            Instrucciones:
            1. Retorna un JSON con llaves: "comuna" y "especialidad".
            2. El valor debe coincidir EXACTAMENTE con los nombres de las listas.
            3. Si no encuentras el dato exacto, usa "NULL".
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

            # 5. Lógica de Filtrado Final
            if c_ia != "NULL" and e_ia != "NULL":
                # Buscamos en el dataframe filtrado por el botón "Tipo"
                resultado = df_filtrado_tipo[
                    (df_filtrado_tipo['Comuna_Origen'] == c_ia) & 
                    (df_filtrado_tipo['Especialidad_Destino'] == e_ia)
                ]

                if not resultado.empty:
                    st.success(f"✅ Destino para {e_ia} ({tipo_seleccionado}) en {c_ia}:")
                    for _, row in resultado.iterrows():
                        with st.expander(f"📍 {row['Establecimiento_Destino']}", expanded=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Rango Edad:** {row['Rango_Edad']}")
                                st.write(f"**CIE-10:** {row['CIE-10']}")
                            with col2:
                                if row['Observacion']:
                                    st.info(f"**Observación:** {row['Observacion']}")
                else:
                    st.warning(f"No se encontró ruta para {e_ia} en {c_ia} dentro de la categoría {tipo_seleccionado}.")
            else:
                st.info(f"No pudimos identificar la comuna o especialidad en el área de {tipo_seleccionado}.")

except Exception as e:
    st.error(f"Error: {e}")