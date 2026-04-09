/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { _t } from "@web/core/l10n/translation";

patch(NumberPopup.prototype, {
    setup() {
        super.setup();
        this.state.discount_type = "percentage";
    },
    setType(ev) {
        this.state.discount_type = ev.target.value;
    },
    confirm() {
        this.props.getPayload(this.getPayload());
        this.props.close();
    },
    getPayload() {
        
        if (this.state.discount_type == "price") {
            const amount = typeof this.state.buffer === 'string' ? parseFloat(this.state.buffer) : this.state.buffer
            return {
                discount_type: this.state.discount_type,
                amount: amount,
            };
        } else {
            return this.state.buffer
        }
    },
});
