import scrapy
import json
from lxml import html
from time import gmtime, strftime
        
def strip_html(s):
    return str(html.fromstring(s).text_content())

def walmart_loc_url(zip_code: str) -> str:
    return 'https://www.walmart.ca/api/product-page/geo-location?postalCode=' + zip_code

def walmart_available_stock_url(latitude: str, longitude: str, upc: str) -> str:
    return 'https://www.walmart.ca/api/product-page/find-in-store?latitude={}&longitude={}&lang=en&upc={}'.format(latitude, longitude, upc)

class WalmartNintendoSwitchSpider(scrapy.Spider):
    name = 'walmart_nintendo_switch'

    _latitude = ""
    _longitude = ""

    def start_requests(self):
        # TODO(sdsmith): only do the loc call if it has changed!
        yield scrapy.Request(url=walmart_loc_url('L7T1X4'), callback=self.parse_loc, meta={'start_gmtime': gmtime()})

    def parse_loc(self, response):
        data = json.loads(response.body)
        latitude = data['lat']
        longitude = data['lng']

        urls = [
            'https://www.walmart.ca/en/ip/nintendo-switch-with-neon-blue-and-neon-red-joycon-nintendo-switch/6000200280557',
            'https://www.walmart.ca/en/ip/nintendo-switch-with-gray-joycon-nintendo-switch/6000200280830'
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_product_page, meta={'start_gmtime': response.meta['start_gmtime'],
                                                                                  'latitude': latitude,
                                                                                  'longitude': longitude})

    def parse_product_page(self, response):
        latitude = response.meta['latitude']
        longitude = response.meta['longitude']

        product_name = response.xpath('//h1[@data-automation="product-title"]/text()').get()
        
        text = strip_html(response.css('body script:first-of-type').getall()[1])
        start_js = 'window.__PRELOADED_STATE__='
        if text.find(start_js) != 0:
            print("JS start is not found!")
            assert false
        text = text[len(start_js):-1]
        data = json.loads(text)

        skus_data = data['entities']['skus']
        upc = skus_data[list(skus_data)[0]]['upc'][0]

        yield scrapy.Request(url=walmart_available_stock_url(latitude, longitude, upc),
                             callback=self.parse_available_stock,
                             meta={'start_gmtime': response.meta['start_gmtime'],
                                   'product_name': product_name})

    def parse_available_stock(self, response):
        data = json.loads(response.body)

        filename = self.name + '_' + strftime("%Y-%m-%d_%H:%M:%S_UTC", response.meta['start_gmtime']) + '.log'
        with open(filename, 'a') as f:
            for i, loc in enumerate(data['info']):
                f.write('{}: {} at {} - price ${}, availability {}\n'.format(response.meta['product_name'],
                                                                             loc['displayName'],
                                                                             loc['intersection'],
                                                                             loc['sellPrice'],
                                                                             loc['availabilityStatus']))

        self.log('Found {} locations, saved in {}'.format(i + 1, filename))
