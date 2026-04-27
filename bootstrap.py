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

    # Asgurar que la ruta exista
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
            repo_url = f"git+https://{token}@github.com/FISCO-1505/Finaccess_Resources.git" #para poder descargr una rama es de la siguiente forma "@nombre_rama" agregandose al final"
            
            with st.spinner("Uploading sources..."):
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", 
                        "install", "--target", local_lib_path, 
                        repo_url
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL #stdout=None, stderr=None
                        )

                    st.success("Sources loaded correctly.")
                    import FISCO_Sources
                except Exception as e:
                    st.error(f"Error: Library did not load correctly.")
                    st.stop()
        else:
            st.error("No se encontró GITHUB_TOKEN en los Secrets de Streamlit.")
            st.stop()

# Ejecutar la función
ensure_private_lib()