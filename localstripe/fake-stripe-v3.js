/*
 * Copyright 2017 Adrien Vergé
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

// Check and warn if the real Stripe is already used in webpage
(function () {
  var iframes = document.getElementsByTagName('iframe');

  for (var i = 0; i < iframes.length; i++) {
    if (iframes[i].getAttribute('name').startsWith('__privateStripeFrame')) {
      console.log('localstripe: Stripe seems to be already used in page ' +
                  '(found a <iframe name="' + iframes[i].getAttribute('name') +
                  '"> in document). For the mock service to work, you need to' +
                  ' include its JavaScript library *before* creating Stripe ' +
                  'elements in the page.');
      //var fakeInput = document.createElement('input');
      //fakeInput.setAttribute('type', 'text');
      //fakeInput.setAttribute('value', 'coucou toi');

      //iframes[i].parentElement.insertBefore(fakeInput, iframes[i]);
      //iframes[i].parentElement.removeChild(iframes[i]);
    }
  }
})();

class Element {
  mount(domElement) {
    if (typeof domElement === 'string') {
      domElement = document.querySelector(domElement)[0];
    }

    const span = document.createElement('span');
    span.textContent = 'Fake Stripe: ';
    domElement.appendChild(span);

    const inputs = {
      number: null,
      exp_month: null,
      exp_year: null,
      cvc: null,
      address_zip: null,
    };

    const changed = event => {
      this.value = {
        number: inputs.number.value,
        exp_month: inputs.exp_month.value,
        exp_year: '20' + inputs.exp_year.value,
        cvc: inputs.cvc.value,
        address_zip: inputs.address_zip.value,
      };

      if (event.target === inputs.number && this.value.number.length >= 16) {
        inputs.exp_month.focus();
      } else if (event.target === inputs.exp_month &&
                 parseInt(this.value.exp_month) > 1) {
        inputs.exp_year.focus();
      } else if (event.target === inputs.exp_year &&
                 this.value.exp_year.length >= 4) {
        inputs.cvc.focus();
      } else if (event.target === inputs.cvc &&
                 this.value.cvc.length >= 3) {
        inputs.address_zip.focus();
      }
    };

    Object.keys(inputs).forEach(field => {
      inputs[field] = document.createElement('input');
      inputs[field].setAttribute('type', 'text');
      inputs[field].setAttribute('placeholder', field);
      inputs[field].setAttribute('size', field === 'number' ? 16 :
                                         field === 'address_zip' ? 5 :
                                         field === 'cvc' ? 3 : 2);
      inputs[field].oninput = changed;
      domElement.appendChild(inputs[field]);
    });
  }

  on(event, handler) {
  }
}

Stripe = (apiKey) => {
  return {
    elements: () => {
      return {
        create: (type, options) => {
          console.log('localstripe: Stripe().elements().create()');
          return new Element();
        },
      };
    },
    createToken: (card) => {
      console.log('localstripe: Stripe().createToken()');
      return new Promise(resolve => {
        const req = new XMLHttpRequest();
        req.onerror = event => {
          resolve({error: event.target.responseText});
        };
        req.onload = event => {
          let res = event.target.responseText;
          try {
            res = JSON.parse(res);
          } catch (e) {}
          if (event.target.status === 200) {
            resolve({token: res});
          } else {
            if (typeof res === 'object' && res.error) {
              resolve(res);
            } else {
              resolve({error: res});
            }
          }
        };

        let body = [];
        Object.keys(card.value).forEach(field => {
          body.push('card[' + field + ']=' + card.value[field]);
        });
        body.push('key=' + apiKey);
        body.push('payment_user_agent=localstripe');
        body = body.join('&');

        req.open('POST', 'http://localhost:{{ PORT }}/v1/tokens', true);
        req.setRequestHeader('Content-Type',
                             'application/x-www-form-urlencoded');
        req.send(body);
      });
    },
    createSource: () => {}, // TODO
    retrieveSource: () => {}, // TODO
  };
};

console.log('localstripe: The Stripe object was just replaced in the page. ' +
            'Stripe elements created from now on will be fake ones, ' +
            'communicating with the mock server.');
