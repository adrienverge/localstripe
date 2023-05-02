from .resources import Session, PaymentMethod, Customer, Subscription, PaymentIntent, Plan
from .errors import UserError

CHECKOUT_HTML = """
<html><body>
<a href="{CANCEL_URL}">
	Back
</a>
<br>
<form id="paymentForm" method="post">
	<label for="cardNumber">Card Number:</label>
	<br>
	<input type="text" maxlength="16" minlength="16" id="cardNumber" name="cardNumber" placeholder="1234123412341234">
	<br>
	<input type="text" id="cardExpiry" minlength="4" maxlength="4" placeholder="MMYY" name="cardExpiry">
	<input type="text" id="cardCvc" minlength="3" maxlength="3" placeholder="CVC" name="cardCvc">
	<div style="color: red">{CARD_ERROR}</div>
	<br>
	<label for="billingName">Name on card:</label>
	<br>
	<input type="text" id="billingName" name="billingName">
	<br>
	<br>
</form>
<button type="submit" form="paymentForm" value="Pay">Pay</button>
</body></html>
"""

checkout_html_apis = []

def checkout_page(request, session_id, cardNumber=None, cardExpiry=None, cardCvc=None, billingName=None):
    session_id = request.match_info.get('session_id', None)
    session = Session._api_retrieve(session_id)
    html_vars = {"CANCEL_URL": session.cancel_url.format(CHECKOUT_SESSION_ID=session_id), "CARD_ERROR": ''}
    if request.method == "POST":
		# Get customer if it already exists
        customer = None
        if session.customer:
            customer = Customer._api_retrieve(session.customer)

		# Payment method data
        billing_details = {
			"name": billingName,
			"email": customer.email if customer else session.customer_email
		}
        card = {
			"number": cardNumber,
			"cvc": cardCvc,
			"exp_month": cardExpiry[0:2],
			"exp_year": cardExpiry[2:4],
		}

		# Created payment method
        pm = PaymentMethod(type=session.payment_method_types[0], billing_details=billing_details, card=card)

        if customer is None:
			# This tests out payment method
            try:
                customer = Customer(name=billingName, email=session.customer_email, payment_method=pm.id, invoice_settings={'default_payment_method': pm.id})
            except UserError as e:
                if e.code == 402:
                    html_vars["CARD_ERROR"] = "Your credit card was declined. Try paying with a debit card instead."
        else:
            try:
                pm._api_attach(pm.id, customer.id)
            except UserError as e:
                if e.code == 402:
                    html_vars["CARD_ERROR"] = "Your credit card was declined. Try paying with a debit card instead."

        if not html_vars["CARD_ERROR"]:
            return checkout_pay(session, customer.id, pm.id)

    return CHECKOUT_HTML.format(**html_vars)

def checkout_pay(session, customer, payment_method):
	# Recurring payments
    if session.mode == 'subscription':
		# Subscriptions require items to be plans so we first create plans before creating the subscription
        plans = []
        for item in session.line_items:
            product = item.get('price_data')
            plan_data = {
				"amount": product['unit_amount_decimal'],
				"currency": product['currency'],
				"product": product['product']
			}
            if session.mode == 'subscription':
                plan_data['interval'] = 'month'
            plan = Plan(**plan_data)
            plans.append({
				'plan': plan.id,
				'quantity': item['quantity'],
			})

		# this should auto create an invoice and attempt to pay it
        sub = Subscription(customer=customer, items=plans, metadata=session.subscription_data['metadata'])
        session.subscription = sub.id

	# One time payments
    elif session.mode == 'payment':
        pi_data = {
			"customer": customer,
			"payment_method": payment_method,
		}
        PaymentIntent._api_update(session.payment_intent, **pi_data)
        PaymentIntent._api_confirm(session.payment_intent)

    session._complete_session()

    return session.success_url.format(CHECKOUT_SESSION_ID=session.id)

checkout_html_apis.append(('GET', '/c/pay/{session_id}', checkout_page))
checkout_html_apis.append(('POST', '/c/pay/{session_id}', checkout_page))
