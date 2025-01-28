from argparse import ArgumentParser
from dataclasses import dataclass
from importlib.resources import as_file, files
import logging
from os import environ

from aiohttp import web
import stripe

use_real_stripe_api = False
stripe_api_pk = 'pk_test_12345'
stripe.api_key = 'sk_test_12345'


@dataclass
class CustomerState:
    cus: str | None = None
    pm: str | None = None


# Normally these values would be securely stored in a database, indexed by some
# authenticated customer identifier. For this sample, we have no authentication
# system so just store one global "customer":
customer_state = CustomerState()


app = web.Application()
routes = web.RouteTableDef()


@routes.get('/stripe.js')
async def stripe_js(request):
    del request

    global use_real_stripe_api

    if use_real_stripe_api:
        stripe_js_location = 'https://js.stripe.com/v3/'
    else:
        stripe_js_location = 'http://localhost:8420/js.stripe.com/v3/'

    return web.Response(content_type='application/javascript', text=f"""\
const script = document.createElement('script');
script.src = "{stripe_js_location}";
document.head.appendChild(script);
""")


@routes.get('/pm_setup.js')
async def pm_setup_js(request):
    del request

    with as_file(files('samples.pm_setup').joinpath('pm_setup.js')) as f:
        return web.FileResponse(f)


@routes.get('/')
async def index(request):
    del request

    with files('samples.pm_setup').joinpath('index.html').open('r') as f:
        return web.Response(
            text=f.read(),
            content_type='text/html',
        )


@routes.get('/publishable_key')
async def publishable_key(request):
    return web.json_response(dict(
        stripe_api_pk=stripe_api_pk,
    ))


@routes.post('/setup_intent')
async def setup_intent(request):
    del request

    global customer_state, stripe_api_pk

    cus = stripe.Customer.create()
    customer_state.cus = cus.id

    seti = stripe.SetupIntent.create(
        customer=cus.id,
        payment_method_types=["card"],
    )
    return web.json_response(dict(
        id=seti.id,
        client_secret=seti.client_secret,
    ))


@routes.post('/payment_method')
async def payment_method(request):
    body = await request.json()

    seti = stripe.SetupIntent.retrieve(body['setup_intent'])

    customer_state.pm = seti.payment_method

    return web.Response()


@routes.post('/payment_intent')
async def payment_intent(request):
    global customer_state

    body = await request.json()

    pi = stripe.PaymentIntent.create(
        customer=customer_state.cus,
        payment_method=customer_state.pm,
        amount=body['amount'],
        currency='usd',
    )

    return web.json_response(dict(
        client_secret=pi.client_secret,
    ))


@routes.post('/pay_off_session')
async def pay_off_session(request):
    global customer_state

    body = await request.json()

    pi = stripe.PaymentIntent.create(
        customer=customer_state.cus,
        payment_method=customer_state.pm,
        amount=body['amount'],
        currency='usd',
        off_session=True,
        confirm=True,
    )

    if pi.status == 'succeeded':
        return web.Response()

    return web.Response(status=400, text=f'Payment failed; status={pi.status}')


app.add_routes(routes)


def main():
    global stripe_api_pk, use_real_stripe_api

    parser = ArgumentParser()
    parser.add_argument(
        '--real-stripe', action='store_true', help="""\
Use the actual Stripe API. This is useful for verifying this sample and
localstripe are providing an accurate simulation.

To use, you must set the environment variable SK to your Stripe account's
secret API key, and PK to your Stripe account's publishable API key. It is
obviously recommended that you use the test mode variant of your Stripe account
for this.
""")
    args = parser.parse_args()

    if args.real_stripe:
        use_real_stripe_api = True
        stripe.api_key = environ.get('SK')
        stripe_api_pk = environ.get('PK')
        if not stripe.api_key or not stripe_api_pk:
            parser.print_help()
            parser.exit(1)
    else:
        stripe.api_base = 'http://localhost:8420'

    logger = logging.getLogger('aiohttp.access')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    web.run_app(app, access_log=logger)


if __name__ == '__main__':
    main()
