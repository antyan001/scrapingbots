import logging
logging.basicConfig(filename='./__avitoparse__.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options, DesiredCapabilities
from selenium.webdriver.common.proxy import Proxy, ProxyType

import socket
import socks
import urllib
import requests
from urllib.request import urlopen 
from requests.adapters import HTTPAdapter
from requests import ConnectionError, HTTPError, Timeout
from requests.packages.urllib3.util.retry import Retry
import asyncio
from proxybroker import Broker
from bs4 import BeautifulSoup

import csv
import sys
import os
import re
import random
import shutil
import base64
import pandas as pd
import numpy as np
import tqdm
from tqdm import tqdm
from tqdm import tqdm_notebook
from PIL import Image
from pathlib import Path
from time import sleep
from collections import OrderedDict
from fake_useragent import UserAgent
import traceback
import dateparser
from datetime import datetime, timedelta

# import pytesseract
# from pytesseract import image_to_string
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"


class ProxyGet():

    def get_random_proxy(self):
        """
        Get random proxy from 'proxies.txt'.
        """
        lines = open('proxies.txt').read().splitlines()
        rproxy =random.choice(lines)
        if rproxy.startswith('https'):
            proxydict={'https': rproxy}
        else:
            proxydict={'http': rproxy}
        PROXYLST =  rproxy.split('//')[-1].split(':')
        return proxydict, PROXYLST
    
    async def save(self,proxies, filename):
        """Save proxies to a file."""
        with open(filename, 'a') as f:
            while True:
                proxy = await proxies.get()
                if proxy is None:
                    break
                # Check accurately if the proxy is working.
                if (proxy.is_working) and (proxy.avg_resp_time <=2.):
                    proto = 'https' if 'HTTPS' in proxy.types else 'http'
                    row = '%s://%s:%d\n' % (proto, proxy.host, proxy.port)
                    f.write(row)


    def collect_proxies(self):
        proxies = asyncio.Queue()
        broker = Broker(proxies)
        tasks = asyncio.gather(broker.find(types=['HTTP','HTTPS'], countries=['RU'], limit=200),
                               self.save(proxies, filename='proxies.txt'))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)
        #loop.close()


class AvitoBot(ProxyGet):
    
    def __init__(self,args):        
        if args.driver == 'Chrome':
            
            self.ua = UserAgent()
            user_agent = self.ua.random            
            self.headers =  {  'user-agent': user_agent,
                               'referrer': 'https://m.avito.ru',
                               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                               'Accept-Encoding': 'gzip, deflate, br',
                               'Accept-Language': 'en-US,en;q=0.9',
                               'Pragma': 'no-cache'  } 
            
            self.useproxy             = args.useproxy
            self.usesocks             = args.usesocks
            
            chrome_options = Options()
            chrome_options.binary_location = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
            if self.useproxy:
                self.proxyDict            = args.proxyDict
                proxy_address, proxy_port = args.proxylst                
                chrome_options.add_argument('--proxy-server=%s:%s' % (proxy_address, proxy_port))
            else:
                self.proxyDict  = None
            chrome_options.headless = args.headless
            prefs = {"profile.managed_default_content_settings.images":2}
            chrome_options.add_experimental_option("prefs",prefs)
            chrome_options.add_argument(f'user-agent={user_agent}')

#             prox = Proxy()
#             prox.proxy_type = ProxyType.MANUAL
#             prox.http_proxy = '193.34.93.221:42112' #"%s:%i" %(proxy_address, int(proxy_port))
#             capabilities = webdriver.DesiredCapabilities.CHROME
#             prox.add_to_capabilities(capabilities)
            
#             capabilities = dict( DesiredCapabilities.CHROME )         
#             capabilities['proxy'] = {
#                 'httpProxy'  : "%s:%i" %(proxy_address, int(proxy_port)),
#                 #'ftpProxy'  : "%s:%i" %(proxy_address, proxy_port),
#                 #'sslProxy'  : "%s:%i" %(proxy_address, proxy_port),
#                 'noProxy'    : None,
#                 'proxyType'  : "MANUAL",
#                 'class'      : "org.openqa.selenium.Proxy",
#                 'autodetect' : False
#             }            
            
