import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
// import { SelectPartnerButton } from "@point_of_sale/app/screens/product_screen/control_buttons/select_partner_button/select_partner_button"; 
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(ControlButtons.prototype, {
    async SplitBillScreen() {
        const order = this.pos.get_order();
        if(order.is_split) {
            await this.splitByPersonPopup(order);
            return;
        } else if(order.is_product_split) {
            this.pos.showScreen('SplitBillScreen');
            return;
        }
        if (order.get_orderlines().length > 0) { 
            let select_list = [{id:"0", label: _t("Split by Product"), item: 0}, {id:"1", label: _t("Split by Person"), item: 1}]
            const selectedOpt = await makeAwaitable(this.dialog, SelectionPopup, {
                list: select_list,
                title: _t('What do you want to do?'),
            });
            if(selectedOpt == 0) {
                this.pos.showScreen('SplitBillScreen');
                order.is_product_split = true;
            }
            else {
                await this.splitByPersonPopup(order);
            } 
        }
    },
    async splitByPersonPopup(order) {
        const { confirmed, payload: personNum } = await this.dialog.add(TextInputPopup, {
            startingValue: order.is_split? String(order.to_split): String(order.customer_count),
            title: _t('Number of Person'),
            getPayload: async (personNum) => {
                if(personNum == "") 
                    return
                if(Number(personNum) > order.customer_count) {
                    await this.dialog.add(AlertDialog, {title: "Split Error", body: "split should be less then or equal to total guest"});
                    return
                }
                if(order.split_done > 0) {
                    await this.dialog.add(AlertDialog, {title: "Split Error", body: "Cannot change number of person after more then one payment is made"});
                    return
                }
                if(!/^\d+$/.test(personNum)) {
                    await this.dialog.add(AlertDialog, {title: "Split Error", body: "Add only number"});
                    return
                }
                await order.setSplitBill(Number(personNum) > 0? Number(personNum): 1);
            },
        }); 
    }
}); 