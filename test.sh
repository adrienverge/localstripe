#!/bin/bash
# Copyright 2017 Adrien Vergé

set -eux

HOST=http://localhost:8420
SK=sk_test_12345

cus=$(curl -s -u $SK: $HOST/v1/customers \
          -d email=james.robinson@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -s -u $SK: $HOST/v1/plans \
   -d id=basique-mensuel \
   -d name='Abonnement basique (mensuel)' \
   -d amount=3000 \
   -d currency=eur \
   -d interval=month

curl -s -u $SK: $HOST/v1/plans \
   -d id=basique-annuel \
   -d name='Abonnement basique (annuel)' \
   -d amount=20000 \
   -d currency=eur \
   -d interval=year

curl -s -u $SK: $HOST/v1/coupons \
   -d id=PARRAIN \
   -d percent_off=30 \
   -d duration=once

tok=$(curl -s $HOST/v1/tokens \
          -d key=pk_test_sldkjflaksdfj \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2018 \
          -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -s -u $SK: $HOST/v1/customers/$cus/sources \
   -d source=$tok

curl -s -u $SK: $HOST/v1/subscriptions \
   -d customer=$cus \
   -d items[0][plan]=basique-mensuel

curl -s -u $SK: $HOST/v1/invoices/upcoming?customer=$cus

curl -s -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription_items\[0\]\[plan\]\=pro-annuel&subscription_tax_percent=20

curl -s -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription=sub_miO4oEkgMFXQ8f\&subscription_items%5B0%5D%5Bid%5D=si_RBrVStcKDimMnp\&subscription_items%5B0%5D%5Bplan%5D=basique-annuel\&subscription_proration_date=1504182686\&subscription_tax_percent=20
