import { describe, expect, test } from "@odoo/hoot";
import { computeAgendaGrid, dayOpening, snapToDay, toTime } from "@odossey_veterinary/agenda/vet_agenda_grid";

// Clinic of the tests: Monday to Friday 8:40-12:40 and 14:00-18:00 every 20 minutes (general slot), Saturday
// 9:00-13:00 every 30 minutes (slot set in the opening hours). FullCalendar days: 0 = Sunday, 6 = Saturday.
const weekday = (d) => [
    { daysOfWeek: [d], startTime: "08:40", endTime: "12:40" },
    { daysOfWeek: [d], startTime: "14:00", endTime: "18:00" },
];
const AGENDA = {
    business_hours: [1, 2, 3, 4, 5].flatMap(weekday).concat([{ daysOfWeek: [6], startTime: "09:00", endTime: "13:00" }]),
    slot_minutes: 20,
    slot_by_day: { 0: 20, 1: 20, 2: 20, 3: 20, 4: 20, 5: 20, 6: 30 },
};

describe.current.tags("headless");

test("opening of a day is the start of its first period, never its closing", () => {
    expect(dayOpening(AGENDA, 6)).toBe(9 * 60);
    expect(dayOpening(AGENDA, 1)).toBe(8 * 60 + 40, { message: "two periods: the morning one" });
    expect(dayOpening(AGENDA, 0)).toBe(0, { message: "closed on Sunday" });
});

test("day view of Saturday: from 9:00 to 13:00 every 30 minutes", () => {
    const grid = computeAgendaGrid(AGENDA, "day", 6);
    expect([toTime(grid.start), toTime(grid.end), grid.slot, grid.labelSlot, grid.rowFactor]).toEqual([
        "09:00:00", "13:00:00", 30, 30, 1,
    ]);
});

test("day view of a day with two periods: from 8:40 to 18:00 every 20 minutes", () => {
    const grid = computeAgendaGrid(AGENDA, "day", 1);
    expect([toTime(grid.start), toTime(grid.end), grid.slot, grid.labelSlot]).toEqual(["08:40:00", "18:00:00", 20, 20]);
    expect(grid.hiddenDays).toEqual([0], { message: "Sunday closed" });
});

test("week view: rows of 10 minutes at half height, labels every 20, from 8:40", () => {
    const grid = computeAgendaGrid(AGENDA, "week", 1);
    expect([toTime(grid.start), toTime(grid.end), grid.slot, grid.labelSlot, grid.rowFactor]).toEqual([
        "08:40:00", "18:00:00", 10, 20, 0.5,
    ]);
});

test("week view without slots per day: the grid of always", () => {
    const grid = computeAgendaGrid({ ...AGENDA, slot_by_day: {} }, "week", 1);
    expect([toTime(grid.start), grid.slot, grid.labelSlot, grid.rowFactor]).toEqual(["08:40:00", 20, 20, 1]);
});

test("clicks land on the rows of their own day", () => {
    const at = (iso) => luxon.DateTime.fromISO(iso);
    // Saturday 21/11/2026 9:10 → 9:00 (rows of 30 from 9:00); Monday 16/11/2026 8:50 → 8:40 (rows of 20 from 8:40)
    expect(snapToDay(AGENDA, at("2026-11-21T09:10")).toFormat("HH:mm")).toBe("09:00");
    expect(snapToDay(AGENDA, at("2026-11-16T08:50")).toFormat("HH:mm")).toBe("08:40");
    expect(snapToDay(AGENDA, at("2026-11-16T08:52"), true).toFormat("HH:mm")).toBe("09:00");
});
