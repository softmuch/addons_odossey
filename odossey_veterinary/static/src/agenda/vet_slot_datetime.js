import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DateTimeField, dateTimeField } from "@web/views/fields/datetime/datetime_field";
import { getVetAgendaSettings } from "./vet_agenda_settings";

/**
 * Date & time of an appointment: the time picker offers the agenda slots (Settings › Veterinary › Agenda Slots),
 * e.g. :00, :20 and :40 with 20-minute slots, instead of quarters of an hour.
 */
export class VetSlotDateTimeField extends Component {
    static template = "odossey_veterinary.VetSlotDateTimeField";
    static components = { DateTimeField };
    static props = { ...DateTimeField.props };

    setup() {
        this.orm = useService("orm");
        this.slot = null;
        onWillStart(async () => {
            try {
                const settings = await getVetAgendaSettings(this.orm);
                this.slot = settings.slot_minutes;
            } catch {
                this.slot = null;
            }
        });
    }

    get fieldProps() {
        const props = { ...this.props };
        if (this.slot && isNaN(props.rounding)) {
            props.rounding = this.slot;
        }
        return props;
    }
}

registry.category("fields").add("vet_slot_datetime", {
    ...dateTimeField,
    component: VetSlotDateTimeField,
});
