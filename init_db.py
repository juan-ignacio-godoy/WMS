import sqlite3
import os

DB_NAME = "wms.db"

def init_db():
    print(f"[INFO] Initializing database: {DB_NAME}...")
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # 1. Create PRODUCTS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT
            )
        ''')
        print("[OK] Table 'products' check/creation successful.")

        # 2. Create LOCATIONS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                position_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('Libre', 'Ocupada')),
                product_sku TEXT,
                FOREIGN KEY (product_sku) REFERENCES products (sku)
            )
        ''')
        print("[OK] Table 'locations' check/creation successful.")

        # 3. Create MOVEMENTS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                type TEXT CHECK(type IN ('Entrada', 'Salida')),
                sku TEXT,
                quantity INTEGER,
                position_id TEXT,
                FOREIGN KEY (sku) REFERENCES products (sku),
                FOREIGN KEY (position_id) REFERENCES locations (position_id)
            )
        ''')
        print("[OK] Table 'movements' check/creation successful.")

        # 4. Seed Locations (A-01 to A-20)
        # Check if locations exist first to avoid duplicates if re-run
        cursor.execute("SELECT COUNT(*) FROM locations")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("[INFO] Seeding initial locations (A-01 to A-20)...")
            locations = []
            for i in range(1, 21):
                pos_id = f"A-{i:02d}" # A-01, A-02, ...
                locations.append((pos_id, 'Libre', None))
            
            cursor.executemany("INSERT INTO locations (position_id, status, product_sku) VALUES (?, ?, ?)", locations)
            conn.commit()
            print(f"[OK] Seeded {len(locations)} locations.")
        else:
            print(f"[INFO] Locations table already has {count} entries. Skipping seed.")

        # Seed some dummy products for easier testing
        cursor.execute("SELECT COUNT(*) FROM products")
        prod_count = cursor.fetchone()[0]
        if prod_count == 0:
            print("[INFO] Seeding dummy products for testing...")
            products = [
                ('P001', 'Laptop Dell', 'Electronica'),
                ('P002', 'Monitor Samsung', 'Electronica'),
                ('P003', 'Silla de Oficina', 'Mobiliario'),
                ('P004', 'Escritorio', 'Mobiliario')
            ]
            cursor.executemany("INSERT INTO products (sku, name, category) VALUES (?, ?, ?)", products)
            conn.commit()
            print(f"[OK] Seeded {len(products)} products.")

        conn.close()
        print("[SUCCESS] Database initialization complete.")

    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")

if __name__ == "__main__":
    init_db()
