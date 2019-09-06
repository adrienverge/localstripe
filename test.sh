#!/bin/bash
# Copyright 2017 Adrien Vergé

set -eux

HOST=http://localhost:8420
SK=sk_test_12345

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
          -d email=james.robinson@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/customers/$cus \
     -d description='Adding a description...'

curl -sSf -u $SK: $HOST/v1/customers/$cus \
     -d preferred_locales[]='fr-FR' -d preferred_locales[]='es-ES'

curl -sSf -u $SK: -X DELETE $HOST/v1/customers/$cus

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
           -d description='This customer is a company' \
           -d email=foo@bar.com \
           -d tax_id_data[0][type]=eu_vat -d tax_id_data[0][value]=FR12345678901 \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/customers/$cus/tax_ids \
     -d type=eu_vat -d value=DE123456789

curl -sSf -u $SK: $HOST/v1/customers/$cus?expand%5B%5D=tax_ids.data.customer

txr1=$(curl -sSf -u $SK: $HOST/v1/tax_rates \
            -d display_name=VAT \
            -d description='TVA France taux normal' \
            -d jurisdiction=FR \
            -d percentage=20.0 \
            -d inclusive=false \
      | grep -oE 'txr_\w+' | head -n 1)

txr2=$(curl -sSf -u $SK: $HOST/v1/tax_rates \
            -d display_name=VAT \
            -d description='TVA France taux réduit' \
            -d jurisdiction=FR \
            -d percentage=10.0 \
            -d inclusive=false \
      | grep -oE 'txr_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=basique-mensuel \
   -d product[name]='Abonnement basique (mensuel)' \
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
   -d id=annual-tiered-volume \
   -d name='Annual tiered volume' \
   -d currency=eur \
   -d interval=year \
   -d interval_count=1 \
   -d usage_type=licensed \
   -d billing_scheme=tiered \
   -d tiers_mode=volume \
   -d tiers[0][from]=0 \
   -d tiers[0][up_to]=1 \
   -d tiers[0][unit_amount]=500 \
   -d tiers[0][flat_amount]=1000 \
   -d tiers[1][from]=2 \
   -d tiers[1][up_to]=inf \
   -d tiers[1][unit_amount]=1000 \
   -d tiers[1][flat_amount]=1200

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=monthly-tiered-graduated \
   -d name='Monthly tiered graduated' \
   -d currency=eur \
   -d interval=month \
   -d interval_count=1 \
   -d usage_type=licensed \
   -d billing_scheme=tiered \
   -d tiers_mode=graduated \
   -d tiers[0][from]=0 \
   -d tiers[0][up_to]=1 \
   -d tiers[0][unit_amount]=500 \
   -d tiers[0][flat_amount]=1000 \
   -d tiers[1][from]=2 \
   -d tiers[1][up_to]=inf \
   -d tiers[1][unit_amount]=1000 \
   -d tiers[1][flat_amount]=1200

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=pro-annuel \
   -d product[name]='Abonnement PRO (annuel)' \
   -d product[statement_descriptor]='abonnement pro' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSf -u $SK: $HOST/v1/plans \
   -d product[name]='Without id' \
   -d product[statement_descriptor]='Without id' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSf -u $SK: $HOST/v1/plans \
   -d id=delete-me \
   -d product[name]='Delete me' \
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

curl -sSf -u $SK: $HOST/v1/plans?expand%5B%5D=data.product

code=$(curl -so /dev/null -w '%{http_code}' -u $SK: \
            $HOST/v1/plans?expand%5B%5D=data.doesnotexist)
[ "$code" -eq 400 ]

curl -sSf -u $SK: $HOST/v1/coupons \
   -d id=PARRAIN \
   -d percent_off=30 \
   -d duration=once

# This is what a Stripe.js request does:
tok=$(curl -sSf $HOST/v1/tokens \
          -d key=pk_test_sldkjflaksdfj \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2018 \
          -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

# This is what a request from back-end does:
tok=$(curl -sSf -u $SK: $HOST/v1/tokens \
           -d card[number]=4242424242424242 \
           -d card[exp_month]=12 \
           -d card[exp_year]=2019 \
           -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

# add a new card
card=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE 'card_\w+')

# observe new card in customer response
res=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus \
  | grep -oE $card)
[ -n "$res" ]

# delete the card
curl -sSf -u $SK: $HOST/v1/customers/$cus/sources/$card \
     -X DELETE

# observe card no longer in customer response
res=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus \
  | grep -oE $card || true)
[ -z "$res" ]

# add a new card
card=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
       -d source[name]=John\ Smith \
  | grep -oE 'card_\w+')

# observe name on card
name=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/sources/$card \
  | grep -oE '"name": "John Smith",')
[ -n "$name" ]

# update name on card
curl -sSf -u $SK: $HOST/v1/customers/$cus/sources/$card \
     -d name=Jane\ Doe

