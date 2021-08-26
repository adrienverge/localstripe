#!/bin/bash
# Copyright 2017 Adrien Vergé

set -eux

HOST=http://localhost:8420
SK=sk_test_12345

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
          -d email=james.robinson@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/customers/$cus \
     -d description='Adding a description...'

curl -sSfg -u $SK: $HOST/v1/customers/$cus \
     -d preferred_locales[]='fr-FR' -d preferred_locales[]='es-ES'

curl -sSfg -u $SK: -X DELETE $HOST/v1/customers/$cus

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d description='This customer is a company' \
           -d email=foo@bar.com \
           -d phone=0102030405 \
           -d address[line1]='6 boulevard de Brandebourg' \
           -d address[city]=Ivry-sur-Seine -d address[country]=FR \
           -d tax_id_data[0][type]=eu_vat -d tax_id_data[0][value]=FR12345678901 \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/customers/$cus/tax_ids \
     -d type=eu_vat -d value=DE123456789 \
     -d expand[]=customer

curl -sSfg -u $SK: $HOST/v1/customers/$cus?expand[]=tax_ids.data.customer

curl -sSfg -u $SK: $HOST/v1/customers/$cus?expand[]=subscriptions.data.items.data

code=$(curl -sg -o /dev/null -w '%{http_code}' -u $SK: \
       $HOST/v1/customers/$cus?expand[]=subscriptions.data.items.data.tax_ids)
[ "$code" -eq 400 ]

txr1=$(curl -sSfg -u $SK: $HOST/v1/tax_rates \
            -d display_name=VAT \
            -d description='TVA France taux normal' \
            -d jurisdiction=FR \
            -d percentage=20.0 \
            -d inclusive=false \
      | grep -oE 'txr_\w+' | head -n 1)

txr2=$(curl -sSfg -u $SK: $HOST/v1/tax_rates \
            -d display_name=VAT \
            -d description='TVA France taux réduit' \
            -d jurisdiction=FR \
            -d percentage=10.0 \
            -d inclusive=false \
      | grep -oE 'txr_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=basique-mensuel \
   -d product[name]='Abonnement basique (mensuel)' \
   -d amount=2500 \
   -d currency=eur \
   -d interval=month

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=basique-annuel \
   -d name='Abonnement basique (annuel)' \
   -d amount=20000 \
   -d currency=eur \
   -d interval=year

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=annual-tiered-volume \
   -d name='Annual tiered volume' \
   -d currency=eur \
   -d interval=year \
   -d interval_count=1 \
   -d usage_type=licensed \
   -d billing_scheme=tiered \
   -d tiers_mode=volume \
   -d tiers[0][up_to]=1 \
   -d tiers[0][unit_amount]=500 \
   -d tiers[0][flat_amount]=1000 \
   -d tiers[1][up_to]=inf \
   -d tiers[1][unit_amount]=1000 \
   -d tiers[1][flat_amount]=1200

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=monthly-tiered-graduated \
   -d name='Monthly tiered graduated' \
   -d currency=eur \
   -d interval=month \
   -d interval_count=1 \
   -d usage_type=licensed \
   -d billing_scheme=tiered \
   -d tiers_mode=graduated \
   -d tiers[0][up_to]=1 \
   -d tiers[0][unit_amount]=500 \
   -d tiers[0][flat_amount]=1000 \
   -d tiers[1][up_to]=inf \
   -d tiers[1][unit_amount]=1000 \
   -d tiers[1][flat_amount]=1200

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=pro-annuel \
   -d product[name]='Abonnement PRO (annuel)' \
   -d product[statement_descriptor]='abonnement pro' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSfg -u $SK: $HOST/v1/plans \
   -d product[name]='Without id' \
   -d product[statement_descriptor]='Without id' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSfg -u $SK: $HOST/v1/plans \
   -d id=delete-me \
   -d product[name]='Delete me' \
   -d amount=30000 \
   -d currency=eur \
   -d interval=year

curl -sSfg -u $SK: -X DELETE $HOST/v1/plans/delete-me

code=$(curl -sg -o /dev/null -w '%{http_code}' -u $SK: $HOST/v1/plans \
            -d doesnotexist=1)
[ "$code" -eq 400 ]

code=$(curl -sg -o /dev/null -w '%{http_code}' -u $SK: \
            $HOST/v1/plans?doesnotexist=1)
[ "$code" -eq 400 ]

curl -sSfg -u $SK: $HOST/v1/products \
     -d name=T-shirt \
     -d type=good \
     -d description='Comfortable cotton t-shirt' \
     -d attributes[]=size \
     -d attributes[]=gender

curl -sSfg -u $SK: $HOST/v1/products \
     -d id=PRODUCT1234 \
     -d name='Product 1234' \
     -d type=service

curl -sSfg -u $SK: $HOST/v1/products/PRODUCT1234

curl -sSfg -u $SK: $HOST/v1/plans?expand[]=data.product

code=$(curl -sg -o /dev/null -w '%{http_code}' -u $SK: \
            $HOST/v1/plans?expand[]=data.doesnotexist)
[ "$code" -eq 400 ]

curl -sSfg -u $SK: $HOST/v1/coupons \
   -d id=PARRAIN \
   -d percent_off=30 \
   -d duration=once

# This is what a Stripe.js request does:
tok=$(curl -sSfg $HOST/v1/tokens \
          -d key=pk_test_sldkjflaksdfj \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2018 \
          -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

# This is what a request from back-end does:
tok=$(curl -sSfg -u $SK: $HOST/v1/tokens \
           -d card[number]=4242424242424242 \
           -d card[exp_month]=12 \
           -d card[exp_year]=2019 \
           -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

# add a new card
card=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE 'card_\w+')

# observe new card in customer response
res=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus \
  | grep -oE $card)
[ -n "$res" ]

# observe new card in customer sources response
res=$(
  curl -sSf -u $SK: $HOST/v1/customers/$cus/sources \
  | grep -oE $card)
[ -n "$res" ]


# observe new card in customer sources response when requesting object=card
res=$(
  curl -sSfG -u $SK: $HOST/v1/customers/$cus/sources \
     -d object=card \
  | grep -oE $card)
[ -n "$res" ]

# delete the card
curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources/$card \
     -X DELETE

# observe card no longer in customer response
res=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus \
  | grep -oE $card || true)
