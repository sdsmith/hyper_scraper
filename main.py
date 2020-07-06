#!/usr/bin/env python3

from scrapy.crawler import CrawlerProcess
from hyper_scraper.spiders.walmart_spider import WalmartNintendoSwitchSpider
from pathlib import Path
import sqlite3


def setup_db():
    Path('db').mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect('db/hyper_scraper.db')  # Creates the db

    try:
        c = conn.cursor()

        c.execute("""
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT COLLATE NOCASE
);
""")

        c.execute("""
CREATE TABLE IF NOT EXISTS store_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER,
    location TEXT COLLATE NOCASE
);
""")

        c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_updated INTEGER,
    name TEXT COLLATE NOCASE,
    store_id INTEGER,
    location_id INTEGER,
    quantity INTEGER,
    price INTEGER,
    FOREIGN KEY(store_id) REFERENCES stores(id),
    FOREIGN KEY(location_id) REFERENCES store_locations(id)
);
""")

        conn.commit()

    finally:
        conn.close()


if __name__ == '__main__':
    setup_db()

    process = CrawlerProcess()
    process.crawl(WalmartNintendoSwitchSpider)
    process.start()
