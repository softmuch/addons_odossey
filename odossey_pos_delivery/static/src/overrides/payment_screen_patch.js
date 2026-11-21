import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
patch(PaymentScreen.prototype, {
    async _finalizeValidation() {
        const order = this.currentOrder;
        const isDelivery = order?.is_delivery;

        if (isDelivery) {
            const partner = order.get_partner();
            const anonId =
                this.pos.config.partner_id?.id || this.pos.config.partner_id;
            const valid =
                partner &&
                partner.street &&
                partner.city &&
                !(anonId && partner.id === anonId);
            if (!valid) {
                this.notification.add(
                    _t("Delivery: please select a customer with complete address (street and city)."),
                    { type: "warning" }
                );
                return;
            }
        }

        await super._finalizeValidation(...arguments);

        // The delivery record is marked "paid" server side when the paid order is
        // synced (pos.order._process_saved_order). Do NOT call the ORM here: super()
        // already switched to ReceiptScreen, this component gets destroyed and its
        // protected ORM promises never resolve (the record stayed "unpaid").
        if (isDelivery && order.state !== "draft") {
            this.pos.showScreen("DeliveryScreen");
        }
    },
});
