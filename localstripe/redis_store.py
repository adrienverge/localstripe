import pickle
import typing

from redis.sentinel import Sentinel

# TODO - This whole thing needs to be wrapped in an object abstracting details from the rest of the code

sentinel = Sentinel([('localstripe-redis', 26379)])
sentinel.discover_master('mymaster')
sentinel.discover_slaves('mymaster')
redis_master = sentinel.master_for('mymaster')
redis_slave = sentinel.slave_for('mymaster')


# TODO - Should be [StripeObject, None]
def fetch(redis_key: str) -> typing.Union[typing.Any, None]:
    pickled = redis_slave.get(redis_key)
    if pickled is not None:
        return pickle.loads(pickled)
    else:
        return None


def fetch_all(matching):
    matching_keys = redis_slave.scan_iter(match=matching)
    return [pickle.loads(value) for value in redis_slave.mget(matching_keys)]
