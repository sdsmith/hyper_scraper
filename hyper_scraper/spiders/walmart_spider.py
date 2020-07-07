#!/usr/bin/env python3
import scrapy
import json
from lxml import html
from time import strftime, mktime
from notifs import slack
from pathlib import Path
import sqlite3
from db.dao import Dao


def strip_html(s):
    return str(html.fromstring(s).text_content())


class WalmartNintendoSwitchSpider(scrapy.Spider):
    name = 'walmart_nintendo_switch'

    def _loc_url(self, zip_code: str) -> str:
        return 'https://www.walmart.ca/api/product-page/geo-location?postalCode=' + zip_code

    def _available_stock_url(self, latitude: str, longitude: str, upc: str) -> str:
        return 'https://www.walmart.ca/api/product-page/find-in-store?'\
            'latitude={}&longitude={}&lang=en&upc={}'.format(latitude, longitude, upc)

    def start_requests(self):
        store_name = 'walmart'

        slack.send_health_message('Starting Walmart check...')
        store_id = Dao.get_store_id(store_name)

        # TODO(sdsmith): only do the loc call if it has changed!
        yield scrapy.Request(url=self._loc_url('L7T1X4'), callback=self.parse_loc, meta={'db': {'store_id': store_id}})

    def parse_loc(self, response):
        data = json.loads(response.body)
        latitude = data['lat']
        longitude = data['lng']

        urls = [
            'https://www.walmart.ca/en/ip/nintendo-switch-with-neon-blue-and-neon-red-joycon-nintendo-switch/6000200280557',
            'https://www.walmart.ca/en/ip/nintendo-switch-with-gray-joycon-nintendo-switch/6000200280830'
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_product_page,
                                 meta={'latitude': latitude,
                                       'longitude': longitude,
                                       'db': response.meta['db']})

    def parse_product_page(self, response):
        latitude = response.meta['latitude']
        longitude = response.meta['longitude']

        product_name = response.xpath('//h1[@data-automation="product-title"]/text()').get().strip()

        text = strip_html(response.css('body script:first-of-type').getall()[1])
        start_js = 'window.__PRELOADED_STATE__='
        if text.find(start_js) != 0:
            self.log("JS start is not found!")
            assert False
        text = text[len(start_js):-1]
        data = json.loads(text)

        skus_data = data['entities']['skus']
        upc = skus_data[list(skus_data)[0]]['upc'][0]

        yield scrapy.Request(url=self._available_stock_url(latitude, longitude, upc),
                             callback=self.parse_available_stock,
                             meta={'product_name': product_name,
                                   'db': response.meta['db']})

    def parse_available_stock(self, response):
        data = json.loads(response.body)
        product_name = response.meta['product_name']
        start_datetime = self.crawler.stats.get_stats(self)['start_time']  # in utc
        start_time_epoch = mktime(start_datetime.timetuple())

        Path('logs').mkdir(parents=True, exist_ok=True)
        logfile = 'logs/' + self.name + '_' + strftime("%Y-%m-%d_%H:%M:%S_UTC", start_datetime.timetuple()) + '.log'

        # NOTE(sdsmith): These are totally out of the blue numbers
        availStatusToQuantity = {'OUT_OF_STOCK': 0,
                                 'LIMITED': 5,
                                 'AVAILABLE': 30}

        with sqlite3.connect('db/hyper_scraper.db') as conn:
            c = conn.cursor()

            with open(logfile, 'a') as f:
                for i, loc in enumerate(data['info']):
                    notify = False
                    location = loc['displayName'] + ', ' + loc['intersection']
                    new_quantity = availStatusToQuantity[loc['availabilityStatus']]
                    price = loc['sellPrice']
                    msg = '{}: {} - price ${}, availability {}\n'.format(product_name,
                                                                         location,
                                                                         price,
                                                                         loc['availabilityStatus'])

                    store_id = response.meta['db']['store_id']
                    c.execute('SELECT ps.id, ps.last_updated, ps.location_id, ps.quantity, ps.price FROM product_stock AS ps INNER JOIN store_locations AS sl ON sl.id = ps.location_id INNER JOIN products AS p ON p.id=ps.product_id WHERE p.name=? AND ps.store_id=? AND sl.location=? ORDER BY ps.last_updated DESC', (product_name, store_id, location))
                    row_product_stock = c.fetchone()

                    if row_product_stock is None:
                        # Record new product

                        # Store
                        c.execute('SELECT id FROM store_locations WHERE store_id=? AND location=?', (store_id, location))
                        loc_id = -1
                        row_loc = c.fetchone()
                        if row_loc is not None:
                            loc_id = row_loc[0]
                        else:
                            c.execute('INSERT INTO store_locations(store_id, location) VALUES (?, ?)', (store_id, location))
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
                        c.execute('INSERT INTO product_stock(last_updated, product_id, store_id, location_id, quantity, price)'
                                  'VALUES (?, ?, ?, ?, ?, ?)',
                                  (start_time_epoch, product_id, store_id, loc_id,
                                   new_quantity, price))

                        if loc['availabilityStatus'] != 'OUT_OF_STOCK':
                            notify = True

                    else:
                        # Check old product
                        loc_id = row_product_stock[2]
                        old_quantity = row_product_stock[3]
                        old_price = row_product_stock[4]
                        if new_quantity != old_quantity or price != old_price:
                            # Something changed, add new entry
                            c.execute('SELECT id FROM products WHERE name=?', (product_name,))
                            row_products = c.fetchone()
                            assert row_products is not None
                            product_id = row_products[0]
                            c.execute('INSERT INTO products(last_updated, product_id, store_id, location_id, '
                                      'quantity, price) VALUES(?, ?, ?, ?, ?, ?)',
                                      (start_time_epoch, product_id, store_id, loc_id,
                                       new_quantity, price))
                            notify = True

                        else:
                            # TODO(sdsmith): nothing new, don't notify
                            assert notify is False

                    if notify:
                        slack.send_message(msg)

                    f.write(msg)

            status_msg = '{}: found {} locations, saved in {}'.format(product_name, i + 1, logfile)
            self.log(status_msg)
            slack.send_health_message(status_msg)
