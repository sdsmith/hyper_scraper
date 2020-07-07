#!/usr/bin/env python3

import sys
from scrapy.crawler import CrawlerProcess
from hyper_scraper.spiders.walmart_spider import WalmartNintendoSwitchSpider
from db.dao import Dao
from notifs import slack


if __name__ == '__main__':
    Dao.setup_db()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'stock':
            s = Dao.products_in_stock()
            slack.send_message(s)
            print(s)
            exit(0)
        else:
            print('Usage: main.py [stock]')
            exit(1)

    process = CrawlerProcess()
    process.crawl(WalmartNintendoSwitchSpider)
    process.start()
