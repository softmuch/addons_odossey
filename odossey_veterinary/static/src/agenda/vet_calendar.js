import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { getVetAgendaSettings } from "./vet_agenda_settings";

/**
 * Agenda of the clinic: the day starts at the opening time and closed hours are shaded, one row per slot
 * (Settings › Veterinary › Agenda Slots) counted from the opening (8:40, 9:00, 9:20...), taller rows and a cell
 * that tells the reception who comes and who attends without opening the appointment.
 */
export class VetCalendarModel extends CalendarModel {
    async load(params = {}) {
        if (!this.vetAgenda) {
            this.vetAgenda = await getVetAgendaSettings(this.orm);
            this.applyVetAgendaSettings();
        }
        return super.load(params);
    }

    applyVetAgendaSettings() {
        const { default_scale: scale, color_by: colorBy } = this.vetAgenda;
        // view of the first visit (Settings › Veterinary › Agenda Opens On); afterwards the user's last choice
        if (scale && this.meta.scales.includes(scale) && !browser.localStorage.getItem(this.storageKey)) {
            this.meta.scale = scale;
        }
        // Settings › Veterinary › Book by Room: no room filter when the clinic books by veterinarian
        if (this.vetAgenda.use_rooms === false) {
            if (this.meta.filtersInfo.vet_room_id) {
                const { vet_room_id, ...filtersInfo } = this.meta.filtersInfo;
                this.meta.filtersInfo = filtersInfo;
            }
            if (this.meta.popoverFieldNodes.vet_room_id) {
                const { vet_room_id, ...popoverFieldNodes } = this.meta.popoverFieldNodes;
                this.meta.popoverFieldNodes = popoverFieldNodes;
            }
        }
        // Settings › Veterinary › Colors: vet_card_color holds the color of the veterinarian / type / room
        if (colorBy && this.meta.fields.vet_card_color) {
            this.meta.fieldMapping = { ...this.meta.fieldMapping, color: "vet_card_color" };
            if (!this.meta.fieldNames.includes("vet_card_color")) {
                this.meta.fieldNames = [...this.meta.fieldNames, "vet_card_color"];
            }
        }
    }

    normalizeRecord(rawRecord) {
        const record = super.normalizeRecord(rawRecord);
        record.vetCard = (this.vetAgenda && this.vetAgenda.card) || {};
        return record;
    }
}

function toMinutes(time) {
    const [h, m] = time.split(":").map((v) => parseInt(v));
    return h * 60 + (m || 0);
}

function toTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00`;
}

export class VetCalendarCommonRenderer extends CalendarCommonRenderer {
    static eventTemplate = "odossey_veterinary.VetCalendarEvent";

    get options() {
        const options = super.options;
        const agenda = this.props.model.vetAgenda || {};
        const hours = agenda.business_hours || [];
        const slot = agenda.slot_minutes || 15;
        if (hours.length) {
            const start = Math.min(...hours.map((h) => toMinutes(h.startTime)));
            const end = Math.max(...hours.map((h) => toMinutes(h.endTime)));
            // the last row ends at closing time or later, aligned to the slot grid
            const rows = Math.ceil((end - start) / slot);
            if (agenda.hide_closed_days) {
                const open = new Set(hours.flatMap((h) => h.daysOfWeek));
                const hidden = [0, 1, 2, 3, 4, 5, 6].filter((d) => !open.has(d));
                if (hidden.length < 7) {
                    options.hiddenDays = hidden;
                }
            }
            Object.assign(options, {
                businessHours: hours,
                slotMinTime: toTime(start),
                slotMaxTime: toTime(Math.min(24 * 60, start + rows * slot)),
                scrollTime: toTime(start),
            });
        }
        Object.assign(options, {
            slotDuration: { minutes: slot },
            snapDuration: { minutes: slot },
            slotLabelInterval: { minutes: slot },
            viewClassNames: ["o_vet_agenda", `o_vet_rows_${agenda.row_height || "comfortable"}`],
        });
        return options;
    }

    eventClassNames(info) {
        const classes = super.eventClassNames(info);
        const record = this.props.model.records[info.event.id];
        const raw = record && record.rawRecord;
        if (raw) {
            classes.push("o_vet_event_card");
            if (raw.vet_card_status) {
                classes.push(`o_vet_status_${raw.vet_card_status}`);
            }
            if (raw.vet_is_provisional) {
                classes.push("o_vet_provisional");
            }
        }
        return classes;
    }
}

export class VetCalendarRenderer extends CalendarRenderer {
    static components = {
        ...CalendarRenderer.components,
        day: VetCalendarCommonRenderer,
        week: VetCalendarCommonRenderer,
        month: VetCalendarCommonRenderer,
    };
}

export class VetCalendarController extends CalendarController {
    getQuickCreateFormViewProps(record) {
        const props = super.getQuickCreateFormViewProps(record);
        return {
            ...props,
            title: _t("New Appointment"),
            context: { ...this.props.context, ...props.context },
            // the dialog does not refresh the agenda by itself
            onRecordSaved: () => this.model.load(),
        };
    }
}

export const vetCalendarView = {
    ...calendarView,
    Controller: VetCalendarController,
    Model: VetCalendarModel,
    Renderer: VetCalendarRenderer,
};

registry.category("views").add("vet_calendar", vetCalendarView);
