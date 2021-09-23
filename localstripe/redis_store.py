import pickle

from redis.sentinel import Sentinel

sentinel = Sentinel([('localstripe-redis', 26379)])
sentinel.discover_master('mymaster')
sentinel.discover_slaves('mymaster')
redis_master = sentinel.master_for('mymaster')
redis_slave = sentinel.slave_for('mymaster')

def fetch_all(matching):
    matching_keys = redis_slave.scan_iter(match=matching)
    return [pickle.loads(value) for value in redis_slave.mget(matching_keys)]
