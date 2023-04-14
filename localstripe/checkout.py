CHECKOUT_HTML = """
<html><body>
<form>
  <label for="cardNumber">Card Number:</label>
  <br>
  <input type="text" maxlength="16" minlength="16" id="cardNumber" name="cardNumber" placeholder="1234123412341234">
  <br>
  <input type="number" id="cardExpiry" minlength="4" maxlength="4" placeholder="MMYY" name="cardExpiry">
  <input type="number" id="cardCvc" minlength="3" maxlength="3" placeholder="CVC" name="cardCvc">
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
    return CHECKOUT_HTML

checkout_apis.append(('GET', '/c/pay/', checkout_page))
