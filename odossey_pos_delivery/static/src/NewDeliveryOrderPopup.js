import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class NewDeliveryOrderPopup extends Component {
    static template = "odossey_pos_delivery.NewDeliveryOrderPopup";
    static props = {
        confirm: { type: Function },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            search_query: "",
            search_results: [],
            show_results: false,
            searching: false,
            selected_partner: null,

            partner_name: "",
            partner_phone: "",
            street: "",
            street_number: "",
            floor_apt: "",
            neighborhood: "",
            amount_total: "",
            shipping_cost: "",
            estimated_time: "30",
            note: "",
            error: "",
        });
        this._searchTimer = null;
    }

    async onSearchInput(ev) {
        const query = ev.target.value;
        this.state.search_query = query;
        this.state.selected_partner = null;

        clearTimeout(this._searchTimer);

        if (query.trim().length < 3) {
            this.state.search_results = [];
            this.state.show_results = false;
            return;
        }

        this._searchTimer = setTimeout(async () => {
            this.state.searching = true;
            try {
                const results = await this.orm.searchRead(
                    "res.partner",
                    ["|", "|",
                        ["name", "ilike", query.trim()],
                        ["phone", "ilike", query.trim()],
                        ["mobile", "ilike", query.trim()]
                    ],
                    ["id", "name", "phone", "mobile", "street", "street2"],
                    { limit: 10 }
                );
                this.state.search_results = results;
                this.state.show_results = results.length > 0;
            } catch (e) {
                console.error("Error buscando clientes:", e);
            } finally {
                this.state.searching = false;
            }
        }, 300);
    }

    selectPartner(partner) {
        this.state.selected_partner = partner;
        this.state.search_query = partner.name;
        this.state.show_results = false;
        this.state.partner_name = partner.name;
        this.state.partner_phone = partner.phone || partner.mobile || "";
        this.state.street = partner.street || "";
        this.state.street_number = "";
        this.state.floor_apt = partner.street2 || "";
        this.state.neighborhood = "";
    }

    clearPartner() {
        this.state.selected_partner = null;
        this.state.search_query = "";
        this.state.search_results = [];
        this.state.show_results = false;
        this.state.partner_name = "";
        this.state.partner_phone = "";
        this.state.street = "";
        this.state.street_number = "";
        this.state.floor_apt = "";
        this.state.neighborhood = "";
    }

    hideResults() {
        setTimeout(() => { this.state.show_results = false; }, 200);
    }

    confirm() {
        this.state.error = "";
        if (!this.state.partner_name.trim()) {
            this.state.error = "El nombre es requerido.";
            return;
        }
        if (!this.state.partner_phone.trim()) {
            this.state.error = "El teléfono es requerido.";
            return;
        }
        if (!this.state.street.trim()) {
            this.state.error = "La calle es requerida.";
            return;
        }

        const delivery_address = [
            this.state.street.trim(),
            this.state.street_number.trim(),
            this.state.floor_apt.trim(),
            this.state.neighborhood.trim(),
        ].filter(Boolean).join(", ");

        this.props.confirm({
            partner_id: this.state.selected_partner?.id || false,
            partner_name: this.state.partner_name.trim(),
            partner_phone: this.state.partner_phone.trim(),
            delivery_address,
            note: this.state.note.trim(),
            amount_total: parseFloat(this.state.amount_total) || 0,
            shipping_cost: parseFloat(this.state.shipping_cost) || 0,
            estimated_time: parseInt(this.state.estimated_time) || 30,
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