[ -z "$res" ]

# add a new card
card=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
       -d source[name]=John\ Smith \
  | grep -oE 'card_\w+')

# observe name on card
name=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources/$card \
  | grep -oE '"name": "John Smith",')
[ -n "$name" ]

# update name on card
curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources/$card \
     -d name=Jane\ Doe

# observe name on card
name=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources/$card \
  | grep -oE '"name": "Jane Doe",')
[ -n "$name" ]

card=$(curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
          -d source[object]=card \
          -d source[number]=4242424242424242 \
          -d source[exp_month]=12 \
          -d source[exp_year]=2020 \
          -d source[cvc]=123 \
      | grep -oE 'card_\w+')

code=$(curl -sg -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/$cus/cards \
            -d source[object]=card \
            -d source[number]=4000000000000002 \
            -d source[exp_month]=4 \
            -d source[exp_year]=2042 \
            -d source[cvc]=123)
[ "$code" = 402 ]

# new charges are captured by default
captured=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# create a pre-auth charge
charge=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# charge was not captured
captured=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"captured": false,')
[ -n "$captured" ]

# cannot capture more than pre-authed amount
code=$(
  curl -sg -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges/$charge/capture \
       -d amount=2000)
[ "$code" = 400 ]

# can capture less than the pre-auth amount
captured=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge/capture \
       -d amount=800 \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# difference between pre-auth and capture is refunded
refunded=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"amount_refunded": 200,')
[ -n "$captured" ]

# create a pre-auth charge
charge=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# capture the full amount (default)
captured=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge/capture \
       -X POST \
  | grep -oE '"captured": true,')
[ -n "$captured" ]

# none is refunded
refunded=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"amount_refunded": 0,')
[ -n "$captured" ]

# cannot capture an already captured charge
code=$(
  curl -sg -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges/$charge/capture \
       -X POST)
[ "$code" = 400 ]

sepa_cus=$(
  curl -sSfg -u $SK: $HOST/v1/customers \
       -d description='I pay with SEPA debit' \
       -d email=sepa@euro.fr \
  | grep -oE 'cus_\w+' | head -n 1)

