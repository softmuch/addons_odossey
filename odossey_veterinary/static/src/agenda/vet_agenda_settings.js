/**
 * Agenda settings of the clinic (opening hours, slot length, row height), read once per page load and shared by
 * the agenda and the time picker of the appointments.
 */
let settingsPromise = null;

export function getVetAgendaSettings(orm) {
    if (!settingsPromise) {
        settingsPromise = orm.call("calendar.event", "vet_get_agenda_settings", []).catch((error) => {
            settingsPromise = null;
            throw error;
        });
    }
    return settingsPromise;
}
