import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "wms.db"

def get_connection():
    """Crea y retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
    return conn

def init_db():
    """Inicializa la estructura de la base de datos."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Productos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        categoria TEXT
    )
    ''')
    
    # Tabla de Ubicaciones
    # estado: 'Disponible', 'Ocupada'
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ubicaciones (
        id TEXT PRIMARY KEY,
        estado TEXT DEFAULT 'Disponible',
        sku_producto TEXT,
        FOREIGN KEY (sku_producto) REFERENCES productos (sku)
    )
    ''')
    
    # Tabla de Movimientos (Historial - Opcional pero recomendado para tracking)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT, -- 'ENTRADA', 'SALIDA'
        sku_producto TEXT,
        ubicacion_id TEXT,
        usuario TEXT
    )
    ''')

    conn.commit()
    conn.close()

def crear_ubicaciones_ejemplo(cantidad=20):
    """Crea ubicaciones de la A-01 a la A-XX si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for i in range(1, cantidad + 1):
        ubicacion_id = f"A-{i:02d}" # A-01, A-02...
        try:
            cursor.execute("INSERT INTO ubicaciones (id, estado) VALUES (?, 'Disponible')", (ubicacion_id,))
        except sqlite3.IntegrityError:
            pass # Ya existe
            
    conn.commit()
    conn.close()

# --- Funciones de Productos ---

def registrar_producto(sku, nombre, descripcion="", categoria="General"):
    """Registra un nuevo producto en el catálogo."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO productos (sku, nombre, descripcion, categoria)
            VALUES (?, ?, ?, ?)
        ''', (sku, nombre, descripcion, categoria))
        conn.commit()
        return True, "Producto registrado con éxito."
    except sqlite3.IntegrityError:
        return False, "Error: El SKU ya existe."
    except Exception as e:
        return False, f"Error desconocido: {e}"
    finally:
        conn.close()

def buscar_producto_catalogo(query=""):
    """Busca productos por nombre o SKU."""
    conn = get_connection()
    query = f"%{query}%"
    df = pd.read_sql_query('''
        SELECT * FROM productos 
        WHERE sku LIKE ? OR nombre LIKE ?
    ''', conn, params=(query, query))
    conn.close()
    return df

def obtener_todos_productos():
    """Retorna lista de todos los productos (SKU y Nombre) para dropdowns."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sku, nombre FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return [dict(p) for p in productos]

# --- Funciones de Ubicaciones y Movimientos ---

def obtener_estado_almacen():
    """Retorna un DataFrame con el estado de todas las ubicaciones y info del producto si está ocupada."""
    conn = get_connection()
    query = '''
        SELECT 
            u.id as Ubicacion, 
            u.estado as Estado, 
            u.sku_producto as SKU,
            p.nombre as Producto,
            p.categoria as Categoria
        FROM ubicaciones u
        LEFT JOIN productos p ON u.sku_producto = p.sku
        ORDER BY u.id ASC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def obtener_ubicaciones_disponibles():
    """Retorna lista de IDs de ubicaciones disponibles."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ubicaciones WHERE estado = 'Disponible'")
    ubicaciones = [row['id'] for row in cursor.fetchall()]
    conn.close()
    return ubicaciones

def obtener_ubicaciones_ocupadas():
    """Retorna lista de IDs de ubicaciones ocupadas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ubicaciones WHERE estado = 'Ocupada'")
    ubicaciones = [row['id'] for row in cursor.fetchall()]
    conn.close()
    return ubicaciones

def registrar_entrada(sku, ubicacion_id, usuario="Admin"):
    """Mueve un producto a una ubicación. Valida disponibilidad."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar estado actual de la ubicación
        cursor.execute("SELECT estado FROM ubicaciones WHERE id = ?", (ubicacion_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, "Ubicación no existe."
        
        if resultado['estado'] == 'Ocupada':
            return False, f"La ubicación {ubicacion_id} ya está ocupada."
            
        # Actualizar ubicación
        cursor.execute('''
            UPDATE ubicaciones 
            SET estado = 'Ocupada', sku_producto = ?
            WHERE id = ?
        ''', (sku, ubicacion_id))
        
        # Registrar movimiento
        cursor.execute('''
            INSERT INTO movimientos (tipo, sku_producto, ubicacion_id, usuario)
            VALUES ('ENTRADA', ?, ?, ?)
        ''', (sku, ubicacion_id, usuario))
        
        conn.commit()
        return True, f"Entrada exitosa: {sku} en {ubicacion_id}"
        
    except Exception as e:
        conn.rollback()
        return False, f"Error en base de datos: {e}"
    finally:
        conn.close()

def registrar_salida(ubicacion_id, usuario="Admin"):
    """Libera una ubicación (Despacho)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar info actual
        cursor.execute("SELECT estado, sku_producto FROM ubicaciones WHERE id = ?", (ubicacion_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, "Ubicación no existe."
        
        if resultado['estado'] == 'Disponible':
            return False, "La ubicación ya está vacía."
            
        sku_anterior = resultado['sku_producto']
        
        # Actualizar ubicación
        cursor.execute('''
            UPDATE ubicaciones 
            SET estado = 'Disponible', sku_producto = NULL
            WHERE id = ?
        ''', (ubicacion_id,))
        
        # Registrar movimiento
        cursor.execute('''
            INSERT INTO movimientos (tipo, sku_producto, ubicacion_id, usuario)
            VALUES ('SALIDA', ?, ?, ?)
        ''', (sku_anterior, ubicacion_id, usuario))
        
        conn.commit()
        return True, f"Salida exitosa: {sku_anterior} despachado de {ubicacion_id}"
        
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()
