let seti;
let setiClientSecret;
let stripe;
let paymentElement;

const init = async () => {
  const response = await fetch('/publishable_key', {method: "GET"});
  const {
    stripe_api_pk: publishableKey,
  } = await response.json();

  stripe = Stripe(publishableKey);

  document.getElementById(
      'setup-form',
  ).addEventListener('submit', handleSetupSubmit);

  document.getElementById(
      'payment-method-form',
  ).addEventListener('submit', handlePaymentMethodSubmit);

  document.getElementById(
      'payment-form',
  ).addEventListener('submit', handlePaymentSubmit);
}

const handleSetupSubmit = async (event) => {
  event.preventDefault();

  const response = await fetch('/setup_intent', {method: "POST"});
  const {
    id: id,
    client_secret: clientSecret,
  } = await response.json();

  seti = id;
  setiClientSecret = clientSecret;

  const elements = stripe.elements({
    clientSecret: clientSecret,
  });

  if (paymentElement) {
    paymentElement.unmount();
  }

  paymentElement = elements.create('card');

  paymentElement.mount('#payment-method-element');

  document.getElementById(
      'payment-method-form-fieldset',
  ).removeAttribute('disabled');
}

let handlePaymentMethodSubmit = async (event) => {
  event.preventDefault();

  const {error} = await stripe.confirmCardSetup(setiClientSecret, {
    payment_method: {
      card: paymentElement,
    },
  });

  const container = document.getElementById('payment-method-result-message');
  if (error) {
    container.textContent = error.message;
  } else {
    const response = await fetch('/payment_method', {
      method: "POST",
      body: JSON.stringify({ setup_intent: seti })
    });
    if (response.ok) {
      container.textContent = "Successfully confirmed payment method!";
      document.getElementById(
          'payment-form-fieldset',
      ).removeAttribute('disabled');
    } else {
      container.textContent = "Error confirming payment method!";
    }
  }
};

let handlePaymentSubmit = async (event) => {
  event.preventDefault();

  const response = await fetch('/payment_intent', {
    method: "POST",
    body: JSON.stringify({
      amount: document.getElementById('payment-amount').value,
    })
  });
  const {client_secret: clientSecret} = await response.json();

  const {error} = await stripe.confirmCardPayment(clientSecret, {});

  const container = document.getElementById('payment-result-message');
  if (error) {
    container.textContent = error.message;
  } else {
    container.textContent = "Successfully confirmed payment!";
  }
};

await init();
