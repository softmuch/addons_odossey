import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

export const VET_POS_RETURN_KEY = "odossey_veterinary.pos_return";

/**
 * Veterinary › Billing › Cash Desk: opens the till directly (or the list of tills when the clinic has several);
 * leaving the till brings the user back to the agenda.
 */
async function openCashDesk(env) {
    const configs = await env.services.orm.searchRead("pos.config", [["active", "=", true]], ["id"], {
        limit: 2,
    });
    try {
        browser.sessionStorage.setItem(VET_POS_RETURN_KEY, "1");
    } catch {
        // private window: the till still opens, the user may come back by the menu
    }
    if (configs.length === 1) {
        browser.location.href = `/pos/ui?config_id=${configs[0].id}`;
        return;
    }
    return env.services.action.doAction("point_of_sale.action_pos_config_kanban", {
        clearBreadcrumbs: true,
    });
}

registry.category("actions").add("odossey_veterinary.open_cash_desk", openCashDesk);