#             self.driver = webdriver.Chrome(chrome_options=options, 
#                                            executable_path="C:\\chromedriver\\chromedriver.exe",
#                                            desired_capabilities=capabilities)
            self.driver = webdriver.Chrome(options=chrome_options, 
                                           executable_path="C:\\chromedriver\\chromedriver.exe")
    
        elif args.driver=='Firefox':
            self.driver = webdriver.Firefox(executable_path="C:\\geckodriver\\geckodriver.exe")
        else:
            self.driver = webdriver.PhantomJS(executable_path='C:\\phantomjs\\bin')
        
        
        
        #***************************************************************************************
        self.userdict       = {0:'all', 1:'sobstvennik', 2:'agentstvo'}
        self.savepath       = Path.joinpath(Path(os.getcwd()), 'screenshots')
        self.savecsv        = Path.joinpath(Path(os.getcwd()), 'csv')
        self.takescreenshot = args.takescreenshot
        self.headless       = args.headless
        self.parsemobile    = args.parsemobile
        self.runparallel    = args.runparallel
        self.usertype       = args.usertype
        self.get_wall_soup  = args.get_wall_soup
        self.adv_scrap_soup = args.adv_scrap_soup
        self.findnewadvs, self.daysback    = args.findnewadvs['findnewadvs'], args.findnewadvs['daysback']
        self.marketplace, self.region, self.real_estate      = args.url.split('/')[2:5]
        #***************************************************************************************
    
    def remdirs(self):
        if os.path.isdir(self.savepath) or os.path.isdir(self.savecsv):
            shutil.rmtree(self.savepath)
            shutil.rmtree(self.savecsv)
        if (not os.path.isdir(self.savepath)) and (not os.path.isdir(self.savecsv)):
            os.makedirs(self.savepath)
            os.makedirs(self.savecsv)        
    
    def cleardirs(self):
        folders=[str(self.savepath),str(self.savecsv)]
        for folder in folders:
            for the_file in os.listdir(folder):
                file_path = os.path.join(folder, the_file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    #elif os.path.isdir(file_path): shutil.rmtree(file_path)
                except Exception as e:
                    print(e)        
            
    def take_screenshot(self):        
        if os.path.isdir(self.savepath):
            shutil.rmtree(self.savepath)
        os.makedirs(self.savepath)
        self.driver.save_screenshot(str(Path.joinpath(self.savepath,'screenshot.png')))
    
    def crop(self,location,size):
        x=location['x']
        y=location['y']
        width = size['width']
        height = size['height']
        image = Image.open(Path.joinpath(self.savepath,'screenshot.png'))
        image.crop((x,y,x+width,y+height)).save(Path.joinpath(self.savepath,'screenshot_crop.gif'))

    def canvas2png(self,imgbase64,savepath):
        imgstr = imgbase64.split(',')[1]
        imgdata = base64.b64decode(imgstr)
        with open(savepath, 'wb') as f:
            f.write(imgdata) 
            
    def phone_recogn(self,filetag):
        imgpng = Image.open(Path.joinpath(self.savepath,'phone_{}.png'.format(filetag)))
        phonestr = image_to_string(imgpng)
        #print('phone has been recognized as: {}'.format(phonestr))
        return phonestr
    
    #--------------------------------------------------------------------------------------------------------------
    
    def get_html_socks(self,url):
        session = requests.session()
        # Tor uses the 9150 port as the default socks port
        session.proxies = {'http' :  'socks5://127.0.0.1:9150',
                           'https': 'socks5://127.0.0.1:9150'}
        session.headers = self.headers
        # Make a request through the Tor connection
        # IP visible through Tor
        res = session.get(url).text  
        return res

    def get_html(self,url,proxyDict):
        
        self.isrepeat=True
        while self.isrepeat:        
            session = requests.session()
            if proxyDict is not None:    
                session.proxies = proxyDict
            else:
                session.proxies = None
            session.headers = self.headers        
            retry   = Retry(connect=2, backoff_factor=0.2)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)  

            try:
                r = session.get(url,timeout=50)
                self.isrepeat=False
            except (ConnectionError, HTTPError, Timeout):
                r.status_code = "Connection refused"
                print(r.status_code)          
#                 sleep(np.random.randint(10,20))
                sleep(40)
                self.random_request()
                proxyDict = self.proxyDict
               
        return r.text
    
