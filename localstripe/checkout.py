from .resources import Session

CHECKOUT_HTML = """
<html><body>
<form>
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
  <input type="submit" value="Pay">
</form>
</body></html>
"""

checkout_apis = []

def checkout_page(request):
    session_id = request.match_info.get('session_id', None)
    session = Session._api_retrieve(session_id)
    return CHECKOUT_HTML

checkout_apis.append(('GET', '/c/pay/{session_id}', checkout_page))
