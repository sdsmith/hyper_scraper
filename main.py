#!/usr/bin/env python3

from scrapy.crawler import CrawlerProcess
from hyper_scraper.spiders.walmart_spider import WalmartNintendoSwitchSpider
from db.dao import Dao

if __name__ == '__main__':
    Dao.setup_db()

    process = CrawlerProcess()
    process.crawl(WalmartNintendoSwitchSpider)
    process.start()
