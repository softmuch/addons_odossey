import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);

        const url = new URL(window.location.href);
        if (url.searchParams.get("close_session")) {
            url.searchParams.delete("close_session");
            window.history.replaceState({}, "", url);
            await this.closeSession();
        }
    },
});
