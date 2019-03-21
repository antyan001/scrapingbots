import warnings
warnings.filterwarnings('ignore')

import logging
#logging.basicConfig(level=logging.ERROR)
#logger = logging.getLogger(__name__)
logging.getLogger("selenium").setLevel(logging.CRITICAL)

from src.pars_tools import ProxyGet, AvitoBot 
import argparse
import os
import sys
import re
import joblib
from pathlib import Path
import pandas as pd
import numpy as np
import random
import tqdm
import csv
from time import sleep
from tqdm import tqdm
from collections import OrderedDict

from multiprocessing import Process, JoinableQueue
from queue import Queue
from threading import Thread
from joblib import Parallel, delayed
import time
import json


def is_interactive():
    return not hasattr(sys.modules['__main__'], '__file__')


def saver(q):
    file_path      = Path.joinpath(Path(os.getcwd()), 'csv','avito_db.csv')
    file_path_pgs  = Path.joinpath(Path(os.getcwd()), 'csv','parsed_pages.dat')
    headers = ['href', 'title', 'full_text', 'phone', 'region', 'city', 'real_estate', 'type', 'marketplace']
    #if not os.path.isfile(str(file_path)):
    with open(file_path, 'a', encoding='utf8') as outcsv:
        writer = csv.writer(outcsv, delimiter=',', quotechar='"', 
                            quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
#         writer.writerow(['href', 'title', 'full_text', 'phonestr', 'loctext', 'sellerinfo']) 
#         if not os.path.isfile(str(file_spath)):
#             writer.writerow(headers)
        file_is_empty = os.stat(str(file_path)).st_size == 0
        if file_is_empty:
            writer.writerow(headers)     
        while True:
            strfrom_q = q.get()
            if strfrom_q is None: break
            page, arrstr = strfrom_q.split('&&&')
            val = json.loads(arrstr)                    
            for item in val:
                writer.writerow(item)                    
            with open(file_path_pgs, 'a', encoding='utf8') as f:
                f.write(page + '\n')                
            q.task_done()
        # Finish up
        q.task_done()   

def parse_page(q,pagesarr):
    #q,pagesarr = arg
    #collectres = []
    #parsedpages[0][0][1]
    for page in pagesarr:  
#         print('page num#{}'.format(page))
        args.proxylst  = ProxyGet().get_random_proxy()[1]
        args.proxyDict = ProxyGet().get_random_proxy()[0]
        bot = AvitoBot(args)             
        res = bot.navigate(page[1])
        restr = json.dumps(res)
        q.put(str(page[0]) + '&&&' + restr)

        del bot
    #return collectres        
        

parser = argparse.ArgumentParser('arguments for setting driver and additional parsing options')
parser.add_argument('--driver', type=str, default='Chrome')
parser.add_argument('--headless', type=bool, default=True)   # headless mode
parser.add_argument('--url', type=str, default='https://www.avito.ru/sankt-peterburg/kvartiry/')  # pass main url for query: 'https://www.avito.ru/moskovskaya_oblast/kvartiry/'
parser.add_argument('--usertype', type=int, default=2)  # choose category: 1 - sobstvennik/private, 2 - agentstvo
parser.add_argument('--get_wall_soup', type=bool, default=True) # choose the way to grab each page: soup=>True or selenium=>False
parser.add_argument('--adv_scrap_soup', type=bool, default=True)
parser.add_argument('--findnewadvs', type=dict, default={'findnewadvs':False,'daysback':4})
parser.add_argument('--useproxy', type=bool, default=True)
parser.add_argument('--usesocks', type=bool, default=False)
parser.add_argument('--proxylst', nargs='+', default=ProxyGet().get_random_proxy()[1]) # pass proxy to selenium driver
parser.add_argument('--proxyDict', type=dict, default=ProxyGet().get_random_proxy()[0]) # pass proxy to request.get() method
parser.add_argument('--takescreenshot', type=bool, default=False)
parser.add_argument('--parsemobile', type=bool, default=True)  # parse mobile=>True/web=>False version of Avito
parser.add_argument('--runparallel', type=bool, default=True)  # run bot in parallel mode

# work-around for Jupyter notebook and IPython console
argv = [] if is_interactive() else sys.argv[1:]
args = parser.parse_args(argv)

outjson = joblib.load(Path.joinpath(Path(os.getcwd()), 'avito_links_all_sankt-peterburg_kvartiry_agentstva.json'))

for item in outjson:
    for p,v in item.items():
        for adv in v:
            adv['href']=re.sub('www','m',adv['href'])
    
parsedpages = [[(k,v) for k,v in item.items()] for item in outjson if len(item)!=0]


arr = np.arange(len(parsedpages))
num_partitions=3
batches = np.array_split(arr, num_partitions)

print('batches to be processed:')
print(batches)

for indx in tqdm(batches):
    result_queue = JoinableQueue() #Queue()
    p = Thread(target=saver, args=(result_queue,))    
    threadlst=[]
    p.start()
    # We create list of threads and pass shared queue to all of them.
    threadlst=[Thread(target=parse_page, args=(result_queue, parsedpages[i])) for i in indx]
    # Starting threads...
    print("Start: %s" % time.ctime())
    for th in threadlst:
        th.start()
    # Waiting for threads to finish execution...
    for th in threadlst:
        th.join() 
    print("End:   %s" % time.ctime())

    result_queue.put(None) # Poison pill
    p.join()  
    