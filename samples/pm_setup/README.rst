localstripe sample: Set up a payment method for future payments
===============================================================

This is a demonstration of how to inject localstripe for testing a simplistic
client/server Stripe web integration. This is derived from the Stripe
instructions for collecting payment methods on a single-page web app.

**This sample is not intended to represent best practice for production code!**

From the localstripe directory...

.. code:: shell

 # Launch localstripe:
 python -m localstripe --from-scratch &
 # Launch this sample's server:
 python -m samples.pm_setup.server
 # ... now browse to http://0.0.0.0:8080 and try the test card
 # 4242424242424242.
