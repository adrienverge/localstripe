from typing import Iterable, Dict, Any, Union
import os
from azure.cosmos import CosmosClient, exceptions, PartitionKey


connection_string = os.environ['ConnectionStrings__CosmosSql']
client = CosmosClient.from_connection_string(connection_string)
database_name = 'localstripe'
try:
    database = client.create_database(database_name)
except exceptions.CosmosResourceExistsError:
    database = client.get_database_client(database_name)

database = client.get_database_client(database_name)
container_name = 'localstripe'

try:
    container = database.create_container(id=container_name, partition_key=PartitionKey(path="/partitionKey"))
except exceptions.CosmosResourceExistsError:
    container = database.get_container_client(container_name)
except exceptions.CosmosHttpResponseError:
    raise


# TODO - Should be [StripeObject, None]
def fetch_by_id(record_id) -> Union[Any, None]:
    result = container.query_items(
        query=f'SELECT * FROM {container_name} r WHERE r.id="{record_id}"',
        enable_cross_partition_query=True)
    if len(list(result)) > 1:
        raise 'More than one match. This is impossible.'
    return next(result, None)


def fetch_by_query(query) -> Iterable[Dict[str, Any]]:
    result = container.query_items(
        query=query,
        enable_cross_partition_query=True)
    return result


def fetch_all(matching):  # TODO replace all usages with fetch_by_query
    # matching_keys = redis_slave.scan_iter(match=matching)
    # return [pickle.loads(value) for value in redis_slave.mget(matching_keys)]
    raise NotImplementedError


def upsert_record(record):
    container.upsert_item(vars(record))


def delete_record(record):
    container.delete_item(record)


def delete_by_id(record_id):
    container.delete_item(item=record_id)


def delete_all_data():
    for record in container.read_all_items():
        container.delete_item(record)
