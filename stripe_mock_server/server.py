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
import os.path
import re

import flask
from werkzeug.exceptions import BadRequest

from .resources import Card, Charge, Coupon, Customer, Invoice, InvoiceItem, \
                       Plan, Refund, Subscription, SubscriptionItem, Token, \
                       extra_apis, store
from .errors import UserError


app = flask.Flask('stripe_mock_server')


@app.errorhandler(UserError)
def handle_invalid_usage(error):
    return error.to_flask_response()


def add_cors_headers(response, origin):
    response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type, Accept')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET, POST, OPTIONS, DELETE')


@app.after_request
def after_request(response):
    if flask.request.headers.get('Origin', None):
        add_cors_headers(response, flask.request.headers['Origin'])
    return response


def get_post_data():
    try:
        return flask.request.get_json(force=True)
    except BadRequest:
        return flask.request.form.to_dict()


# Try to decode values like
#    curl -d card[cvc]=123 -d subscription_items[0][plan]=pro-yearly
def unflatten_data(data):
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
                data.append(transform_lists(v))
            return data
        else:
            for k in data.keys():
                if type(data[k]) is dict:
                    data[k] = transform_lists(data[k])
            return data

    data = transform_lists(data)

    return data


def get_api_key():
    if flask.request.authorization is not None:
        api_key = flask.request.authorization['username']
    else:
        header = flask.request.headers.get('Authorization', '').split(' ')
        if len(header) != 2 or header[0] != 'Bearer':
            return
        api_key = header[1]
    if api_key.startswith('sk_') and len(api_key) > 5:
        return api_key


def wrap_auth(method, url):
    # There is an exception for POST /v1/tokens: the auth is made using the
    # public key, that is passed in POST data.
    accept_key_in_post_data = method == 'POST' and url == '/v1/tokens'

    def decorator(fn):
        def wrapped_fn(*args, **kwargs):
            is_auth = get_api_key() is not None

            if method == 'POST':
                data = unflatten_data(get_post_data())
            else:
                data = unflatten_data(flask.request.args.to_dict())

            if not is_auth and accept_key_in_post_data:
                if ('key' in data and type(data['key']) == str and
                        data['key'].startswith('pk_')):
                    is_auth = True

                    del data['key']
                    if 'payment_user_agent' in data:
                        del data['payment_user_agent']
                    if 'referrer' in data:
                        del data['referrer']

            if not is_auth:
                raise UserError(401, 'Unauthorized')

            return fn(data=data, *args, **kwargs)
        wrapped_fn.__name__ = '%s_%s' % (method, url)
        return wrapped_fn
    return decorator


def api_create(cls, method, url):
    @wrap_auth(method, url)
    def f(data):
        if not data:
            raise UserError(400, 'Bad request')
        return flask.jsonify(cls._api_create(**data)._export())
    return f


def api_retrieve(cls, method, url):
    @wrap_auth(method, url)
    def f(data, id):
        return flask.jsonify(cls._api_retrieve(id, **data)._export())
    return f


def api_update(cls, method, url):
    @wrap_auth(method, url)
    def f(data, id):
        if not data:
            raise UserError(400, 'Bad request')
        return flask.jsonify(cls._api_update(id, **data)._export())
    return f


def api_delete(cls, method, url):
    @wrap_auth(method, url)
    def f(data, id):
        return flask.jsonify(cls._api_delete(id)._export())
    return f


def api_list_all(cls, method, url):
    @wrap_auth(method, url)
    def f(data):
        return flask.jsonify(cls._api_list_all(url, **data)._export())
    return f


def api_extra(func, method, url):
    @wrap_auth(method, url)
    def f(data, **kwargs):
        data.update(kwargs)
        return flask.jsonify(func(**data)._export())
    return f


for cls in (Card, Charge, Coupon, Customer, Invoice, InvoiceItem, Plan, Refund,
            Subscription, SubscriptionItem, Token):
    for method, url, func in (
            ('POST', '/v1/' + cls.object + 's', api_create),
            ('GET', '/v1/' + cls.object + 's/<string:id>', api_retrieve),
            ('POST', '/v1/' + cls.object + 's/<string:id>', api_update),
            ('DELETE', '/v1/' + cls.object + 's/<string:id>', api_delete),
            ('GET', '/v1/' + cls.object + 's', api_list_all)):
        app.route(url, methods=[method])(func(cls, method, url))


for method, url, func in extra_apis:
    app.route(url, methods=[method])(api_extra(func, method, url))


PORT = None


@app.route('/js.stripe.com/v3/')
def fake_stripe_js():
    path = os.path.dirname(os.path.realpath(__file__)) + '/fake-stripe-v3.js'
    with open(path) as f:
        contents = f.read().replace('{{ PORT }}', str(PORT))
        return flask.Response(contents, mimetype='application/javascript')


def start():
    global PORT

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8420)
    parser.add_argument('--from-scratch', action='store_true')
    args = parser.parse_args()

    if not args.from_scratch:
        store.try_load_from_disk()

    PORT = args.port

    app.run(host='0.0.0.0', port=args.port, debug=True)


if __name__ == '__main__':
    start()
