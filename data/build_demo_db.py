"""Crea data/sales.db: base de demo con tiendas, productos y ventas (2026)."""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = Path(__file__).parent / "sales.db"


def build(path: Path = DB, seed: int = 11) -> Path:
    rnd = random.Random(seed)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE stores (store_id INTEGER PRIMARY KEY, store_name TEXT, region TEXT);
    CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT, category TEXT, list_price REAL);
    CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, sale_date DATE, store_id INTEGER REFERENCES stores,
                        product_id INTEGER REFERENCES products, quantity INTEGER, unit_price REAL);
    """)
    stores = [(1, "Palermo", "CABA"), (2, "Belgrano", "CABA"), (3, "Córdoba Centro", "Centro"),
              (4, "Rosario", "Litoral"), (5, "Mendoza", "Cuyo")]
    products = [(1, "Notebook Pro", "Tecnología", 1200), (2, "Monitor 27", "Tecnología", 320),
                (3, "Auriculares", "Tecnología", 75), (4, "Cafetera", "Hogar", 140),
                (5, "Freidora de aire", "Hogar", 160), (6, "Zapatillas", "Deportes", 110),
                (7, "Bicicleta", "Deportes", 650), (8, "Campera", "Moda", 130)]
    con.executemany("INSERT INTO stores VALUES (?,?,?)", stores)
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    sales, sid, d = [], 1, date(2026, 1, 1)
    while d <= date(2026, 10, 31):
        for _ in range(rnd.randint(4, 12)):
            p = rnd.choice(products)
            sales.append((sid, d.isoformat(), rnd.randint(1, 5), p[0], rnd.randint(1, 3),
                          round(p[3] * rnd.uniform(0.85, 1.0), 2)))
            sid += 1
        d += timedelta(days=1)
    con.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?)", sales)
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print("Base creada:", build())
