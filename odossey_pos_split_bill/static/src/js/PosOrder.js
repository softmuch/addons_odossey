import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { lt } from "@point_of_sale/utils";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";
import { accountTaxHelpers } from "@account/helpers/account_tax";


patch(PosOrder.prototype, {
  setup() {
    super.setup(...arguments);
    if (this.config.module_pos_restaurant) {
      this.is_split = this.is_split;
      this.to_split = this.to_split;
      this.split_done = this.split_done;
      this.n_payments = this.n_payments;
    }
  },
  getDefaultAmountDueToPayIn(paymentMethod) {
    let res = super.getDefaultAmountDueToPayIn(paymentMethod);
    return res;
  },
  get_total_with_tax_split() {
    const total = this.taxTotals.order_sign * this.taxTotals.order_total;
    const split_total = roundPrecision(total / this.to_split, this.currency.rounding);
    if (!this.is_split) return total;
    // Guard: all splits done (receipt display after order completion)
    if (this.split_done >= this.to_split) return total;
    // This payment covers the last remaining people — pay the exact remainder
    if (this.split_done + this.n_payments >= this.to_split) {
      return roundPrecision(total - (split_total * this.split_done), this.currency.rounding);
    }
    // Regular payment: one person pays for n_payments shares
    return roundPrecision(split_total * this.n_payments, this.currency.rounding);
  },
  get_tax_details_split() {
    const fulldetails = this.get_tax_details();
    if (this.is_split) {
      const newFulldetails = fulldetails.map((ele) => {
        ele.amount = ele.amount / this.to_split;
        ele.base = ele.base / this.to_split;
        return ele;
      });
      return newFulldetails;
    }
    return fulldetails;
  },
  get_subtotal_split() {
    const subtotal = this.get_subtotal();
    if (this.is_split && subtotal > 0) {
      // split_done >= to_split means this is the last-person receipt display
      if (this.split_done >= this.to_split)
        return subtotal - this.get_total_paid();
      return roundPrecision((subtotal / this.to_split) * this.n_payments, this.currency.rounding);
    }
    return subtotal;
  },
  get_total_without_tax_split() {
    const total = this.get_total_without_tax();
    if (this.is_split)
      return roundPrecision(total / this.to_split, this.currency.rounding);
    else return total;
  },
  get_change(paymentline) {
    let change;
    if (!paymentline) {
      // Only sum payments from the CURRENT split round (exclude completed rounds)
      // to avoid showing incorrect change when previous persons' lines accumulate.
      const completedUuids = this.completedSplitPaymentUuids;
      const currentPaid = this.is_split && completedUuids
          ? this.payment_ids
              .filter((p) => p.is_done() && !p.is_change && !completedUuids.has(p.uuid))
              .reduce((sum, p) => sum + p.get_amount(), 0)
          : this.get_total_paid();
      change = currentPaid - this.get_total_with_tax_split() - this.get_rounding_applied();
    } else {
      const split_amount = this.get_total_with_tax_split();
      change = paymentline.amount - split_amount;
    }
    return roundPrecision(Math.max(0, change), this.currency.rounding);
  },
  get_total_tax_split() {
    const tax = this.get_total_tax();
    if (this.is_split) {
      return roundPrecision(tax / this.to_split, this.currency.rounding);
    } else {
      return tax;
    }
  },
  get_total_discount_split() {
    const discount = this.get_total_discount();
    if (this.is_split && discount > 0)
      return roundPrecision(discount / this.to_split, this.currency.rounding);
    else return discount;
  },
  export_for_printing_split(baseUrl, headerData) {
    const receipt = this.export_for_printing(baseUrl, headerData);
    if (this.is_split) {
      Object.assign(receipt, {
        subtotal: this.get_subtotal_split(),
        amount_total: this.get_total_with_tax_split(true),
        amount_tax: this.get_total_tax_split(),
        amount_paid: this.get_total_paid() - this.get_change(),
        total_discount: this.get_total_discount_split(),
        is_split: this.is_split,
        to_split: this.to_split,
        total_split: this.split_done,
        tax_details: this.get_tax_details_split()
      });
    }
    return receipt;
  },
  get_due() {
    return (
        this.taxTotals.order_sign *
        roundPrecision(this.taxTotals.order_remaining, this.currency.rounding)
    );
  },
  // Override getTotalDue so the payment screen's "total" display and amountPerGuest()
  // both show the split-round amount (with last-person remainder) instead of the full order total.
  getTotalDue() {
    if (this.is_split && this.to_split > 1) {
      return this.get_total_with_tax_split();
    }
    return super.getTotalDue();
  },
  // Override amountPerGuest so it divides by the number of people in the CURRENT round
  // (n_payments), not by the total table guest count.
  amountPerGuest() {
    if (this.is_split && this.to_split > 1 && this.n_payments > 0) {
      return this.get_total_with_tax_split() / this.n_payments;
    }
    return super.amountPerGuest(...arguments);
  },
  splitDone() {
    this.r_split = this.split_done;
    // Mark current payment line UUIDs as belonging to a completed split round.
    // UUID never changes after creation (unlike .id which may not update after sync).
    if (!this.completedSplitPaymentUuids) {
        this.completedSplitPaymentUuids = new Set();
    }
    for (const line of this.payment_ids) {
        this.completedSplitPaymentUuids.add(line.uuid);
    }
    if (this.split_done != this.to_split) {
      this.split_done = this.split_done + this.n_payments;
    }
    if (this.split_done == this.to_split) {
        this.state = "paid";
    }
    this.n_payments = 1;
  },
  async setSplitBill(splits) {
    if (splits == 1) {
      this.is_split = false;
      this.to_split = splits;
      this.split_done = 0;
      this.n_payments = 1;
    } else {
      this.is_split = true;
      this.to_split = splits;
      this.split_done = 0;
      this.n_payments = 1;
    }
  },
  get taxTotals() {
    if (this.is_split && this.to_split > 1) {
      const currency = this.config.currency_id;
      const company = this.company;
      const orderLines = this.lines;

      const documentSign = this.lines.length === 0 || !this.lines.every((l) => lt(l.qty, 0, { decimals: currency.decimal_places })) ? 1 : -1;

      const baseLines = orderLines.map((line) => {
          return accountTaxHelpers.prepare_base_line_for_taxes_computation(
              line,
              line.prepareBaseLineForTaxesComputationExtraValues({
                  quantity: documentSign * line.qty,
              })
          );
      });
      accountTaxHelpers.add_tax_details_in_base_lines(baseLines, company);
      accountTaxHelpers.round_base_lines_tax_details(baseLines, company);

      const cashRounding =
          !this.config.only_round_cash_method && this.config.cash_rounding
              ? this.config.rounding_method
              : null;

      const taxTotals = accountTaxHelpers.get_tax_totals_summary(baseLines, currency, company, {
          cash_rounding: cashRounding,
      });

      taxTotals.order_sign = documentSign;
      taxTotals.order_total =
          taxTotals.total_amount_currency - (taxTotals.cash_rounding_base_amount_currency || 0.0);

      let order_rounding = 0;
      let remaining = 0;
      if (this.split_done + this.n_payments >= this.to_split)
        remaining = taxTotals.order_total - this.amount_paid;
      else
        // Round per-person share first, then multiply — stays consistent with get_total_with_tax_split()
        remaining = roundPrecision(taxTotals.order_total / this.to_split, this.currency.rounding) * this.n_payments;

      // Exclude completed split-round payments from the remaining calculation.
      // Those lines stay in payment_ids for accounting but must not reduce
      // the amount still due for the CURRENT person's payment screen.
      const completedUuids = this.completedSplitPaymentUuids;
      const validPayments = this.payment_ids.filter(
          (p) => p.is_done() && !p.is_change && !(completedUuids?.has(p.uuid))
      );
      for (const [payment, isLast] of validPayments.map((p, i) => [p, i === validPayments.length - 1])) {
          const paymentAmount = documentSign * payment.get_amount();
          if (isLast) {
              if (this.config.cash_rounding) {
                  const roundedRemaining = this.getRoundedRemaining(
                      this.config.rounding_method,
                      remaining
                  );
                  if (!floatIsZero(paymentAmount - remaining, this.currency.decimal_places)) {
                      order_rounding = roundedRemaining - remaining;
                  }
              }
          }
          remaining -= paymentAmount;
      }

      taxTotals.order_rounding = order_rounding;
      taxTotals.order_remaining = remaining;

      const remaining_with_rounding = remaining + order_rounding;
      if (floatIsZero(remaining_with_rounding, currency.decimal_places)) {
          taxTotals.order_has_zero_remaining = true;
      } else {
          taxTotals.order_has_zero_remaining = false;
      }
      return taxTotals;
    } else {
      return super.taxTotals;
    }
  },

  get totalsplits() {
    return this.to_split;
  }
});
