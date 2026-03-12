# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 15:32:54 2026

@author: elizabeth.cervantes
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import xlsxwriter



cols={"Trade Date" : "Trade Date", 
      "Family Name" : "Client", 
      "Transaction Type" : "Transaction Type", 
      "Net Amount Local" : "Net Amount Local",
      "Local Currency Code" : "Local Currency Code",
      "Local To Base FX Rate" : "Local To Base FX Rate", 
      "Net Amount Base" : "Net Amount Base",
      "Referencia Movimiento" : "Referencia Movimiento"} 

st.title("Transaction Report")

# Subir archivo CSV
uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])

df = None

if uploaded_file:

    file_type = uploaded_file.name.split(".")[-1].lower()


    if file_type == "csv":
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
    else:
        df = pd.read_excel(uploaded_file)

    #st.dataframe(df)
    df.columns = df.columns.str.strip()

    st.success("File uploaded successfully")
    #st.dataframe(df.head()) 
    
if df is not None:

    if st.button("Filter file"):

        required_cols = set(cols.keys())
        file_cols = set(df.columns)

        missing_cols = required_cols - file_cols

        if missing_cols:

            st.error("❌ The file does not contain all the necessary columns")

            st.write("The following columns are missing:")
            for col in missing_cols:
                st.write(f"- {col}")

        else:

            st.success("✅ File ready to download")

            # Limpiar espacios en nombres de columnas
            df.columns = df.columns.str.strip().str.replace("  ", " ")
            
            
            # Seleccionar columnas necesarias y renombrarlas
            df = df[list(cols.keys())].rename(columns=cols) 
                 
           
            # Filtrar tipo de transacción
            df_filtrado = df.query("`Transaction Type` in ['Addition', 'Withdrawal of Cash']")
           
            
            
            # Eliminar NAN 
            df_filtrado = df_filtrado[df_filtrado["Referencia Movimiento"].notna()]
        
            # Limpiar espacios
            df_filtrado["Referencia Movimiento"] = (
                df_filtrado["Referencia Movimiento"]
                .astype(str)
                .str.strip()
                .str.upper()
            )
        
            # Eliminar vacíos después del strip
            df_filtrado = df_filtrado[df_filtrado["Referencia Movimiento"] != ""]
        
            # Excluir ciertos textos
            mask_excluir = df_filtrado["Referencia Movimiento"].str.contains(
                r"\b(debit|internal|interest|card)\b",
                case=False,
                regex=True
                ) | df_filtrado["Referencia Movimiento"].str.match(
                r"(?i)^(transfer)$"
            )
        
            df_filtrado = df_filtrado[~mask_excluir]
            
            df_filtrado["Trade Date"] = pd.to_datetime(df_filtrado["Trade Date"],format="%m/%d/%Y")
            
            
            fecha_min = df_filtrado['Trade Date'].min()
            fecha_max = df_filtrado['Trade Date'].max()  
            format_fecha_min = f"{fecha_min.month}/{fecha_min.day}/{fecha_min.year}"
            format_fecha_max = f"{fecha_max.month}/{fecha_min.day}/{fecha_min.year}"
            
            # Formatear sin ceros a la izquierda
            df_filtrado["Trade Date"] = df_filtrado["Trade Date"].apply(lambda x: f"{x.month}/{x.day}/{x.year}")
            
            ancho = df_filtrado['Referencia Movimiento'].str.len().max()

        
            # Crear archivo Excel en memoria
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_filtrado.to_excel(writer, index=False, sheet_name="Filtered_data",startrow=1,header=False)
                
               
                
                workbook  = writer.book
                worksheet = writer.sheets["Filtered_data"]
            
                # Ocultar líneas de cuadrícula
                worksheet.hide_gridlines(0) #2

                # Anchos personalizados por columna
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
                    "Net Amount Local": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "General"}),
                    "Local Currency Code": workbook.add_format({"align": "center", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"}),
                    "Local To Base FX Rate": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "0.00"}),
                    "Net Amount Base": workbook.add_format({"align": "right", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000","num_format": "General"}),
                    "Referencia Movimiento": workbook.add_format({"align": "left", "valign": "vcenter", "font_name": "Lato Light", "font_size": 11, "font_color": "#000000"})
                }
                
                
                
                # Aplicar formato y ancho por columna
                for col_num, col_name in enumerate(df_filtrado.columns):
                    fmt = column_formats.get(col_name)  # formato con alineación
                    width = column_widths.get(col_name, 20)  # ancho por defecto 20 si no está en el diccionario
                    worksheet.set_column(col_num, col_num, width, fmt)

            
                #Formato
                # ===== Formato encabezado =====
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
            
               
            
                # ===== Escribir encabezados con formato =====
                for col_num, column in enumerate(df_filtrado.columns):
                    worksheet.write(0, col_num, column, header_format)
                    
                
                    
            output.seek(0)
    
            nombre_archivo = st.text_input("File name", f"Transaction_{format_fecha_min}-{format_fecha_max}")
            
            # Botón para descargar
            st.download_button(
                label="Download Excel",
                data=output,
                file_name=f"{nombre_archivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
