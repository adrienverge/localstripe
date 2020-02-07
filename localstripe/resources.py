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

import asyncio
from datetime import datetime, timedelta
import hashlib
import pickle
import random
import re
import string
import time

from dateutil.relativedelta import relativedelta

from .errors import UserError
from .webhooks import schedule_webhook


# Save built-in keyword `type`, because some classes override it by using
# `type` as a method argument:
_type = type


class Store(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def try_load_from_disk(self):
        try:
            with open('/tmp/localstripe.pickle', 'rb') as f:
                old = pickle.load(f)
                self.clear()
                self.update(old)
        except FileNotFoundError:
            pass

    def dump_to_disk(self):
        with open('/tmp/localstripe.pickle', 'wb') as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)

    def __setitem__(self, *args, **kwargs):
        super().__setitem__(*args, **kwargs)
        self.dump_to_disk()

    def __delitem__(self, *args, **kwargs):
        super().__delitem__(*args, **kwargs)
        self.dump_to_disk()


store = Store()


def random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits)
                   for i in range(n))


def fingerprint(s: str):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]


def try_convert_to_bool(arg):
    if type(arg) is str:
        if arg.lower() == 'false':
            return False
        elif arg.lower() == 'true':
            return True
    return arg


def try_convert_to_int(arg):
    if type(arg) == int:
        return arg
    elif type(arg) in (str, float):
        try:
            return int(arg)
        except ValueError:
            pass
    return arg


def try_convert_to_float(arg):
    if type(arg) == float:
        return arg
    elif type(arg) in (str, int):
        try:
            return float(arg)
        except ValueError:
            pass
    return arg


extra_apis = []