src=$(curl -sSfg -u $SK: $HOST/v1/sources \
           -d type=ach_credit_transfer \
           -d currency=usd \
           -d owner[email]='jenny.rosen@example.com' \
      | grep -oE 'src_\w+')

curl -sSfg -u $SK: $HOST/v1/customers/$sepa_cus/sources \
     -d source=$src

# This is what a Stripe.js request does:
src=$(curl -sSfg -u $SK: $HOST/v1/sources \
           -d type=sepa_debit \
           -d sepa_debit[iban]=DE89370400440532013000 \
           -d currency=eur \
           -d owner[name]='Jenny Rosen' \
      | grep -oE 'src_\w+')

curl -sSfg -u $SK: $HOST/v1/customers/$sepa_cus/sources \
     -d source=$src

# Get a customer source directly:
curl -sSfg -u $SK: $HOST/v1/customers/$sepa_cus/sources/$src
code=$(curl -sg -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/cus_doesnotexist/sources/$src)
[ "$code" = 404 ]
code=$(curl -sg -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/customers/$sepa_cus/sources/src_doesnotexist)
[ "$code" = 404 ]

tok=$(curl -sSfg -u $SK: $HOST/v1/tokens \
           -d card[number]=4242424242424242 \
           -d card[exp_month]=12 \
           -d card[exp_year]=2020 \
           -d card[cvc]=123 \
      | grep -oE 'tok_\w+')

curl -sSfg -u $SK: $HOST/v1/customers \
     -d description='Customer with already existing source' \
     -d source=$tok

# For a customer with no source, `default_source` should be `null`:
cus=$(curl -sSfg -u $SK: $HOST/v1/customers -d email=joe.malvic@example.com \
      | grep -oE 'cus_\w+' | head -n 1)
ds=$(curl -sSfg -u $SK: $HOST/v1/customers/$cus?expand[]=default_source \
     | grep -oE '"default_source": \w+,')
[ "$ds" = '"default_source": null,' ]
curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
          -d source[object]=card \
          -d source[number]=4242424242424242 \
          -d source[exp_month]=12 \
          -d source[exp_year]=2020 \
          -d source[cvc]=123
ds=$(curl -sSfg -u $SK: $HOST/v1/customers/$cus?expand[]=default_source \
     | grep -oE '"default_source": null",' || true)
[ -z "$ds" ]

# we can charge a customer without specifying the source
curl -sSfg -u $SK: $HOST/v1/charges \
     -d customer=$cus \
     -d amount=1000 \
     -d currency=usd

curl -sSfg -u $SK: $HOST/v1/invoices?customer=$cus

code=$(curl -sg -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/invoices/upcoming?customer=$cus)
[ "$code" = 404 ]

curl -sSfg -u $SK: $HOST/v1/subscriptions \
     -d customer=$cus \
     -d items[0][plan]=basique-mensuel \
     -d expand[]=latest_invoice.payment_intent

res=$(curl -sSfg -u $SK: $HOST/v1/subscriptions \
           -d customer=$cus \
           -d items[0][plan]=basique-mensuel \
           -d items[0][tax_rates][0]=$txr1)
