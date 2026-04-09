import { ElMessageBox } from 'element-plus'
import { useClient } from './odoo'
import { h } from 'vue'
import DebugMenu from '@/components/DebugMenu.vue'
import { zero_pad } from './util'

export async function debugMenu() {
  ElMessageBox({
    title: 'Debug',
    message: () => {
      return h(DebugMenu)
    },
  })
}

export async function createOrders(n: number) {
  for (let i = 0; i < n; i++) {
    await createOrder()
  }
}

export async function createOrder(state: string = 'cooking') {
  const { orm } = await useClient()

  const rand = (max: number) => Math.floor(Math.random() * max)

  const uid =
    zero_pad(rand(10000), 5) + '-' + zero_pad(rand(100), 3) + '-' + zero_pad(rand(1000), 4)

  const order = (uid: string) => {
    return {
      name: 'Order ' + uid,
      amount_paid: 0,
      amount_total: 21.740000000000002,
      amount_tax: 2.84,
      amount_return: 0,
      lines: [
        [
          0,
          0,
          {
            uuid: crypto.randomUUID(),
            skip_change: false,
            custom_attribute_value_ids: [],
            qty: 2,
            price_unit: 7.5,
            price_subtotal: 7.5,
            price_subtotal_incl: 8.63,
            discount: 0,
            product_id: 56,
            tax_ids: [[6, false, [1]]],
            pack_lot_ids: [],
            attribute_value_ids: [],
            full_product_name: 'Bacon Burger',
            price_extra: 0,
            customer_note: '',
            price_type: 'original',
            note: '',
            ab_stock_warehouse_id: 1,
          },
        ],
      ],
      statement_ids: [],
      pos_session_id: 6,
      pricelist_id: false,
      partner_id: false,
      user_id: 2,
      uid: uid,
      sequence_number: rand(100),
      date_order: '2024-07-19 06:54:42',
      fiscal_position_id: false,
      server_id: false,
      to_invoice: false,
      shipping_date: false,
      is_tipped: false,
      tip_amount: 0,
      access_token: '9189c3d4-c36e-4fa5-af94-b09d79f442f6',
      last_order_preparation_change:
        '{"fba20bd7-e6e0-479d-a0e9-8bc135328b62 - ":{"line_uuid":"fba20bd7-e6e0-479d-a0e9-8bc135328b62","product_id":56,"name":"Bacon Burger","note":"","quantity":2}}',
      ticket_code: 'd5mmg',
      table_id: 3,
      customer_count: 1,
      booked: true,
      changes: [
        [
          0,
          0,
          {
            created_at: '2024-07-19 06:54:56',
            sequence_number: 1,
            lines: [
              [
                0,
                0,
                {
                  product_id: 56,
                  qty: 2,
                  state: state,
                  note: '',
                  attribute_value_ids: [],
                },
              ],
            ],
          },
        ],
      ],
    }
  }

  orm.call(
    'pos.order',
    'create_from_ui',
    [
      [
        {
          id: uid,
          data: order(uid),
          to_invoice: false,
        },
      ],
      true,
    ],
    {
      context: {
        lang: 'en_US',
        tz: 'Europe/Vienna',
        uid: 2,
        allowed_company_ids: [1],
      },
    },
  )
}
