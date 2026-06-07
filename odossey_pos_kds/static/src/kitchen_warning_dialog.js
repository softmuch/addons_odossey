import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class KitchenWarningDialog extends Component {
    static template = "odossey_pos_kds.KitchenWarningDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        body: { type: String, optional: true },
        proceedLabel: { type: String, optional: true },
        orderLabel: { type: String, optional: true },
        cancelLabel: { type: String, optional: true },
        onProceed: { type: Function, optional: true },
        onOrder: { type: Function, optional: true },
        onCancel: { type: Function, optional: true },
    };
    static defaultProps = {
        title: _t("Kitchen Screen Not Notified"),
        body: _t("The order has not been sent to the kitchen screen. How would you like to proceed?"),
        proceedLabel: _t("Proceed"),
        orderLabel: _t("Order and Proceed"),
        cancelLabel: _t("Cancel"),
    };

    proceed() {
        this.props.onProceed?.();
        this.props.close();
    }

    sendToKitchen() {
        this.props.onOrder?.();
        this.props.close();
    }

    cancel() {
        this.props.onCancel?.();
        this.props.close();
    }
}
