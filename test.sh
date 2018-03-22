#!/bin/bash
# Copyright 2017 Adrien Vergé

set -eux

HOST=http://localhost:8420
SK=sk_test_12345

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
          -d email=james.robinson@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/customers/$cus \
     -d description='Adding a description...' \

curl -sSf -u $SK: -X DELETE $HOST/v1/customers/$cus

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
           -d description='This customer is a company' \
           -d email=foo@bar.com \
           -d business_vat_id=FR1234567890 \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=basique-mensuel \
   -d name='Abonnement basique (mensuel)' \
   -d amount=2500 \
   -d currency=eur \
   -d interval=month

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=basique-annuel \
   -d name='Abonnement basique (annuel)' \
   -d amount=20000 \
   -d currency=eur \
   -d interval=year

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=pro-annuel \
   -d name='Abonnement PRO (annuel)' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=delete-me \
   -d name='Delete me' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSf -u $SK: -X DELETE $HOST/v1/plans/delete-me

code=$(curl -so /dev/null -w '%{http_code}' -u $SK: $HOST/v1/plans \
            -d doesnotexist=1)
[ "$code" -eq 400 ]

code=$(curl -so /dev/null -w '%{http_code}' -u $SK: \
            $HOST/v1/plans?doesnotexist=1)
[ "$code" -eq 400 ]

curl -sSf -u $SK: $HOST/v1/products \
     -d name=T-shirt \
     -d type=good \
     -d description='Comfortable cotton t-shirt' \
     -d attributes[]=size \
     -d attributes[]=gender

curl -sSf -u $SK: $HOST/v1/coupons \
   -d id=PARRAIN \
   -d percent_off=30 \
   -d duration=once

tok=$(curl -sSf $HOST/v1/tokens \
          -d key=pk_test_sldkjflaksdfj \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2018 \
          -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
   -d source=$tok

curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
          -d source[object]=card \
          -d source[number]=4242424242424242 \
          -d source[exp_month]=12 \
          -d source[exp_year]=2020 \
          -d source[cvc]=123

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/invoices/upcoming?customer=$cus)
[ "$code" = 404 ]

sub=$(curl -sSf -u $SK: $HOST/v1/subscriptions \
         -d customer=$cus \
         -d items[0][plan]=basique-mensuel \
      | grep -oE 'sub_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription_items%5B0%5D%5Bplan%5D=pro-annuel\&subscription_tax_percent=20

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription=$sub\&subscription_items%5B0%5D%5Bid%5D=si_RBrVStcKDimMnp\&subscription_items%5B0%5D%5Bplan%5D=basique-annuel\&subscription_proration_date=1504182686\&subscription_tax_percent=20
