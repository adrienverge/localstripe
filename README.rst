localstripe
===========

*A fake but stateful Stripe server that you can run locally, for testing
purposes.*

This is a program that you can launch to simulate a Stripe server locally,
without touching real Stripe servers nor the Internet.

Unlike other test/mock software like `stripe-mock
<https://github.com/stripe/stripe-mock>`_, localstripe is *stateful*: it keeps
track of the actions performed (creating a customer, adding a card, etc.) so
that these actions have an impact on the next queries.

The goal is to have a ready-to-use mock server for end-to-end testing any
application.

Features
--------

- **works with any language**: localstripe is not a library that you include,
  but a real server that you can query at ``http://localhost:8420``, using
  regular Stripe API requests
- **stateful**: if you create a Stripe object (let's say, a customer), you will
  get it back on future requests
- **integrates with Stripe Elements**: localstripe includes a JavaScript file
  that can mock Stripe Elements on any webpage, allowing you to create tokens on
  the fake server, from your webpage
- **supports webhooks** that you can customize using a special API route

Get started
-----------

Install localstripe:

.. code:: shell

 pip3 install --user -U localstripe
 # or, to install globally:
 sudo pip3 install localstripe

Then simply run the command ``localstripe``. The fake Stripe server is now
listening on port 8420.

Examples
--------

In the following example, let's create a ``Plan``, a ``Customer``, and subscribe
the latter to the former:

.. code:: shell

 curl localhost:8420/v1/plans -u sk_test_12345: \
      -d id=pro-plan \
      -d amount=2500 \
      -d currency=eur \
      -d interval=month \
      -d name="Plan for professionals"

.. code:: shell

 {
   "amount": 2500,
   "created": 1504187388,
   "currency": "eur",
   "id": "pro-plan",
   "interval": "month",
   "interval_count": 1,
   "livemode": false,
   "metadata": {},
   "name": "Plan for professionals",
   "object": "plan",
   "statement_descriptor": null,
   "trial_period_days": null
 }

.. code:: shell

 curl localhost:8420/v1/customers -u sk_test_12345: \
      -d description="Customer for david.anderson@example.com"

.. code:: shell

 {
   "id": "cus_b3IecP7GlNCPMM",
   "description": "Customer for david.anderson@example.com",
   "account_balance": 0,
   "currency": "eur",
   "default_source": null,
   ...
 }

.. code:: shell

 curl localhost:8420/v1/subscriptions -u sk_test_12345: \
      -d customer=cus_b3IecP7GlNCPMM \
      -d items[0][plan]=pro-plan

.. code:: shell

 {
   "id": "sub_UJIdAleo3FnwG7",
   "customer": "cus_b3IecP7GlNCPMM",
   "current_period_end": 1506779564,
   "current_period_start": 1504187564,
   "items": {
   ...
 }

Now if you retrieve that customer again, it has an associated subscription:

.. code:: shell

 curl localhost:8420/v1/customers/cus_b3IecP7GlNCPMM -u sk_test_12345:

.. code:: shell

 {
   "id": "cus_b3IecP7GlNCPMM",
   "description": "Customer for david.anderson@example.com",
   ...
   "subscriptions": {
     "data": [
       {
         "id": "sub_UJIdAleo3FnwG7",
         "items": {
           "data": [
             {
               "id": "si_2y5q9Q6lvAB9cr",
               "plan": {
                 "id": "pro-plan",
                 "name": "Plan for professionals",
                 "amount": 2500,
                 "currency": "eur",
                 "interval": "month",
   ...
 }

Integrate with your back-end
----------------------------

For instance in a Python application, you only need to set ``stripe.api_base``
to ``http://localhost:8420``:

.. code:: python

 import stripe

 stripe.api_key = 'sk_test_12345'
 stripe.api_base = 'http://localhost:8420'

Integrate with Stripe Elements
------------------------------

If your application takes card numbers on a web page using Stripe Elements, you
may want tokens to be sent to the mock server inside of the real Stripe server.

To achieve this, you need to load the
``http://localhost:8420/js.stripe.com/v3/`` script into your page. It will
overwrite the global ``Stripe`` object, so new elements and card forms will
actually send data to the ``http://localhost:8420/v1/tokens`` API.

For example if you use a testing tool like Protractor, you need to inject this
JavaScript source in the web page before it creates card elements:

.. code:: html

 <script src="http://localhost:8420/js.stripe.com/v3/"></script>

Use webhooks
------------

Register a webhook using the special ``/_config`` route:

.. code:: shell

 curl localhost:8420/_config/webhooks/mywebhook1 \
      -d url=http://localhost:8888/api/url -d secret=whsec_s3cr3t

Then, localstripe will send webhooks to this url. Only a few event types are
currently supported (these include ``customer.created``, ``customer.updated``,
``customer.deleted``, ``customer.source.created``, ``invoice.created``,
``invoice.payment_succeeded``).

Hacking and contributing
------------------------

To quickly run localstripe from source, and reload when a file changed:

.. code:: shell

 find -name '*.py' | entr -r python3 -m localstripe

To quickly build and run localstripe from source:

.. code:: shell

 python3 setup.py sdist
 pip3 install --user --upgrade dist/localstripe-*.tar.gz
 localstripe

License
-------

This program is licensed under the GNU General Public License version 3.
