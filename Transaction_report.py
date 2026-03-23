# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 15:32:54 2026

@author: elizabeth.cervantes
"""

import streamlit as st
import subprocess
import sys
import os

def ensure_private_lib():
    # Si existe /home/adminuser, estamos en Streamlit Cloud
    is_cloud = os.path.exists("/home/adminuser")
    
    if is_cloud:
        # En la nube usamos /tmp para evitar problemas de permisos de escritura
        local_lib_path = "/tmp/fisco_vendor"
    else:
        # En local usamos la carpeta vendor en el directorio actual
        local_lib_path = os.path.join(os.getcwd(), "vendor")

    # Asegurar que la ruta exista
    if not os.path.exists(local_lib_path):
        os.makedirs(local_lib_path)
    
    if local_lib_path not in sys.path:
        # Insertamos al inicio para dar prioridad a nuestra librería
        sys.path.insert(0, local_lib_path)

    try:
        import FISCO_Sources
    except ImportError:
        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo_url = f"git+https://{token}@github.com/FISCO-1505/Finaccess_Resources.git"
            
            with st.spinner("Configuring resources..."):
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", 
                        "install", "--target", local_lib_path, 
                        repo_url
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    st.success("Resources configured correctly.")
                    import FISCO_Sources
                except Exception as e:
                    st.error(f"Critical error: The library could not be installed.")
                    st.stop()
        else:
            st.error("GITHUB_TOKEN was not found in Streamlit's Secrets.")
            st.stop()

# Ejecutar la función
ensure_private_lib()



import pandas as pd
from io import BytesIO
import xlsxwriter

from pathlib import Path
from FISCO_Sources import auth, crypto, images

images.imagen_f("Transaction Report")

def main():
    
    # Obtener ruta del archivo
    global ruta_base
    ruta_base = Path(__file__).resolve().parent

    # Llamada a tu librería para validar acceso
    acceso_concedido = auth.verificar_acceso(st.secrets["PSW_STREAMLIT"], crypto,"EN")

    if not acceso_concedido:
        # Aquí puedes poner un mensaje opcional o dejarlo en blanco
        st.info("Please log in via the side menu to continue.")


    else:
        # ______________________________________ Contenido Principal ______________________________________

        
        # Insertar menú lateral
        with st.sidebar:
            # Título
            st.title(":blue[Select an option]")
            # Pills Options
            selection = st.pills(label="Options", label_visibility="collapsed",
                                 options=["Home", "Generate Report"],
                                 default="Home"
                                )
        # Ejecutar opción seleccionada
        if selection == "Generate Report":

            # Columnas necesarias
            cols={"Trade Date" : "Trade Date", 
                "Family Name" : "Client", 
                "Transaction Type" : "Transaction Type", 
                "Net Amount Local" : "Net Amount Local",
                "Local Currency Code" : "Local Currency Code",
                "Local To Base FX Rate" : "Local To Base FX Rate", 
                "Net Amount Base" : "Net Amount Base",
                "Referencia Movimiento" : "Referencia Movimiento"} 
            
            # Función para realizar el filtro de los datos
            def filtrar(df, cols):
            
                # Seleccionar columnas necesarias y renombrarlas
                df = (df
                      [list(cols.keys())]
                      .rename(columns=cols)
                      .query("`Transaction Type` in ['Addition', 'Withdrawal of Cash']")
                )

                # Eliminar NAN de la columna Referencia Movimiento
                df = df[df["Referencia Movimiento"].notna()]
                
                # Limpiar espacios a los datos de la columna Referencia Movimientos
                df["Referencia Movimiento"] = (
                    df["Referencia Movimiento"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )
                # Eliminar referencias de movimientos vacías
                df = df[df["Referencia Movimiento"] != ""]

                # Excluir ciertos textos
                mask_excluir = (
                    df["Referencia Movimiento"].str.contains(
                        r"\b(debit|internal|interest|card)\b",
                        case=False,
                        regex=True
                    ) 
                    | df["Referencia Movimiento"].str.match(r"(?i)^(transfer)$")
                )

                # Guardamos nuestra tabla filtrada
                df = df[~mask_excluir] 

                # Ordenar los datos 
                df = df.sort_values(by=["Trade Date", "Client"])

                cambio_fecha = df['Trade Date'].ne(df['Trade Date'].shift())

                grupos = df.groupby(cambio_fecha.cumsum(), group_keys=False)
                df = grupos.apply(
                    lambda g: pd.concat(
                        [g, pd.DataFrame([[None]*len(g.columns)], columns=g.columns)],
                        ignore_index=True  
                    )
                )

                df = df.iloc[:-1]

                return df.reset_index(drop=True)
            
            # Titulo 
            st.title("Transaction Report")

            # Subir archivo tipo CSV o XLSX
            uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])

            # Creamos un DataFrame sin valores
            df = None

            if uploaded_file:

                # Variable que guarda el tipo de archivo
                file_type = uploaded_file.name.split(".")[-1].lower()

                # Leer el archivo y sustituye lo que había en df
                if file_type == "csv":
                    df = pd.read_csv(uploaded_file, sep=None, engine="python")
                else:
                    df = pd.read_excel(uploaded_file)
                    # Aplicar formato a la columna de fecha
                    df["Trade Date"] = df["Trade Date"].dt.strftime("%#d/%#m/%Y")

                # Mensaje exitoso
                st.success("File uploaded successfully") 
                
            if df is not None: 

                fecha_min = df['Trade Date'].min()
                fecha_max = df['Trade Date'].max()

                if fecha_min == fecha_max:
                    default_name = f"Transaction_{fecha_min}"
                else:
                    default_name = f"Transaction_{fecha_min}-{fecha_max}"

                if "archivo_listo" not in st.session_state:
                    st.session_state.archivo_listo = False
                if "nombre_archivo" not in st.session_state:
                    st.session_state.nombre_archivo = default_name 

                # ----- Boón para filtrar ----    
                if st.button("Filter file"):

                    # Quitar espacios en los nombres de las columnas
                    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)
                    # Columnas necesarias para poder filtrar
                    required_cols = set(cols.keys())
                    # Columnas faltantes
                    missing_cols = required_cols - set(df.columns)

                    # Enviar mensajes de error si faltan columnas para realizar el filtro
                    if missing_cols:

                        st.error("❌ The file doesn't contain all the necessary columns")
                        st.write("The following columns are missing:")
                        for col in missing_cols:
                            # Mostrar cuales son las columnas que faltan
                            st.write(f"- {col}")

                    else:
                        # Realizar el filtro
                        filtrar(df, cols)
                        df_filtrado = filtrar(df, cols)

                        # Obtener longitud de la referencia
                        ancho = df_filtrado['Referencia Movimiento'].str.len().max()

                    
                        # Crear archivo Excel en memoria
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                            df_filtrado.to_excel(writer, index=False, 
                                                 sheet_name="Filtered_data",startrow=1,header=False)
                            
                            workbook  = writer.book
                            worksheet = writer.sheets["Filtered_data"]

                            # Ancho de cada columna 
                            column_widths = {
                                "Trade Date": 14,
                                "Client": 12,
                                "Transaction Type": 20,
                                "Net Amount Local": 18,
                                "Local Currency Code": 10,
                                "Local To Base FX Rate": 10,
                                "Net Amount Base": 18,
                                "Referencia Movimiento": ancho+18
                            }

                        # Dar formatos a cada columna
                            column_formats = {
                                "Trade Date": workbook.add_format({"align": "center", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"}),
                                "Client": workbook.add_format({"align": "left", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"}),
                                "Transaction Type": workbook.add_format({"align": "left", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"}),
                                "Net Amount Local": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "#,##0.00"}),
                                "Local Currency Code": workbook.add_format({"align": "center", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"}),
                                "Local To Base FX Rate": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "0.00"}),
                                "Net Amount Base": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "#,##0.00"}),
                                "Referencia Movimiento": workbook.add_format({"align": "left", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"})
                            } 
                            
                            # Aplicar formato y ancho por columna
                            for col_num, col_name in enumerate(df_filtrado.columns):
                                # formato con alineación
                                fmt = column_formats.get(col_name)  
                                # ancho de 20 
                                width = column_widths.get(col_name, 20)  
                                worksheet.set_column(col_num, col_num, width, fmt)
                            
                            # Formato de encabezados
                            header_format = workbook.add_format({
                                "bold": True,
                                "font_name": "Lato Light",
                                "font_size": 12,
                                "align": "center",
                                "valign": "vcenter",
                                "font_color": "white",
                                "bg_color": "#0B2E4E",
                                "border": 0, 
                                "text_wrap": True
                            })
                        
                            # Escribir encabezados  
                            for col_num, column in enumerate(df_filtrado.columns):
                                worksheet.write(0, col_num, column, header_format)
                                
                            
                        # Muve el cursor al inicio               
                        output.seek(0)

                        # Guardar archivo en session_state
                        st.session_state.output_file = output
                        st.session_state.archivo_listo = True

                        # Mensaje listo para descargar
                        st.success("✅ File ready to download") 

                if st.session_state.archivo_listo:
                    # Input editable
                    st.session_state.nombre_archivo = st.text_input(
                        "File name", 
                        value = st.session_state.nombre_archivo
                     )
                    
                    nombre_archivo = st.session_state.nombre_archivo.strip() or "archivo"
                        
                        
                    # Botón para descargar
                    st.download_button(
                        label="Download Excel",
                        data=st.session_state.output_file,
                        file_name=f"{nombre_archivo}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
             # Cargar imagen
             images.imagen_home("Advisors") 

             # Instrucciones
             st.header("Instructions")
             st.info("Follow the steps carefully to complete the process")
             st.markdown("""
                1. Click the Generate Report button.
                2. Drag or upload the .csv or .xlsx file you want to filter, you will see the message""")
             st.success("File uploaded successfully")  
             st.markdown(""" 
                3. Click the Filter file button.""")
             st.markdown("""            
                   If necessary columns are missing, you will see the message:""")
             st.error("❌ The file doesn't contain all the necessary columns. The following columns are missing:")
             st.markdown("""              
                In that case, you should review the file and upload it again, making sure it contains the necessary columns.""")
             st.markdown(""" 
                If the file has the necessary columns to perform the filter, you will see the message:""")
             st.success("✅ File ready to download") 
             st.markdown("""
                4. Enter the name you want to use to save the filtered file. 
                5. Press Enter to apply. """)  
             st.warning("If you don't press Enter, the name change won't be applied.")
             st.markdown("""                            
                6. Click the Download Excel button.""")  
             st.warning("Don't close the page during the download.")
             st.markdown("""            
                7. Click Save As and choose the folder.
                8. Log out.
                         """)           
             
             

        # Botón cerrar sesión
        if st.sidebar.button("Log out"):
            st.cache_data.clear()
            st.toast("Caché eliminada")
            st.session_state["pswd"] = False
            st.rerun()
        
if __name__ == "__main__":
    main()