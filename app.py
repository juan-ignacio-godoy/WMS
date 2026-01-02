import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
from init_db import init_db

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="WMS Sencillo", layout="wide")
DB_NAME = "wms.db"

# --- VERIFICACIÓN ROBUSTA DE BASE DE DATOS ---
def check_database_ready():
    """
    Intenta leer la tabla 'products'. Si falla, asume que la BD no existe
    o está corrupta y ejecuta init_db().
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Intentamos una consulta simple para ver si la tabla existe
        cursor.execute("SELECT 1 FROM products LIMIT 1")
        conn.close()
        # Si llega aquí, la tabla existe.
    except (sqlite3.OperationalError, Exception):
        # Si falla (ej: no such table: products), inicializamos
        init_db()
        st.success("Base de datos creada correctamente en la nube.")

# Ejecutar verificación SIEMPRE antes de cualquier otra cosa
check_database_ready()


# --- FUNCIONES DE BASE DE DATOS ---
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

def get_inventory():
    """Calcula el stock actual sumando entradas y restando salidas."""
    query = '''
        SELECT 
            p.sku, 
            p.name, 
            p.category, 
            COALESCE(SUM(CASE WHEN m.type='Entrada' THEN m.quantity WHEN m.type='Salida' THEN -m.quantity ELSE 0 END), 0) as total_quantity
        FROM products p
        LEFT JOIN movements m ON p.sku = m.sku
        GROUP BY p.sku, p.name, p.category
    '''
    return run_query(query, fetch_data=True)


def register_movement(tipo, sku, qty, position_id):
    """
    Registra un movimiento y actualiza el estado de la ubicación.
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

# --- INTERFAZ DE USUARIO ---

st.sidebar.image("logo.png", use_container_width=True)
st.title("📦 Sistema de Gestión de Almacenes (WMS)")

tab1, tab2, tab3 = st.tabs(["📝 Registrar Movimiento", "🗺️ Mapa de Almacén", "📊 Inventario"])

# --- TAB 1: Registrar Movimiento ---
with tab1:
    st.header("Entradas y Salidas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        tipo_movimiento = st.radio("Tipo de Movimiento", ["Entrada", "Salida"], horizontal=True)
    
    products_df = get_products()
    
    # Check if dataframe is None before checking logic
    if products_df is None:
         st.error("Error crítico conectando a la base de datos.")
    elif products_df.empty:
        st.warning("No hay productos en la base de datos.")
    else:
        # Selector de Producto
        product_list = products_df['sku'] + " - " + products_df['name']
        selected_product_str = st.selectbox("Seleccionar Producto", product_list)
        if selected_product_str:
            selected_sku = selected_product_str.split(" - ")[0]
            
            # Validaciones dinámicas según tipo
            if tipo_movimiento == "Entrada":
                st.info("🟢 Ingresando mercancía. Seleccione una ubicación LIBRE.")
                free_locs = get_free_locations()
                
                if free_locs is not None and not free_locs.empty:
                    location_opts = free_locs['position_id'].tolist()
                    selected_pos = st.selectbox("Ubicación Destino", location_opts)
                else:
                    st.error("¡No hay ubicaciones libres disponibles!")
                    selected_pos = None
                    
            else: # Salida
                st.info("🔴 Retirando mercancía. Seleccione una ubicación donde esté el producto.")
                occupied_locs = get_occupied_locations_by_sku(selected_sku)
                
                if occupied_locs is not None and not occupied_locs.empty:
                    location_opts = occupied_locs['position_id'].tolist()
                    selected_pos = st.selectbox("Ubicación Origen", location_opts)
                else:
                    st.warning(f"El producto {selected_sku} no se encuentra en ninguna ubicación.")
                    selected_pos = None

            qty = st.number_input("Cantidad", min_value=1, value=1)
            
            if st.button("Confirmar Movimiento", type="primary"):
                if not selected_pos:
                    st.error("Debe seleccionar una ubicación válida.")
                else:
                    success = register_movement(tipo_movimiento, selected_sku, qty, selected_pos)
                    if success:
                        st.success(f"Movimiento de {tipo_movimiento} realizado con éxito.")
                        st.rerun()

# --- TAB 2: Mapa de Almacén ---
with tab2:
    st.header("Estado del Almacén")
    st.write("Visualización de posiciones. Verde = Libre, Rojo = Ocupada.")

    locations_df = get_locations()
    
    if locations_df is not None and not locations_df.empty:
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

# --- TAB 3: Inventario ---
with tab3:
    st.header("Stock Actual de Productos")
    
    inventory_df = get_inventory()
    
    if inventory_df is not None and not inventory_df.empty:
        # Renombrar columnas para visualización
        inventory_df.columns = ['SKU', 'Producto', 'Categoría', 'Cantidad Total']
        
        st.dataframe(
            inventory_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay información de inventario disponible.")
