#!/usr/bin/env python3
import scrapy
import json
from lxml import html
from time import gmtime, strftime
from notifs import slack
from pathlib import Path
from utils import strip_html


class BestbuyNintendoSwitchSpider(scrapy.Spider):
    name = 'bestbuy_nintendo_switch'
    handle_httpstatus_list = [415]
    
    @staticmethod
    def _loc_url(postal_code: str) -> str:
        # postalCode only takes the first 3 digits of the postal code
        return 'https://www.bestbuy.ca/api/v2/json/locations?lang=en-CA&postalCode=' + postal_code[:3]
    
    @staticmethod
    def _available_stock_url(location_ids: [str], postal_code: str, sku: str) -> str:
        locations = '|'.join(location_ids)
    
        return 'https://www.bestbuy.ca/ecomm-api/availability/products?accept=application/'\
            'vnd.bestbuy.standardproduct.v1+json&accept-language=en-CA&'\
            'locations={}&postalCode={}&skus={}'.format(locations, postal_code[:3], sku)
    
    @staticmethod
    def _get_sku_from_product_url(url: str) -> str:
        # It's the last thing in the url
        # ex: https://www.bestbuy.ca/en-ca/product/nintendo-switch-console-with-neon-red-blue-joy-con/13817625
        return url.split('/')[-1]
    
    def start_requests(self):
        slack.send_health_message('Starting Bestbuy check...')
        postal_code = 'L7T1X4'
        yield scrapy.Request(url=self._loc_url(postal_code), callback=self.parse_loc, meta={'start_gmtime': gmtime(),
                                                                                            'postal_code': postal_code})

    def parse_loc(self, response):
        data = json.loads(response.body)

        location_info = {}  # loc_ids:info
        for loc in data['locations']:
            loc_id = loc['locationId']
            location_info[loc_id] = loc

        urls = [
            'https://www.bestbuy.ca/en-ca/product/nintendo-switch-console-with-neon-red-blue-joy-con/13817625',
            'https://www.bestbuy.ca/en-ca/product/nintendo-switch-console-with-grey-joy-con/13817626'
        ]
        for url in urls:
            sku = self._get_sku_from_product_url(url)

            yield scrapy.Request(url=url,
                                 callback=self.parse_product_page,
                                 meta={'start_gmtime': response.meta['start_gmtime'],
                                       'postal_code': response.meta['postal_code'],
                                       'location_info': location_info,
                                       'sku': sku})

    def parse_product_page(self, response):
        product_name = response.xpath('//div[contains(@class, "x-product-detail-page")]/h1/text()').get()
        price = response.xpath('//meta[@itemProp="price"]/@content').get()

        req = scrapy.Request(url=self._available_stock_url(response.meta['location_info'].keys(),
                                                           response.meta['postal_code'],
                                                           response.meta['sku']),
                             callback=self.parse_available_stock,                             
                             headers={'Host': 'www.bestbuy.ca',
                                      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0',
                                      'Accept': '*/*',
                                      'Accept-Encoding': 'gzip, deflate, br',
                                      'Accept-Language': 'en-US,en;q=0.5',
                                      'Referer': 'https://www.bestbuy.ca/en-ca/product/nintendo-switch-console-with-neon-red-blue-joy-con/13817625',
                                      'DNT': '1',
                                      'Connection': 'close',
                                      # 'Cache-Control': 'max-age=0, no-cache',                                      
                                      # 'TE': 'Trailers',
                                      #'Pragma': 'no-cache'
                             },
                             meta={'dont_merge_cookies': True,
                                   'start_gmtime': response.meta['start_gmtime'],
                                   'product_name': product_name,
                                   'price': price})
        print('STEWART:\n\theader: ' + str(req.headers) + '\n\tbody: ' + req.body.decode('utf-8'))
        yield req
        
        # yield scrapy.Request(url=self._available_stock_url(response.meta['location_info'].keys(),
        #                                                    response.meta['postal_code'],
        #                                                    response.meta['sku']),
        #                      callback=self.parse_available_stock,
        #                      headers={'Accept': '*/*'},
        #                      meta={'dont_merge_cookies': True,
        #                            'start_gmtime': response.meta['start_gmtime'],
        #                            'product_name': product_name,
        #                            'price': price})

    def parse_available_stock(self, response):
        # DEBUG(sdsmith): 
        print('STEWART: request headers: ' + str(response.request.headers))
        if response.status != 200:
            exit(1)

        data = json.loads(response.body)
        product_name = response.meta['product_name']
        
        Path('logs').mkdir(parents=True, exist_ok=True)
        filename = 'logs/' + self.name + '_' + strftime("%Y-%m-%d_%H:%M:%S_UTC", response.meta['start_gmtime']) + '.log'
        msg = ''
        with open(filename, 'a') as f:
            for product in data['availabilities']:
                pickup = product['pickup']
                if pickup['status'] != 'OutOfStock':
                    for loc in pickup['locations']:
                        quantity = loc['quantityOnHand']
                        if quantity > 0:
                            loc_info = response.meta['location_info'][loc['locationKey']]

                            loc_name = loc_info['name']
                            loc_addr = loc_info['address1']
                            if loc_info['address2']:
                                loc_addr += ' ' + loc_info['address2']
                            loc_addr += ', ' + loc_info['city']

                            msg = '{}: {} at {} - price ${}, availability {}\n'.format(product_name,
                                                                                       loc_name,
                                                                                       loc_addr,
                                                                                       response.meta['price'],
                                                                                       quantity)

                            slack.send_message(msg)
                else:
                    msg = '{}: Bestbuys are out of stock'.format(response.meta['product_name'])

            f.write(msg)

        status_msg = '{}: found {} locations, saved in {}'.format(product_name, len(response.meta['location_info']), filename)
        self.log(status_msg)
        slack.send_health_message(status_msg)