#         if proxyDict is not None:
#             r = requests.get(url,proxies=proxyDict,headers=self.headers, timeout=150)
#         else:
#             r = requests.get(url,headers=self.headers, timeout=150)
#         return r.text

    def get_total_pages(self,html):
        soup = BeautifulSoup(html,'lxml')
        pages = soup.find('div',class_='pagination-pages').find_all('a',class_='pagination-page')[-1].get('href')
        if self.usertype == 1: # private
            total_pages = int(pages.split('&')[-4].split('=')[1])
        elif self.usertype == 2: ## agency
            total_pages = int(pages.split('&')[-4].split('=')[1])
        else: ## all
            total_pages = int(pages.split('&')[-3].split('=')[1])
        return total_pages

    def gel_wall_data_driver(self,url):
        json=[]
        self.driver.get(url) 
        # find regular advers:
        item_list = self.driver.find_elements_by_xpath('//div[@class="item_table-wrapper"]')
        if item_list!=[]:
            for item in item_list:     
                __href     = item.find_element_by_xpath('./div/div/h3/a[@class="item-description-title-link"]').get_attribute('href')
                __title    = item.find_element_by_xpath('./div/div/h3/a[@class="item-description-title-link"]').get_attribute('title')
                #__itemname = item.find_element_by_xpath('./div/div/h3/a[@class="item-description-title-link"]').text
                __data     = item.find_element_by_xpath('./div/div[@class="data"]/div[@class="js-item-date c-2"]').get_attribute('data-absolute-date')
                if self.findnewadvs:
                    if dateparser.parse(__data) >= datetime.now() - timedelta(days=self.daysback):
                        json+=[{'href':__href, 'title':__title}]
                else:
                    json+=[{'href':__href, 'title':__title}] 
        # find vip advers:
        try:
            vipadvs = self.driver.find_elements_by_xpath('//div[@class="serp-vips-item "]')
        except:
            vipadvs = self.driver.find_elements_by_xpath('//div[@class="serp-vips-item serp-vips-item_large"]')
        if vipadvs!=[]:
            for item in vipadvs:     
                __href     = item.find_element_by_xpath('./div/div/h3/a[@class="description-title-link js-item-link"]').get_attribute('href')
                __title    = item.find_element_by_xpath('./div/div/h3/a[@class="description-title-link js-item-link"]').get_attribute('title')
                __itemname = item.find_element_by_xpath('./div/div/h3/a[@class="description-title-link js-item-link"]').text
                __data     = item.find_element_by_xpath('./div/div/div/div[@class="js-item-date c-2"]').get_attribute('data-absolute-date')
                if self.findnewadvs:
                    if dateparser.parse(__data) >= datetime.now() - timedelta(days=self.daysback):
                        json+=[{'href':__href, 'title':__title}]
                else:
                    json+=[{'href':__href, 'title':__title}] 

        return json

    
    def gel_wall_data_soup(self,html):
        json=[]
        soup = BeautifulSoup(html,'lxml')
        # find regular advers:
        item_list = soup.find('div',class_='catalog-list').find_all('div',class_='item_table-wrapper')
        if item_list!=[]:
            for item in item_list:
                __href      = 'https://www.avito.ru'+item.find('a',class_='item-description-title-link').get('href')
                __title     = item.find('a',class_='item-description-title-link').get('title')
                #__itemname  = item.find('a',class_='item-description-title-link').find('span',itemprop='name').text
                #__advinfo   = item.find('div',class_='item_table-description').find('div',class_='data').text.strip()
                __data      = item.find('div',class_='js-item-date c-2').get('data-absolute-date')
                __data      = re.sub('\xa0',' ',__data.strip())   
                if self.findnewadvs:
                    if dateparser.parse(__data) >= datetime.now() - timedelta(days=self.daysback):
                        json+=[{'href':__href, 'title':__title}]
                else:
                    json+=[{'href':__href, 'title':__title}]       
        # find vip advers
        vipadvs = soup.find_all('div',class_='serp-vips-content')
        if vipadvs!=[]:
            for item in vipadvs:
                __href      = 'https://www.avito.ru'+item.find('div',class_='serp-vips-item').find('a',class_='description-title-link').get('href')
                __title     = item.find('div',class_='serp-vips-item').find('a',class_='description-title-link').get('title')
                #__itemname  = item.find('div',class_='serp-vips-item').find('a',class_='description-title-link').find('span',itemprop='name').text
                __data      = item.find('div',class_='js-item-date c-2').get('data-absolute-date')
                __data      = re.sub('\xa0',' ',__data.strip())              
                if self.findnewadvs:
                    if dateparser.parse(__data) >= datetime.now() - timedelta(days=self.daysback):
                        json+=[{'href':__href, 'title':__title}]
                else:
                    json+=[{'href':__href, 'title':__title}]
                
        return json
  
 
    def advert_collect_by_pages(self,url_string,__max,__min):
        __count=0
        url_base_part = url_string
        query_part    = 'sdam?'
        page_part     = 'p='
        maxminrange   = '&pmax={0:}&pmin={1:}'
        url_str = url_base_part+query_part+page_part+'{2:}'+maxminrange+'&user='+str(self.usertype)
