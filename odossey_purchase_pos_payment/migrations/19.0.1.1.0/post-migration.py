# License OPL-1


def migrate(cr, version):
    """`reference_amount` is new: every payment made before it existed was
    booked in the order's own currency, so it equals `amount`. Recompute
    the stored `purchase.order.amount_paid`/`amount_difference` from it
    (the ORM recompute ran before this backfill, against zeros)."""
    cr.execute(
        """
        UPDATE pos_payment
           SET reference_amount = amount
         WHERE purchase_order_id IS NOT NULL
           AND reference_amount IS NULL
        """
    )
    cr.execute(
        """
        UPDATE purchase_order po
           SET amount_paid = COALESCE(pay.total, 0),
               amount_difference = po.amount_total - COALESCE(pay.total, 0)
          FROM (
                SELECT purchase_order_id, SUM(ABS(reference_amount)) AS total
                  FROM pos_payment
                 WHERE purchase_order_id IS NOT NULL
              GROUP BY purchase_order_id
               ) pay
         WHERE pay.purchase_order_id = po.id
        """
    )
