import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DateTimeField, dateTimeField } from "@web/views/fields/datetime/datetime_field";
import { getVetAgendaSettings } from "./vet_agenda_settings";

/**
 * Date & time of an appointment: the time picker offers the agenda slots (Settings › Veterinary › Agenda Slots),
 * e.g. :00, :20 and :40 with 20-minute slots, instead of quarters of an hour; the slot of the day of the appointment
 * when it is set in the opening hours (:00 and :30 on Saturday with 30-minute Saturday slots).
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
                this.settings = await getVetAgendaSettings(this.orm);
                this.slot = this.settings.slot_minutes;
            } catch {
                this.slot = null;
            }
        });
    }

    get fieldProps() {
        const props = { ...this.props };
        if (this.slot && isNaN(props.rounding)) {
            // the slot of the day of the appointment (e.g. 30 minutes on Saturday), otherwise the general one
            const value = props.record.data[props.name];
            const bySlot = this.settings.slot_by_day || {};
            props.rounding = (value && value.isValid && bySlot[String(value.weekday % 7)]) || this.slot;
        }
        return props;
    }
}

registry.category("fields").add("vet_slot_datetime", {
    ...dateTimeField,
    component: VetSlotDateTimeField,
});