sub=$(echo "$res" | grep -oE 'sub_\w+' | head -n 1)
in=$(echo "$res" | grep -oE 'in_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/invoices?customer=$cus

curl -sSfg -u $SK: $HOST/v1/invoices/upcoming?customer=$cus

curl -sSfg -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription_items[0][plan]=pro-annuel\&subscription_tax_percent=20

curl -sSfg -u $SK: $HOST/v1/invoices/upcoming?customer=$cus\&subscription=$sub\&subscription_items[0][id]=si_RBrVStcKDimMnp\&subscription_items[0][plan]=basique-annuel\&subscription_proration_date=1504182686\&subscription_tax_percent=20

curl -sSfg -u $SK: $HOST/v1/invoices/$in/lines

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d description='This customer will have a subscription with volume tiered pricing' \
           -d email=tiered@bar.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

curl -sSfg -u $SK: $HOST/v1/subscriptions \
      -d customer=$cus \
      -d items[0][plan]=annual-tiered-volume \
      -d items[0][quantity]=5

curl -sSfg -u $SK: $HOST/v1/invoices?customer=$cus

curl -sSfg -u $SK: $HOST/v1/subscriptions?customer=$cus

curl -sSfg -u $SK: $HOST/v1/customers/$cus/subscriptions

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d description='This customer will have a subscription with graduated tiered pricing' \
           -d email=tiered@bar.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

sub=$(curl -sSfg -u $SK: $HOST/v1/subscriptions \
           -d customer=$cus \
           -d items[0][plan]=monthly-tiered-graduated \
           -d items[0][quantity]=5 \
      | grep -oE 'sub_\w+' | head -n 1)

data=$(curl -sSfg -u $SK: $HOST/v1/subscriptions/$sub \
            -d items[0][plan]=annual-tiered-volume)

same_data=$(curl -sSfg -u $SK: $HOST/v1/subscriptions/$sub \
                 -d items[0][plan]=annual-tiered-volume)

diff <(echo "$data") <(echo "$same_data")

curl -sSfg -u $SK: $HOST/v1/subscriptions/$sub \
     -d metadata[toto]=toto

curl -sSfg -u $SK: $HOST/v1/invoices?customer=$cus

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d description='This customer will switch from a yearly to another
                           yearly plan' \
           -d email=switch@bar.com \
      | grep -oE 'cus_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/customers/$cus/sources \
     -d source=$tok

sub=$(curl -sSfg -u $SK: $HOST/v1/subscriptions \
           -d customer=$cus \
           -d items[0][plan]=basique-annuel)
sub_id=$(echo "$sub" | grep -oE 'sub_\w+' | head -n 1)
sub_item_id=$(echo "$sub" | grep -oE 'si_\w+' | head -n 1)

sub=$(curl -sSfg -u $SK: $HOST/v1/subscriptions/$sub_id \
           -d items[0][plan]=pro-annuel \
           -d items[0][id]=$sub_item_id)

in=$(curl -sSfg -u $SK: $HOST/v1/invoices \
          -d customer=$cus)
grep -q "Abonnement PRO (annuel)" <<<"$in"
grep -q "Abonnement basique (annuel)" <<<"$in"

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d email=john.malkovich@example.com \
      | grep -oE 'cus_\w+' | head -n 1)

pm=$(curl -sSfg -u $SK: $HOST/v1/payment_methods \
          -d type=card \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2020 \
          -d card[cvc]=123 \
     | grep -oE 'pm_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/payment_methods/$pm/attach \
     -d customer=$cus

curl -sSfg -u $SK: $HOST/v1/customers/$cus \
     -d invoice_settings[default_payment_method]=$pm

curl -sSfg -u $SK: $HOST/v1/customers/$cus?expand[]=invoice_settings.default_payment_method

curl -sSfg -u $SK: $HOST/v1/payment_methods?customer=$cus\&type=card

curl -sSfg -u $SK: $HOST/v1/payment_methods/$pm/detach -X POST

pm=$(curl -sSfg -u $SK: $HOST/v1/payment_methods \
          -d type=card \
          -d card[number]=4000000000000002 \
          -d card[exp_month]=4 \
          -d card[exp_year]=2042 \
          -d card[cvc]=123 \
     | grep -oE 'pm_\w+' | head -n 1)
code=$(curl -sg -o /dev/null -w "%{http_code}" -u $SK: \
            $HOST/v1/payment_methods/$pm/attach \
            -d customer=$cus)
[ "$code" = 402 ]

curl -sSfg -u $SK: $HOST/v1/payment_methods?customer=$cus\&type=card

res=$(curl -sSfg -u $SK: $HOST/v1/setup_intents -X POST)
seti=$(echo "$res" | grep '"id"' | grep -oE 'seti_\w+' | head -n 1)
seti_secret=$(echo $res | grep -oE 'seti_\w+_secret_\w+' | head -n 1)

curl -sSfg -u $SK: $HOST/v1/setup_intents/$seti/confirm -X POST

curl -sSfg -u $SK: $HOST/v1/setup_intents/$seti/cancel -X POST

res=$(curl -sSfg -u $SK: $HOST/v1/setup_intents -X POST)
seti=$(echo "$res" | grep '"id"' | grep -oE 'seti_\w+' | head -n 1)
seti_secret=$(echo $res | grep -oE 'seti_\w+_secret_\w+' | head -n 1)

# This is what a Stripe.js request does:
curl -sSfg $HOST/v1/setup_intents/$seti/confirm \
     -d key=pk_test_sldkjflaksdfj \
     -d use_stripe_sdk=true \
     -d client_secret=$seti_secret \
     -d payment_method_data[type]=card \
     -d payment_method_data[card][number]=4242424242424242 \
     -d payment_method_data[card][cvc]=242 \
     -d payment_method_data[card][exp_month]=4 \
     -d payment_method_data[card][exp_year]=24 \
     -d payment_method_data[billing_details][address][postal_code]=42424

# off_session cannot be used when confirm is false
code=$(
  curl -sg -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/payment_intents \
       -d amount=1000 \
       -d currency=usd \
       -d off_session=true \
       -d confirm=false)
[ "$code" = 400 ]

# card fingerprint
fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "79758cf4654d6cc6",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4000056655665556 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "d510ca86026aae9d",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=5555555555554444 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE '"fingerprint": "6589b0d46b6f2f0d",')
[ -n "$fingerprint" ]

