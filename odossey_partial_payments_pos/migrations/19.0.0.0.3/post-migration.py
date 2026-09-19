# License OPL-1


def migrate(cr, version):
    """The internal "Crédito Cliente/Proveedor" tender now splits its
    closing entry per customer (see `_get_or_create_credit_payment_method`)."""
    cr.execute("UPDATE pos_payment_method SET split_transactions = TRUE WHERE is_credit_transfer")
