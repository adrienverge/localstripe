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
import pickle
import random
import re
import string
import time

from dateutil.relativedelta import relativedelta

from .errors import UserError
from .webhooks import schedule_webhook


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

        obj = {}

        # Take basic properties
        for key, value in vars(self).items():
            if not key.startswith('_'):
                if isinstance(value, StripeObject):
                    obj[key] = value._export()
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
                if path is None:
                    id = obj[k]
                    assert type(id) is str
                    cls = StripeObject._get_class_for_id(id)
                    obj[k] = cls._api_retrieve(id)._export()
                else:
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

        self._number = number

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
        self.fingerprint = random_id(16)
        self.funding = 'credit'
        self.name = name
        self.tokenization_method = None

        self.customer = None

    @property
    def last4(self):
        return self._number[-4:]


class Charge(StripeObject):
    object = 'charge'
    _id_prefix = 'ch_'

    def __init__(self, amount=None, currency=None, description=None,
                 metadata=None, customer=None, source=None,
                 on_succeed=None, on_fail=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        try:
            assert type(amount) is int and amount >= 0
            assert type(currency) is str and currency
            if description is not None:
                assert type(description) is str
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
            if source is not None:
                assert type(source) is str
                assert source.startswith('src_') or source.startswith('card_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        if source is None:
            customer_obj = Customer._api_retrieve(customer)
            if customer_obj.default_source is None:
                raise UserError(404, 'This customer has no source')
            source = customer_obj.default_source

        if source.startswith('src_'):
            source = Source._api_retrieve(source)
        elif source.startswith('card_'):
            source = Card._api_retrieve(source)

        if customer is None:
            customer = source.customer

        if source.object == 'card':
            decline = {
                '4000000000000002': 'card_declined',  # fails when adding card
                '4000000000000341': 'card_declined',  # fails only at payment
                '4000000000000127': 'incorrect_cvc',
                '4000000000000069': 'expired_card',
                '4000000000000119': 'processing_error',
                '4242424242424241': 'incorrect_number',
            }.get(source._number, None)
            if decline:
                raise UserError(402, 'Your card was declined.',
                                {'code': decline})

        # All exceptions must be raised before this point.
        super().__init__()

        self.amount = amount
        self.currency = currency
        self.customer = customer
        self.description = description
        self.invoice = None
        self.metadata = metadata or {}
        self.paid = False
        self.status = 'pending'
        self.receipt_email = None
        self.receipt_number = None
        self.refunds = List('/v1/customers/' + self.id + '/sources')
        self.source = source

    def _set_callbacks(self, on_succeed, on_fail):
        if self.source.object == 'source' and self.source.type == 'sepa_debit':
            # From Stripe docs:
            # The charge status transitions from pending to failed.
            if self.source._sepa_debit_iban == 'DE62370400440532013001':
                async def callback():
                    await asyncio.sleep(0.5)
                    self.paid = False
                    self.status = 'failed'
                    if on_fail:
                        on_fail()
            else:
                async def callback():
                    await asyncio.sleep(0.5)
                    self.paid = True
                    self.status = 'succeeded'
                    if on_succeed:
                        on_succeed()
            asyncio.ensure_future(callback())
        else:
            self.paid = True
            self.status = 'succeeded'
            if on_succeed:
                on_succeed()

    @property
    def amount_refunded(self):
        refunded = 0
        for refund in self.refunds._list:
            refunded += refund.amount
        return refunded

    @property
    def refunded(self):
        return self.amount <= self.amount_refunded


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

    def __init__(self, description=None, email=None, business_vat_id=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            if description is not None:
                assert type(description) is str
            if email is not None:
                assert type(email) is str
            if business_vat_id is not None:
                assert type(business_vat_id) is str
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

        self.description = description or ''
        self.email = email or ''
        self.business_vat_id = business_vat_id
        self.metadata = metadata or {}
        self.account_balance = 0
        self.currency = 'eur'
        self.delinquent = False
        self.discount = None
        self.shipping = None
        self.default_source = None

        self.sources = List('/v1/customers/' + self.id + '/sources')

        schedule_webhook(Event('customer.created', self))

    @property
    def subscriptions(self):
        return Subscription._api_list_all(
            '/v1/customers/' + self.id + '/subscriptions', customer=self.id)

    @classmethod
    def _api_update(cls, id, **data):
        obj = super()._api_update(id, **data)
        schedule_webhook(Event('customer.updated', obj))
        return obj

    @classmethod
    def _api_delete(cls, id):
        obj = super()._api_retrieve(id)
        schedule_webhook(Event('customer.deleted', obj))
        return super()._api_delete(id)

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
            source_obj.customer = id
        else:
            source_obj = Card(source=source)
            source_obj.customer = id

        obj.sources._list.append(source_obj)

        if obj.default_source is None:
            obj.default_source = source_obj.id

        schedule_webhook(Event('customer.source.created', source_obj))

        return source_obj


extra_apis.append(
    ('POST', '/v1/customers/{id}/sources', Customer._api_add_source))

extra_apis.append(  # this is the old API route:
    ('POST', '/v1/customers/{id}/cards', Customer._api_add_source))


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
        raise UserError(400, 'Bad request')


class Invoice(StripeObject):
    object = 'invoice'
    _id_prefix = 'in_'

    def __init__(self, customer=None, subscription=None, metadata=None,
                 items=[], tax_percent=None, date=None, description=None,
                 upcoming=False, simulation=False, on_payment_fail=None,
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
            assert type(tax_percent) is float
            assert tax_percent >= 0 and tax_percent <= 100
            if date is not None:
                assert type(date) is int and date > 1500000000
            else:
                date = int(time.time())
            if description is not None:
                assert type(description) is str
        except AssertionError:
            raise UserError(400, 'Bad request')

        customer_obj = Customer._api_retrieve(customer)
        if customer_obj.default_source is None:
            raise UserError(404, 'This customer has no source')
        if subscription is not None:
            subscription_obj = Subscription._api_retrieve(subscription)

        # All exceptions must be raised before this point.
        super().__init__()

        self.customer = customer
        self.subscription = subscription
        self.tax_percent = tax_percent
        self.date = date
        self.metadata = metadata or {}
        self.application_fee = None
        self.attempt_count = 1
        self.attempted = True
        self.closed = True
        self.currency = 'eur'
        self.description = description
        self.discount = None
        self.ending_balance = 0
        self.forgiven = False
        self.receipt_number = None
        self.starting_balance = 0
        self.statement_descriptor = None
        self.webhooks_delivered_at = self.date

        self.period_start = None
        self.period_end = None
        if subscription is not None:
            self.period_start = subscription_obj.current_period_start
            self.period_end = subscription_obj.current_period_end

        self._charge = None

        self.lines = List('/v1/invoices/' + self.id + '/lines')
        for item in items:
            item.invoice = self.id
            self.lines._list.append(item)

        pending_items = [ii for ii in InvoiceItem._api_list_all(
            None, customer=self.customer, limit=99)._list
            if ii.invoice is None]
        for ii in pending_items:
            if not simulation:
                ii.invoice = self.id
            self.lines._list.append(ii)

        self._upcoming = upcoming

        self._on_payment_fail = on_payment_fail

        if not upcoming and not simulation:
            schedule_webhook(Event('invoice.created', self))

            self.charge  # trigger creation of charge

    @property
    def subtotal(self):
        return sum([ii.amount for ii in self.lines._list])

    @property
    def tax(self):
        return int(self.subtotal * self.tax_percent / 100.0)

    @property
    def total(self):
        return self.subtotal + self.tax

    @property
    def amount_due(self):
        return self.total

    @property
    def next_payment_attempt(self):
        if self._upcoming:
            return self.date

    @property
    def paid(self):
        if self._charge is not None:
            return Charge._api_retrieve(self._charge).paid
        return not self._upcoming

    @property
    def charge(self):
        if self._charge is None and not self._upcoming and self.total > 0:
            customer_obj = Customer._api_retrieve(self.customer)
            charge_obj = Charge(amount=self.total, currency=self.currency,
                                customer=self.customer,
                                source=customer_obj.default_source)
            self._charge = charge_obj.id

            def on_succeed():
                schedule_webhook(Event('invoice.payment_succeeded', self))

            def on_fail():
                schedule_webhook(Event('invoice.payment_failed', self))
                if self._on_payment_fail:
                    self._on_payment_fail()

            charge_obj._set_callbacks(on_succeed, on_fail)

        return self._charge

    @classmethod
    def _get_next_invoice(cls, customer=None, subscription=None,
                          tax_percent=None, description=None, metadata=None,
                          # /upcoming route properties:
                          upcoming=False,
                          coupon=None,
                          subscription_items=None,
                          subscription_prorate=None,
                          subscription_proration_date=None,
                          subscription_tax_percent=None,
                          subscription_trial_end=None):
        subscription_proration_date = \
            try_convert_to_int(subscription_proration_date)
        try:
            assert type(customer) is str and customer.startswith('cus_')
            if subscription_items is not None:
                assert type(subscription_items) is list
                for si in subscription_items:
                    assert type(si.get('plan', None)) is str
            if subscription_proration_date is not None:
                assert type(subscription_proration_date) is int
                assert subscription_proration_date > 1500000000
        except AssertionError:
            raise UserError(400, 'Bad request')

        # return 404 if not existant
        customer_obj = Customer._api_retrieve(customer)

        simulation = subscription_items is not None or \
            subscription_prorate is not None or \
            subscription_tax_percent is not None or \
            subscription_trial_end is not None

        current_subscription = None
        li = [s for s in customer_obj.subscriptions._list
              if subscription is None or s.id == subscription]
        if len(li):
            current_subscription = li[0]
        elif subscription is not None:
            raise UserError(404, 'No such subscription for customer')

        invoice_items = []
        items = subscription_items or \
            (current_subscription and current_subscription.items._list) or []
        for si in items:
            if subscription_items is not None:
                plan = Plan._api_retrieve(si['plan'])
            else:
                plan = si.plan
            invoice_items.append(
                InvoiceItem(subscription=subscription, plan=plan.id,
                            amount=plan.amount, currency=plan.currency,
                            description=plan.name, customer=customer))

        if tax_percent is None:
            if subscription_tax_percent is not None:
                tax_percent = subscription_tax_percent
            elif current_subscription:
                tax_percent = current_subscription.tax_percent
            else:
                tax_percent = 0.0

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
                       date=date,
                       description=description,
                       upcoming=upcoming)

        else:  # if simulation
            if subscription is not None:
                # Get previous invoice for this subscription and customer, and
                # deduce what is already paid:
                # TODO: Better not to use limit, but take date into account
                previous = cls._api_list_all(None, customer=customer,
                                             subscription=subscription,
                                             limit=99)
                for previous_invoice in previous._list:
                    invoice_items.append(
                        InvoiceItem(amount=- previous_invoice.subtotal,
                                    currency=previous_invoice.currency,
                                    proration=True,
                                    description='Unused time',
                                    customer=customer,
                                    period_start=previous_invoice.period_start,
                                    period_end=previous_invoice.period_end))

            invoice = cls(customer=customer,
                          items=invoice_items,
                          tax_percent=tax_percent,
                          date=date,
                          description=description,
                          upcoming=upcoming,
                          simulation=True)

            if subscription_proration_date is not None:
                for ii in invoice.lines._list:
                    ii.period['start'] = subscription_proration_date
                    ii.period['end'] = subscription_proration_date

            return invoice

    @classmethod
    def _api_create(cls, customer=None, subscription=None, tax_percent=None,
                    description=None, metadata=None):
        return cls._get_next_invoice(
            customer=customer, subscription=subscription,
            tax_percent=tax_percent, description=description,
            metadata=metadata)

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
                              subscription_tax_percent=None,
                              subscription_trial_end=None):
        invoice = cls._get_next_invoice(
            customer=customer, subscription=subscription,
            upcoming=True,
            coupon=coupon, subscription_items=subscription_items,
            subscription_prorate=subscription_prorate,
            subscription_proration_date=subscription_proration_date,
            subscription_tax_percent=subscription_tax_percent,
            subscription_trial_end=subscription_trial_end)

        # Do not store this invoice
        del store[cls.object + ':' + invoice.id]
        invoice.id = None

        return invoice

    @classmethod
    def _api_pay_invoice(cls, id):
        obj = Invoice._api_retrieve(id)

        if obj.total > 0:
            charge = Charge._api_retrieve(obj.charge)
            try:
                assert not charge.paid
            except AssertionError:
                raise UserError(400, 'Bad request')

            charge.paid = True

        return obj


extra_apis.extend((
    ('GET', '/v1/invoices/upcoming', Invoice._api_upcoming_invoice),
    ('POST', '/v1/invoices/{id}/pay', Invoice._api_pay_invoice)))


class InvoiceItem(StripeObject):
    object = 'invoiceitem'
    _id_prefix = 'ii_'

    def __init__(self, invoice=None, subscription=None, plan=None, amount=None,
                 currency=None, customer=None, period_start=None,
                 period_end=None, proration=False, description=None,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        amount = try_convert_to_int(amount)
        period_start = try_convert_to_int(period_start)
        period_end = try_convert_to_int(period_end)
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
        except AssertionError:
            raise UserError(400, 'Bad request')

        Customer._api_retrieve(customer)  # to return 404 if not existant
        if invoice is not None:
            Invoice._api_retrieve(invoice)  # to return 404 if not existant
        if plan is not None:
            plan = Plan._api_retrieve(plan)  # to return 404 if not existant

        # All exceptions must be raised before this point.
        super().__init__()

        self.invoice = invoice
        self.subscription = subscription
        self.plan = plan
        self.amount = amount
        self.currency = currency
        self.customer = customer
        self.date = int(time.time())
        self.period = dict(start=period_start, end=period_end)
        self.proration = proration
        self.description = description
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


class Plan(StripeObject):
    object = 'plan'

    def __init__(self, id=None, metadata=None, amount=None, product=None,
                 currency=None, interval=None, interval_count=1,
                 trial_period_days=None,
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
        try:
            assert type(id) is str and id
            assert type(amount) is int and amount >= 0
            assert type(currency) is str and currency
            assert type(interval) is str
            assert interval in ('day', 'week', 'month', 'year')
            assert type(interval_count) is int
            if trial_period_days is not None:
                assert type(trial_period_days) is int
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
        self.amount = amount
        self.currency = currency
        self.interval = interval
        self.interval_count = interval_count
        self.trial_period_days = trial_period_days

    @property
    def name(self):  # Support Stripe API <= 2018-02-05
        return Product._api_retrieve(self.product).name

    @property
    def statement_descriptor(self):  # Support Stripe API <= 2018-02-05
        return Product._api_retrieve(self.product).statement_descriptor


class Product(StripeObject):
    object = 'product'
    _id_prefix = 'prod_'

    # Save built-in keyword `type`, because the `type` property will
    # override it:
    _type = type

    def __init__(self, name=None, type=None, active=True, caption=None,
                 description=None, attributes=None, shippable=True, url=None,
                 statement_descriptor=None, metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        try:
            assert self._type(name) is str and name
            assert type in ('good', 'service')
            assert self._type(active) is bool
            if caption is not None:
                assert self._type(caption) is str
            if description is not None:
                assert self._type(description) is str
            if attributes is not None:
                assert self._type(attributes) is list
                assert all(self._type(a) is str for a in attributes)
            assert self._type(shippable) is bool
            if url is not None:
                assert self._type(url) is str
            if statement_descriptor is not None:
                assert self._type(statement_descriptor) is str
                assert len(statement_descriptor) <= 22
        except AssertionError:
            raise UserError(400, 'Bad request')

        # All exceptions must be raised before this point.
        super().__init__()

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

    # Save built-in keyword `type`, because the `type` property will
    # override it:
    _type = type

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
            assert self._type(currency) is str and currency
            if owner is not None:
                assert self._type(owner) is dict
                assert self._type(owner.get('name', '')) is str
                assert self._type(owner.get('email', '')) is str
            if type == 'sepa_debit':
                assert self._type(sepa_debit) is dict
                assert 'iban' in sepa_debit
                assert self._type(sepa_debit['iban']) is str
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
                'fingerprint': random_id(16),
                'mandate_reference': 'NXDSYREGC9PSMKWY',
                'mandate_url': 'https://fake/NXDSYREGC9PSMKWY',
            }


class Subscription(StripeObject):
    object = 'subscription'
    _id_prefix = 'sub_'

    def __init__(self, customer=None, metadata=None, items=None,
                 tax_percent=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        tax_percent = try_convert_to_float(tax_percent)
        try:
            assert type(customer) is str and customer.startswith('cus_')
            if tax_percent is not None:
                assert type(tax_percent) is float
                assert tax_percent >= 0 and tax_percent <= 100
            else:
                tax_percent = 0
            assert type(items) is list
            for item in items:
                assert type(item.get('plan', None)) is str
                if item.get('quantity', None) is not None:
                    item['quantity'] = try_convert_to_int(item['quantity'])
                    assert type(item['quantity']) is int
                    assert item['quantity'] > 0
                else:
                    item['quantity'] = 1
        except AssertionError:
            raise UserError(400, 'Bad request')

        if len(items) != 1:
            raise UserError(500, 'Not implemented')

        Customer._api_retrieve(customer)  # to return 404 if not existant
        plan = Plan._api_retrieve(items[0]['plan'])

        # All exceptions must be raised before this point.
        super().__init__()

        self.customer = customer
        self.metadata = metadata or {}
        self.tax_percent = tax_percent
        self.application_fee_percent = None
        self.cancel_at_period_end = False
        self.canceled_at = None
        self.discount = None
        self.ended_at = None
        self.quantity = 1
        self.status = 'active'
        self.trial_end = None
        self.trial_start = None

        self._set_up_subscription_and_invoice(plan)
        self.start = self.current_period_start

        schedule_webhook(Event('customer.subscription.created', self))

    @property
    def plan(self):
        return self.items._list[0].plan

    def _set_up_subscription_and_invoice(self, plan, create_an_invoice=True):
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

        self.items = List('/v1/subscription_items?subscription=' + self.id)
        self.items._list.append(
            SubscriptionItem(subscription=self.id, plan=plan.id, quantity=1))

        invoice_items = []

        # Get previous invoice for this subscription and customer, and
        # deduce what is already paid:
        # TODO: Better not to use limit, but take date into account
        previous = Invoice._api_list_all(None, customer=self.customer,
                                         subscription=self.id, limit=99)
        for previous_invoice in previous._list:
            invoice_items.append(
                InvoiceItem(amount=- previous_invoice.subtotal,
                            currency=previous_invoice.currency,
                            proration=True,
                            description='Unused time',
                            customer=self.customer))

        if create_an_invoice:
            for si in self.items._list:
                invoice_items.append(
                    InvoiceItem(subscription=self.id, plan=si.plan.id,
                                amount=si.plan.amount,
                                currency=si.plan.currency,
                                description=si.plan.name,
                                customer=self.customer,
                                period_start=self.current_period_start,
                                period_end=self.current_period_end))
            try:
                # Create associated invoice
                Invoice(customer=self.customer,
                        subscription=self.id,
                        items=invoice_items,
                        tax_percent=self.tax_percent,
                        date=self.current_period_start,
                        on_payment_fail=self._on_first_payment_failed)
            except UserError as e:
                self._on_first_payment_failed()
                raise e

    def _on_first_payment_failed(self):
        Subscription._api_delete(self.id)

    def _update(self, metadata=None, items=None, tax_percent=None,
                proration_date=None):
        tax_percent = try_convert_to_float(tax_percent)
        proration_date = try_convert_to_int(proration_date)
        try:
            if tax_percent is not None:
                assert type(tax_percent) is float
                assert tax_percent >= 0 and tax_percent <= 100
            if proration_date is not None:
                assert type(proration_date) is int
                assert proration_date > 1500000000
            if items is not None:
                assert type(items) is list
                for item in items:
                    id = item.get('id', None)
                    plan = item.get('plan', None)
                    quantity = try_convert_to_int(item.get('quantity', None))
                    assert id is not None or plan is not None
                    if id is not None:
                        assert type(id) is str and id.startswith('si_')
                    if quantity is not None:
                        assert type(quantity) is int and quantity > 0
        except AssertionError:
            raise UserError(400, 'Bad request')

        if tax_percent is not None:
            self.tax_percent = tax_percent

        if items is None or len(items) != 1 or not items[0]['plan']:
            raise UserError(500, 'Not implemented')

        plan = Plan._api_retrieve(items[0]['plan'])
        # If the subscription is updated to a more expensive plan, an invoice
        # is not automatically generated. To achieve that, an invoice has to
        # be manually created using the POST /invoices route.
        self._set_up_subscription_and_invoice(plan, create_an_invoice=False)

    @classmethod
    def _api_delete(cls, id):
        obj = super()._api_retrieve(id)
        obj.ended_at = int(time.time())
        obj.status = 'canceled'
        schedule_webhook(Event('customer.subscription.deleted', obj))
        return super()._api_delete(id)

    @classmethod
    def _api_list_all(cls, url, customer=None, limit=None):
        try:
            if customer is not None:
                assert type(customer) is str and customer.startswith('cus_')
        except AssertionError:
            raise UserError(400, 'Bad request')

        li = super(Subscription, cls)._api_list_all(url, limit=limit)
        if customer is not None:
            Customer._api_retrieve(customer)  # to return 404 if not existant
            li._list = [invoice for invoice in li._list
                        if invoice.customer == customer]
        return li


class SubscriptionItem(StripeObject):
    object = 'subscription_item'
    _id_prefix = 'si_'

    def __init__(self, subscription=None, plan=None, quantity=1,
                 metadata=None, **kwargs):
        if kwargs:
            raise UserError(400, 'Unexpected ' + ', '.join(kwargs.keys()))

        quantity = try_convert_to_int(quantity)
        try:
            assert type(subscription) is str
            assert subscription.startswith('sub_')
            assert type(plan) is str
            assert type(quantity) is int and quantity > 0
        except AssertionError:
            raise UserError(400, 'Bad request')

        plan = Plan._api_retrieve(plan)  # to return 404 if not existant

        # All exceptions must be raised before this point.
        super().__init__()

        self.plan = plan
        self.quantity = quantity
        self.metadata = metadata or {}

        self._subscription = subscription


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