class StripeObject(object):
    object = None

    def __init__(self, id=None):
        if not isinstance(self, List):
            if id is None:
                assert hasattr(self, '_id_prefix')
                self.id = getattr(self, '_id_prefix') + random_id(14)
            else:
                self.id = id

            self.created = int(time.time())

            self.livemode = False

            key = self.object + ':' + self.id
            if key in store.keys():
                raise UserError(409, 'Conflict')
            store[key] = self

    @classmethod
    def _get_class_for_id(cls, id):
        for child in cls.__subclasses__():
            if hasattr(child, '_id_prefix'):
                if id.startswith(child._id_prefix):
                    return child

    @classmethod
    def _api_create(cls, **data):
        return cls(**data)

    @classmethod
    def _api_retrieve(cls, id):
        obj = store.get(cls.object + ':' + id, None)

        if obj is None:
            raise UserError(404, 'Not Found')

        return obj

    @classmethod
    def _api_update(cls, id, **data):
        obj = cls._api_retrieve(id)
        obj._update(**data)
        return obj

    @classmethod
    def _api_delete(cls, id):
        key = cls.object + ':' + id
        if key not in store.keys():
            raise UserError(404, 'Not Found')
        del store[key]
        return {"deleted": True, "id": id}

    @classmethod
    def _api_list_all(cls, url, limit=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        li = List(url, limit=limit)
        li._list = [value for key, value in store.items()
                    if key.startswith(cls.object + ':')]
        return li

    def _update(self, **data):
        # Do not modify object during checks -> do two loops
        for key, value in data.items():
            if key.startswith('_') or not hasattr(self, key):
                raise UserError(400, 'Bad request')
        # Treat metadata differently: do not delete absent fields
        metadata = data.pop('metadata', None)
        if metadata:
            if type(metadata) is not dict:
                raise UserError(400, 'Bad request')
            self.metadata = self.metadata or {}
            for key, value in metadata.items():
                self.metadata[key] = value
        for key, value in data.items():
            setattr(self, key, value)

    def _export(self, expand=None):
        try:
            if expand is None:
                expand = []
            assert type(expand) is list
            assert all([type(e) is str for e in expand])
        except AssertionError:
            raise UserError(400, 'Bad request')

        if any(len(path.split('.')) > 4 for path in expand):
            raise UserError(
                400, 'You cannot expand more than 4 levels of a property')

        obj = {}

        # Take basic properties
        for key, value in vars(self).items():
            if not key.startswith('_'):
                if isinstance(value, StripeObject):
                    obj[key] = value._export()
                elif (isinstance(value, list) and len(value) and
                        isinstance(value[0], StripeObject)):
                    obj[key] = [item._export() for item in value]
                elif isinstance(value, dict):
                    obj[key] = value.copy()
                else:
                    obj[key] = value

        # And add dynamic properties
        for prop in dir(self):
            if not prop.startswith('_') and prop not in obj:
                value = getattr(self, prop)
                if isinstance(value, StripeObject):
                    obj[prop] = value._export()
                else:
                    obj[prop] = value

        def do_expand(path, obj):
            if type(obj) is list:
                for i in obj:
                    do_expand(path, i)
            else:
                k, path = path.split('.', 1) if '.' in path else (path, None)
                if type(obj[k]) is str:
                    id = obj[k]
                    cls = StripeObject._get_class_for_id(id)
                    obj[k] = cls._api_retrieve(id)._export()
                if path is not None:
                    do_expand(path, obj[k])
        try:
            for path in expand:
                do_expand(path, obj)
        except KeyError as e:
            raise UserError(400, 'Bad expand %s' % e)

        return obj


class Card(StripeObject):
    object = 'card'
    _id_prefix = 'card_'

    def __init__(self, source=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(source) is dict
            assert source.get('object', None) == 'card'
            number = source.get('number', None)
            exp_month = try_convert_to_int(source.get('exp_month', None))
            exp_year = try_convert_to_int(source.get('exp_year', None))
            cvc = source.get('cvc', None)
            address_city = source.get('address_city', None)
            address_country = source.get('address_country', None)
            address_line1 = source.get('address_line1', None)
            address_line2 = source.get('address_line2', None)
            address_state = source.get('address_state', None)
            address_zip = source.get('address_zip', None)
            name = source.get('name', None)
            assert type(number) is str and len(number) == 16
            assert type(exp_month) is int
            assert exp_month >= 1 and exp_month <= 12
            assert type(exp_year) is int
            if exp_year > 0 and exp_year < 100:
                exp_year += 2000
            assert exp_year >= 2017 and exp_year <= 2100
            assert type(cvc) is str and len(cvc) == 3
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self._card_number = number

        self.type = 'card'
        self.metadata = {}
        self.address_city = address_city
        self.address_country = address_country
        self.address_line1 = address_line1
        self.address_line1_check = None
        self.address_line2 = address_line2
        self.address_state = address_state
        self.address_zip = address_zip
        self.address_zip_check = None
        self.brand = 'Visa'
        self.country = 'US'
        self.cvc_check = 'pass'
        self.dynamic_last4 = None
        self.exp_month = exp_month
        self.exp_year = exp_year
        self.fingerprint = fingerprint(self._card_number)
        self.funding = 'credit'
        self.name = name
        self.tokenization_method = None

        self.customer = None

    @property
    def last4(self):
        return self._card_number[-4:]

    def _requires_authentication(self):
        return PaymentMethod._requires_authentication(self)

    def _attaching_is_declined(self):
        return PaymentMethod._attaching_is_declined(self)

    def _charging_is_declined(self):
        return PaymentMethod._charging_is_declined(self)


class Charge(StripeObject):
    object = 'charge'
    _id_prefix = 'ch_'

    def __init__(self, amount=None, currency=None, description=None,
                 metadata=None, customer=None, source=None, capture=True,
                 **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        capture = try_convert_to_bool(capture)
        try:
            assert type(amount) is int and amount >= 0
            assert type(currency) is str and currency
            if description is not None:
                assert type(description) is str
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if source is not None:
                assert type(source) is str
                assert (source.startswith('pm_') or source.startswith('src_')
                        or source.startswith('card_'))
            assert type(capture) is bool
        except AssertionError:
            raise UserError(400, 'Bad request')

        if source is None:
            customer_obj = Customer._api_retrieve(customer)
            source = customer_obj._get_default_payment_method_or_source()
            if source is None:
                raise UserError(404, 'This customer has no payment method')
        else:
            source = PaymentMethod._api_retrieve(source)

        if customer is None:
            customer = source.customer

        # All exceptions must be raised before this point.
        super().__init__()

        self._authorized = not source._charging_is_declined()

        self.amount = amount
        self.currency = currency
        self.customer = customer
        self.description = description
        self.invoice = None
        self.metadata = metadata or {}
        self.status = 'pending'
        self.receipt_email = None
        self.receipt_number = None
        self.refunds = List('/v1/charges/' + self.id + '/refunds')
        self.payment_method = source.id
        self.failure_code = None
        self.failure_message = None
        self.captured = capture

    def _trigger_payment(self, on_success=None, on_failure_now=None,
                         on_failure_later=None):
        pm = PaymentMethod._api_retrieve(self.payment_method)
        async_payment = pm.type == 'sepa_debit'

        if async_payment:
            if not self._authorized:
                async def callback():
                    await asyncio.sleep(0.5)
                    self.status = 'failed'
                    if on_failure_later:
                        on_failure_later()
            else:
                async def callback():
                    await asyncio.sleep(0.5)
                    self.status = 'succeeded'
                    if on_success:
                        on_success()
            asyncio.ensure_future(callback())

        else:
            if not self._authorized:
                self.status = 'failed'
                self.failure_code = 'card_declined'
                self.failure_message = 'Your card was declined.'
                if on_failure_now:
                    on_failure_now()
            else:
                self.status = 'succeeded'
                if on_success:
                    on_success()

    @classmethod
    def _api_create(cls, **data):
        obj = super()._api_create(**data)

        # for successful pre-auth, return unpaid charge
        if not obj.captured and obj._authorized:
            return obj

        def on_failure():
            raise UserError(402, 'Your card was declined.',
                            {'code': 'card_declined', 'charge': obj.id})

        obj._trigger_payment(
            on_failure_now=on_failure,
            on_failure_later=on_failure
        )

        return obj

    @classmethod
    def _api_capture(cls, id, amount=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('ch_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if amount is None:
            amount = obj.amount

        amount = try_convert_to_int(amount)
        try:
            assert type(amount) is int and 0 <= amount <= obj.amount
            assert obj.captured is False
        except AssertionError:
            raise UserError(400, 'Bad request')

        def on_success():
            obj.captured = True
            if amount < obj.amount:
                refunded = obj.amount - amount
                obj.refunds._list.append(Refund(obj.id, refunded))

        obj._trigger_payment(on_success)
        return obj

    @property
    def paid(self):
        return self.status == 'succeeded'

    @property
    def amount_refunded(self):
        refunded = 0
        for refund in self.refunds._list:
            refunded += refund.amount
        return refunded

    @property
    def refunded(self):
        return self.amount <= self.amount_refunded


extra_apis.append((
    ('POST', '/v1/charges/{id}/capture', Charge._api_capture)))


class Coupon(StripeObject):
    object = 'coupon'

    def __init__(self, id=None, duration=None, amount_off=None,
                 percent_off=None, currency=None, metadata=None,
                 duration_in_months=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount_off = try_convert_to_int(amount_off)
        percent_off = try_convert_to_int(percent_off)
        duration_in_months = try_convert_to_int(duration_in_months)
        try:
            assert type(id) is str and id
            assert (amount_off is None) != (percent_off is None)
            if amount_off is not None:
                assert type(amount_off) is int and amount_off >= 0
            if percent_off is not None:
                assert type(percent_off) is int
                assert percent_off >= 0 and percent_off <= 100
            assert duration in ('forever', 'once', 'repeating')
            if amount_off is not None:
                assert type(currency) is str and currency
            if duration == 'repeating':
                assert type(duration_in_months) is int
                assert duration_in_months > 0
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__(id)

        self.amount_off = amount_off
        self.percent_off = percent_off
        self.metadata = metadata or {}
        self.currency = currency
        self.duration = duration
        self.duration_in_months = duration_in_months
        self.max_redemptions = None
        self.redeem_by = None
        self.times_redeemed = 0
        self.valid = True


class Customer(StripeObject):
    object = 'customer'
    _id_prefix = 'cus_'

    def __init__(self, name=None, description=None, email=None,
                 phone=None, address=None,
                 invoice_settings=None, business_vat_id=None,
                 preferred_locales=None, tax_id_data=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            if name is not None:
                assert type(name) is str
            if description is not None:
                assert type(description) is str
            if email is not None:
                assert type(email) is str
            if phone is not None:
                assert type(phone) is str
            if address is not None:
                assert type(address) is dict
                assert set(address.keys()).issubset({
                    'city', 'country', 'line1', 'line2', 'postal_code',
                    'state'})
                assert all(type(f) is str for f in address.values())
            if invoice_settings is None:
                invoice_settings = {}
            assert type(invoice_settings) is dict
            if 'default_payment_method' not in invoice_settings:
                invoice_settings['default_payment_method'] = None
            if invoice_settings['default_payment_method'] is not None:
                assert type(invoice_settings['default_payment_method']) is str
                assert (invoice_settings['default_payment_method']
                        .startswith('pm_'))
            if business_vat_id is not None:
                assert type(business_vat_id) is str
            if preferred_locales is not None:
                assert type(preferred_locales) is list
                assert all(type(l) is str for l in preferred_locales)
            if tax_id_data is None:
                tax_id_data = []
            assert type(tax_id_data) is list
            for data in tax_id_data:
                assert type(data) is dict
                assert set(data.keys()) == {'type', 'value'}
                assert data['type'] in ('eu_vat', 'nz_gst', 'au_abn')
                assert type(data['value']) is str and len(data['value']) > 10
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.name = name
        self.description = description
        self.email = email
        self.phone = phone
        self.address = address
        self.invoice_settings = invoice_settings
        self.business_vat_id = business_vat_id
        self.preferred_locales = preferred_locales
        self.metadata = metadata or {}
        self.account_balance = 0
        self.delinquent = False
        self.discount = None
        self.shipping = None
        self.default_source = None

        self.sources = List('/v1/customers/' + self.id + '/sources')
        self.tax_ids = List('/v1/customers/' + self.id + '/tax_ids')
        self.tax_ids._list = [TaxId(customer=self.id, **data)
                              for data in tax_id_data]

        schedule_webhook(Event('customer.created', self))

    def _get_default_payment_method_or_source(self):
        if self.invoice_settings.get('default_payment_method'):
            return PaymentMethod._api_retrieve(
                self.invoice_settings['default_payment_method'])
        elif self.default_source:
            return [s for s in self.sources._list
                    if s.id == self.default_source][0]

    @property
    def currency(self):
        source = self._get_default_payment_method_or_source()
        if isinstance(source, Source):  # not Card
            return source.currency
        return 'eur'  # arbitrary default

    @property
    def subscriptions(self):
        return Subscription._api_list_all(
            '/v1/customers/' + self.id + '/subscriptions', customer=self.id)

    @classmethod
    def _api_create(cls, source=None, **data):
        obj = super()._api_create(**data)

        if source:
            cls._api_add_source(obj.id, source)

        return obj

    @classmethod
    def _api_update(cls, id, **data):
        if ('invoice_settings' in data and
                data['invoice_settings'].get('default_payment_method') == ''):
            data['invoice_settings']['default_payment_method'] = None

        obj = super()._api_update(id, **data)
        schedule_webhook(Event('customer.updated', obj))
        return obj

    @classmethod
    def _api_delete(cls, id):
        obj = super()._api_retrieve(id)
        schedule_webhook(Event('customer.deleted', obj))
        return super()._api_delete(id)

    @classmethod
    def _api_retrieve_source(cls, id, source_id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        # return 404 if does not exist
        Customer._api_retrieve(id)

        if type(source_id) is str and source_id.startswith('src_'):
            source_obj = Source._api_retrieve(source_id)
        elif type(source_id) is str and source_id.startswith('card_'):
            source_obj = Card._api_retrieve(source_id)
            if source_obj.customer != id:
                raise UserError(404, 'This customer does not own this card')
        else:
            raise UserError(400, 'Bad request')

        return source_obj

    @classmethod
    def _api_update_source(cls, id, source_id, **data):
        source_obj = cls._api_retrieve_source(id, source_id)
        return type(source_obj)._api_update(source_id, **data)

    @classmethod
    def _api_add_source(cls, id, source=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            if type(source) is str:
                assert source[:4] in ('src_', 'tok_')
            else:
                assert type(source) is dict
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if type(source) is str and source.startswith('src_'):
            source_obj = Source._api_retrieve(source)
        elif type(source) is str and source.startswith('tok_'):
            source_obj = Token._api_retrieve(source).card
        else:
            source_obj = Card(source=source)

        if source_obj._attaching_is_declined():
            raise UserError(402, 'Your card was declined.',
                            {'code': 'card_declined'})

        if isinstance(source_obj, Card):
            source_obj.customer = id

        obj.sources._list.append(source_obj)

        if obj.default_source is None:
            obj.default_source = source_obj.id

        schedule_webhook(Event('customer.source.created', source_obj))

        return source_obj

    @classmethod
    def _api_remove_source(cls, id, source_id, **kwargs):
        obj = cls._api_retrieve(id)
        source_obj = cls._api_retrieve_source(id, source_id)

        type(source_obj)._api_delete(source_id)
        obj.sources._list.remove(source_obj)

        if obj.default_source == source_obj.id:
            obj.default_source = None
            for source in obj.sources._list:
                obj.default_source = source.id
                break

        return obj

    @classmethod
    def _api_add_tax_id(cls, id, type=None, value=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type in ('eu_vat', 'nz_gst', 'au_abn')
            assert _type(value) is str and len(value) > 10
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        tax_id = TaxId(customer=id, type=type, value=value)
        obj.tax_ids._list.append(tax_id)

        return tax_id

    @classmethod
    def _api_list_tax_ids(cls, id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        obj = cls._api_retrieve(id)
        return obj.tax_ids

    @classmethod
    def _api_list_subscriptions(cls, id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        return cls._api_retrieve(id).subscriptions

    @classmethod
    def _api_add_subscription(cls, id, **data):
        return Subscription._api_create(customer=id, **data)

    @classmethod
    def _api_retrieve_subscription(cls, id, subscription_id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        obj = Subscription._api_retrieve(subscription_id)

        if obj.customer != id:
            raise UserError(404, 'Customer ' + id + ' does not have a '
                                 'subscription with ID ' + subscription_id)

        return obj

    @classmethod
    def _api_update_subscription(cls, id, subscription_id, **data):
        obj = Subscription._api_retrieve(subscription_id)

        if obj.customer != id:
            raise UserError(404, 'Customer ' + id + ' does not have a '
                                 'subscription with ID ' + subscription_id)

        return Subscription._api_update(subscription_id, **data)


extra_apis.extend((
    ('POST', '/v1/customers/{id}/sources', Customer._api_add_source),
    # Retrieve single source by id:
    ('GET', '/v1/customers/{id}/sources/{source_id}',
     Customer._api_retrieve_source),
    # Update single source by id:
    ('POST', '/v1/customers/{id}/sources/{source_id}',
     Customer._api_update_source),
    # Delete single source by id:
    ('DELETE', '/v1/customers/{id}/sources/{source_id}',
     Customer._api_remove_source),
    ('GET', '/v1/customers/{id}/subscriptions',
     Customer._api_list_subscriptions),
    ('POST', '/v1/customers/{id}/subscriptions',
     Customer._api_add_subscription),
    ('GET', '/v1/customers/{id}/subscriptions/{subscription_id}',
     Customer._api_retrieve_subscription),
    ('POST', '/v1/customers/{id}/subscriptions/{subscription_id}',
     Customer._api_update_subscription),
    # This is the old API route:
    ('POST', '/v1/customers/{id}/cards', Customer._api_add_source),
    ('POST', '/v1/customers/{id}/tax_ids', Customer._api_add_tax_id),
    ('GET', '/v1/customers/{id}/tax_ids', Customer._api_list_tax_ids)))


class Event(StripeObject):
    object = 'event'
    _id_prefix = 'evt_'

    def __init__(self, type, data):
        # All exceptions must be raised before this point.
        super().__init__()

        self.type = type
        self.data = {'object': data._export()}
        self.api_version = '2017-08-15'

    @classmethod
    def _api_create(cls, **data):
        raise UserError(405, 'Method Not Allowed')

    @classmethod
    def _api_update(cls, id, **data):
        raise UserError(405, 'Method Not Allowed')

    @classmethod
    def _api_delete(cls, id):
        raise UserError(405, 'Method Not Allowed')


class Invoice(StripeObject):
    object = 'invoice'
    _id_prefix = 'in_'

    def __init__(self, customer=None, subscription=None, metadata=None,
                 items=[], date=None, description=None,
                 simulation=False,
                 tax_percent=None,  # deprecated
                 default_tax_rates=None,
                 **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        tax_percent = try_convert_to_float(tax_percent)
        date = try_convert_to_int(date)
        try:
            assert type(customer) is str and customer.startswith('cus_')
            if subscription is not None:
                assert type(subscription) is str
                assert subscription.startswith('sub_')
            if date is not None:
                assert type(date) is int and date > 1500000000
            else:
                date = int(time.time())
            if description is not None:
                assert type(description) is str
            if tax_percent is not None:
                assert default_tax_rates is None
                assert type(tax_percent) is float
                assert tax_percent >= 0 and tax_percent <= 100
            if default_tax_rates is not None:
                assert tax_percent is None
                assert type(default_tax_rates) is list
                assert all(type(txr) is str and txr.startswith('txr_')
                           for txr in default_tax_rates)
        except AssertionError:
            raise UserError(400, 'Bad request')

        Customer._api_retrieve(customer)  # to return 404 if not existant

        if subscription is not None:
            subscription_obj = Subscription._api_retrieve(subscription)

        if default_tax_rates is not None:
            default_tax_rates = [TaxRate._api_retrieve(tr)
                                 for tr in default_tax_rates]

        # All exceptions must be raised before this point.
        super().__init__()

        self.customer = customer
        self.subscription = subscription
        self.tax_percent = tax_percent
        self.default_tax_rates = default_tax_rates
        self.date = date
        self.metadata = metadata or {}
        self.payment_intent = None
        self.application_fee = None
        self.attempt_count = 1
        self.attempted = True
        self.description = description
        self.discount = None
        self.ending_balance = 0
        self.receipt_number = None
        self.starting_balance = 0
        self.statement_descriptor = None
        self.webhooks_delivered_at = self.date
        self.status_transitions = {
            'finalized_at': None,
            'paid_at': None,
            'voided_at': None,
        }

        self.period_start = None
        self.period_end = None
        if subscription is not None:
            self.period_start = subscription_obj.current_period_start
            self.period_end = subscription_obj.current_period_end

        self.lines = List('/v1/invoices/' + self.id + '/lines')
        for item in items:
            item.invoice = self.id
            self.lines._list.append(InvoiceLineItem(item))

        pending_items = [ii for ii in InvoiceItem._api_list_all(
            None, customer=self.customer, limit=99)._list
            if ii.invoice is None]
        for ii in pending_items:
            if not simulation:
                ii.invoice = self.id
            self.lines._list.append(InvoiceLineItem(ii))

        if len(self.lines._list):
            self.currency = self.lines._list[0].currency
        else:
            self.currency = 'eur'  # arbitrary default

        self._draft = True
        self._voided = False

        if not simulation:
            schedule_webhook(Event('invoice.created', self))

    @property
    def subtotal(self):
        return sum([il.amount for il in self.lines._list])

    @property
    def tax(self):
        if self.tax_percent is not None:  # legacy support
            return int(self.subtotal * self.tax_percent / 100.0)

        return sum([ta['amount'] for ta in self.total_tax_amounts])

    @property
    def total_tax_amounts(self):
        concat = []
        for il in self.lines._list:
            tax_amounts = []
            if il.tax_rates:
                tax_amounts = il.tax_amounts
            elif self.default_tax_rates:
                tax_amounts = [tr._tax_amount(il.amount)
                               for tr in self.default_tax_rates]
            concat.extend(tax_amounts)
        # TODO: reduce `concat` by unique `tax_rate` ID
        return concat

    @property
    def total(self):
        return self.subtotal + self.tax

    @property
    def amount_due(self):
        return self.total

    @property
    def next_payment_attempt(self):
        if self.status in ('draft', 'open'):
            return self.date

    @property
    def status(self):
        if self._draft:
            return 'draft'
        elif self._voided:
            return 'void'
        elif self.total <= 0:
            return 'paid'
        elif self.payment_intent:
            pi = PaymentIntent._api_retrieve(self.payment_intent)
            if pi.status == 'succeeded':
                return 'paid'
            elif pi.status == 'canceled':
                return 'void'
        return 'open'

    @property
    def charge(self):
        if self.payment_intent:
            pi = PaymentIntent._api_retrieve(self.payment_intent)
            if len(pi.charges._list):
                return pi.charges._list[-1]

    def _finalize(self):
        assert self.status == 'draft'
        self._draft = False
        self.status_transitions['finalized_at'] = int(time.time())

    def _on_payment_success(self):
        assert self.status == 'paid'
        self.status_transitions['paid_at'] = int(time.time())
        schedule_webhook(Event('invoice.payment_succeeded', self))
        if self.subscription:
            sub = Subscription._api_retrieve(self.subscription)
            sub._on_initial_payment_success(self)

    def _on_payment_failure_now(self):
        assert self.status in ('open', 'void')
        if self.status == 'void':
            self.status_transitions['voided_at'] = int(time.time())
        schedule_webhook(Event('invoice.payment_failed', self))
        if self.subscription:
            sub = Subscription._api_retrieve(self.subscription)
            if sub.status == 'incomplete':
                sub._on_initial_payment_failure_now(self)
            else:
                sub._on_recurring_payment_failure(self)

    def _on_payment_failure_later(self):
        assert self.status in ('open', 'void')
        if self.status == 'void':
            self.status_transitions['voided_at'] = int(time.time())
        schedule_webhook(Event('invoice.payment_failed', self))
        if self.subscription:
            sub = Subscription._api_retrieve(self.subscription)
            if sub.status == 'incomplete':
                sub._on_initial_payment_failure_later(self)
            else:
                sub._on_recurring_payment_failure(self)

    @classmethod
    def _get_next_invoice(cls, customer=None, subscription=None,
                          tax_percent=None, default_tax_rates=None,
                          description=None, metadata=None,
                          # /upcoming route properties:
                          upcoming=False,
                          coupon=None,
                          subscription_items=None,
                          subscription_prorate=None,
                          subscription_proration_date=None,
                          subscription_tax_percent=None,  # deprecated
                          subscription_default_tax_rates=None,
                          subscription_trial_end=None):
        subscription_proration_date = \
            try_convert_to_int(subscription_proration_date)
        try:
            assert type(customer) is str and customer.startswith('cus_')
            if default_tax_rates is not None:
                assert type(default_tax_rates) is list
                assert all(type(txr) is str and txr.startswith('txr_')
                           for txr in default_tax_rates)
            if subscription_items is not None:
                assert type(subscription_items) is list
                for si in subscription_items:
                    assert type(si.get('plan', None)) is str
                    si['tax_rates'] = si.get('tax_rates', None)
                    if si['tax_rates'] is not None:
                        assert type(si['tax_rates']) is list
                        assert all(type(tr) is str for tr in si['tax_rates'])
                if subscription_default_tax_rates is not None:
                    assert subscription_tax_percent is None
                    assert type(subscription_default_tax_rates) is list
                    assert all(type(txr) is str and txr.startswith('txr_')
                               for txr in subscription_default_tax_rates)
                    assert all(type(tr) is str
                               for tr in subscription_default_tax_rates)
            if subscription_proration_date is not None:
                assert type(subscription_proration_date) is int
                assert subscription_proration_date > 1500000000
        except AssertionError:
            raise UserError(400, 'Bad request')

        # return 404 if not existant
        customer_obj = Customer._api_retrieve(customer)
        if subscription_items:
            for si in subscription_items:
                Plan._api_retrieve(si['plan'])  # to return 404 if not existant
                # To return 404 if not existant:
                if si['tax_rates'] is not None:
                    [TaxRate._api_retrieve(tr) for tr in si['tax_rates']]
            # To return 404 if not existant:
            if subscription_default_tax_rates is not None:
                [TaxRate._api_retrieve(tr)
                 for tr in subscription_default_tax_rates]

        pending_items = [ii for ii in InvoiceItem._api_list_all(
            None, customer=customer, limit=99)._list
            if ii.invoice is None]
        if (not upcoming and not subscription and
                not subscription_items and not pending_items):
            raise UserError(400, 'Bad request')

        simulation = subscription_items is not None or \
            subscription_prorate is not None or \
            subscription_tax_percent is not None or \
            subscription_default_tax_rates is not None or \
            subscription_trial_end is not None

        current_subscription = None
        li = [s for s in customer_obj.subscriptions._list
              if subscription is None or s.id == subscription]
        if len(li):
            current_subscription = li[0]
        elif subscription is not None:
            raise UserError(404, 'No such subscription for customer')

        if default_tax_rates is None:
            if subscription_default_tax_rates is not None:
                default_tax_rates = subscription_default_tax_rates
            elif current_subscription is not None and \
                    current_subscription.default_tax_rates is not None:
                default_tax_rates = \
                    [tr.id for tr in current_subscription.default_tax_rates]

        invoice_items = []
        items = subscription_items or \
            (current_subscription and current_subscription.items._list) or []
        for si in items:
            if subscription_items is not None:
                plan = Plan._api_retrieve(si['plan'])
            else:
                plan = si.plan
            if subscription_items is not None:
                tax_rates = si['tax_rates']
            else:
                tax_rates = [tr.id for tr in (si.tax_rates or [])]
            invoice_items.append(
                InvoiceItem(subscription=subscription,
                            plan=plan.id,
                            amount=plan.amount,
                            currency=plan.currency,
                            description=plan.name,
                            tax_rates=tax_rates,
                            customer=customer))

        if tax_percent is None:
            if subscription_tax_percent is not None:
                tax_percent = subscription_tax_percent
            elif current_subscription:
                tax_percent = current_subscription.tax_percent

        date = int(time.time())  # now
        if current_subscription:
            date = current_subscription.current_period_end

        if not simulation and not current_subscription:
            raise UserError(404, 'No upcoming invoices for customer')

        elif not simulation and current_subscription:
            return cls(customer=customer,
                       subscription=current_subscription.id,
                       items=invoice_items,
                       tax_percent=tax_percent,
                       default_tax_rates=default_tax_rates,
                       date=date,
                       description=description)

        else:  # if simulation
            if subscription is not None:
                # Get previous invoice for this subscription and customer, and
                # deduce what is already paid:
                # TODO: Better not to use limit, but take date into account
                previous = cls._api_list_all(None, customer=customer,
                                             subscription=subscription,
                                             limit=99)
                for previous_invoice in previous._list:
                    previous_tax_rates = \
                        [tr.id
                         for tr in previous_invoice.lines._list[0].tax_rates]
                    invoice_items.append(
                        InvoiceItem(amount=- previous_invoice.subtotal,
                                    currency=previous_invoice.currency,
                                    proration=True,
                                    description='Unused time',
                                    tax_rates=previous_tax_rates,
                                    customer=customer,
                                    period_start=previous_invoice.period_start,
                                    period_end=previous_invoice.period_end))

            invoice = cls(customer=customer,
                          items=invoice_items,
                          tax_percent=tax_percent,
                          default_tax_rates=default_tax_rates,
                          date=date,
                          description=description,
                          simulation=True)

            if subscription_proration_date is not None:
                for il in invoice.lines._list:
                    il.period['start'] = subscription_proration_date
                    il.period['end'] = subscription_proration_date

            return invoice

    @classmethod
    def _api_create(cls, customer=None, subscription=None, tax_percent=None,
                    default_tax_rates=None, description=None, metadata=None):
        return cls._get_next_invoice(
            customer=customer, subscription=subscription,
            tax_percent=tax_percent, default_tax_rates=default_tax_rates,
            description=description, metadata=metadata)

    @classmethod
    def _api_delete(cls, id):
        obj = cls._api_retrieve(id)
        if obj.status != 'draft':
            raise UserError(400, 'Bad request')

        return super()._api_delete(id)

    @classmethod
    def _api_list_all(cls, url, customer=None, subscription=None, limit=None):
        try:
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if subscription is not None:
                assert type(subscription) is str
                assert subscription.startswith('sub_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        li = super(Invoice, cls)._api_list_all(url, limit=limit)
        if customer is not None:
            Customer._api_retrieve(customer)  # to return 404 if not existant
            li._list = [i for i in li._list if i.customer == customer]
        if subscription is not None:
            # to return 404 if not existant
            Subscription._api_retrieve(subscription)
            li._list = [i for i in li._list if i.subscription == subscription]
        li._list.sort(key=lambda i: i.date, reverse=True)
        return li

    @classmethod
    def _api_upcoming_invoice(cls, customer=None, subscription=None,
                              coupon=None, subscription_items=None,
                              subscription_prorate=None,
                              subscription_proration_date=None,
                              subscription_tax_percent=None,  # deprecated
                              subscription_default_tax_rates=None,
                              subscription_trial_end=None):
        invoice = cls._get_next_invoice(
            customer=customer, subscription=subscription,
            upcoming=True,
            coupon=coupon, subscription_items=subscription_items,
            subscription_prorate=subscription_prorate,
            subscription_proration_date=subscription_proration_date,
            subscription_tax_percent=subscription_tax_percent,
            subscription_default_tax_rates=subscription_default_tax_rates,
            subscription_trial_end=subscription_trial_end)

        # Do not store this invoice
        del store[cls.object + ':' + invoice.id]
        invoice.id = None

        return invoice

    @classmethod
    def _api_pay_invoice(cls, id):
        obj = Invoice._api_retrieve(id)

        if obj.status == 'paid':
            raise UserError(400, 'Invoice is already paid')
        elif obj.status not in ('draft', 'open'):
            raise UserError(400, 'Bad request')

        obj._draft = False

        if obj.total <= 0:
            obj._on_payment_success()
        else:
            cus = Customer._api_retrieve(obj.customer)
            if cus._get_default_payment_method_or_source() is None:
                raise UserError(404, 'This customer has no payment method')
            pm = cus._get_default_payment_method_or_source()
            pi = PaymentIntent(amount=obj.total,
                               currency=obj.currency,
                               customer=obj.customer,
                               payment_method=pm.id)
            obj.payment_intent = pi.id
            pi.invoice = obj.id
            PaymentIntent._api_confirm(obj.payment_intent)

        return obj

    @classmethod
    def _api_void_invoice(cls, id):
        obj = Invoice._api_retrieve(id)

        if obj.status not in ('draft', 'open'):
            raise UserError(400, 'Bad request')

        PaymentIntent._api_cancel(obj.payment_intent)

        obj._draft = False
        obj._voided = True
        obj.status_transitions['voided_at'] = int(time.time())

        if obj.subscription:
            sub = Subscription._api_retrieve(obj.subscription)
            sub._on_initial_payment_voided(obj)

        return obj

    @classmethod
    def _api_list_lines(cls, id, limit=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        obj = cls._api_retrieve(id)

        lines = List('/v1/invoices/' + id + '/lines', limit=limit)
        lines._list = obj.lines._list

        return lines


extra_apis.extend((
    ('GET', '/v1/invoices/upcoming', Invoice._api_upcoming_invoice),
    ('POST', '/v1/invoices/{id}/pay', Invoice._api_pay_invoice),
    ('POST', '/v1/invoices/{id}/void', Invoice._api_void_invoice),
    ('GET', '/v1/invoices/{id}/lines', Invoice._api_list_lines)))


class InvoiceItem(StripeObject):
    object = 'invoiceitem'
    _id_prefix = 'ii_'

    def __init__(self, invoice=None, subscription=None, plan=None, amount=None,
                 currency=None, customer=None, period_start=None,
                 period_end=None, proration=False, description=None,
                 tax_rates=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        period_start = try_convert_to_int(period_start)
        period_end = try_convert_to_int(period_end)
        proration = try_convert_to_bool(proration)
        try:
            if invoice is not None:
                assert type(invoice) is str and invoice.startswith('in_')
            if subscription is not None:
                assert type(subscription) is str
                assert subscription.startswith('sub_')
            if plan is not None:
                assert type(plan) is str and plan
            assert type(amount) is int
            assert type(currency) is str and currency
            assert type(customer) is str and customer.startswith('cus_')
            if period_start is not None:
                assert type(period_start) is int and period_start > 1500000000
                assert type(period_end) is int and period_end > 1500000000
            else:
                period_start = period_end = int(time.time())
            assert type(proration) is bool
            if description is not None:
                assert type(description) is str
            else:
                description = 'Invoice item'
            if tax_rates is not None:
                assert type(tax_rates) is list
                assert all(type(tr) is str for tr in tax_rates)
        except AssertionError:
            raise UserError(400, 'Bad request')

        Customer._api_retrieve(customer)  # to return 404 if not existant
        if invoice is not None:
            Invoice._api_retrieve(invoice)  # to return 404 if not existant
        if plan is not None:
            plan = Plan._api_retrieve(plan)  # to return 404 if not existant
        if tax_rates is not None:
            # To return 404 if not existant:
            tax_rates = [TaxRate._api_retrieve(tr) for tr in tax_rates]

        # All exceptions must be raised before this point.
        super().__init__()

        self.invoice = invoice
        self.subscription = subscription
        self.plan = plan
        self.quantity = 1
        self.amount = amount
        self.currency = currency
        self.customer = customer
        self.date = int(time.time())
        self.period = dict(start=period_start, end=period_end)
        self.proration = proration
        self.description = description
        self.tax_rates = tax_rates
        self.metadata = metadata or {}

    @classmethod
    def _api_list_all(cls, url, customer=None, limit=None):
        try:
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        li = super(InvoiceItem, cls)._api_list_all(url, limit=limit)
        li._list = [ii for ii in li._list if ii.invoice is None]
        if customer is not None:
            Customer._api_retrieve(customer)  # to return 404 if not existant
            li._list = [ii for ii in li._list if ii.customer == customer]
        li._list.sort(key=lambda i: i.date, reverse=True)
        return li


class InvoiceLineItem(StripeObject):
    object = 'line_item'
    _id_prefix = 'il_'

    def __init__(self, item):
        try:
            assert isinstance(item, (InvoiceItem, SubscriptionItem))
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.type = \
            'invoiceitem' if isinstance(item, InvoiceItem) else 'subscription'

        if self.type == 'subscription':
            self.subscription_item = item.id
            self.subscription = item._subscription
            self.plan = item.plan
            self.proration = False
            self.currency = item.plan.currency
            self.description = item.plan.name
            self.amount = item._calculate_amount()
            subscription_obj = Subscription._api_retrieve(item._subscription)
            self.period = dict(start=subscription_obj.current_period_start,
                               end=subscription_obj.current_period_end)
        elif self.type == 'invoiceitem':
            self.invoice_item = item.id
            self.subscription = None
            self.plan = None
            self.proration = item.proration
            self.currency = item.currency
            self.description = item.description
            self.amount = item.amount
            self.period = item.period

        # Legacy support, before InvoiceLineItem
        self.invoice = item.invoice

        self.tax_rates = item.tax_rates or []
        self.metadata = item.metadata
        self.quantity = item.quantity

    @property
    def tax_amounts(self):
        return [tr._tax_amount(self.amount) for tr in self.tax_rates]

    @classmethod
    def _api_create(cls, **data):
        raise UserError(405, 'Method Not Allowed')

    @classmethod
    def _api_update(cls, id, **data):
        raise UserError(405, 'Method Not Allowed')

    @classmethod
    def _api_delete(cls, id):
        raise UserError(405, 'Method Not Allowed')


class List(StripeObject):
    object = 'list'

    def __init__(self, url=None, limit=None):
        limit = try_convert_to_int(limit)
        limit = 10 if limit is None else limit
        try:
            assert type(limit) is int and limit > 0
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.url = url

        self._limit = limit
        self._list = []

    @property
    def data(self):
        return [item._export() for item in self._list][:self._limit]

    @property
    def total_count(self):
        return len(self._list)

    @property
    def has_more(self):
        return len(self._list) > self._limit


class PaymentIntent(StripeObject):
    object = 'payment_intent'
    _id_prefix = 'pi_'

    def __init__(self, amount=None, currency=None, customer=None,
                 payment_method=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        try:
            # Invoices with amount == 0 don't create PaymentIntents:
            assert type(amount) is int and amount > 0
            assert type(currency) is str and currency
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if payment_method is not None:
                assert type(payment_method) is str
                assert (payment_method.startswith('pm_') or
                        payment_method.startswith('src_') or
                        payment_method.startswith('card_'))
        except AssertionError:
            raise UserError(400, 'Bad request')

        if customer:
            Customer._api_retrieve(customer)  # to return 404 if not existant
        if payment_method:
            # return 404 if not existant
            PaymentMethod._api_retrieve(payment_method)

        # All exceptions must be raised before this point.
        super().__init__()

        self.amount = amount
        self.currency = currency
        self.charges = List('/v1/charges?payment_intent=' + self.id)
        self.client_secret = self.id + '_secret_' + random_id(16)
        self.customer = customer
        self.payment_method = payment_method
        self.metadata = metadata or {}
        self.invoice = None
        self.next_action = None

        self._canceled = False
        self._authentication_failed = False

    def _trigger_payment(self):
        if self.status != 'requires_confirmation':
            raise UserError(400, 'Bad request')

        def on_success():
            if self.invoice:
                invoice = Invoice._api_retrieve(self.invoice)
                invoice._on_payment_success()

        def on_failure_now():
            if self.invoice:
                invoice = Invoice._api_retrieve(self.invoice)
                invoice._on_payment_failure_now()

        def on_failure_later():
            if self.invoice:
                invoice = Invoice._api_retrieve(self.invoice)
                invoice._on_payment_failure_later()

        charge = Charge(amount=self.amount,
                        currency=self.currency,
                        customer=self.customer,
                        source=self.payment_method)
        self.charges._list.append(charge)
        charge._trigger_payment(on_success, on_failure_now, on_failure_later)

    @property
    def status(self):
        if self._canceled:
            return 'canceled'
        if not self.payment_method:
            return 'requires_payment_method'
        if self.next_action:
            return 'requires_action'
        if len(self.charges._list) == 0:
            return 'requires_confirmation'
        charge = self.charges._list[-1]
        if charge.status == 'succeeded':
            return 'succeeded'
        elif charge.status == 'failed':
            return 'requires_payment_method'
        elif charge.status == 'pending':
            return 'processing'

    @property
    def last_payment_error(self):
        if self._authentication_failed:
            return {
                'code': 'payment_intent_authentication_failure',
                'message': (
                    'The provided PaymentMethod has failed authentication.'),
            }
        if len(self.charges._list):
            charge = self.charges._list[-1]
            if charge.status == 'failed':
                return {
                    'charge': charge.id,
                    'code': charge.failure_code,
                    'message': charge.failure_message,
                }

    @classmethod
    def _api_confirm(cls, id, payment_method=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        if payment_method is not None:
            raise UserError(500, 'Not implemented')

        try:
            assert type(id) is str and id.startswith('pi_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if obj.status != 'requires_confirmation':
            raise UserError(400, 'Bad request')

        obj._authentication_failed = False
        payment_method = PaymentMethod._api_retrieve(obj.payment_method)
        if payment_method._requires_authentication():
            obj.next_action = {
                'type': 'use_stripe_sdk',
                'use_stripe_sdk': {'type': 'three_d_secure_redirect',
                                   'stripe_js': ''},
            }
        else:
            obj._trigger_payment()

        return obj

    @classmethod
    def _api_cancel(cls, id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('pi_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)
        if obj.status not in ('requires_payment_method', 'requires_capture',
                              'requires_confirmation', 'requires_action'):
            raise UserError(400, 'Bad request')

        obj._canceled = True
        obj.next_action = None
        return obj

    @classmethod
    def _api_authenticate(cls, id, client_secret=None, success=False,
                          **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        success = try_convert_to_bool(success)
        try:
            assert type(id) is str and id.startswith('pi_')
            assert type(client_secret) is str
            assert type(success) is bool
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if client_secret != obj.client_secret:
            raise UserError(401, 'Unauthorized')
        if obj.status != 'requires_action':
            raise UserError(400, 'Bad request')

        obj.next_action = None
        if success:
            obj._trigger_payment()
        else:
            obj._authentication_failed = True
            obj.payment_method = None
            if obj.invoice:
                invoice = Invoice._api_retrieve(obj.invoice)
                invoice._on_payment_failure_later()

        return obj


extra_apis.extend((
    ('POST', '/v1/payment_intents/{id}/confirm', PaymentIntent._api_confirm),
    ('POST', '/v1/payment_intents/{id}/cancel', PaymentIntent._api_cancel),
    ('POST', '/v1/payment_intents/{id}/_authenticate',
     PaymentIntent._api_authenticate)))


class PaymentMethod(StripeObject):
    object = 'payment_method'
    _id_prefix = 'pm_'

    def __init__(self, type=None, billing_details=None, card=None,
                 sepa_debit=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type in ('card', 'sepa_debit')
            assert billing_details is None or _type(billing_details) is dict
            if type == 'card':
                assert _type(card) is dict and card.keys() == {
                    'number', 'exp_month', 'exp_year', 'cvc'}
                card['exp_month'] = try_convert_to_int(card['exp_month'])
                card['exp_year'] = try_convert_to_int(card['exp_year'])
                assert _type(card['number']) is str
                assert _type(card['exp_month']) is int
                assert _type(card['exp_year']) is int
                assert _type(card['cvc']) is str
                assert len(card['number']) == 16
                assert card['exp_month'] >= 1 and card['exp_month'] <= 12
                if card['exp_year'] > 0 and card['exp_year'] < 100:
                    card['exp_year'] += 2000
                assert len(card['cvc']) == 3
            elif type == 'sepa_debit':
                assert _type(sepa_debit) is dict
                assert 'iban' in sepa_debit
                assert _type(sepa_debit['iban']) is str
                assert 14 <= len(sepa_debit['iban']) <= 34
        except AssertionError:
            raise UserError(400, 'Bad request')

        if type == 'card':
            if not (2019 <= card['exp_year'] < 2100):
                raise UserError(400, 'Bad request',
                                {'code': 'invalid_expiry_year'})

        # All exceptions must be raised before this point.
        super().__init__()

        self.type = type
        self.billing_details = billing_details or {}

        if self.type == 'card':
            self._card_number = card['number']
            self.card = {
                'exp_month': card['exp_month'],
                'exp_year': card['exp_year'],
                'last4': self._card_number[-4:],
                'brand': 'visa',
                'country': 'FR',
                'fingerprint': fingerprint(self._card_number),
                'funding': 'credit',
                'three_d_secure_usage': {'supported': True},
            }
        elif self.type == 'sepa_debit':
            self._sepa_debit_iban = \
                re.sub(r'\s', '', sepa_debit['iban']).upper()
            self.sepa_debit = {
                'country': self._sepa_debit_iban[:2],
                'bank_code': self._sepa_debit_iban[4:12],
                'last4': self._sepa_debit_iban[-4:],
                'fingerprint': fingerprint(self._sepa_debit_iban),
                'mandate_reference': 'NXDSYREGC9PSMKWY',
                'mandate_url': 'https://fake/NXDSYREGC9PSMKWY',
            }

        self.customer = None
        self.metadata = metadata or {}

    def _requires_authentication(self):
        if self.type == 'card':
            return self._card_number in ('4000002500003155',
                                         '4000002760003184',
                                         '4000008260003178',
                                         '4000000000003220',
                                         '4000000000003063',
                                         '4000008400001629')
        return False

    def _attaching_is_declined(self):
        if self.type == 'card':
            return self._card_number in ('4000000000000002',
                                         '4000000000009995',
                                         '4000000000009987',
                                         '4000000000009979',
                                         '4000000000000069',
                                         '4000000000000127',
                                         '4000000000000119',
                                         '4242424242424241')
        return False

    def _charging_is_declined(self):
        if self.type == 'card':
            return self._card_number in ('4000000000000341',
                                         '4000008260003178',
                                         '4000008400001629')
        elif self.type == 'sepa_debit':
            return self._sepa_debit_iban == 'DE62370400440532013001'
        return False

    @classmethod
    def _api_attach(cls, id, customer=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('pm_')
            assert type(customer) is str and customer.startswith('cus_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)
        Customer._api_retrieve(customer)  # to return 404 if not existant

        if obj._attaching_is_declined():
            raise UserError(402, 'Your card was declined.',
                            {'code': 'card_declined'})

        obj.customer = customer
        return obj

    @classmethod
    def _api_detach(cls, id, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('pm_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)
        obj.customer = None
        return obj

    @classmethod
    def _api_retrieve(cls, id):
        # https://stripe.com/docs/payments/payment-methods#transitioning
        # You can retrieve all saved compatible payment instruments through the
        # Payment Methods API.
        if id.startswith('card_'):
            return Card._api_retrieve(id)
        elif id.startswith('src_'):
            return Source._api_retrieve(id)

        return super()._api_retrieve(id)

    @classmethod
    def _api_list_all(cls, url, customer=None, type=None, limit=None):
        try:
            assert _type(customer) is str and customer.startswith('cus_')
            assert type in ('card', )
        except AssertionError:
            raise UserError(400, 'Bad request')

        Customer._api_retrieve(customer)  # to return 404 if not existant

        li = super(PaymentMethod, cls)._api_list_all(url, limit=limit)
        li._list = [pm for pm in li._list
                    if pm.customer == customer and pm.type == type]
        return li


extra_apis.extend((
    ('POST', '/v1/payment_methods/{id}/attach', PaymentMethod._api_attach),
    ('POST', '/v1/payment_methods/{id}/detach', PaymentMethod._api_detach)))


class Plan(StripeObject):
    object = 'plan'
    _id_prefix = 'plan_'

    def __init__(self, id=None, metadata=None, amount=None, product=None,
                 currency=None, interval=None, interval_count=1,
                 trial_period_days=None, nickname=None, usage_type='licensed',
                 billing_scheme='per_unit', tiers=None, tiers_mode=None,
                 unit_amount=0, flat_amount=0,
                 active=True,
                 # Legacy arguments, before Stripe API 2018-02-05:
                 name=None, statement_descriptor=None,
                 **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        # Support Stripe API <= 2018-02-05:
        if product is None and name is not None:
            product = dict(name=name, metadata=metadata,
                           statement_descriptor=statement_descriptor)

        amount = try_convert_to_int(amount)
        interval_count = try_convert_to_int(interval_count)
        trial_period_days = try_convert_to_int(trial_period_days)
        active = try_convert_to_bool(active)
        try:
            assert id is None or type(id) is str and id
            assert type(active) is bool
            assert billing_scheme in ['per_unit', 'tiered']
            if billing_scheme == 'per_unit':
                assert type(amount) is int and amount >= 0
            else:
                assert tiers_mode in ['graduated', 'volume']
                assert type(tiers) is list and len(tiers) > 0
                for t in tiers:
                    assert \
                        type(t) is dict and 'up_to' in t and \
                        (t['up_to'] == 'inf' or
                         type(try_convert_to_int(t['up_to'])) is int)
                    unit_amount = try_convert_to_int(t.get('unit_amount', 0))
                    assert type(unit_amount) is int and unit_amount >= 0
                    flat_amount = try_convert_to_int(t.get('flat_amount', 0))
                    assert type(flat_amount) is int and flat_amount >= 0
            assert type(currency) is str and currency
            assert type(interval) is str
            assert interval in ('day', 'week', 'month', 'year')
            assert type(interval_count) is int
            if trial_period_days is not None:
                assert type(trial_period_days) is int
            if nickname is not None:
                assert type(nickname) is str
            assert usage_type in ['licensed', 'metered']
        except AssertionError:
            raise UserError(400, 'Bad request')

        if type(product) is str:
            Product._api_retrieve(product)  # to return 404 if not existant
        else:
            product = Product(type='service', **product).id

        # All exceptions must be raised before this point.
        super().__init__(id)

        self.metadata = metadata or {}
        self.product = product
        self.active = active
        self.amount = amount
        self.currency = currency
        self.interval = interval
        self.interval_count = interval_count
        self.trial_period_days = trial_period_days
        self.nickname = nickname
        self.usage_type = usage_type
        self.billing_scheme = billing_scheme
        self.tiers = tiers
        self.tiers_mode = tiers_mode

        schedule_webhook(Event('plan.created', self))

    @property
    def name(self):  # Support Stripe API <= 2018-02-05
        return Product._api_retrieve(self.product).name

    @property
    def statement_descriptor(self):  # Support Stripe API <= 2018-02-05
        return Product._api_retrieve(self.product).statement_descriptor


class Product(StripeObject):
    object = 'product'
    _id_prefix = 'prod_'

    def __init__(self, id=None, name=None, type=None, active=True,
                 caption=None, description=None, attributes=None,
                 shippable=True, url=None, statement_descriptor=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        active = try_convert_to_bool(active)
        try:
            assert id is None or _type(id) is str and id
            assert _type(name) is str and name
            assert type in ('good', 'service')
            assert _type(active) is bool
            if caption is not None:
                assert _type(caption) is str
            if description is not None:
                assert _type(description) is str
            if attributes is not None:
                assert _type(attributes) is list
            assert _type(shippable) is bool
            if url is not None:
                assert _type(url) is str
            if statement_descriptor is not None:
                assert _type(statement_descriptor) is str
                assert len(statement_descriptor) <= 22
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__(id)

        self.name = name
        self.type = type
        self.active = active
        self.caption = caption
        self.description = description
        self.attributes = attributes
        self.shippable = shippable
        self.url = url
        self.statement_descriptor = statement_descriptor
        self.metadata = metadata or {}

        schedule_webhook(Event('product.created', self))


class Refund(StripeObject):
    object = 'refund'
    _id_prefix = 're_'

    def __init__(self, charge=None, amount=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        try:
            assert type(charge) is str and charge.startswith('ch_')
            if amount is not None:
                assert type(amount) is int and amount > 0
        except AssertionError:
            raise UserError(400, 'Bad request')

        charge_obj = Charge._api_retrieve(charge)

        # All exceptions must be raised before this point.
        super().__init__()

        self.charge = charge
        self.metadata = metadata or {}
        self.amount = amount
        self.date = self.created
        self.currency = charge_obj.currency
        self.status = 'succeeded'

        if self.amount is None:
            self.amount = charge_obj.amount

    @classmethod
    def _api_list_all(cls, url, charge=None, limit=None):
        try:
            if charge is not None:
                assert type(charge) is str and charge.startswith('ch_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        li = super(Refund, cls)._api_list_all(url, limit=limit)
        if charge is not None:
            Charge._api_retrieve(charge)  # to return 404 if not existant
            li._list = [r for r in li._list if r.charge == charge]
        li._list.sort(key=lambda i: i.date, reverse=True)
        return li


class Source(StripeObject):
    object = 'source'
    _id_prefix = 'src_'

    def __init__(self, type=None, currency=None, owner=None, metadata=None,
                 # custom arguments depending on the type:
                 sepa_debit=None,
                 **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type in (
                'ach_credit_transfer', 'ach_debit', 'alipay', 'bancontact',
                'bitcoin', 'card', 'eps', 'giropay', 'ideal', 'multibanco',
                'p24', 'sepa_debit', 'sofort', 'three_d_secure')
            assert _type(currency) is str and currency
            if owner is not None:
                assert _type(owner) is dict
                assert _type(owner.get('name', '')) is str
                assert _type(owner.get('email', '')) is str
            if type == 'sepa_debit':
                assert _type(sepa_debit) is dict
                assert 'iban' in sepa_debit
                assert _type(sepa_debit['iban']) is str
                assert 14 <= len(sepa_debit['iban']) <= 34
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.type = type
        self.currency = currency
        self.owner = owner
        self.metadata = metadata or {}
        self.status = 'chargeable'
        self.usage = 'reusable'

        if self.type == 'sepa_debit':
            self._sepa_debit_iban = \
                re.sub(r'\s', '', sepa_debit['iban']).upper()
            self.sepa_debit = {
                'country': self._sepa_debit_iban[:2],
                'bank_code': self._sepa_debit_iban[4:12],
                'last4': self._sepa_debit_iban[-4:],
                'fingerprint': fingerprint(self._sepa_debit_iban),
                'mandate_reference': 'NXDSYREGC9PSMKWY',
                'mandate_url': 'https://fake/NXDSYREGC9PSMKWY',
            }

    def _requires_authentication(self):
        if self.type == 'sepa_debit':
            return PaymentMethod._requires_authentication(self)
        return False

    def _attaching_is_declined(self):
        if self.type == 'sepa_debit':
            return PaymentMethod._attaching_is_declined(self)
        return False

    def _charging_is_declined(self):
        if self.type == 'sepa_debit':
            return PaymentMethod._charging_is_declined(self)
        return False


class SetupIntent(StripeObject):
    object = 'setup_intent'
    _id_prefix = 'seti_'

    def __init__(self, customer=None, usage=None, payment_method_types=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if usage is None:
                usage = 'off_session'
            assert usage in ('off_session', 'on_session')
            if payment_method_types is None:
                payment_method_types = ['card']
            assert type(payment_method_types) is list
            assert all(t in ('card', 'sepa_debit', 'ideal')
                       for t in payment_method_types)
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.customer = customer
        self.usage = usage
        self.metadata = metadata or {}
        self.client_secret = self.id + '_secret_' + random_id(16)
        self.payment_method_types = payment_method_types
        self.payment_method = None
        self.status = 'requires_payment_method'
        self.next_action = None

    @classmethod
    def _api_confirm(cls, id, use_stripe_sdk=None, client_secret=None,
                     payment_method_data=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('seti_')
            if client_secret is not None:
                assert type(client_secret) is str
            if payment_method_data is not None:
                assert type(payment_method_data) is dict
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if client_secret and client_secret != obj.client_secret:
            raise UserError(401, 'Unauthorized')

        if payment_method_data:
            if obj.payment_method is not None:
                raise UserError(400, 'Bad request')

            pm = PaymentMethod(**payment_method_data)
            obj.payment_method = pm.id

            if pm._attaching_is_declined():
                obj.status = 'canceled'
                obj.next_action = None
                raise UserError(402, 'Your card was declined.',
                                {'code': 'card_declined'})
            elif pm._requires_authentication():
                obj.status = 'requires_action'
                obj.next_action = {'type': 'use_stripe_sdk',
                                   'use_stripe_sdk': {
                                       'type': 'three_d_secure_redirect',
                                       'stripe_js': ''}}
            else:
                obj.status = 'succeeded'
                obj.next_action = None
        elif obj.payment_method is None:
            obj.status = 'requires_payment_method'
            obj.next_action = None
        else:
            obj.status = 'succeeded'
            obj.next_action = None
        return obj

    @classmethod
    def _api_cancel(cls, id, use_stripe_sdk=None, client_secret=None,
                    **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(id) is str and id.startswith('seti_')
            if client_secret is not None:
                assert type(client_secret) is str
        except AssertionError:
            raise UserError(400, 'Bad request')

        obj = cls._api_retrieve(id)

        if client_secret and client_secret != obj.client_secret:
            raise UserError(401, 'Unauthorized')

        obj.status = 'canceled'
        obj.next_action = None
        return obj


extra_apis.extend((
    ('POST', '/v1/setup_intents/{id}/confirm', SetupIntent._api_confirm),
    ('POST', '/v1/setup_intents/{id}/cancel', SetupIntent._api_cancel)))


class Subscription(StripeObject):
    object = 'subscription'
    _id_prefix = 'sub_'

    def __init__(self, customer=None, metadata=None, items=None,
                 trial_end=None, default_tax_rates=None,
                 plan=None, quantity=None,  # legacy support
                 tax_percent=None,  # deprecated
                 enable_incomplete_payments=True,  # legacy support
                 payment_behavior='allow_incomplete',
                 trial_period_days=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        # Legacy support (stripe-php still uses these parameters instead of
        # providing `items: [...]`):
        if items is None and plan is not None:
            items = [{'plan': plan, 'quantity': quantity}]

        trial_end = try_convert_to_int(trial_end)
        tax_percent = try_convert_to_float(tax_percent)
        enable_incomplete_payments = try_convert_to_bool(
            enable_incomplete_payments)
        trial_period_days = try_convert_to_int(trial_period_days)

        try:
            assert type(customer) is str and customer.startswith('cus_')
            if trial_end is not None:
                if trial_end == 'now':
                    trial_end = int(time.time())
                assert type(trial_end) is int
                assert trial_end > 1500000000
            if tax_percent is not None:
                assert default_tax_rates is None
                assert type(tax_percent) is float
                assert tax_percent >= 0 and tax_percent <= 100
            if default_tax_rates is not None:
                assert tax_percent is None
                assert type(default_tax_rates) is list
                assert all(type(txr) is str and txr.startswith('txr_')
                           for txr in default_tax_rates)
            if trial_period_days is not None:
                assert type(trial_period_days) is int
            assert type(items) is list
            for item in items:
                assert type(item.get('plan', None)) is str
                if item.get('quantity', None) is not None:
                    item['quantity'] = try_convert_to_int(item['quantity'])
                    assert type(item['quantity']) is int
                    assert item['quantity'] > 0
                else:
                    item['quantity'] = 1
                item['tax_rates'] = item.get('tax_rates', None)
                if item['tax_rates'] is not None:
                    assert type(item['tax_rates']) is list
                    assert all(type(tr) is str for tr in item['tax_rates'])
            assert type(enable_incomplete_payments) is bool
            assert payment_behavior in ('allow_incomplete',
                                        'error_if_incomplete')
        except AssertionError:
            raise UserError(400, 'Bad request')

        if len(items) != 1:
            raise UserError(500, 'Not implemented')

        Customer._api_retrieve(customer)  # to return 404 if not existant
        for item in items:
            Plan._api_retrieve(item['plan'])  # to return 404 if not existant
            # To return 404 if not existant:
            if item['tax_rates'] is not None:
                [TaxRate._api_retrieve(tr) for tr in item['tax_rates']]
        # To return 404 if not existant:
        if default_tax_rates is not None:
            default_tax_rates = [TaxRate._api_retrieve(tr)
                                 for tr in default_tax_rates]

        # All exceptions must be raised before this point.
        super().__init__()

        self.customer = customer
        self.metadata = metadata or {}
        self.tax_percent = tax_percent
        self.default_tax_rates = default_tax_rates
        self.application_fee_percent = None
        self.cancel_at_period_end = False
        self.canceled_at = None
        self.discount = None
        self.ended_at = None
        self.quantity = items[0]['quantity']
        self.status = 'incomplete'
        self.trial_end = None
        self.trial_start = None
        self.trial_period_days = trial_period_days
        self.latest_invoice = None
        self.start_date = int(time.time())
        self._enable_incomplete_payments = (
            enable_incomplete_payments and
            payment_behavior != 'error_if_incomplete')

        self._set_up_plan(Plan._api_retrieve(items[0]['plan']))

        self.items = List('/v1/subscription_items?subscription=' + self.id)
        self.items._list.append(
            SubscriptionItem(
                subscription=self.id,
                plan=items[0]['plan'],
                quantity=items[0]['quantity'],
                tax_rates=items[0]['tax_rates']))

        create_an_invoice = \
            self.trial_end is None and self.trial_period_days is None
        if create_an_invoice:
            self._create_invoice()

        schedule_webhook(Event('customer.subscription.created', self))

    @property
    def plan(self):
        return self.items._list[0].plan

    def _set_up_plan(self, plan):
        current_period_start = datetime.now()
        current_period_end = current_period_start
        if plan.interval == 'day':
            current_period_end += timedelta(days=1)
        elif plan.interval == 'week':
            current_period_end += timedelta(days=7)
        elif plan.interval == 'month':
            current_period_end += relativedelta(months=1)
        elif plan.interval == 'year':
            current_period_end += relativedelta(years=1)
        self.current_period_start = int(current_period_start.timestamp())
        self.current_period_end = int(current_period_end.timestamp())

    def _create_invoice(self):
        pending_items = [ii for ii in InvoiceItem._api_list_all(
            None, customer=self.customer, limit=99)._list
            if ii.invoice is None]

        for si in self.items._list:
            pending_items.append(si)

        # Create associated invoice
        invoice = Invoice(
            customer=self.customer,
            subscription=self.id,
            items=pending_items,
            tax_percent=self.tax_percent,
            default_tax_rates=[tr.id
                               for tr in (self.default_tax_rates or [])],
            date=self.current_period_start)
        self.latest_invoice = invoice.id
        invoice._finalize()
        if invoice.status != 'paid':  # 0 € invoices are already 'paid'
            Invoice._api_pay_invoice(invoice.id)

        if invoice.status == 'paid':
            self.status = 'active'
        elif invoice.charge:
            if invoice.charge.status == 'failed':
                if self.status != 'incomplete':
                    self._on_recurring_payment_failure(invoice)
            # If source is SEPA, subscription starts `active` (even with
            # `enable_incomplete_payments`), then is canceled later if the
            # payment fails:
            if (invoice.charge.status == 'pending' and
                    PaymentMethod._api_retrieve(
                        invoice.charge.payment_method).type == 'sepa_debit'):
                self.status = 'active'

    def _on_initial_payment_success(self, invoice):
        self.status = 'active'

    def _on_initial_payment_failure_now(self, invoice):
        if not self._enable_incomplete_payments:
            super()._api_delete(self.id)
            raise UserError(402, invoice.charge.failure_message,
                            {'code': invoice.charge.failure_code})

    def _on_initial_payment_failure_later(self, invoice):
        Subscription._api_delete(self.id)

    def _on_initial_payment_voided(self, invoice):
        if self._enable_incomplete_payments:
            self.status = 'incomplete_expired'
        else:
            self.status = 'canceled'

    def _on_recurring_payment_failure(self, invoice):
        # If source is SEPA, any payment failure at creation or upgrade cancels
        # the subscription:
        if (invoice.charge and PaymentMethod._api_retrieve(
                invoice.charge.payment_method).type == 'sepa_debit'):
            return Subscription._api_delete(self.id)

        self.status = 'past_due'

    def _update(self, metadata=None, items=None, trial_end=None,
                default_tax_rates=None, tax_percent=None,
                plan=None, quantity=None,  # legacy support
                prorate=None, proration_date=None, cancel_at_period_end=None,
                # Currently unimplemented, only False works as expected:
                enable_incomplete_payments=False):

        # Legacy support (stripe-php still uses these parameters instead of
        # providing `items: [...]`):
        if items is None and plan is not None:
            items = [{'plan': plan, 'quantity': quantity}]

        trial_end = try_convert_to_int(trial_end)
        tax_percent = try_convert_to_float(tax_percent)
        prorate = try_convert_to_bool(prorate)
        proration_date = try_convert_to_int(proration_date)
        cancel_at_period_end = try_convert_to_bool(cancel_at_period_end)

        try:
            if trial_end is not None:
                if trial_end == 'now':
                    trial_end = int(time.time())
                assert type(trial_end) is int
                assert trial_end > 1500000000
            if tax_percent is not None:
                assert default_tax_rates is None
                assert type(tax_percent) is float
                assert tax_percent >= 0 and tax_percent <= 100
            if default_tax_rates is not None:
                assert tax_percent is None
                assert type(default_tax_rates) is list
                assert all(type(txr) is str and txr.startswith('txr_')
                           for txr in default_tax_rates)
            if prorate is not None:
                assert type(prorate) is bool
            if proration_date is not None:
                assert type(proration_date) is int
                assert proration_date > 1500000000
            if cancel_at_period_end is not None:
                assert type(cancel_at_period_end) is bool
            if items is not None:
                assert type(items) is list
                for item in items:
                    id = item.get('id', None)
                    if id is not None:
                        assert type(id) is str and id.startswith('si_')
                    if item.get('quantity', None) is not None:
                        item['quantity'] = try_convert_to_int(item['quantity'])
                        assert type(item['quantity']) is int
                        assert item['quantity'] > 0
                    else:
                        item['quantity'] = 1
                    item['tax_rates'] = item.get('tax_rates', None)
                    if item['tax_rates'] is not None:
                        assert type(item['tax_rates']) is list
                        assert all(type(tr) is str for tr in item['tax_rates'])
        except AssertionError:
            raise UserError(400, 'Bad request')

        old_plan = self.plan
        if items is not None:
            if len(items) != 1:
                raise UserError(500, 'Not implemented')

            # If no plan specified in update request, we stay on the current
            # one
            if not items[0].get('plan', None):
                items[0]['plan'] = self.plan.id

            # To return 404 if not existant:
            Plan._api_retrieve(items[0]['plan'])

            # To return 404 if not existant:
            if items[0]['tax_rates'] is not None:
                [TaxRate._api_retrieve(tr) for tr in items[0]['tax_rates']]

            self.quantity = items[0]['quantity']

            if (self.items._list[0].plan.id != items[0]['plan'] or
                    self.items._list[0].quantity != items[0]['quantity']):
                self.items = List('/v1/subscription_items?subscription=' +
                                  self.id)
                item = SubscriptionItem(subscription=self.id,
                                        plan=items[0]['plan'],
                                        quantity=items[0]['quantity'],
                                        tax_rates=items[0]['tax_rates'])
                self.items._list.append(item)

                # Create unused time pending item.
                # Get previous invoice for this subscription and customer, and
                # deduce what is already paid:
                # TODO: Better not to use limit, but take date into account
                previous = Invoice._api_list_all(None, customer=self.customer,
                                                 subscription=self.id,
                                                 limit=99)
                for previous_invoice in previous._list:
                    previous_tax_rates = [tr.id for tr in (
                        previous_invoice.lines._list[0].tax_rates or [])]
                    InvoiceItem(amount=- previous_invoice.subtotal,
                                currency=previous_invoice.currency,
                                proration=True,
                                description='Unused time',
                                tax_rates=previous_tax_rates,
                                customer=self.customer)

            elif self.items._list[0].tax_rates != items[0]['tax_rates']:
                self.items = List('/v1/subscription_items?subscription=' +
                                  self.id)
                item = SubscriptionItem(subscription=self.id,
                                        plan=items[0]['plan'],
                                        quantity=items[0]['quantity'],
                                        tax_rates=items[0]['tax_rates'])
                self.items._list.append(item)

        if tax_percent is not None:
            self.tax_percent = tax_percent
        if default_tax_rates is not None:
            self.default_tax_rates = [TaxRate._api_retrieve(tr)
                                      for tr in default_tax_rates]

        if trial_end is not None:
            self.trial_end = trial_end

        if cancel_at_period_end is not None:
            self.cancel_at_period_end = cancel_at_period_end

        if (self.plan.interval != old_plan.interval or
                self.plan.interval_count != old_plan.interval_count):
            self._set_up_plan(Plan._api_retrieve(items[0]['plan']))

        # If the subscription is updated to a more expensive plan, an invoice
        # is not automatically generated. To achieve that, an invoice has to
        # be manually created using the POST /invoices route.
        create_an_invoice = self.plan.billing_scheme == 'per_unit' and (
            self.plan.interval != old_plan.interval or
            self.plan.interval_count != old_plan.interval_count)
        if create_an_invoice:
            self._create_invoice()

    @classmethod
    def _api_delete(cls, id):
        obj = Subscription._api_retrieve(id)
        obj.ended_at = int(time.time())
        obj.status = 'canceled'
        schedule_webhook(Event('customer.subscription.deleted', obj))
        return obj

    @classmethod
    def _api_list_all(cls, url, customer=None, status=None, limit=None):
        try:
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if status is not None:
                assert status in ('all', 'incomplete', 'incomplete_expired',
                                  'trialing', 'active', 'past_due', 'unpaid',
                                  'canceled')
        except AssertionError:
            raise UserError(400, 'Bad request')

        li = super(Subscription, cls)._api_list_all(url, limit=limit)
        if status is None:
            li._list = [sub for sub in li._list if sub.status not in
                        ('canceled', 'incomplete_expired')]
        elif status != 'all':
            li._list = [sub for sub in li._list if sub.status == status]
        if customer is not None:
            Customer._api_retrieve(customer)  # to return 404 if not existant
            li._list = [sub for sub in li._list if sub.customer == customer]
        return li


class SubscriptionItem(StripeObject):
    object = 'subscription_item'
    _id_prefix = 'si_'

    def __init__(self, subscription=None, plan=None, quantity=1,
                 tax_rates=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        quantity = try_convert_to_int(quantity)
        try:
            assert type(subscription) is str
            assert subscription.startswith('sub_')
            assert type(plan) is str
            assert type(quantity) is int and quantity > 0
            if tax_rates is not None:
                assert type(tax_rates) is list
                assert all(type(tr) is str for tr in tax_rates)
        except AssertionError:
            raise UserError(400, 'Bad request')

        plan = Plan._api_retrieve(plan)  # to return 404 if not existant
        # To return 404 if not existant:
        if tax_rates is not None:
            tax_rates = [TaxRate._api_retrieve(tr) for tr in tax_rates]

        # All exceptions must be raised before this point.
        super().__init__()

        self.plan = plan
        self.quantity = quantity
        self.tax_rates = tax_rates
        self.metadata = metadata or {}

        self._subscription = subscription

    def _calculate_amount(self):
        if self.plan.billing_scheme == 'per_unit':
            return self.plan.amount * self.quantity

        if self.plan.tiers_mode == 'volume':
            index = next(
                (i for i, t in enumerate(self.plan.tiers)
                    if t['up_to'] == 'inf'
                    or self.quantity <= int(t['up_to'])))
            return self._calculate_amount_in_tier(
                self.quantity, index)

        if self.plan.tiers_mode == 'graduated':
            quantity = self.quantity
            amount = 0

            tier_from = -1
            for i, t in enumerate(self.plan.tiers):
                tier_from += 1
                if quantity <= 0 or tier_from > quantity:
                    break

                amount += self._calculate_amount_in_tier(
                    quantity - tier_from, i)

                if t['up_to'] == 'inf':
                    quantity = 0
                else:
                    up_to = int(t['up_to'])
                    quantity -= up_to
                    tier_from = up_to

            return amount

        return 0

    def _calculate_amount_in_tier(self, quantity, index):
        t = self.plan.tiers[index]
        return int(t['unit_amount']) * quantity + int(t['flat_amount'])


class TaxId(StripeObject):
    object = 'tax_id'
    _id_prefix = 'txi_'

    def __init__(self, country=None, customer=None, type=None, value=None,
                 **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert _type(customer) is str
            assert customer.startswith('cus_')
            assert type in ('eu_vat', 'nz_gst', 'au_abn')
            assert _type(value) is str and len(value) > 10
            if country is None:
                country = value[0:2]
            assert _type(country) is str
        except AssertionError:
            raise UserError(400, 'Bad request')

        Customer._api_retrieve(customer)  # to return 404 if not existant

        # All exceptions must be raised before this point.
        super().__init__()

        self.country = country
        self.customer = customer
        self.type = type
        self.value = value

        self.verification = {'status': 'verified',
                             'verified_name': '',
                             'verified_address': ''}
        # Test values from
        # https://stripe.com/docs/billing/testing#customer-tax-id-verfication
        if '111111111' in value:
            self.verification['status'] = 'unverified'
        elif '222222222' in value:
            self.verification['status'] = 'pending'


class TaxRate(StripeObject):
    object = 'tax_rate'
    _id_prefix = 'txr_'

    def __init__(self, display_name=None, inclusive=None, percentage=None,
                 active=True, description=None, jurisdiction=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        inclusive = try_convert_to_bool(inclusive)
        percentage = try_convert_to_float(percentage)
        active = try_convert_to_bool(active)
        try:
            assert type(display_name) is str and display_name
            assert type(inclusive) is bool
            assert type(percentage) is float
            assert type(active) is bool
            assert percentage >= 0 and percentage <= 100
            assert description is None or type(description) is str
            assert jurisdiction is None or type(jurisdiction) is str
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.display_name = display_name
        self.inclusive = inclusive
        self.percentage = percentage
        self.active = active
        self.description = description
        self.jurisdiction = jurisdiction
        self.metadata = metadata or {}

    def _tax_amount(self, amount):
        return {'amount': int(amount * self.percentage / 100.0),
                'inclusive': self.inclusive,
                'tax_rate': self.id}


class Token(StripeObject):
    object = 'token'
    _id_prefix = 'tok_'

    def __init__(self, card=None, customer=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert type(card) is dict
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        # If this raises, abort and don't create the token
        card['object'] = 'card'
        card_obj = Card(source=card)
        if customer is not None:
            card_obj.customer = customer

        # All exceptions must be raised before this point.
        super().__init__()

        self.type = 'card'
        self.card = card_obj
