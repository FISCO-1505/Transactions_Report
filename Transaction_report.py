# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 15:32:54 2026

@author: elizabeth.cervantes
"""
import bootstrap #Carga la libreria de FISCO_Sources, siempre ponerlo
import streamlit as st
import pandas as pd
from io import BytesIO
import xlsxwriter
import gc
from datetime import datetime

from pathlib import Path
from FISCO_Sources import auth, crypto, images


images.imagen_f("Transactions & Funds")

def mask_cash(df):
    return (
        df["Referencia Movimiento"].str.contains(
            r"\b(?:debit|internal|interest|card)\b",
            case=False,
            regex=True
        )
        |
        df["Referencia Movimiento"].str.match(
            r"(?i)^(transfer)$"
        )
    )

# ----------------------------------------------------------------

def mask_security(df):
    return df["Security Name"].str.contains(
        r"\bCASH\b",
        case=False,
        regex=True,
        na=False
    )

# -----------------------------------------------------------------

# Función para realizar el filtro de los datos
def filtrar(df,columna_clave,transacciones,mask_excluir_func,sort_cols,cols_seleccionar=None,columnas_drop=None,rename_cols=None):
    
    # Selección inicial
    if cols_seleccionar:
        df = df[cols_seleccionar]

    if columnas_drop:
        df = df.drop(columns=columnas_drop, errors='ignore')

    if rename_cols:
        df = df.rename(columns=rename_cols)

    # Filtrar transacciones
    df = df.query("`Transaction Type` in @transacciones")

    # Guardar vacíos
    datos_vacios = df[
        df[columna_clave].isna() |
        (df[columna_clave].astype(str).str.strip() == "")
    ]

    # Limpiar
    df = df[df[columna_clave].notna()].copy()

    df[columna_clave] = (
        df[columna_clave]
        .astype(str)
        .str.strip()
    )

    df = df[df[columna_clave] != ""]

    datos_cero = df[df["Net Amount Base"] == 0]

    df = df[df["Net Amount Base"] != 0]

    # Aplicar regla específica
    mask_excluir = mask_excluir_func(df)

    datos_excluidos = (
        pd.concat([datos_vacios, datos_cero, df[mask_excluir]])
        .sort_values(by=sort_cols)
        .reset_index(drop=True)
    )

    df = (
        df[~mask_excluir]
        .sort_values(by=sort_cols)
        .reset_index(drop=True)
    )

    return df, datos_excluidos

# ---------------------------------------------------------------------------------------------
def column_formats(workbook):
    left = workbook.add_format({
        "align": "left",
        "valign": "vcenter",
        "font_name": "Lato Light",
        "font_size": 11,
        "font_color": "#000000",
    })

    center = workbook.add_format({
        "align": "center",
        "valign": "vcenter",
        "font_name": "Lato Light",
        "font_size": 11,
        "font_color": "#000000",
    })

    amount = workbook.add_format({
        "align": "right",
        "valign": "vcenter",
        "font_name": "Lato Light",
        "font_size": 11,
        "font_color": "#000000",
        "num_format": "#,##0.00",
    })

    fx_rate = workbook.add_format({
        "align": "right",
        "valign": "vcenter",
        "font_name": "Lato Light",
        "font_size": 11,
        "font_color": "#000000",
        "num_format": "0.00",
    })

    return { "custodia":{
        "Trade Date": center,
        "Account Code": left,
        "Transaction Type": left,
        "Net Amount Local": amount,
        "Local Currency Code": center,
        "Local To Base FX Rate": fx_rate,
        "Net Amount Base": amount,
        "Security Name": left,
        "ISINSymbol": left, 
        "Settlement Date": center,
        "Quantity": amount,
        "LocalPrice": amount,   
    }, 
    "efectivo":{
        "Trade Date":center,
        "Client": left,
        "Transaction Type": left,
        "Net Amount Local": amount,
        "Local Currency Code": center,
        "Local To Base FX Rate": fx_rate,
        "Net Amount Base": amount,
        "Referencia Movimiento": left
    } 
    }
# ---------------------------------------------------------------------------------------------
column_widths_cash = {
        "Trade Date": 14,
        "Client": 12,
        "Transaction Type": 20,
        "Net Amount Local": 18,
        "Local Currency Code": 11,
        "Local To Base FX Rate": 10,
        "Net Amount Base": 18,
        "Account Code": 30
    } 

column_widths_funds = {
    "Account Code": 30,
    "ISINSymbol": 18,
    "Transaction Type": 20,
    "Trade Date": 14,
    "Settlement Date": 14,
    "Quantity": 18,
    "LocalPrice": 12,
    "Net Amount Local": 18,
    "Local Currency Code": 11,
    "Local To Base FX Rate": 10,
    "Net Amount Base": 18,
    }

# ---------------------------------------------------------------------------------------------
# Función crear Excel
def crear_excel(df,sort_cols,columna_texto=None,column_widths=None,format_factory=None, tipo_formato="custodia"):
    
    # Reemplazar valores NAN
    df = df.fillna("-")
    # Ordenar los datos 
    df = df.sort_values(by=sort_cols)
    
    if columna_texto and columna_texto in df.columns:
        ancho = (
            df[columna_texto]
            .fillna("")
            .astype(str)
            .str.len()
            .max()
        )

        if column_widths is not None:
            column_widths[columna_texto] = (ancho+2) * 1.3
    
     # Crear archivo Excel en memoria
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    all_formats = format_factory(workbook) if format_factory else {}
    formats = all_formats[tipo_formato]
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

    
    # Aplicar formato y ancho por columna
    for col_num, col_name in enumerate(df.columns):
        # formato con alineación
        fmt = formats.get(col_name)  
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
def descargar(nombre_archivo, output):
    
    # Mensaje exitoso
    st.success("✅ File ready to download")
        
    #Botón para descargar
    clicked = st.download_button(
        label="Download Excel",
        data=output,
        file_name=f"{nombre_archivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",          
    )

    if clicked:
        # Limpiar cache
        st.cache_data.clear()
        
# ---------------------------------------------------------------------------------------------

def mostrar_interfaz(titulo=None, texto=None, key=None):
    
    st.title(titulo)

    # ------------------------
    # SUBIR ARCHIVO
    # ------------------------
    uploaded_file = st.file_uploader(texto, type=["csv", "xlsx"],key=key)

    if uploaded_file is None:
        st.session_state.pop("filter_clicked", None)
        st.session_state.pop("df", None)
        st.stop()

    if uploaded_file is not None:
        if uploaded_file != st.session_state.last_file:
            st.session_state.last_file = uploaded_file
            
            # Reset completo
            st.session_state.filter_clicked = False
            st.session_state.df_filtrado = None
            st.session_state.datos_excluidos = None
            st.session_state.proceso_completo = False
            st.session_state.archivo_listo = False

    return uploaded_file


# -----------------------------------------------------------------------------------------------------------

def leer_archivo(uploaded_file, columnas_necesarias, columna_filtro, valores, mensaje, contains=False, ignore_case=False, columnas_fecha=None):
    
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
                st.warning("⚠️ The file is empty")
                st.stop()
            
            else: 
                
                # Quitar espacios en los nombres de las columnas
                df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)
                
            
                # Columnas faltantes
                columnas_faltantes = set(columnas_necesarias) - set(df.columns)
                
                # Enviar mensajes de error si faltan columnas para realizar el filtro
                if columnas_faltantes:
                    st.error("❌ The file doesn't contain all the necessary columns")
                    st.info("The following columns are missing:")
                    for col in columnas_faltantes:
                        # Mostrar cuales son las columnas que faltan
                        st.write(f"- {col}")
                    st.stop()
                    
                filtro = df[columna_filtro].dropna()

                if ignore_case:
                    filtro = filtro.str.lower()
                    valores = [v.lower() for v in valores]
            
                if contains:
                    existe = any(filtro.str.contains(valor, regex=False).any() for valor in valores)
                else:
                    existe = any((filtro == valor).any() for valor in valores)
            
                if not existe:
                    st.warning(mensaje)
                    st.stop()
            
            
            df= df.dropna(how="all")
            st.session_state.df = df
            st.success("✅ File uploaded successfully")
        
            if uploaded_file.name.endswith(".xlsx"):
                for col in columnas_fecha:
                    if col in df.columns:
                        df[col] = df[col].apply(
                            lambda x: x.strftime("%d/%m/%Y")
                            if isinstance(x, (pd.Timestamp, datetime))
                            else x
                        )
                    
                
        except Exception as e:
            st.error(f"Error reading the file: {e}")
    return df

# ---------------------------------------------------------------------------------------------
def contenido_principal():

    # Columnas necesarias
    cols = ["Trade Date",
            "Family Name",
            "Transaction Type",
            "Net Amount Local",
            "Local Currency Code",
            "Local To Base FX Rate",
            "Net Amount Base",
            "Referencia Movimiento"]
    
    cols_Funds = ["Account Code",
            "ISINSymbol",
            "Transaction Type",
            "Trade Date",
            "Settlement Date",
            "Quantity",
            "LocalPrice",
            "Net Amount Local", 
            "Local Currency Code",
            "Local To Base FX Rate",
            "Net Amount Base",
            "Security Name"]

    
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
    
    if "last_file" not in st.session_state:
        st.session_state.last_file = None

    # ---------------------------------------------------------------------------------------------

    # Insertar menú lateral
    with st.sidebar:
        # Título
        st.title(":blue[Select an option]")
        # Pills Options
        selection = st.pills(label="Options", label_visibility="collapsed",
                                options=["Home", "Transactions Report", "Funds Transactions"],
                                default="Home"
                            )
        
    # Botón cerrar sesión
    if st.sidebar.button("Log out"):
        st.cache_data.clear()
        st.toast("Caché eliminada")
        st.session_state["pswd"] = False
        st.rerun()

    # Ejecutar opción seleccionada
    if selection == "Transactions Report":

        uploaded_file = mostrar_interfaz(titulo="🧾 Transactions Report", texto="Upload Transactions File", key="transactions_file")

        leer_archivo(uploaded_file, cols,
                      'Transaction Type',
                       ["addition", "withdrawal of cash"], 
                       "⚠️ There are no Addition or Withdrawal of Cash", 
                       contains=True, 
                       ignore_case=True, 
                       columnas_fecha=["Trade Date"])

        
        # ------------------------
        # BOTÓN FILTRAR
        # ------------------------  
        if st.session_state.df is not None:
            if st.button("Filter file"):
                st.session_state.filter_clicked = True
                
            if st.session_state.filter_clicked:
                df = st.session_state.df.copy()  
                
                # FILTRAR
                df_filtrado, datos_excluidos = filtrar(
                            df=df,
                            columna_clave="Referencia Movimiento",
                            transacciones=["Addition", "Withdrawal of Cash"],
                            mask_excluir_func=mask_cash,
                            sort_cols=["Trade Date", "Client"],
                            cols_seleccionar=cols,
                            rename_cols={"Family Name": "Client"}
                        )
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
                        hide_index = True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("Select")
                            },
                            width = "stretch"
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
                    output = crear_excel(df_final, sort_cols=["Trade Date", "Client"],
                                        columna_texto="Referencia Movimiento",
                                        column_widths=column_widths_cash,
                                        format_factory=column_formats,
                                        tipo_formato="efectivo"
                                        )
                    
                    # Guardar en session state
                    st.session_state.archivo_listo = True
                    
                    # ------------------------
                    # DESCARGAR
                    # ------------------------
                    if not df_final.empty: 
                        fecha_min = df_final["Trade Date"].min()
                        fecha_max = df_final["Trade Date"].max()
                        # Nombre por default 
                        if fecha_min == fecha_max:
                            nombre_archivo = f"Report_{fecha_min}"
                        else:
                            nombre_archivo = f"Report_{fecha_min}-{fecha_max}"
                        st.session_state.nombre_archivo = nombre_archivo
                        if st.session_state.archivo_listo:
                            descargar(st.session_state.nombre_archivo, output)
                    else:
                        st.warning("⚠️ The file is empty; please add data if you want to download the file")
            if datos_excluidos.empty:
                df_final = st.session_state.df_filtrado.copy()
                # ------------------------
                # CREAR EXCEL
                # ------------------------
                output = crear_excel(df_final, sort_cols=["Trade Date", "Client"],
                                        columna_texto="Referencia Movimiento",
                                        column_widths=column_widths_cash,
                                        format_factory=column_formats,
                                        tipo_formato="efectivo"
                                        )
                
                # Guardar en session state
                st.session_state.archivo_listo = True
                
                # ------------------------
                # DESCARGAR
                # ------------------------
                if not df_final.empty: 
                    fecha_min = df_final["Trade Date"].min()
                    fecha_max = df_final["Trade Date"].max()
                    # Nombre por default 
                    if fecha_min == fecha_max:
                        nombre_archivo = f"Report_{fecha_min}"
                    else:
                        nombre_archivo = f"Report_{fecha_min}-{fecha_max}"
                    st.session_state.nombre_archivo = nombre_archivo
                    if st.session_state.archivo_listo:
                        descargar(st.session_state.nombre_archivo, output)

            if uploaded_file is None and "df" in st.session_state:
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    # ------------------------------          
    # Codigo de Funds Transactions  
    # ------------------------------
              
    elif selection == "Funds Transactions":

        uploaded_file = mostrar_interfaz(titulo="🧾 Funds Transactions", texto="Upload Funds File", key="funds_file")

        leer_archivo(uploaded_file, cols_Funds,
                      'Transaction Type',
                       ["Purchase", "Sell"], 
                       "⚠️ There are no Purchases or Sales",  
                       columnas_fecha=["Trade Date", "Settlement Date"])
        
        # ------------------------
        # BOTÓN FILTRAR
        # ------------------------  
        if st.session_state.df is not None:
            if st.button("Filter file"):
                st.session_state.filter_clicked = True
                
            if st.session_state.filter_clicked:
                df = st.session_state.df.copy() 
                
                
                
                # FILTRAR
                df_filtrado, datos_excluidos = filtrar(
                    df=df,
                    columna_clave="Security Name",
                    transacciones=["Purchase", "Sell"],
                    mask_excluir_func=mask_security,
                    sort_cols=["Trade Date", "Account Code"],
                    columnas_drop=[
                        'Family Name',
                        'Portfolio',
                        'Account ID',
                        'Referencia Movimiento'
                    ]
                )
                st.session_state.df_filtrado = df_filtrado 
                st.session_state.datos_excluidos = datos_excluidos
                st.session_state.proceso_completo = True 
                
                if df_filtrado.empty:
                    st.warning("⚠️ All transactions are cash and/or zero-amount")
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
                        hide_index = True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("Select")
                            },
                            width = "stretch"
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
                    output = crear_excel(
                                        df=df_final,
                                        sort_cols=["Trade Date", "Account Code"],
                                        columna_texto="Security Name",
                                        column_widths=column_widths_funds,
                                        format_factory=column_formats,
                                        tipo_formato="custodia"
                                    )
                    
                    # Guardar en session state
                    st.session_state.archivo_listo = True
                    
                    # ------------------------
                    # DESCARGAR
                    # ------------------------
                    if not df_final.empty: 
                        fecha_min = df_final["Trade Date"].min()
                        fecha_max = df_final["Trade Date"].max()
                        # Nombre por default 
                        if fecha_min == fecha_max:
                            nombre_archivo = f"Funds Report_{fecha_min}"
                        else:
                            nombre_archivo = f"Funds Report_{fecha_min}-{fecha_max}"
                        st.session_state.nombre_archivo = nombre_archivo
                        if st.session_state.archivo_listo:
                            descargar(st.session_state.nombre_archivo, output)
                    else:
                        st.warning("⚠️ The file is empty; please add data if you want to download the file")
            if datos_excluidos.empty:
                df_final = st.session_state.df_filtrado.copy()
                # ------------------------
                # CREAR EXCEL
                # ------------------------
                output = crear_excel(
                                        df=df_final,
                                        sort_cols=["Trade Date", "Account Code"],
                                        columna_texto="Security Name",
                                        column_widths=column_widths_funds,
                                        format_factory=column_formats,
                                        tipo_formato="custodia"
                                    )
                
                # Guardar en session state
                st.session_state.archivo_listo = True
                
                # ------------------------
                # DESCARGAR
                # ------------------------
                if not df_final.empty: 
                    fecha_min = df_final["Trade Date"].min()
                    fecha_max = df_final["Trade Date"].max()
                    # Nombre por default 
                    if fecha_min == fecha_max:
                        nombre_archivo = f"Funds Report_{fecha_min}"
                    else:
                        nombre_archivo = f"Funds Report_{fecha_min}-{fecha_max}"
                    st.session_state.nombre_archivo = nombre_archivo
                    if st.session_state.archivo_listo:
                        descargar(st.session_state.nombre_archivo, output)

            if uploaded_file is None and "df" in st.session_state:
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
                        
    else:

        images.imagen_home("Advisors")
        # Instrucciones
        st.header("Instructions")
        st.info("Follow the steps carefully to complete the process")
        st.markdown("""
        1. Click the **Transactions Report** or **Funds Transactions** button, depending on the report you wish to generate. 
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


def main():
    # Obtener ruta del archivo
    global ruta_base
    ruta_base = Path(__file__).resolve().parent

    auth.gestionar_sesion_segura(
        contenido_principal_func = contenido_principal,
        password_secreta = st.secrets["PSW_STREAMLIT"],
        idioma = "EN",
        timeout_segundos = 600, #10 min
        log_out=True #
    )
       
if __name__ == "__main__":
    main()