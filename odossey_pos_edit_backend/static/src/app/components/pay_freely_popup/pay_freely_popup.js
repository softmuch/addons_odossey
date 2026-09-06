import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { formatFloat } from "@web/core/utils/numbers";
import { parseFloat } from "@web/views/fields/parsers";

export class PayFreelyPopup extends Component {
    static template = "odossey_pos_edit_backend.PayFreelyPopup";
    static components = { Dialog, AutoComplete };
    static props = {
        title: { type: String, optional: true },
        partner: Object,
        totalResidual: Number,
        totalResidualLabel: { type: String, optional: true },
        paymentMethods: Array,
        banks: { type: Array, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: _t("Pagar Libremente"),
        banks: [],
        totalResidualLabel: "",
    };

    setup() {
        this.state = useState({
            amountText: formatFloat(this.props.totalResidual),
            payment_method_id: this.props.paymentMethods[0]?.id || false,
            number: "",
            bank_id: false,
            bank_name: "",
            issuer_vat: this.props.partner.vat || "",
            check_type: "common",
            issue_date: this._today(),
            payment_date: this._today(),
        });
    }

    _today() {
        return new Date().toISOString().split("T")[0];
    }

    get selectedPaymentMethod() {
        // `t-model` on a native <select> always stores the value as a
        // string, never as the number `pm.id` actually is -- a strict `===`
        // between them never matches, so this always returned undefined and
        // `isCheck` was always false (check fields never showed, no matter
        // which method was picked). Cast before comparing.
        const id = Number(this.state.payment_method_id);
        return this.props.paymentMethods.find((pm) => pm.id === id);
    }

    get isCheck() {
        return this.selectedPaymentMethod?.payment_method_type === "check";
    }

    get amount() {
        try {
            return parseFloat(this.state.amountText);
        } catch {
            return 0;
        }
    }

    // Same rule as the backend wizard's own `_onchange_amount_cap`: an
    // amount higher than what's actually owed has nowhere to go (no
    // advance-payment concept for pos.order), so it's snapped back down to
    // the max instead of letting the cashier submit a value that would just
    // get rejected server-side.
    formatAmountOnBlur() {
        const capped = Math.min(this.amount, this.props.totalResidual);
        this.state.amountText = formatFloat(capped > 0 ? capped : this.props.totalResidual);
    }

    getBankSources() {
        return [
            {
                options: (currentInput) => {
                    const query = currentInput.trim().toLowerCase();
                    const banks = query
                        ? this.props.banks.filter((bank) => bank.name.toLowerCase().includes(query))
                        : this.props.banks;
                    return banks.slice(0, 30).map((bank) => ({
                        label: bank.name,
                        onSelect: () => this.selectBank(bank),
                    }));
                },
            },
        ];
    }

    selectBank(bank) {
        this.state.bank_id = bank.id;
        this.state.bank_name = bank.name;
    }

    onBankInput({ inputValue }) {
        if (!inputValue) {
            this.state.bank_id = false;
        }
    }

    get isValid() {
        if (!(this.amount > 0 && this.amount <= this.props.totalResidual && this.state.payment_method_id)) {
            return false;
        }
        if (this.isCheck) {
            return Boolean(
                this.state.number && this.state.bank_id && this.state.issue_date && this.state.payment_date
            );
        }
        return true;
    }

    confirm() {
        if (!this.isValid) {
            return;
        }
        this.props.getPayload({
            ...this.state,
            amount: this.amount,
            payment_method_id: Number(this.state.payment_method_id),
        });
        this.props.close();
    }

    discard() {
        this.props.close();
    }
}
