from config import honeycomb


# Honeycomb's beeline has to be initialized _after_ the fork:
# https://docs.honeycomb.io/getting-data-in/python/beeline/#gunicorn
def post_worker_init(worker):
    honeycomb.init()
