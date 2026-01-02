from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import pandas as pd
import os
import sys

# Ensure root directory is in sys.path to import init_db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from init_db import init_db
except ImportError:
    # Fail silently or log if not found (dev vs prod structures)
    print("Warning: init_db not found")

app = FastAPI()

DB_NAME = "wms.db"

@app.on_event("startup")
def startup_event():
    if not os.path.exists(DB_NAME):
        print("Database not found. Initializing...")
        try:
            init_db()
        except NameError:
            pass # init_db import failed


def run_query(query, params=(), fetch_columns=False):
    """Executes query and returns list of dicts if fetch_columns=True"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row # Return rows as dict-like
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_columns:
            data = cursor.fetchall()
            result = [dict(row) for row in data]
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        print(f"[ERROR] DB Error: {e}")
        return None

# --- API Endpoints ---

@app.get("/api/dashboard-stats")
def get_dashboard_stats():
    # 1. Total Products
    products = run_query("SELECT COUNT(*) as count FROM products", fetch_columns=True)
    total_skus = products[0]['count'] if products else 0

    # 2. Locations Status
    locs = run_query("SELECT status FROM locations", fetch_columns=True)
    total_locs = len(locs)
    occupied = len([l for l in locs if l['status'] == 'Ocupada'])
    
    occupancy_rate = f"{(occupied / total_locs * 100):.1f}%" if total_locs > 0 else "0%"

    # 3. Movements Today (Mocking 'today' as total for simplicity in prototype)
    moves = run_query("SELECT COUNT(*) as count FROM movements", fetch_columns=True)
    today_moves = moves[0]['count'] if moves else 0

    return [
        {"title": "Total SKUs", "value": str(total_skus), "change": "+0%", "icon": "Box", "color": "bg-blue-500"},
        {"title": "Ocupación", "value": occupancy_rate, "change": "+2%", "icon": "Map", "color": "bg-emerald-500"},
        {"title": "Movimientos", "value": str(today_moves), "change": "Active", "icon": "TrendingUp", "color": "bg-purple-500"}
    ]

@app.get("/api/recent-moves")
def get_recent_moves():
    query = """
        SELECT m.id, m.type, m.sku, p.name, m.quantity as qty, m.date as time, 'Admin' as user 
        FROM movements m
        JOIN products p ON m.sku = p.sku
        ORDER BY m.id DESC LIMIT 5
    """
    return run_query(query, fetch_columns=True)

@app.get("/api/warehouse-map")
def get_warehouse_map():
    # Fetch real locations from DB
    locs = run_query("SELECT position_id as id, status, product_sku as product FROM locations", fetch_columns=True)
    
    # Transform for Frontend (add 'occupied' boolean)
    result = []
    if locs:
        for l in locs:
            result.append({
                "id": l['id'],
                "occupied": l['status'] == 'Ocupada',
                "product": l['product']
            })
    return result

# --- Movement Registration API ---

class MovementRequest(BaseModel):
    type: str # 'Entrada' or 'Salida'
    sku: str
    quantity: int
    position_id: str

@app.get("/api/products")
def get_products_list():
    return run_query("SELECT sku, name, category FROM products", fetch_columns=True)

@app.get("/api/available-locations")
def get_available_locations(status: str = 'Libre'):
    """Status can be 'Libre' or 'Ocupada'"""
    query = "SELECT position_id, product_sku FROM locations WHERE status = ?"
    return run_query(query, (status,), fetch_columns=True)

@app.post("/api/register-movement")
def api_register_movement(move: MovementRequest):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Validation (Basic)
        if move.type == 'Entrada':
            # Check if location is free
            loc = cursor.execute("SELECT status FROM locations WHERE position_id = ?", (move.position_id,)).fetchone()
            if not loc or loc[0] != 'Libre':
                raise HTTPException(status_code=400, detail="Location is not free")
        elif move.type == 'Salida':
            # Check if product is there
            loc = cursor.execute("SELECT product_sku FROM locations WHERE position_id = ?", (move.position_id,)).fetchone()
            if not loc or loc[0] != move.sku:
                 raise HTTPException(status_code=400, detail="Product not at this location")

        # 2. Insert Movement
        cursor.execute('''
            INSERT INTO movements (date, type, sku, quantity, position_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, move.type, move.sku, move.quantity, move.position_id))

        # 3. Update Location
        if move.type == "Entrada":
            cursor.execute('''
                UPDATE locations SET status = 'Ocupada', product_sku = ? WHERE position_id = ?
            ''', (move.sku, move.position_id))
        elif move.type == "Salida":
            cursor.execute('''
                UPDATE locations SET status = 'Libre', product_sku = NULL WHERE position_id = ?
            ''', (move.position_id,))

        conn.commit()
        conn.close()
        return {"message": "Movement registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Static Files (Frontend) ---
@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')
