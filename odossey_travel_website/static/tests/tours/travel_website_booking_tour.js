import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("odossey_travel_website_booking", {
    url: "/viajes",
    steps: () => [
        {
            content: "Open the trip",
            trigger: ".o_travel_trip_card:contains('Web trip') a.btn",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Choose 2 passengers",
            trigger: "#travel_pax",
            run: "select 2",
        },
        {
            content: "Book",
            trigger: ".o_travel_trip_page form button[type=submit]",
            run: "click",
            expectUnloadPage: true,
        },
        { trigger: "#name", run: "edit Tour Customer" },
        { trigger: "#email", run: "edit tour.customer@example.com" },
        { trigger: "#vat", run: "edit 33444555" },
        { trigger: "input[name=passenger_0_name]", run: "edit Tour Customer" },
        { trigger: "input[name=passenger_1_name]", run: "edit Tour Companion" },
        { trigger: "#accept_conditions", run: "click" },
        {
            content: "Continue to payment",
            trigger: ".o_travel_booking_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The booking is shown on the portal with the trip information",
            trigger: "#travel_info:contains('Web trip')",
        },
        {
            content: "The customer can choose to pay the deposit",
            trigger: "button[name=o_sale_portal_amount_prepayment_button]",
        },
    ],
});
