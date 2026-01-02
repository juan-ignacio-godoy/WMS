import database as db
import os

def run_tests():
    print("----- INICIANDO PRUEBAS DE LÓGICA WMS -----")
    
    # 1. Verificar inicialización
    print("[TEST 1] Verificando ubicaciones...")
    locs = db.obtener_estado_almacen()
    if len(locs) >= 20:
        print(f"✅ Se encontraron {len(locs)} ubicaciones.")
    else:
        print(f"❌ ERROR: Solo se encontraron {len(locs)} ubicaciones.")
        
    # 2. Registrar Producto
    print("[TEST 2] Registrando producto de prueba...")
    sku = "TEST-999"
    nombre = "Producto Prueba Auto"
    
    # Limpiar si existe de pruebas anteriores
    conn = db.get_connection()
    conn.execute("DELETE FROM productos WHERE sku = ?", (sku,))
    conn.execute("UPDATE ubicaciones SET estado='Disponible', sku_producto=NULL WHERE sku_producto = ?", (sku,))
    conn.commit()
    conn.close()
    
    success, msg = db.registrar_producto(sku, nombre)
    if success:
         print(f"✅ Producto registrado: {msg}")
    else:
         print(f"❌ Error registrando producto: {msg}")

    # 3. Flujo de Entrada
    print("[TEST 3] Realizando entrada en A-01...")
    # Asegurar que A-01 esté libre
    conn = db.get_connection()
    conn.execute("UPDATE ubicaciones SET estado='Disponible', sku_producto=NULL WHERE id='A-01'")
    conn.commit()
    conn.close()
    
    success, msg = db.registrar_entrada(sku, "A-01")
    if success:
        print(f"✅ Entrada exitosa: {msg}")
    else:
        print(f"❌ Error en entrada: {msg}")
        
    # Verificar que A-01 está ocupada
    df = db.obtener_estado_almacen()
    a01 = df[df['Ubicacion'] == 'A-01'].iloc[0]
    if a01['Estado'] == 'Ocupada' and a01['SKU'] == sku:
        print("✅ Verificación de estado: A-01 está Ocupada con TEST-999.")
    else:
        print(f"❌ Error: El estado de A-01 no es correcto. Estado: {a01['Estado']}, SKU: {a01['SKU']}")

    # 4. Flujo de Salida
    print("[TEST 4] Realizando salida de A-01...")
    success, msg = db.registrar_salida("A-01")
    if success:
        print(f"✅ Salida exitosa: {msg}")
    else:
        print(f"❌ Error en salida: {msg}")

    # Verificar que A-01 está libre
    df = db.obtener_estado_almacen()
    a01 = df[df['Ubicacion'] == 'A-01'].iloc[0]
    if a01['Estado'] == 'Disponible':
         print("✅ Verificación de estado: A-01 está nuevamente Disponible.")
    else:
         print(f"❌ Error: A-01 sigue ocupada.")

    print("----- PRUEBAS FINALIZADAS -----")

if __name__ == "__main__":
    run_tests()