#         print(url_str.format(__max,__min,1))
        try:
            if not self.usesocks:
                soup = BeautifulSoup(self.get_html(url_str.format(__max,__min,1),self.proxyDict),'lxml')
            else:
                soup = BeautifulSoup(self.get_html_socks(url_str.format(__max,__min,1)),'lxml')
            nullresult = soup.find('div',class_='nulus_catalog-page').find('h2',class_='nulus__header').text
            print(nullresult)
            json=None
        except:
            json=OrderedDict()
            print(url_str.format(__max,__min,1))
            self.isrepeat=True
            while self.isrepeat:
                try:
#                     __count+=1
                    if not self.usesocks:
                        total_pages = self.get_total_pages(self.get_html(url_str.format(__max,__min,1),self.proxyDict))
                    else:
                        total_pages = self.get_total_pages(self.get_html_socks(url_str.format(__max,__min,1)))
                    self.isrepeat = False
                except Exception as err:
#                     print('{}: find another proxy from list...'.format(__count))
#                     logger.error(err)
#                     sleep(np.random.randint(5,10))
#                     self.random_request()
#                     if __count >=2:
                    total_pages = 1
                    self.isrepeat = False                    
            print('total number of pages to be parsed is: {}'.format(total_pages))      
            for i in tqdm_notebook(range(1,total_pages+1)):
                self.isrepeat=True
                while self.isrepeat:
                    try:
                        if self.get_wall_soup: #use soup
                            if not self.usesocks:
                                wallcrawl = self.gel_wall_data_soup(self.get_html(url_str.format(__max,__min,i),self.proxyDict))
                            else: # use socks
                                wallcrawl = self.gel_wall_data_soup(self.get_html_socks(url_str.format(__max,__min,1)))
                        else: #use selenium
                            wallcrawl = self.gel_wall_data_driver(url_str.format(__max,__min,i))
                        if wallcrawl!=[]:
                            json.update({i:wallcrawl})
#                         sleep(np.random.randint(5,10))  
                        sleep(5)
                        self.isrepeat = False
                    except Exception as ex:
                        logger.error(ex)
                        if self.get_wall_soup:
                            self.random_request()
                            sleep(np.random.randint(20,40))
                        else:
                            self.closedriver()
                            sleep(np.random.randint(20,40))
                            self.restartdriver() 
                
        return json 

    def find_location_info(self,url):
        soup = BeautifulSoup(self.get_html(url,self.proxyDict),'lxml')
        loctext = soup.find('span',class_='CdyRB _3SYIM J63BQ').text        
        return loctext
        
    def find_user_info(self,url):
        file_path      = Path.joinpath(Path(os.getcwd()), 'csv', 'find_user_info_error.dat')
        try:
