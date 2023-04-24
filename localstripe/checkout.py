from .resources import Session, PaymentMethod, Customer, Subscription, PaymentIntent, Plan

CHECKOUT_HTML = """
<html><body>
<form id="paymentForm" method="post">
  <label for="cardNumber">Card Number:</label>
  <br>
  <input type="text" maxlength="16" minlength="16" id="cardNumber" name="cardNumber" placeholder="1234123412341234">
  <br>
  <input type="text" id="cardExpiry" minlength="4" maxlength="4" placeholder="MMYY" name="cardExpiry">
  <input type="text" id="cardCvc" minlength="3" maxlength="3" placeholder="CVC" name="cardCvc">
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
checkout_extra_apis = []

def checkout_page(request):
    session_id = request.match_info.get('session_id', None)
    session = Session._api_retrieve(session_id)
    return CHECKOUT_HTML

def checkout_pay(session_id, cardNumber=None, cardExpiry=None, cardCvc=None, billingName=None):
  # Get session info
  session = Session._api_retrieve(session_id)

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

  # If customer doesn't exist create a new customer and attach payment method
  if customer is None:
    customer = Customer(name=billingName, email=session.customer_email, payment_method=pm.id, invoice_settings={'default_payment_method': pm.id})

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
    Subscription(customer=customer.id, items=plans)

  # One time payments
  elif session.mode == 'payment':
    item = session.line_items[0]['price_data']
    PaymentIntent._api_create(amount=item['unit_amount_decimal'],
                               currency=item['currency'],
                               customer=customer.id,
                               payment_method=pm.id,
                               confirm=True)

  return session.success_url.format(CHECKOUT_SESSION_ID=session_id)

checkout_html_apis.append(('GET', '/c/pay/{session_id}', checkout_page))
checkout_extra_apis.append(('POST', '/c/pay/{session_id}', checkout_pay))
