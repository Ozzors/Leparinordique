import streamlit as st

# Prueba de logo
st.title("Prueba de Logo")
st.image("assets/logo.png", width=200)

with st.sidebar:
    st.image("assets/logo.png", width=150)
    st.write("Logo en la barra lateral")
