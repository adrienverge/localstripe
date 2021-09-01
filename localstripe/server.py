# -*- coding: utf-8 -*-
# Copyright 2017 Adrien Vergé
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import base64
import json
import logging
import os.path
import re
import socket

from aiohttp import web

from .resources import BalanceTransaction, Charge, Coupon, Customer, Event, \
    Invoice, InvoiceItem, PaymentIntent, PaymentMethod, Payout, Plan, \
    Product, Refund, SetupIntent, Source, Subscription, SubscriptionItem, \
    TaxRate, Token, extra_apis, store
from .errors import UserError
from .webhooks import register_webhook


def json_response(*args, **kwargs):
    return web.json_response(
        *args,
        dumps=lambda x: json.dumps(x, indent=2, sort_keys=True) + '\n',
        **kwargs)


async def add_cors_headers(request, response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = \
            'Content-Type, Accept'
        response.headers['Access-Control-Allow-Methods'] = \
            'GET, POST, OPTIONS, DELETE'


@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except UserError as e:
        return e.to_response()


async def get_post_data(request, remove_auth=True):
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        data = await request.post()
        if data:
            data = unflatten_data(data)

    if data and remove_auth:
        # Remove auth-related properties:
        if 'key' in data:
            del data['key']
        if 'payment_user_agent' in data:
            del data['payment_user_agent']
        if 'referrer' in data:
            del data['referrer']

    return data


# Try to decode values like
#    curl -d card[cvc]=123 -d subscription_items[0][plan]=pro-yearly
def unflatten_data(multidict):
    # Transform `{'attributes[]': 'size', 'attributes[]': 'gender'}` into
    # `{'attributes': ['size', 'gender']}`
    def handle_multiple_keys(multidict):
        data = dict()
        for k in multidict.keys():
            values = multidict.getall(k)
            values = [handle_multiple_keys(v) if hasattr(v, 'keys') else v
                      for v in values]
            if len(k) > 2 and k.endswith('[]'):
                k = k[:-2]
            else:
                values = values[0]
            data[k] = values
        return data

    data = handle_multiple_keys(multidict)

    def make_tree(data):
        for k, v in list(data.items()):
            r = re.search(r'^([^\[]+)\[([^\[]+)\](.*)$', k)
            if r:
                k0 = r.group(1)
                k1 = r.group(2) + r.group(3)
                data[k0] = data.get(k0, {})
                data[k0][k1] = v
                data[k0] = make_tree(data[k0])
                del data[k]
        return data

    data = make_tree(data)

    # Transform `{'items': {'0': {'plan': 'pro-yearly'}}}` into
    # `{'items': [{'plan': 'pro-yearly'}]}`
    def transform_lists(data):
        if (len(data) > 0 and
                all([re.match(r'^[0-9]+$', k) for k in data.keys()])):
            new_data = [(int(k), v) for k, v in data.items()]
            new_data.sort(key=lambda k: int(k[0]))
            data = []
            for k, v in sorted(new_data, key=lambda k: int(k[0])):
                if type(v) is dict:
                    data.append(transform_lists(v))
                else:
                    data.append(v)
            return data
        else:
            for k in data.keys():
                if type(data[k]) is dict:
                    data[k] = transform_lists(data[k])
            return data

    data = transform_lists(data)

    return data


def get_api_key(request):
    header = request.headers.get('Authorization', '').split(' ')
    if len(header) != 2:
        return

    if header[0] == 'Basic':
        api_key = base64.b64decode(header[1].encode('utf-8')).decode('utf-8')
        api_key = api_key.split(':')[0]
    elif header[0] == 'Bearer':
        api_key = header[1]

    if api_key.startswith('sk_') and len(api_key) > 5:
        return api_key


@web.middleware
async def auth_middleware(request, handler):
    if request.path.startswith('/js.stripe.com/'):
        is_auth = True

    elif request.path.startswith('/_config/'):
        is_auth = True

    else:
        # There are exceptions (for example POST /v1/tokens, POST /v1/sources)
        # where authentication can be done using the public key (passed as
        # `key` in POST data) instead of the private key.
        accept_key_in_post_data = (
            request.method == 'POST' and
            any(re.match(pattern, request.path) for pattern in (
                r'^/v1/tokens$',
                r'^/v1/sources$',
                r'^/v1/payment_intents/\w+/_authenticate\b',
                r'^/v1/setup_intents/\w+/confirm$',
                r'^/v1/setup_intents/\w+/cancel$',
            )))

        is_auth = get_api_key(request) is not None

        if request.method == 'POST':
            data = await get_post_data(request, remove_auth=False)
        else:
            data = unflatten_data(request.query)

        if not is_auth and accept_key_in_post_data:
            if ('key' in data and type(data['key']) == str and
                    data['key'].startswith('pk_')):
                is_auth = True

    if not is_auth:
        raise UserError(401, 'Unauthorized')

    return await handler(request)


@web.middleware
async def save_store_middleware(request, handler):
    try:
        return await handler(request)
    finally:
        if request.method in ('PUT', 'POST', 'DELETE'):
            store.dump_to_disk()


app = web.Application(middlewares=[error_middleware, auth_middleware,
                                   save_store_middleware])
app.on_response_prepare.append(add_cors_headers)


def api_create(cls, url):
    async def f(request):
        data = await get_post_data(request)
        data = data or {}
        expand = data.pop('expand', None)
        return json_response(cls._api_create(**data)._export(expand=expand))
    return f


def api_retrieve(cls, url):
    def f(request):
        id = request.match_info['id']
        data = unflatten_data(request.query)
        expand = data.pop('expand', None)
        return json_response(cls._api_retrieve(id)._export(expand=expand))
    return f


def api_update(cls, url):
    async def f(request):
        id = request.match_info['id']
        data = await get_post_data(request)
        if not data:
            raise UserError(400, 'Bad request')
        expand = data.pop('expand', None)
        return json_response(cls._api_update(id, **data)._export(
            expand=expand))
    return f


def api_delete(cls, url):
    def f(request):
        id = request.match_info['id']
        ret = cls._api_delete(id)
        return json_response(ret if isinstance(ret, dict) else ret._export())
    return f


def api_list_all(cls, url):
    def f(request):
        data = unflatten_data(request.query)
        expand = data.pop('expand', None)
        return json_response(cls._api_list_all(url, **data)
                             ._export(expand=expand))
    return f


def api_extra(func, url):
    async def f(request):
        data = await get_post_data(request) or {}
        data.update(unflatten_data(request.query) or {})
        if 'id' in request.match_info:
            data['id'] = request.match_info['id']
        if 'source_id' in request.match_info:
            data['source_id'] = request.match_info['source_id']
        if 'subscription_id' in request.match_info:
            data['subscription_id'] = request.match_info['subscription_id']
        expand = data.pop('expand', None)
        return json_response(func(**data)._export(expand=expand))
    return f


# Extra routes must be added *before* regular routes, because otherwise
# `/invoices/upcoming` would fall into `/invoices/{id}`.
for method, url, func in extra_apis:
    app.router.add_route(method, url, api_extra(func, url))


for cls in (BalanceTransaction, Charge, Coupon, Customer, Event, Invoice,
            InvoiceItem, PaymentIntent, PaymentMethod, Payout, Plan, Product,
            Refund, SetupIntent, Source, Subscription, SubscriptionItem,
            TaxRate, Token):
    for method, url, func in (
            ('POST', '/v1/' + cls.object + 's', api_create),
            ('GET', '/v1/' + cls.object + 's/{id}', api_retrieve),
            ('POST', '/v1/' + cls.object + 's/{id}', api_update),
            ('DELETE', '/v1/' + cls.object + 's/{id}', api_delete),
            ('GET', '/v1/' + cls.object + 's', api_list_all)):
        app.router.add_route(method, url, func(cls, url))


def localstripe_js(request):
    path = os.path.dirname(os.path.realpath(__file__)) + '/localstripe-v3.js'
    with open(path) as f:
        return web.Response(text=f.read(),
                            content_type='application/javascript')


app.router.add_get('/js.stripe.com/v3/', localstripe_js)


async def config_webhook(request):
    id = request.match_info['id']
    data = await get_post_data(request) or {}
    url = data.get('url', None)
    secret = data.get('secret', None)
    events = data.get('events', None)
    if not url or not secret or not url.startswith('http'):
        raise UserError(400, 'Bad request')
    if events is not None and type(events) is not list:
        raise UserError(400, 'Bad request')
    register_webhook(id, url, secret, events)
    return web.Response()


async def flush_store(request):
    store.clear()
    return web.Response()


app.router.add_post('/_config/webhooks/{id}', config_webhook)
app.router.add_delete('/_config/data', flush_store)


def start():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8420)
    parser.add_argument('--from-scratch', action='store_true')
    args = parser.parse_args()

    if not args.from_scratch:
        store.try_load_from_disk()

    # Listen on both IPv4 and IPv6
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('::', args.port))

    logger = logging.getLogger('aiohttp.access')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    web.run_app(app, sock=sock, access_log=logger)


if __name__ == '__main__':
    start()
