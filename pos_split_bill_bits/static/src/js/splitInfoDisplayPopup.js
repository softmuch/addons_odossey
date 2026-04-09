/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog"; 

export class SplitInfoDisplayPopup extends Component {
    static components = { Dialog };
    static template = "SplitInfoDisplayPopup" 
    static props = {
        body1: Array,
        body2: Array, 
        title:{type:String, optional: true},
        confirmText:{type:String, optional: true},
        close: { type: Function, optional: true },
    } 
}