/** @odoo-module **/
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add(
  'abichinger_kitchen_screen_tour',
  {
    url: '/abichinger_kitchen_screen/app/',
    test: true,
    steps: () => [
      {
        trigger: '#kitchen_screen_app',
        run: () => {
          console.log('running abichinger_kitchen_screen_tour')
        },
      },
      {
        trigger: 'span:contains("Ready"):first',
        run: 'click',
      },
    ],
  },
)