# sepa debit fingerprint
fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=DE89370400440532013000 \
       -d currency=eur \
  | grep -oE '"fingerprint": "798619b2da10a84a",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=FR1420041010050500013M02606 \
       -d currency=eur \
  | grep -oE '"fingerprint": "ecd0b2a2a3c26824",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/sources \
       -d type=sepa_debit \
       -d sepa_debit[iban]=IT40S0542811101000000123456 \
       -d currency=eur \
  | grep -oE '"fingerprint": "b4fb3b3b13ef1fb0",')
[ -n "$fingerprint" ]

# payment method fingerprint
fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=4242424242424242 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "79758cf4654d6cc6",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=4000056655665556 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "d510ca86026aae9d",')
[ -n "$fingerprint" ]

fingerprint=$(
  curl -sSfg -u $SK: $HOST/v1/payment_methods \
       -d type=card \
       -d card[number]=5555555555554444 \
       -d card[exp_month]=12 \
       -d card[exp_year]=2020 \
       -d card[cvc]=123 \
  | grep -oE '"fingerprint": "6589b0d46b6f2f0d",')
[ -n "$fingerprint" ]

# create a chargeable source
card=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE 'card_\w+' | head -n 1)

# create a normal charge, verify charge status succeeded
status=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
  | grep -oE '"status": "succeeded"')
[ -n "$status" ]

# create a pre-auth charge
charge=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# verify charge status pending
status=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"status": "pending"')
[ -n "$status" ]

# capture the charge
curl -sSfg -u $SK: $HOST/v1/charges/$charge/capture \
     -X POST

# verify charge status succeeded
status=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"status": "succeeded"')
[ -n "$status" ]

# create a non-chargeable source
card=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4000000000000341 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
  | grep -oE 'card_\w+' | head -n 1)

# create a normal charge, observe 402 response
code=$(
  curl -sg -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd)
[ "$code" = 402 ]

# create a normal charge
charge=$(
  curl -sg -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
  | grep -oE 'ch_\w+' | head -n 1)

# verify charge status failed
status=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"status": "failed"')
[ -n "$status" ]


# create a pre-auth charge, observe 402 response
code=$(
  curl -sg -o /dev/null -w "%{http_code}" \
       -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false)
[ "$code" = 402 ]

# create a pre-auth charge
charge=$(
  curl -sg -u $SK: $HOST/v1/charges \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

# verify charge status failed
status=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE '"status": "failed"')
[ -n "$status" ]

# list charges
total_count=$(
  curl -sSfg -u $SK: $HOST/v1/charges | grep -oE '"total_count": 15')
[ -n "$total_count" ]

total_count=$(
  curl -sSfg -u $SK: $HOST/v1/charges?customer=$cus \
  | grep -oE '"total_count": 6')
[ -n "$total_count" ]

total_count=$(
  curl -sSfg -u $SK: $HOST/v1/charges?customer=$cus\&created[gt]=1588166306 \
  | grep -oE '"total_count": 6')
[ -n "$total_count" ]

no_more_events=$(curl -sSfg -u $SK: $HOST/v1/events \
                 | grep -oE '^  "has_more": false' || true)
[ -z "$no_more_events" ]
last_event=$(curl -sSfg -u $SK: $HOST/v1/events?limit=100 \
             | grep -oE 'evt_\w+' | tail -n 1)
