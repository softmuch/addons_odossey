import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("odossey_travel_tour", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open the Travel app",
            trigger: '.o_app[data-menu-xmlid="odossey_travel.menu_travel_root"]',
            run: "click",
        },
        {
            content: "The travel calendar is the main view",
            trigger: ".o_calendar_view",
        },
        {
            content: "Open the Trips menu",
            trigger: '.o_main_navbar button[data-menu-xmlid="odossey_travel.menu_travel_trips"]',
            run: "click",
        },
        {
            content: "Open the trips",
            trigger: '.o-dropdown--menu [data-menu-xmlid="odossey_travel.menu_travel_trip"]',
            run: "click",
        },
        {
            content: "Open the tour trip from the kanban",
            trigger: ".o_kanban_record:contains('Tour Trip Odossey')",
            run: "click",
        },
        {
            content: "The trip form is open",
            trigger: ".o_form_view .o_field_widget[name='name'] input:value('Tour Trip Odossey')",
        },
        {
            content: "Open the Passengers tab",
            trigger: ".o_notebook_headers a:contains('Passengers')",
            run: "click",
        },
        {
            content: "The passenger of the trip is listed",
            trigger: ".o_field_widget[name='passenger_ids'] .o_data_row:contains('Tour Passenger')",
        },
    ],
});
