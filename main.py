#!/usr/bin/env python3

from scrapy.crawler import CrawlerProcess
from hyper_scraper.spiders.walmart_spider import WalmartNintendoSwitchSpider
from pathlib import Path
import sqlite3


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


if __name__ == '__main__':
    setup_db()

    process = CrawlerProcess()
    process.crawl(WalmartNintendoSwitchSpider)
    process.start()