no_more_events=$(curl -sSfg -u $SK: $HOST/v1/events?starting_after=$last_event \
                 | grep -oE '^  "has_more": false')
[ -n "$no_more_events" ]
zero_events=$(curl -sSfg -u $SK: $HOST/v1/events?starting_after=$last_event \
                 | grep -oE '^  "data": \[\]')
[ -n "$zero_events" ]

curl -sSfg -u $SK: $HOST/v1/balance

payout=$(
  curl -sSfg -u $SK: $HOST/v1/payouts \
       -d amount=1100 \
       -d currency=eur \
  | grep -oE 'po_\w+' | head -n 1)

payout_status=$(
  curl -sSfg -u $SK: $HOST/v1/payouts/$payout \
  | grep -oE '"status": "pending",')
[ -n "$payout_status" ]

curl -sg -u $SK: $HOST/v1/payouts/$payout/cancel -X POST

payout_status=$(
  curl -sSfg -u $SK: $HOST/v1/payouts/$payout \
  | grep -oE '"status": "canceled",')
[ -n "$payout_status" ]

curl -sg -u $SK: $HOST/v1/payouts \
      -d amount=1100 \
      -d currency=eur \
      -d status=paid

curl -sg -u $SK: $HOST/v1/payouts \
      -d amount=1100 \
      -d currency=eur \
      -d status=failed

card=$(
  curl -sSfg -u $SK: $HOST/v1/customers/$cus/cards \
       -d source[object]=card \
       -d source[number]=4242424242424242 \
       -d source[exp_month]=12 \
       -d source[exp_year]=2020 \
       -d source[cvc]=123 \
       -d source[name]=John\ Smith \
  | grep -oE 'card_\w+')

# immediately-captured charge has a balance transaction
txn=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
  | grep -oE 'txn_\w+')
[ -n "$txn" ]

# pre-auth charge has no balance transaction
charge=$(
  curl -sSfg -u $SK: $HOST/v1/charges \
       -d customer=$cus \
       -d source=$card \
       -d amount=1000 \
       -d currency=usd \
       -d capture=false \
  | grep -oE 'ch_\w+' | head -n 1)

txn=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge \
  | grep -oE 'txn_\w+' || true)
[ -z "$txn" ]

# captured pre-auth charge has a balance transaction
txn=$(
  curl -sSfg -u $SK: $HOST/v1/charges/$charge/capture \
       -X POST \
  | grep -oE 'txn_\w+')
[ -n "$txn" ]

# transaction is linked back to its source
src=$(
  curl -sSfg -u $SK: $HOST/v1/balance_transactions/$txn \
  | grep -oE "$charge")
[ -n "$src" ]

# refund has a balance transaction
txn=$(
  curl -sSfg -u $SK: $HOST/v1/refunds \
       -d charge=$charge \
  | grep -oE 'txn_\w+')
[ -n "$txn" ]

# creating a customer with a payment method
pm=$(curl -sSfg -u $SK: $HOST/v1/payment_methods \
          -d type=card \
          -d card[number]=4242424242424242 \
          -d card[exp_month]=12 \
          -d card[exp_year]=2020 \
          -d card[cvc]=123 \
    | grep -oE 'pm_\w+' | head -n 1)

cus=$(curl -sSfg -u $SK: $HOST/v1/customers \
           -d description='This customer will have a payment_method when created' \
           -d payment_method=$pm \
     | grep -oE 'cus_\w+' | head -n 1)

card=$(curl -sSfg -u $SK: $HOST/v1/payment_methods?customer=$cus\&type=card \
      | grep -oE "$pm" | head -n 1)

[ -n "$card" ]

# trying to create a customer with a non-existant payment_method returns a 404, and doesn't create customer
total_count=$( curl -sSfg -u $SK: $HOST/v1/customers \
             | grep -oE '"total_count": 9')
[ -n "$total_count" ]

code=$(curl -sg -o /dev/null -w '%{http_code}' -u $SK: $HOST/v1/customers \
           -d description='This customer should not be created, payment_method is wrong' \
           -d payment_method='pm_doesnotexist')
[ "$code" -eq 404 ]

total_count=$( curl -sSfg -u $SK: $HOST/v1/customers \
             | grep -oE '"total_count": 9')
[ -n "$total_count" ]
