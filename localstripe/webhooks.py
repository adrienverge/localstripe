# -*- coding: utf-8 -*-
# Copyright 2018 Adrien Vergé
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

import asyncio
import hashlib
import hmac
import json
import logging

import aiohttp


_webhooks = {}


class Webhook(object):
    def __init__(self, url, secret, events):
        self.url = url
        self.secret = secret
        self.events = events


def register_webhook(id, url, secret, events):
    _webhooks[id] = Webhook(url, secret, events)


async def _send_webhook(event):
    payload = json.dumps(event._export(), indent=2, sort_keys=True)
    payload = payload.encode('utf-8')
    signed_payload = b'%d.%s' % (event.created, payload)

    await asyncio.sleep(1)

    logger = logging.getLogger('aiohttp.access')

    for webhook in _webhooks.values():
        if webhook.events is not None and event.type not in webhook.events:
            continue

        signature = hmac.new(webhook.secret.encode('utf-8'),
                             signed_payload, hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Stripe-Signature': 't=%d,v1=%s' % (event.created, signature)}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(webhook.url,
                                        data=payload, headers=headers) as r:
                    if r.status >= 200 and r.status < 300:
                        logger.info('webhook "%s" successfully delivered'
                                    % event.type)
                    else:
                        logger.info('webhook "%s" failed with response code %d'
                                    % (event.type, r.status))
            except aiohttp.client_exceptions.ClientError as e:
                logger.info('webhook "%s" failed: %s' % (event.type, e))


def schedule_webhook(event):
    asyncio.ensure_future(_send_webhook(event))
