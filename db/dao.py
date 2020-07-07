from pathlib import Path
import sqlite3


class Dao:
    DB_FILE = 'db/hyper_scraper.db'

    @staticmethod
    def setup_db():
        Path('db').mkdir(parents=True, exist_ok=True)
        with sqlite3.connect('db/hyper_scraper.db') as conn:  # Creates the db
            c = conn.cursor()

            c.execute("""
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT COLLATE NOCASE UNIQUE NOT NULL
);
""")

            c.execute("""
CREATE TABLE IF NOT EXISTS store_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    location TEXT COLLATE NOCASE NOT NULL
);
""")

            c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT COLLATE NOCASE UNIQUE NOT NULL
);
""")

            c.execute("""
CREATE TABLE IF NOT EXISTS product_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_updated INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    quantity INTEGER,
    price INTEGER,
    FOREIGN KEY(product_id) REFERENCES products(id)
    FOREIGN KEY(store_id) REFERENCES stores(id),
    FOREIGN KEY(location_id) REFERENCES store_locations(id)
);
""")

            conn.commit()

    @staticmethod
    def get_store_id(store_name: str) -> int:
        """Return store ID of the given store. Inserts the store if not present."""
        store_id = -1

        with sqlite3.connect(Dao.DB_FILE) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM stores WHERE name=?', (store_name,))

            row = c.fetchone()
            if row is not None:
                store_id = row[0]
            else:
                c.execute('INSERT INTO stores(name) VALUES (?)', (store_name,))
                store_id = c.lastrowid

        return store_id

    @staticmethod
    def record_latest_product_stock(utc_epoch: int, product_name: str, store_id: int, location: str,
                                    quantity: int, price: int) -> bool:
        """Records the latest product stock. No record is inserted if nothing
        has changed. Return true if there has been a stock change or the stock
        has been recorded for the first time with greater than zero items.
        """
        stock_change = False

        with sqlite3.connect(Dao.DB_FILE) as conn:
            c = conn.cursor()

            c.execute("""
SELECT ps.id, ps.last_updated, ps.location_id, ps.quantity, ps.price
FROM product_stock AS ps
INNER JOIN store_locations AS sl ON sl.id = ps.location_id
INNER JOIN products AS p ON p.id=ps.product_id
WHERE p.name=? AND ps.store_id=? AND sl.location=?
ORDER BY ps.last_updated DESC""",
                      (product_name, store_id, location))
            row_product_stock = c.fetchone()

            if row_product_stock is None:
                # Record new product

                # Store
                c.execute('SELECT id FROM store_locations WHERE store_id=? AND location=?',
                          (store_id, location))
                loc_id = -1
                row_loc = c.fetchone()
                if row_loc is not None:
                    loc_id = row_loc[0]
                else:
                    c.execute('INSERT INTO store_locations(store_id, location) VALUES (?, ?)',
                              (store_id, location))
                    loc_id = c.lastrowid

                # Product
                c.execute('SELECT id FROM products WHERE name=?', (product_name,))
                product_id = -1
                row_products = c.fetchone()
                if row_products is not None:
                    product_id = row_products[0]
                else:
                    c.execute('INSERT INTO products(name) VALUES (?)', (product_name,))
                    product_id = c.lastrowid

                # Product stock
                c.execute('INSERT INTO product_stock(last_updated, product_id, store_id, '
                          'location_id, quantity, price) VALUES (?, ?, ?, ?, ?, ?)',
                          (utc_epoch, product_id, store_id, loc_id,
                           quantity, price))

                if quantity > 0:
                    stock_change = True

            else:
                # Check old product
                loc_id = row_product_stock[2]
                old_quantity = row_product_stock[3]
                old_price = row_product_stock[4]
                if quantity != old_quantity or price != old_price:
                    # Something changed, add new entry
                    c.execute('SELECT id FROM products WHERE name=?', (product_name,))
                    row_products = c.fetchone()
                    assert row_products is not None
                    product_id = row_products[0]
                    c.execute('INSERT INTO products(last_updated, product_id, store_id, location_id, '
                              'quantity, price) VALUES(?, ?, ?, ?, ?, ?)',
                              (utc_epoch, product_id, store_id, loc_id, quantity, price))
                    stock_change = True

                else:
                    # Nothing new
                    assert stock_change is False

        return stock_change

    @staticmethod
    def products_in_stock():
        """Find all products that are currently in stock."""

        with sqlite3.connect(Dao.DB_FILE) as conn:
            c = conn.cursor()

            c.execute("""
SELECT datetime(ps.last_updated, 'unixepoch'), s.name, sl.location, p.name, ps.price, ps.quantity
FROM product_stock AS ps
INNER JOIN stores AS s ON s.id=ps.store_id
INNER JOIN store_locations AS sl ON sl.id = ps.location_id
INNER JOIN products AS p ON p.id=ps.product_id
INNER JOIN (
    SELECT id, max(last_updated)
    FROM product_stock
    GROUP BY store_id, location_id, product_id) latest_stock ON latest_stock.id=ps.id
WHERE ps.quantity != 0
ORDER BY s.name, sl.location, p.name""")

            for row in c.fetchall():
                timestamp = row[0]
                store = row[1]
                location = row[2]
                product = row[3]
                price = row[4]
                quantity = row[5]

                print('[{}] {}, {} - {}: {} @ ${}'.format(timestamp, store, location, product, quantity, price))
