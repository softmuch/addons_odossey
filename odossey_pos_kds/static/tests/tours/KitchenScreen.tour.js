/** @odoo-module **/
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add(
  'odossey_pos_kds_tour',
  {
    url: '/odossey_pos_kds/app/',
    test: true,
    steps: () => [
      {
        trigger: '#kitchen_screen_app',
        run: () => {
          console.log('running odossey_pos_kds_tour')
        },
      },
      {
        trigger: 'span:contains("Ready"):first',
        run: 'click',
      },
    ],
  },
)