#             self.driver.get(url)
#             __href = 'https://m.avito.ru/'+self.driver.find_element_by_xpath('//div[@class="_3KRNu"]//*').get_attribute('href')
            soup = BeautifulSoup(self.get_html(url,self.proxyDict),'lxml')
            __href = 'https://m.avito.ru'+soup.find('a',class_='_30ro6').get('href')
            soup = BeautifulSoup(self.get_html(__href,self.proxyDict),'lxml')
            author_name = soup.find('div',class_='_3lLfq').text
            legal_type  = soup.find('div',class_='_1iCcN').find('div',class_='_2GgxK').find_all('span',class_='_2VsAk')[0].text
            reg_date    = soup.find('div',class_='_1iCcN').find('div',class_='_2GgxK').find_all('span',class_='_2VsAk')[1].text           
            fulltext = '#'.join([author_name,legal_type,reg_date])    
        except:
            self.isrepeat=True
            count=0
            while self.isrepeat:            
                try:       
    #                 soup = BeautifulSoup(self.get_html(url,self.proxyDict),'lxml')
    #                 __href = 'https://m.avito.ru'+soup.find('a',class_='_30ro6').get('href')
                    self.driver.get(__href)
                    seller_name = self.driver.find_element_by_xpath('//div[@class="_1j-_p"]').text
                    sell_type   = self.driver.find_element_by_xpath('//div[@class="abv9x"]').text
                    regdate     = self.driver.find_element_by_xpath('//div[@class="_220Sl"]').text
                    sellerinfo  = '#'.join([seller_name,sell_type,regdate])
                    sellerinfo  = re.sub('\n',' ',sellerinfo)

                    button = self.driver.find_element_by_xpath('//div[@class="_3B4dQ"]/span[@class="_2bexo"]')
                    button.click()
                    sleep(3)
                    items = self.driver.find_elements_by_xpath('//div[@class="_1PdXO"]')
                    contacts = '#'.join([item.text for item in items])
                    contacts = re.sub('\n',' ',contacts)
                except:
                    count+=1
                    if count >=3: 
                        self.isrepeat=False
                        break
                    sleep(3)
                    self.closedriver()
                    self.restartdriver()                    
#                     with open(file_path, 'a', encoding='utf8') as f:
#                         f.write(url + '\n')  
#                     fulltext = None
                    
                self.isrepeat=False
            fulltext = '#'.join([sellerinfo,contacts])
        return fulltext   
    
    #--------------------------------------------------------------------------------------------------------------
    
    def navigate(self,advjson):
        import re
        collectdata=[]
        #filetag = np.random.randint(1,1500)                    
        #self.remdirs()                
        for item in tqdm_notebook(advjson,total=len(advjson)):
            #print('parse adv #{}'.format(i))
            self.isrepeat=True
            while self.isrepeat:
                try:  
                    if not self.parsemobile:
                        self.driver.get(item['href'])
                        try:
                            button = self.driver.find_element_by_xpath('//a[@class="button item-phone-button js-item-phone-button button-origin button-origin-blue button-origin_full-width button-origin_large-extra item-phone-button_hide-phone item-phone-button_card js-item-phone-button_card"]')
                        except:
                            button = self.driver.find_element_by_xpath('//a[@class="button item-phone-button js-item-phone-button button-origin button-origin_full-width button-origin_large-extra item-phone-button_hide-phone item-phone-button_card js-item-phone-button_card"]')
                        button.click()
                        sleep(3)
                        if self.takescreenshot:
                            self.take_screenshot()         
                            image = self.driver.find_element_by_xpath('//div[@class="item-phone-big-number js-item-phone-big-number"]//*')
                            location = image.location
                            size = image.size   
                            self.crop(location,size)        
                        else:
                            image_ = self.driver.find_element_by_xpath('//div[@class="item-phone-big-number js-item-phone-big-number"]/img').get_attribute('src')
                            #fetch image and save it to png locally
                            self.canvas2png(image_,Path.joinpath(self.savepath,'phone_{}.png'.format(filetag)))
                            #recognize phone number using tesseract functionality
                            phonestr=self.phone_recogn(filetag)
                        
                        # capture adv text
                        soup = BeautifulSoup(self.get_html(item['href'],self.proxyDict),'lxml') 
                        full_text = soup.find('div',class_="item-description-text").text  
                        full_text = re.sub('\n',' ',full_text)
                    else:
                        if not self.adv_scrap_soup:
                            self.driver.get(item['href'])
                            try:  
                                # handle error if page doesn't exist
                                notexist = self.driver.find_element_by_xpath('//div[@class="_2edBr"]').text
                                print(notexist)
                                phonestr   = None
                                full_text  = None 
                                loctext    = None
                                sellerinfo = None
                            except:                                
                                # advert is still active and page exists
                                # capture phone number
                                __phone = self.driver.find_element_by_xpath('//div[@class="_1DzgK"]//*').get_attribute('href')
                                if __phone is not None:
                                    phonestr = __phone.split(':')[-1]
                                else: 
                                    phonestr = None
                                # capture adv text
                                __str = self.driver.find_element_by_xpath('//div[@data-marker="item-description/text"]').text
                                if __str is not None:
                                    full_text = re.sub('\n',' ',__str)
                                else:
                                    full_text = None
