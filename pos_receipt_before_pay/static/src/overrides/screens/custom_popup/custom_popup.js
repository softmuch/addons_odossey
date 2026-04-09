import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";

export class custom_popup extends Component {
    static template = "pos_receipt_before_pay.custom_popup";
    static components = { Dialog, OrderReceipt };

    setup(){
        super.setup()
        this.pos =  usePos()   
    }
}