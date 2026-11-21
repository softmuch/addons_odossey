import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";
import { getVetAgendaSettings } from "./vet_agenda_settings";
import { computeAgendaGrid, daySlot, snapToDay, toTime } from "./vet_agenda_grid";

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

/**
 * Popover of an appointment: "Start Consultation" next to "Edit", so the veterinarian opens the record of the visit
 * straight from the agenda (phone bookings first go through "Register Patient"). A phone booking whose patient is
 * not registered yet shows a green "Register Patient" button in the header, after the title; the delete button
 * stands alone on the right, away from "Start Consultation".
 */
export class VetCalendarCommonPopover extends CalendarCommonPopover {
    static subTemplates = {
        ...CalendarCommonPopover.subTemplates,
        popover: "odossey_veterinary.VetCalendarCommonPopover.popover",
        footer: "odossey_veterinary.VetCalendarCommonPopover.footer",
    };

    setup() {
        super.setup();
        this.action = useService("action");
        this.isVeterinarian = false;
        onWillStart(async () => {
            this.isVeterinarian = await user.hasGroup("odossey_veterinary.group_vet_veterinarian");
        });
    }

    get canStartConsultation() {
        const raw = this.props.record.rawRecord || {};
        // vet_card_status = visit status shown in the agenda (vet_state, or the simplified status of a clinic)
        return (
            this.isVeterinarian &&
            "vet_card_status" in raw &&
            !["done", "cancelled", "no_show"].includes(raw.vet_card_status) &&
            (raw.vet_pet_id || raw.vet_is_provisional)
        );
    }

    /** Patient alerts for the popover, one box per severity (only the severities shown, see
     *  Configuration › Alert Display Settings): same boxes as the consultation header. */
    get vetAlerts() {
        const raw = this.props.record.rawRecord || {};
        return [
            { key: "danger", icon: "fa-exclamation-triangle", text: raw.vet_card_danger_alert },
            { key: "warning", icon: "fa-exclamation-circle", text: raw.vet_card_warning_alert },
            { key: "info", icon: "fa-info-circle", text: raw.vet_card_info_alert },
        ].filter((alert) => alert.text);
    }

    get canRegisterPatient() {
        const raw = this.props.record.rawRecord || {};
        return (
            this.isEventEditable &&
            raw.vet_is_provisional &&
            !raw.vet_pet_id &&
            !["done", "cancelled", "no_show"].includes(raw.vet_card_status)
        );
    }

    async onRegisterPatient() {
        const model = this.props.model;
        const resId = this.props.record.id;
        this.props.close();
        await this.action.doActionButton({
            type: "object",
            name: "action_vet_register_patient",
            resModel: "calendar.event",
            resId,
            resIds: [resId],
            onClose: () => model.load(),
        });
    }

    async onStartConsultation() {
        const model = this.props.model;
        const resId = this.props.record.id;
        this.props.close();
        await this.action.doActionButton({
            type: "object",
            name: "action_vet_start_consultation",
            resModel: "calendar.event",
            resId,
            resIds: [resId],
            onClose: () => model.load(),
        });
    }
}

export class VetCalendarCommonRenderer extends CalendarCommonRenderer {
    static eventTemplate = "odossey_veterinary.VetCalendarEvent";
    static components = { ...CalendarCommonRenderer.components, Popover: VetCalendarCommonPopover };

    get options() {
        const options = super.options;
        const agenda = this.props.model.vetAgenda || {};
        // day view: the slot and the opening of that day (the view is rebuilt when the date changes); week: one
        // grid for all the days (see computeAgendaGrid)
        const grid = computeAgendaGrid(agenda, this.props.model.scale, this.props.model.date.weekday % 7);
        this.vetRowFactor = grid.rowFactor;
        if (grid.start !== null) {
            if (agenda.hide_closed_days && grid.hiddenDays) {
                options.hiddenDays = grid.hiddenDays;
            }
            Object.assign(options, {
                businessHours: grid.hours,
                slotMinTime: toTime(grid.start),
                slotMaxTime: toTime(grid.end),
                scrollTime: toTime(grid.start),
            });
        }
        Object.assign(options, {
            slotDuration: { minutes: grid.slot },
            snapDuration: { minutes: grid.slot },
            slotLabelInterval: { minutes: grid.labelSlot },
            viewClassNames: ["o_vet_agenda", `o_vet_rows_${agenda.row_height || "comfortable"}`],
        });
        return options;
    }

    viewDidMount(info) {
        super.viewDidMount(info);
        // rows shorter than a slot in the week (see options): scale their height
        info.el.style.setProperty("--o-vet-row-factor", String(this.vetRowFactor || 1));
    }

    /**
     * Clicks, selections and drags land on the grid of their own day, counted from its opening: a click on Saturday
     * 9:10 with 30-minute Saturday slots books 9:00-9:30, even if the week shows rows of 10 minutes.
     */
    fcEventToRecord(event) {
        const res = super.fcEventToRecord(event);
        const agenda = this.props.model.vetAgenda;
        if (!agenda || res.isAllDay || this.props.model.scale === "month" || !res.start) {
            return res;
        }
        const existing = res.id && this.props.model.records[res.id];
        if (!existing) {
            // new appointment: the row clicked, at least one slot long
            const start = snapToDay(agenda, res.start);
            const slot = daySlot(agenda, start.weekday % 7);
            let end = res.end ? snapToDay(agenda, res.end.minus({ minutes: 1 })).plus({ minutes: slot }) : null;
            if (!end || end <= start) {
                end = start.plus({ minutes: slot });
            }
            return { ...res, start, end };
        }
        const start = snapToDay(agenda, res.start, true);
        if (!res.end) {
            return { ...res, start };
        }
        const oldDuration = existing.end ? existing.end.diff(existing.start).as("minutes") : null;
        const duration = res.end.diff(res.start).as("minutes");
        if (oldDuration !== null && Math.round(duration) === Math.round(oldDuration)) {
            // moved: keep its length
            return { ...res, start, end: start.plus({ minutes: duration }) };
        }
        // resized: the edge that moved snaps to the grid, the other one stays
        if (+res.start !== +existing.start) {
            return start < res.end ? { ...res, start } : res;
        }
        const end = snapToDay(agenda, res.end, true);
        return end > res.start ? { ...res, end } : res;
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
