-- disable powertranz payment provider credentials
UPDATE payment_provider
   SET powertranz_merchant_id = NULL,
       powertranz_password = NULL;