#                                 loctext    = self.find_location_info(item['href'])
#                                 sellerinfo = self.find_user_info(item['href'])
                        else:
                            try:  
                                # handle error if page doesn't exist
                                soup = BeautifulSoup(self.get_html(item['href'],self.proxyDict),'lxml')
                                notexist = soup.find('div',class_="_2edBr").text
                                print(notexist)
                                phonestr   = None
                                full_text  = None 
                                loctext    = None
                                sellerinfo = None
                            except:
#                                     soup = BeautifulSoup(self.get_html(item['href'],self.proxyDict),'lxml')
                                # advert is still active and page exists
                                # capture phone number            
                                __phone = soup.find('div',class_="_1DzgK").find('a').get('href')
                                if __phone is not None:
                                    phonestr = __phone.split(':')[-1]
                                else: 
                                    phonestr = None
                                # capture adv text
                                __str = soup.find('div',class_="_1jdV1 _1jmEp").find('div').text
                                if __str is not None:
                                    full_text = re.sub('\n',' ',__str)
                                else:
                                    full_text = None                                  
                    #tmp=[full_text, phonestr, loctext, sellerinfo]
                    tmp=[full_text, phonestr]
                    if not any([v is None for v in tmp]):
                        # continue collecting adv info
#                         collectdata.append([item['href'], item['title'], full_text, phonestr, loctext, sellerinfo])
                          collectdata.append([item['href'], item['title'], full_text, phonestr]+
                                             [self.region, item['href'].split('/')[3], self.real_estate, self.userdict[self.usertype], self.marketplace])
                    else:
                        print("got some unprocessed pages...")
                        print('page: '+item['href'])
                    self.isrepeat = False
                    sleep(3)
                except Exception as err:
                    logger.error(err)
                    if self.adv_scrap_soup:
                        self.random_request()
                        sleep(np.random.randint(5,10))
                    else:
                        self.closedriver()
                        sleep(np.random.randint(5,10))
                        self.restartdriver()
 

        if not self.runparallel:   
            file_path=Path.joinpath(self.savecsv,'avito_db.csv')
            # Start writing a data-collection into csv file 
            # Check accurately if file exists.
            #if not os.path.isfile(str(file_path)):
            headers = ['href', 'title', 'full_text', 'phone', 'region', 'city', 'real_estate', 'type', 'marketplace']
            with open(file_path, 'a', encoding='utf8') as outcsv:   
                writer = csv.writer(outcsv, delimiter=',', quotechar='"', 
                                    quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
                file_is_empty = os.stat(str(file_path)).st_size == 0
                if file_is_empty:
                    writer.writerow(headers)   
                for item in collectdata:
                    writer.writerow(item)  
                        
        return collectdata
    
    def closedriver(self):
        self.driver.quit()

    def random_request(self):
        user_agent = self.ua.random            
        self.headers =  {  'user-agent': user_agent,
                           'referrer': 'https://www.reg.ru/',
                           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                           'Accept-Encoding': 'gzip, deflate, br',
                           'Accept-Language': 'en-US,en;q=0.9',
                           'Pragma': 'no-cache'  }  

        if self.useproxy:
            self.proxyDict = self.get_random_proxy()[0]
        else:
            self.proxyDict = None

    def restartdriver(self):
        #print('restarting frozen driver...')          
        # make more randomization to get fresh proxy

        user_agent = self.ua.random            
        self.headers =  {  'user-agent': user_agent,
                           'referrer': 'https://www.reg.ru/',
                           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                           'Accept-Encoding': 'gzip, deflate, br',
                           'Accept-Language': 'en-US,en;q=0.9',
                           'Pragma': 'no-cache'  }  

        chrome_options = Options()
        chrome_options.binary_location = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        if self.useproxy:
            for i in range(10):
                self.proxyDict            = self.get_random_proxy()[0]
                proxy_address, proxy_port = self.get_random_proxy()[1]
            print(proxy_address, proxy_port)                
            chrome_options.add_argument('--proxy-server=%s:%s' % (proxy_address, proxy_port))
        else:
            self.proxyDict = None
        chrome_options.headless = self.headless
        prefs = {"profile.managed_default_content_settings.images":2}
        chrome_options.add_experimental_option("prefs",prefs)
        chrome_options.add_argument(f'user-agent={user_agent}')

        self.driver = webdriver.Chrome(options=chrome_options, 
                                       executable_path="C:\\chromedriver\\chromedriver.exe")        
      
    def __del__(self):
        self.closedriver()
        print('instantiated object has been deleted')
    
    
    
    
   























