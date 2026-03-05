# Import libraries
import pandas as pd
import numpy as np
import streamlit as st

st.title("Prueba Cloud")

df = pd.DataFrame(np.random.randint(10,100,size=(10,3)), columns=["Col1", "Col2", "Col3"])

st.dataframe(df)

st.subheader("Otra prueba")

df1 = pd.DataFrame(np.random.randint(10,100,size=(10,5)), columns=["Col1", "Col2", "Col3", "Col4", "Col5"])

st.dataframe(df1)
