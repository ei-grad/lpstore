from collections import namedtuple
from datetime import datetime, timedelta
from multiprocessing.pool import Pool
import logging
import os
import sys

import requests
import requests_cache

import ujson as json


requests_cache.install_cache('eve_cache')


class Crest():

    base_url = 'https://crest-tq.eveonline.com/'

    def __init__(self):
        self.http = requests.Session()

    def url(self, url):
        return self.base_url + url

    def get(self, url, *args, **kwargs):
        return self.http.get(self.url(url), *args, **kwargs).json()

    def get_type(self, type_id):
        return self.get('inventory/types/%s/' % type_id)

    def get_prices(self):
        return self.get('market/prices/')['items']

    def get_regions(self):
        return self.get('regions/')['items']

    def get_npc_corps(self):
        return self.get('corporations/npccorps/')['items']

    def get_history(self, region_id, type_id):
        url = 'market/%s/history/' % region_id
        type_url = self.url('inventory/types/%s/' % type_id)
        resp = self.get(url, params={'type': type_url})
        if 'items' not in resp:
            logging.warning("Can't get history for %s in %s: %s",
                            type_id, region_id, resp)
            return []
        resp['items'].sort(key=lambda x: x['date'])
        return resp['items']


crest = Crest()


BASEDIR = os.path.dirname(__file__)
PRICES = {i['type']['id']: i for i in crest.get_prices()}
REGIONS = {i['id']: i for i in crest.get_regions()}
NPC_CORPS = {
    i['id']: i
    for i in crest.get_npc_corps()
    if os.path.exists(
        os.path.join(BASEDIR, 'data', 'lpdb',
                     '%s.json' % i['id'])
    )
}


def get_corporation_lpstore_types(corp_id):
    # '''
    # SELECT lpOffers.typeID
    # FROM lpOffers
    # JOIN lpStore ON lpStore.offerID = lpOffers.offerID
    # WHERE corporationID = %s
    # '''
    fname = os.path.join(BASEDIR, 'data', 'lpdb', '%s.json' % corp_id)
    return json.load(open(fname))


LPStoreInfo = namedtuple("LPStoreInfo", (
    'typeID '
    'name '
    'qty '
    'isk_cost '
    'lp_cost '
    'req_items_cost '
    'selfcost_per_pack '
    'region_avg_price '
    'profit_per_item '
    'volume_per_day '
    'profit_per_day '
    'isk_per_lp '
))


def get_history_avg(hist, ndays):

    min_date = (datetime.now() - timedelta(days=ndays + 1)).date().isoformat()

    h = [i for i in hist if i['date'] > min_date]

    for n, i in reversed(list(enumerate(h))):
        if i['highPrice'] > i['avgPrice'] + i['lowPrice']:
            del h[n]

    total_sold = sum([i['avgPrice'] * i['volume'] for i in h])
    volume_per_day = sum(i['volume'] for i in h)
    if not volume_per_day:
        return 0, 1

    return total_sold, volume_per_day


def get_item_info(lp_info, region_id, ndays):

    type_id = lp_info['typeID']
    if type_id not in PRICES:
        return

    hist = crest.get_history(region_id, type_id)

    try:
        total_sold, volume_per_day = get_history_avg(hist, ndays)
    except ValueError:
        return

    avg_price = total_sold / volume_per_day

    req_items_cost = 0
    for req_item_id, count in lp_info.get('reqItems', {}).items():
        h = crest.get_history(region_id, req_item_id)
        ts, tv = get_history_avg(h, ndays)
        req_items_cost += (ts / tv) * count

    qty = lp_info['qty']
    cost_per_item = (lp_info['iskCost'] + req_items_cost) / qty
    profit_per_item = avg_price - cost_per_item
    isk_per_lp = profit_per_item / (lp_info['lpCost'] / qty)

    return LPStoreInfo(
        typeID=type_id,
        name=PRICES[type_id]['type']['name'],
        qty=qty,
        isk_cost=lp_info['iskCost'],
        lp_cost=lp_info['lpCost'],
        req_items_cost=int(req_items_cost),
        selfcost_per_pack=int(cost_per_item * qty),
        region_avg_price=int(avg_price),
        profit_per_item=int(profit_per_item),
        volume_per_day=int(volume_per_day / ndays),
        profit_per_day=int((profit_per_item * volume_per_day) / ndays),
        isk_per_lp=int(isk_per_lp),
    )


POOL = Pool(64)


def get_lpstore_info(region_id, corp_id, ndays=14):

    ret = []

    for lp_info in get_corporation_lpstore_types(corp_id).values():
        ret.append(POOL.apply_async(get_item_info, (lp_info, region_id, ndays)))

    ret = [i.get() for i in ret]
    ret = [i for i in ret if i is not None]

    def filter(i):
        if i.volume_per_day < 2:
            return False
        return i.isk_per_lp > 900 or i.profit_per_day > 50000000

    return [i for i in ret if filter(i)]


def main(output_format):
    hist = get_lpstore_info(10000042, 1000182)
    hist.sort(key=lambda x: x.isk_per_lp)

    if output_format == 'rows':
        for i in hist:
            print("%70s: %6s ISK/item %7s items %12s ISK/d" % (
                i.name, i.isk_per_lp, i.volume_per_day, i.profit_per_day
            ))
    else:
        print('\t'.join(LPStoreInfo._fields))
        for row in hist:
            print('\t'.join(str(getattr(row, field)) for field in LPStoreInfo._fields))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1])
