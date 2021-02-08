#!/usr/bin/env python3
import scrapy
import json
from lxml import html
from time import strftime, mktime
from notifs import slack
from pathlib import Path
from db.dao import Dao
from utils import strip_html


class WalmartNintendoSwitchSpider(scrapy.Spider):
    name = 'walmart_nintendo_switch'

    @staticmethod
    def _loc_url(zip_code: str) -> str:
        return 'https://www.walmart.ca/api/product-page/geo-location?postalCode=' + zip_code

    @staticmethod
    def _available_stock_url(latitude: str, longitude: str, upc: str) -> str:
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

        with open(logfile, 'a') as f:
            for i, loc in enumerate(data['info']):
                location = loc['displayName'] + ', ' + loc['intersection']
                quantity = availStatusToQuantity[loc['availabilityStatus']]
                price = float(loc['sellPrice'])
                msg = '{}: {} - price ${}, availability {}\n'.format(product_name,
                                                                     location,
                                                                     price,
                                                                     loc['availabilityStatus'])

                store_id = response.meta['db']['store_id']
                is_change = Dao.record_latest_product_stock(start_time_epoch, product_name, store_id,
                                                            location, quantity, price)
                if is_change:
                    slack.send_message(msg)

                f.write(msg)

            status_msg = '{}: found {} locations, saved in {}'.format(product_name, i + 1, logfile)
            self.log(status_msg)
            slack.send_health_message(status_msg)
