/**
 * Agenda settings of the clinic (opening hours, slot length, row height), read once per page load and shared by
 * the agenda and the time picker of the appointments. Reload the page after changing them.
 */
let settingsPromise = null;

export function getVetAgendaSettings(orm) {
    if (!settingsPromise) {
        // opening hours in the time zone the agenda is drawn in (the browser's), which can differ from the time
        // zone of the user preferences: otherwise a user set to Europe/Brussels on a computer in Argentina sees the
        // grid start at 12:40 instead of 8:40
        const tz = luxon.Settings.defaultZone.name;
        settingsPromise = orm.call("calendar.event", "vet_get_agenda_settings", [], { context: { tz } }).catch((error) => {
            settingsPromise = null;
            throw error;
        });
    }
    return settingsPromise;
}
