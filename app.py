import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
from init_db import init_db

# Configuración de la página
st.set_page_config(page_title="WMS Sencillo", layout="wide")

DB_NAME = "wms.db"

# Auto-initialization check for Streamlit Cloud
if not os.path.exists(DB_NAME):
    st.toast("Inicializando base de datos...", icon="⚙️")
    init_db()
    st.toast("Base de datos creada exitosamente.", icon="✅")

# --- Funciones de Base de Datos ---
def run_query(query, params=(), fetch_data=False):
    """Ejecuta una consulta SQL y maneja la conexión."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_data:
            data = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            result = pd.DataFrame(data, columns=columns)
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        st.error(f"Error de base de datos: {e}")
        return None

def get_products():
    return run_query("SELECT sku, name, category FROM products", fetch_data=True)

def get_locations():
    return run_query("SELECT position_id, status, product_sku FROM locations", fetch_data=True)

def get_free_locations():
    return run_query("SELECT position_id FROM locations WHERE status = 'Libre'", fetch_data=True)

def get_occupied_locations_by_sku(sku):
    return run_query("SELECT position_id FROM locations WHERE status = 'Ocupada' AND product_sku = ?", (sku,), fetch_data=True)

def register_movement(tipo, sku, qty, position_id):
    """
    Registra un movimiento y actualiza el estado de la ubicación.
    transactionalmente seguro (básico para sqlite).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Registrar en Historial
        cursor.execute('''
            INSERT INTO movements (date, type, sku, quantity, position_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, tipo, sku, qty, position_id))

        # 2. Actualizar Ubicación
        if tipo == "Entrada":
            cursor.execute('''
                UPDATE locations 
                SET status = 'Ocupada', product_sku = ?
                WHERE position_id = ?
            ''', (sku, position_id))
        elif tipo == "Salida":
            # Para Salida, liberamos la ubicación
            cursor.execute('''
                UPDATE locations 
                SET status = 'Libre', product_sku = NULL
                WHERE position_id = ?
            ''', (position_id))

        conn.commit()
        conn.close()
        print(f"[OK] Movimiento registrado: {tipo} {sku} en {position_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Fallo al registrar movimiento: {e}")
        st.error(f"Error al registrar: {e}")
        return False

# --- Interfaz de Usuario ---

st.title("📦 Sistema de Gestión de Almacenes (WMS)")

tab1, tab2 = st.tabs(["📝 Registrar Movimiento", "🗺️ Mapa de Almacén"])

# --- TAB 1: Registrar Movimiento ---
with tab1:
    st.header("Entradas y Salidas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        tipo_movimiento = st.radio("Tipo de Movimiento", ["Entrada", "Salida"], horizontal=True)
    
    products_df = get_products()
    
    if products_df.empty:
        st.warning("No hay productos en la base de datos.")
    else:
        # Selector de Producto
        product_list = products_df['sku'] + " - " + products_df['name']
        selected_product_str = st.selectbox("Seleccionar Producto", product_list)
        selected_sku = selected_product_str.split(" - ")[0]
        
        # Validaciones dinámicas según tipo
        if tipo_movimiento == "Entrada":
            st.info("🟢 Ingresando mercancía. Seleccione una ubicación LIBRE.")
            free_locs = get_free_locations()
            
            if free_locs.empty:
                st.error("¡No hay ubicaciones libres disponibles!")
                location_opts = []
            else:
                location_opts = free_locs['position_id'].tolist()
                
            selected_pos = st.selectbox("Ubicación Destino", location_opts)
            
        else: # Salida
            st.info("🔴 Retirando mercancía. Seleccione una ubicación donde esté el producto.")
            occupied_locs = get_occupied_locations_by_sku(selected_sku)
            
            if occupied_locs.empty:
                st.warning(f"El producto {selected_sku} no se encuentra en ninguna ubicación.")
                location_opts = []
            else:
                location_opts = occupied_locs['position_id'].tolist()
            
            selected_pos = st.selectbox("Ubicación Origen", location_opts)

        qty = st.number_input("Cantidad", min_value=1, value=1)
        
        if st.button("Confirmar Movimiento", type="primary"):
            if not selected_pos:
                st.error("Debe seleccionar una ubicación válida.")
            else:
                success = register_movement(tipo_movimiento, selected_sku, qty, selected_pos)
                if success:
                    st.success(f"Movimiento de {tipo_movimiento} realizado con éxito.")
                    # Rerun para actualizar listas
                    st.rerun()

# --- TAB 2: Mapa de Almacén ---
with tab2:
    st.header("Estado del Almacén")
    st.write("Visualización de posiciones. Verde = Libre, Rojo = Ocupada.")

    locations_df = get_locations()
    
    if not locations_df.empty:
        # Métricas rápidas
        total_pos = len(locations_df)
        free_pos = len(locations_df[locations_df['status'] == 'Libre'])
        occ_pos = total_pos - free_pos
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Posiciones", total_pos)
        m2.metric("Libres", free_pos)
        m3.metric("Ocupadas", occ_pos)

        # Estilizar el DataFrame para el mapa visual
        def color_status(val):
            color = 'background-color: #90ee90' if val == 'Libre' else 'background-color: #ffcccb' # Green vs Red
            return color

        # Mostrar tabla estilizada
        st.dataframe(
            locations_df.style.map(color_status, subset=['status']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay ubicaciones configuradas.")
