import logging
import os
import locale

from flask import Flask, render_template, request

from lpstore.lp import REGIONS, NPC_CORPS, get_lpstore_info, LPStoreInfo


logger = logging.getLogger(__name__)


if 'DEBUG' in os.environ:
    logging.basicConfig(level=logging.DEBUG)


locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')


app = Flask(__name__)

REGIONS = list(REGIONS.values())
REGIONS.sort(key=lambda x: x['name'])

NPC_CORPS = list(NPC_CORPS.values())
NPC_CORPS.sort(key=lambda x: x['name'])


def set_first(l, name):
    for i in l:
        if i['name'] == name:
            break
    l.remove(i)
    l.insert(0, i)


set_first(REGIONS, 'Metropolis')
set_first(REGIONS, 'Heimatar')
set_first(NPC_CORPS, 'Tribal Liberation Force')


@app.route('/')
def home():
    region = int(request.args.get('region', 10000030))
    corp = int(request.args.get('corp', 1000182))
    items = get_lpstore_info(region, corp)
    items.sort(key=lambda x: -x.isk_per_lp)
    return render_template(
        "index.html",
        region=region,
        corp=corp,
        regions=REGIONS,
        npc_corps=NPC_CORPS,
        columns=LPStoreInfo._fields,
        items=items,
    )


@app.template_filter('locale_format')
def locale_format_filter(value):
    if isinstance(value, int):
        return '{:n}'.format(value)
    return value

if __name__ == "__main__":
    app.run()
