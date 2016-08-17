from multiprocessing.pool import ThreadPool

import requests


from lpstore.app import REGIONS, NPC_CORPS


def main():
    with ThreadPool(20) as pool:
        tasks = []
        for i in REGIONS:
            for j in NPC_CORPS:
                tasks.append(pool.apply_async(
                    requests.get,
                    ['https://lp.ei-grad.ru/'],
                    dict(params=(
                        ('region', i['id']),
                        ('corp', j['id']),
                    ))
                ))
        for i in tasks:
            resp = i.get()
            print('%s %s' % (resp.status_code, resp.request.url))


if __name__ == "__main__":
    pass
