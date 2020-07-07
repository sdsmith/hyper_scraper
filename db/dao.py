import sqlite3


class Dao:
    db_file = 'db/hyper_scraper.db'
    
    @staticmethod
    def get_store_id(store_name: str) -> int:
        """Return store ID of the given store. Inserts the store if not present."""
        store_id = -1

        with sqlite3.connect(Dao.db_file) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM stores WHERE name=?', (store_name,))

            row = c.fetchone()
            if row is not None:
                store_id = row[0]
            else:
                c.execute('INSERT INTO stores(name) VALUES (?)', (store_name,))
                store_id = c.lastrowid

        return store_id
