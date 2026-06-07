import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    async pay() {
        const order = this.get_order();
        if (order?.is_delivery) {
            const partner = order.get_partner();
            const anonId = this.config.partner_id?.id || this.config.partner_id;
            const valid =
                partner &&
                partner.street &&
                partner.city &&
                !(anonId && partner.id === anonId);
            if (!valid) {
                this.notification.add(
                    _t("Delivery: please select a customer with complete address (street and city) before payment."),
                    { type: "warning" }
                );
                return;
            }
        }
        await super.pay(...arguments);
    },

});