# observe name on card
name=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/sources/$card \
  | grep -oE '"name": "Jane Doe",')
[ -n "$name" ]

card=$(curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
          -d source[object]=card \
          -d source[number]=4242424242424242 \
          -d source[exp_month]=12 \
          -d source[exp_year]=2020 \
          -d source[cvc]=123 \
      | grep -oE 'card_\w+')

code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/$cus/cards \
            -d source[object]=card \
            -d source[number]=4000000000000002 \
            -d source[exp_month]=4 \
            -d source[exp_year]=2042 \
            -d source[cvc]=123)
[ "$code" = 402 ]

# new charges are captured by default
captured=$(
  curl -sSf -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# create a pre-auth charge
charge=$(
  curl -sSf -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# charge was not captured
captured=$(
  curl -sSf -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"captured": false,')
[ -n "$captured" ]

# cannot capture more than pre-authed amount
code=$(
  curl -s -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges/$charge/capture \
       -d amount=2000)
[ "$code" = 400 ]

# can capture less than the pre-auth amount
captured=$(
  curl -sSf -u $SK: $HOST/v1/charges/$charge/capture \
       -d amount=800 \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# difference between pre-auth and capture is refunded
refunded=$(
  curl -sSf -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"amount_refunded": 200,')
[ -n "$captured" ]

# create a pre-auth charge
charge=$(
  curl -sSf -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# capture the full amount (default)
captured=$(
  curl -sSf -u $SK: $HOST/v1/charges/$charge/capture \
       -X POST \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# none is refunded
refunded=$(
  curl -sSf -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"amount_refunded": 0,')
[ -n "$captured" ]

# cannot capture an already captured charge
code=$(
  curl -s -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges/$charge/capture \
       -X POST)
[ "$code" = 400 ]

sepa_cus=$(
  curl -sSf -u $SK: $HOST/v1/customers \
       -d description='I pay with SEPA debit' \
       -d email=sepa@euro.fr \
  | grep -oE 'cus_\w+' | head -n 1)

src=$(curl -sSf -u $SK: $HOST/v1/sources \
           -d type=ach_credit_transfer \
           -d currency=usd \
           -d owner[email]='jenny.rosen@example.com' \
      | grep -oE 'src_\w+')

curl -sSf -u $SK: $HOST/v1/customers/$sepa_cus/sources \
     -d source=$src

# This is what a Stripe.js request does:
src=$(curl -sSf -u $SK: $HOST/v1/sources \
           -d type=sepa_debit \
           -d sepa_debit[iban]=DE89370400440532013000 \
           -d currency=eur \
           -d owner[name]='Jenny Rosen' \
      | grep -oE 'src_\w+')

curl -sSf -u $SK: $HOST/v1/customers/$sepa_cus/sources \
     -d source=$src

# Get a customer source directly:
curl -sSf -u $SK: $HOST/v1/customers/$sepa_cus/sources/$src
code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/cus_doesnotexist/sources/$src)
[ "$code" = 404 ]
code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/$sepa_cus/sources/src_doesnotexist)
[ "$code" = 404 ]

tok=$(curl -sSf -u $SK: $HOST/v1/tokens \
           -d card[number]=4242424242424242 \
           -d card[exp_month]=12 \
           -d card[exp_year]=2020 \
           -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSf -u $SK: $HOST/v1/customers \
     -d description='Customer with already existing source' \
     -d source=$tok

# For a customer with no source, `default_source` should be `null`:
cus=$(curl -sSf -u $SK: $HOST/v1/customers -d email=joe.malvic@example.com \
      | grep -oE 'cus_\w+' | head -n 1)
ds=$(curl -sSf -u $SK: $HOST/v1/customers/$cus?expand%5B%5D=default_source \
     | grep -oE '"default_source": \w+,')
[ "$ds" = '"default_source": null,' ]
curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
          -d source[object]=card \
          -d source[number]=4242424242424242 \
          -d source[exp_month]=12 \
          -d source[exp_year]=2020 \
          -d source[cvc]=123
ds=$(curl -sSf -u $SK: $HOST/v1/customers/$cus?expand%5B%5D=default_source \
     | grep -oE '"default_source": null",' || true)
[ -z "$ds" ]

# we can charge a customer without specifying the source
curl -sSf -u $SK: $HOST/v1/charges \
     -d customer=$cus \
     -d amount=1000 \
     -d currency=usd

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/invoices/upcoming?customer=$cus)
[ "$code" = 404 ]

curl -sSf -u $SK: $HOST/v1/subscriptions \
     -d customer=$cus \
     -d items[0][plan]=basique-mensuel \
     -d expand[]=latest_invoice.payment_intent

sub=$(curl -sSf -u $SK: $HOST/v1/subscriptions \
           -d customer=$cus \
           -d items[0][plan]=basique-mensuel \
           -d items[0][tax_rates][0]=$txr1 \
      | grep -oE 'sub_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription_items%5B0%5D%5Bplan%5D=pro-annuel\&subscription_tax_percent=20

curl -sSf -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription=$sub\&subscription_items%5B0%5D%5Bid%5D=si_RBrVStcKDimMnp\&subscription_items%5B0%5D%5Bplan%5D=basique-annuel\&subscription_proration_date=1504182686\&subscription_tax_percent=20

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
           -d description='This customer will have a subscription with volume tiered pricing' \
           -d email=tiered@bar.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

curl -sSf -u $SK: $HOST/v1/subscriptions \
      -d customer=$cus \
      -d items[0][plan]=annual-tiered-volume \
      -d items[0][quantity]=5

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
           -d description='This customer will have a subscription with graduated tiered pricing' \
           -d email=tiered@bar.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

sub=$(curl -sSf -u $SK: $HOST/v1/subscriptions \
           -d customer=$cus \
           -d items[0][plan]=monthly-tiered-graduated \
           -d items[0][quantity]=5 \
      | grep -oE 'sub_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/subscriptions/$sub \
     -d items[0][plan]=annual-tiered-volume

curl -sSf -u $SK: $HOST/v1/invoices?customer=$cus

cus=$(curl -sSf -u $SK: $HOST/v1/customers \
           -d email=john.malkovich@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

pm=$(curl -sSf -u $SK: $HOST/v1/payment_methods \
          -d type=card \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2020 \
          -d card[cvc]=123 \
     | grep -oE 'pm_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/payment_methods/$pm/attach \
     -d customer=$cus

curl -sSf -u $SK: $HOST/v1/customers/$cus \
     -d invoice_settings[default_payment_method]=$pm

curl -sSf -u $SK: $HOST/v1/customers/$cus?expand%5B%5D=invoice_settings.default_payment_method

curl -sSf -u $SK: $HOST/v1/payment_methods/$pm/detach -X POST

pm=$(curl -sSf -u $SK: $HOST/v1/payment_methods \
          -d type=card \
          -d card[number]=4000000000000002 \
          -d card[exp_month]=4 \
          -d card[exp_year]=2042 \
          -d card[cvc]=123 \
     | grep -oE 'pm_\w+' | head -n 1)
code=$(curl -s -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/payment_methods/$pm/attach \
            -d customer=$cus)
[ "$code" = 402 ]

res=$(curl -sSf -u $SK: $HOST/v1/setup_intents -X POST)
seti=$(echo "$res" | grep '"id"' | grep -oE 'seti_\w+' | head -n 1)
seti_secret=$(echo $res | grep -oE 'seti_\w+_secret_\w+' | head -n 1)

curl -sSf -u $SK: $HOST/v1/setup_intents/$seti/confirm -X POST

curl -sSf -u $SK: $HOST/v1/setup_intents/$seti/cancel -X POST

res=$(curl -sSf -u $SK: $HOST/v1/setup_intents -X POST)
seti=$(echo "$res" | grep '"id"' | grep -oE 'seti_\w+' | head -n 1)
seti_secret=$(echo $res | grep -oE 'seti_\w+_secret_\w+' | head -n 1)

# This is what a Stripe.js request does:
curl -sSf $HOST/v1/setup_intents/$seti/confirm \
     -d key=pk_test_sldkjflaksdfj \
     -d use_stripe_sdk=true \
     -d client_secret=$seti_secret \
     -d payment_method_data[type]=card \
     -d payment_method_data[card][number]=4242424242424242 \
     -d payment_method_data[card][cvc]=242 \
     -d payment_method_data[card][exp_month]=4 \
     -d payment_method_data[card][exp_year]=24 \
     -d payment_method_data[billing_details][address][postal_code]=42424

# card fingerprint
fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "79758cf4654d6cc6",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4000056655665556 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "d510ca86026aae9d",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=5555555555554444 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "6589b0d46b6f2f0d",')
[ -n "$fingerprint" ]

# sepa debit fingerprint
fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=DE89370400440532013000 \
       -d currency=eur \
  | grep -oE '"fingerprint": "798619b2da10a84a",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=FR1420041010050500013M02606 \
       -d currency=eur \
  | grep -oE '"fingerprint": "ecd0b2a2a3c26824",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=IT40S0542811101000000123456 \
       -d currency=eur \
  | grep -oE '"fingerprint": "b4fb3b3b13ef1fb0",')
[ -n "$fingerprint" ]

# payment method fingerprint
fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=4242424242424242 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "79758cf4654d6cc6",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=4000056655665556 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "d510ca86026aae9d",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSf -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=5555555555554444 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "6589b0d46b6f2f0d",')
[ -n "$fingerprint" ]
