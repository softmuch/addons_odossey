/**
 * Grid of the agenda, without any dependency (unit tested): rows counted from the opening of every day, with the
 * slot of that day (Settings › Veterinary › Agenda Slots, or the slot set in the opening hours of the day).
 * `agenda` is the result of calendar.event.vet_get_agenda_settings(); days follow FullCalendar (0 = Sunday) and
 * hours are in the time zone the agenda is drawn in.
 */

export function toMinutes(time) {
    const [h, m] = time.split(":").map((v) => parseInt(v));
    return h * 60 + (m || 0);
}

export function toTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00`;
}

export function gcd(a, b) {
    a = Math.abs(a);
    b = Math.abs(b);
    return b ? gcd(b, a % b) : a;
}

/** Slot of a day in minutes. */
export function daySlot(agenda, dow) {
    const bySlot = agenda.slot_by_day || {};
    return bySlot[String(dow)] || agenda.slot_minutes || 15;
}

/** Opening periods of a day. */
export function dayHours(agenda, dow) {
    return (agenda.business_hours || []).filter((h) => h.daysOfWeek.includes(dow));
}

/** Opening of a day in minutes (start of its first period, never its closing); 0 when the day is closed. */
export function dayOpening(agenda, dow) {
    const hours = dayHours(agenda, dow);
    return hours.length ? Math.min(...hours.map((h) => toMinutes(h.startTime))) : 0;
}

/**
 * Grid of a view: first and last time, row length, label interval, row height factor and hidden days.
 * - day: the slot and the opening of that day (Saturday 9:00 every 30 minutes);
 * - week: one grid for all the days, the common divisor of their slots and openings (20 and 30 minutes, openings at
 *   8:40 and 9:00 → rows of 10 minutes at half height, labels every 20), so every day keeps its own rows.
 */
export function computeAgendaGrid(agenda, scale, dow) {
    const allHours = agenda.business_hours || [];
    const ownHours = scale === "day" ? dayHours(agenda, dow) : [];
    const hours = ownHours.length ? ownHours : allHours;
    let slot = scale === "day" ? daySlot(agenda, dow) : agenda.slot_minutes || 15;
    let labelSlot = slot;
    let rowFactor = 1;
    const grid = { hours, slot, labelSlot, rowFactor, start: null, end: null, hiddenDays: null };
    if (!hours.length) {
        return grid;
    }
    const start = Math.min(...hours.map((h) => toMinutes(h.startTime)));
    const end = Math.max(...hours.map((h) => toMinutes(h.endTime)));
    if (scale !== "day") {
        const days = [...new Set(hours.flatMap((h) => h.daysOfWeek))];
        const slots = days.map((d) => daySlot(agenda, d));
        const step = days.reduce((acc, d) => gcd(gcd(acc, daySlot(agenda, d)), dayOpening(agenda, d) - start), 0);
        labelSlot = Math.min(...slots);
        slot = Math.max(step || labelSlot, Math.min(10, labelSlot));
        if (labelSlot % slot) {
            labelSlot = slot;
        }
        rowFactor = slot / labelSlot;
    }
    // the last row ends at closing time or later, aligned to the grid
    const rows = Math.ceil((end - start) / labelSlot) * (labelSlot / slot);
    const open = new Set(allHours.flatMap((h) => h.daysOfWeek));
    const hidden = [0, 1, 2, 3, 4, 5, 6].filter((d) => !open.has(d));
    return {
        hours,
        slot,
        labelSlot,
        rowFactor,
        start,
        end: Math.min(24 * 60, start + rows * slot),
        hiddenDays: hidden.length < 7 ? hidden : null,
    };
}

/** Moves a luxon datetime onto the grid of its day: down to its row, or to the nearest row. */
export function snapToDay(agenda, dateTime, nearest = false) {
    const dow = dateTime.weekday % 7;
    const slot = daySlot(agenda, dow);
    const origin = dayOpening(agenda, dow);
    const minutes = dateTime.hour * 60 + dateTime.minute;
    const steps = nearest ? Math.round((minutes - origin) / slot) : Math.floor((minutes - origin) / slot);
    return dateTime.startOf("day").plus({ minutes: origin + steps * slot });
}
