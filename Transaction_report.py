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
        # REVISAR POSIBLE EXPIRACIÓN DEL TOKEN
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

images.imagen_f("Transactions Report")

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
        
        # Columnas necesarias
        cols = {"Trade Date" : "Trade Date", 
                "Family Name" : "Client", 
                "Transaction Type" : "Transaction Type", 
                "Net Amount Local" : "Net Amount Local",
                "Local Currency Code" : "Local Currency Code",
                "Local To Base FX Rate" : "Local To Base FX Rate", 
                "Net Amount Base" : "Net Amount Base",
                "Referencia Movimiento" : "Referencia Movimiento"} 
        # ---------------------------------------------------------------------------------------------    
        
        # Función para realizar el filtro de los datos
        def filtrar(df, cols):

            # Seleccionar columnas necesarias, renombrarlas y filtrar por tipo de transacción
            df = (df
                [list(cols.keys())]
                .rename(columns=cols)
                .query("`Transaction Type` in ['Addition', 'Withdrawal of Cash']")
            )

            # Guardar datos vacíos
            datos_vacios = df[
                df["Referencia Movimiento"].isna() |
                (df["Referencia Movimiento"].astype(str).str.strip() == "")]
            
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
                    r"\b(?:debit|internal|interest|card)\b",
                    case=False,
                    regex=True
                ) 
                | df["Referencia Movimiento"].str.match(r"(?i)^(transfer)$")
            )

            # Obtener todos los datos que vamos a eexcluir
            datos_excluidos = (pd.concat([datos_vacios, df[mask_excluir]])
                                .sort_values(by=["Trade Date", "Client"])
                                .reset_index(drop=True))
            
            datos_excluidos = datos_excluidos[['Trade Date', 
                                            'Client', 
                                            'Transaction Type', 
                                            'Net Amount Local', 
                                            'Local Currency Code', 
                                            'Referencia Movimiento',
                                            'Local To Base FX Rate',
                                            'Net Amount Base']]

            # Guardamos nuestra tabla filtrada
            df = df[~mask_excluir] 

            #if df.empty:
                #return None

            return df, datos_excluidos 
        
        # ---------------------------------------------------------------------------------------------
        
        # Función crear Excel
        def crear_excel(df):
            
            # Ordenar los datos 
            df = df.sort_values(by=["Trade Date", "Client"])
            
            # Obtener longitud de la referencia
            ancho = (df['Referencia Movimiento']
                    .fillna("")
                    .astype(str)
                    .str
                    .len()
                    .max()
                    )
            
            # Crear archivo Excel en memoria
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet("Filtered_data")
            worksheet.hide_gridlines(0) 
            
            row = 1
            # Iterar fechas únicas
            for date in df['Trade Date'].unique():
                col = 0
                df_query = df.query("`Trade Date` == @date").copy()
                n_rows = df_query.shape[0]

                # Iterar columnas y escribirlas
                for columnas in df_query.columns: 
                    worksheet.write_column(row, col, df_query[columnas])
                    col += 1
                row = row + n_rows + 1

            # Ancho de cada columna 
            column_widths = {
                "Trade Date": 14,
                "Client": 12,
                "Transaction Type": 20,
                "Net Amount Local": 18,
                "Local Currency Code": 11,
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
            for col_num, col_name in enumerate(df.columns):
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
            for col_num, column in enumerate(df.columns):
                worksheet.write(0, col_num, column, header_format)
                    
            workbook.close()    
            # Muve el cursor al inicio               
            output.seek(0) 
            
            return output   
        # ---------------------------------------------------------------------------------------------
        
        # Función descargar
        def descargar(nombre_archivo):
            
            # Mensaje exitoso
            st.success("✅ File ready to download")
                
            #Botón para descargar
            clicked = st.download_button(
                label="Download Excel",
                data=st.session_state.output_file,
                file_name=f"{nombre_archivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",          
            )

            return clicked
        # ---------------------------------------------------------------------------------------------
        
        # ------------------------
        # SESSION STATE
        # ------------------------
        if "df" not in st.session_state:
            st.session_state.df = None

        if "nombre_archivo" not in st.session_state:
            st.session_state.nombre_archivo = None
            
        if "filter_clicked" not in st.session_state:
            st.session_state.filter_clicked = False
            
        if "df_filtrado" not in st.session_state:
            st.session_state.df_filtrado = None
            
        if "datos_excluidos" not in st.session_state:
            st.session_state.datos_excluidos = None
            
        if "proceso_completo" not in st.session_state:
            st.session_state.proceso_completo = False

        if "archivo_listo" not in st.session_state:
            st.session_state.archivo_listo = False

        # ---------------------------------------------------------------------------------------------
    
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
            st.set_page_config(page_title="Transactions Report", layout="wide")
            st.title("🧾 Transactions Report")

            # ------------------------
            # SUBIR ARCHIVO
            # ------------------------
            uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])

            if uploaded_file:
                try: 
                    if uploaded_file.name.endswith(".csv"):
                        try:
                            df = pd.read_csv(uploaded_file)
                        except:
                            df = pd.read_csv(uploaded_file, sep=None, engine="python")
                    else: 
                        df = pd.read_excel(uploaded_file)
                        
                    if df.empty: 
                        st.warning("⚠️ Your file is empty")
                    else:
                        df = df.dropna(how="all")
                        st.session_state.df = df
                        st.success("✅ File uploaded successfully")
                        
                        file_type = uploaded_file.name.split(".")[-1].lower()
                        if file_type == "xlsx":
                            df["Trade Date"] = df["Trade Date"].dt.strftime("%#d/%#m/%Y")
                        fecha_min = df["Trade Date"].min()
                        fecha_max = df["Trade Date"].max()
                        # Nombre por default 
                        if fecha_min == fecha_max:
                            nombre_archivo = f"Report_{fecha_min}"
                        else:
                            nombre_archivo = f"Report_{fecha_min}-{fecha_max}"
                        st.session_state.nombre_archivo = nombre_archivo
                except Exception as e:
                    st.error(f"Error reading the file: {e}")
            # ------------------------
            # BOTÓN FILTRAR
            # ------------------------  
            if st.session_state.df is not None:
                if st.button("Filter file"):
                    st.session_state.filter_clicked = True
                    
                if st.session_state.filter_clicked:
                    df = st.session_state.df.copy() 
                    
                    # Quitar espacios en los nombres de las columnas
                    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)
                    # Columnas necesarias para poder filtrar
                    required_cols = set(cols.keys())
                    # Columnas faltantes
                    missing_cols = required_cols - set(df.columns)
                    
                    filtro = df['Transaction Type'].dropna().str.lower()
                    entradas = filtro.str.contains("addition").any()
                    salidas = filtro.str.contains("withdrawal of cash").any()
            
                    # Enviar mensajes de error si faltan columnas para realizar el filtro
                    if missing_cols:
                        st.error("❌ The file doesn't contain all the necessary columns")
                        st.info("The following columns are missing:")
                        for col in missing_cols:
                            # Mostrar cuales son las columnas que faltan
                            st.write(f"- {col}")
                        st.stop()
                    if not entradas and not salidas:
                        st.warning("⚠️ There's not  Addition and Withdrawal of Cash")
                        st.stop()
                    
                    # FILTRAR
                    df_filtrado, datos_excluidos = filtrar(df, cols)
                    st.session_state.df_filtrado = df_filtrado 
                    st.session_state.datos_excluidos = datos_excluidos
                    st.session_state.proceso_completo = True 
                    
                    if df_filtrado.empty:
                        st.warning("⚠️ All transactions are debit, interest, or internal")
                    else:
                        st.success("✅ File filtered successfully") 
                    
            # ------------------------
            # MOSTRAR ELIMINADOS
            # ------------------------  
            if st.session_state.proceso_completo:
                datos_excluidos = st.session_state.datos_excluidos.copy() 
                st.info(f"🗑️ Data to delete: {len(datos_excluidos)}")
                
                if not datos_excluidos.empty:
                    if "Select" not in datos_excluidos.columns:
                        df_display = datos_excluidos.copy()
                        df_display.insert(0,"Select", False)
                        edited_df = st.data_editor(
                            df_display,
                            column_config={
                                "Select": st.column_config.CheckboxColumn("Select")
                                },
                                use_container_width = True
                            )
                        toggle = st.toggle("Add selected data")
                        df_final = st.session_state.df_filtrado.copy()
                        
                        if toggle:
                            seleccionados = edited_df[edited_df["Select"] == True]
                            df_final = pd.concat([df_final, seleccionados.drop(columns=["Select"])])
                            st.info(f"{len(seleccionados)} data were added")
                        else:
                            st.info("No data was added")
                        # ------------------------
                        # CREAR EXCEL
                        # ------------------------
                        output = crear_excel(df_final)
                        
                        # Guardar en session state
                        st.session_state.output_file = output
                        st.session_state.archivo_listo = True
                        
                        # ------------------------
                        # DESCARGAR
                        # ------------------------
                        if st.session_state.archivo_listo:
                            clicked = descargar(st.session_state.nombre_archivo)
                            if clicked:
                                st.session_state.archivo_listo = False
                                
                                st.cache_data.clear()
                                st.rerun()

        else:
            # Instrucciones
            st.header("Instructions")
            st.info("Follow the steps carefully to complete the process")
            st.markdown("""
            1. Click the **Generate Report** button.
            2. Drag or upload the .csv or .xlsx file you want to filter.
            3. Click the **Filter file** button.
            4. Click the checkbox in the Select column to add data.
            5. Click the **Add selected data** if necessary.                           
            6. Click the Download Excel button.""")  
            st.warning("Don't close the page during the download.")
            st.markdown("""            
            7. Click Save As and choose the folder.
            8. Log out and close the window.
                        """)           
        # Botón cerrar sesión
        if st.sidebar.button("Log out"):
            st.cache_data.clear()
            st.toast("Caché eliminada")
            st.session_state["pswd"] = False
            st.rerun()
        
if __name__ == "__main__":
    main()