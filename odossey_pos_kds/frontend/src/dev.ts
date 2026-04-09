import { DateTime, Duration } from 'luxon'
import {
  Order,
  type Attribute,
  type AttributeValue,
  type Floor,
  type KitchenState,
  OrderChange,
  OrderChangeLine,
  PosCategory,
  type PosStore,
  type Product,
  type ResPartner,
  type Table,
  type User,
  type PosCategoryData,
} from './models'
import { randInt, random, zero_pad } from './util'
import type { Client } from './odoo'
import { Database } from './store'
import { shallowRef } from 'vue'
import { PrinterService } from './print'
import { useState } from './state'

type PackageName = '@web/core/l10n/translation'

export function mockRequire<T extends PackageName>(name: T): any {
  switch (name) {
    case '@web/core/l10n/translation':
      return { _t: (msgid: string) => msgid }
  }
}

let _client: Client
export function mockClient(): Client {
  if (!_client) {
    _client = {
      env: {},
      // @ts-expect-error is missing the following properties
      bus: { ...new EventTarget(), addChannel: async () => {} },
      orm: mockORM(),
      user: { name: 'Admin', id: 0, lang: 'en', employee_id: 0 },
    }
  }
  return _client
}

function mockORM(): any {
  return {
    // @ts-ignore eslint-disable-next-line @typescript-eslint/no-unused-vars
    async searchRead(model, domain, fields, kwargs) {
      return []
    },
    // @ts-ignore eslint-disable-next-line @typescript-eslint/no-unused-vars
    async write(model, ids, data, kwargs) {
      return true
    },
    // @ts-ignore eslint-disable-next-line @typescript-eslint/no-unused-vars
    async call(model, method, args, kwargs) {},
  }
}

let _id = 0

function nextId() {
  return _id++
}

const categories: PosCategoryData[] = [
  { id: 0, name: 'Root', parent_id: false, child_ids: [1, 2] },
  { id: 2, name: 'Drinks', parent_id: false, child_ids: [] },
  { id: 1, name: 'Food', parent_id: false, child_ids: [] },
]

const attributeValues: AttributeValue[] = [
  { id: 1, name: 'Lemon' },
  { id: 2, name: 'Peach' },
  { id: 3, name: 'Lipton' },
  { id: 4, name: 'Rauch' },
  { id: 5, name: 'Normal' },
  { id: 6, name: 'Large' },
]

const attributes: Attribute[] = [
  {
    id: nextId(),
    display_name: 'Flavor',
    product_template_value_ids: [1, 2],
  },
  {
    id: nextId(),
    display_name: 'Brand',
    product_template_value_ids: [3, 4],
  },
  {
    id: nextId(),
    display_name: 'Size',
    product_template_value_ids: [5, 6],
  },
]

const products: Product[] = [
  {
    id: nextId(),
    display_name: 'Cheese Burger',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Bacon Burger',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Ice Tea',
    pos_categ_ids: [2],
    type: 'consu',
    valid_product_template_attribute_line_ids: attributes.map((a) => a.id),
    ab_stock_disabled_attributes: [attributeValues[0].id],
  },
  {
    id: nextId(),
    display_name: 'Fanta',
    pos_categ_ids: [2],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Coca Cola',
    pos_categ_ids: [2],
    type: 'consu',
    valid_product_template_attribute_line_ids: [attributes[2].id],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Water',
    pos_categ_ids: [],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Espresso',
    pos_categ_ids: [2],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Club Sandwich',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Margherita',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Kebap',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
  {
    id: nextId(),
    display_name: 'Pasta Bolognese',
    pos_categ_ids: [1],
    type: 'consu',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  },
]

const floors: Floor[] = [
  { id: 1, name: 'Main' },
  { id: 2, name: 'Patio' },
]

const tables: Table[] = [
  { id: 0, table_number: 1, floor_id: 1 },
  { id: 1, table_number: 2, floor_id: 1 },
  { id: 2, table_number: 1, floor_id: 2 },
  { id: 3, table_number: 2, floor_id: 2 },
]

const users: User[] = [
  { id: 0, name: 'John Doe', employee_id: 0 },
  { id: 1, name: 'Jane Smith', employee_id: 1 },
  { id: 2, name: 'Russell Sprout', employee_id: 2 },
  { id: 3, name: 'Melisa Haynes', employee_id: 3 },
]

const partners: ResPartner[] = [
  { id: 0, name: 'Joe Willis', phone: '+1-1234-567' },
  {
    id: 1,
    name: 'Clara Marilag',
    phone: '+1-1234-567',
    email: 'clara.marilag@gmai.com',
    street: '1856 Weekley Street',
    zip: 'TX 78258',
    city: 'San Antonio',
  },
]

function generateLine(
  change: OrderChange,
  product: Product,
  state: KitchenState = 'cooking',
): OrderChangeLine {
  const line = new OrderChangeLine({
    change: change,
    id: nextId(),
    product: product,
    display_name: product.display_name,
    qty: randInt(1, 5) * (random() > 0.8 ? -1 : 1),
    note: random() > 0.8 ? 'Note' : '',
    attribute_value_ids: [],
    line_uuid: '',
    refs: [],
    state: state,
  })
  return line
}

function generateChange(
  order: Order,
  state: KitchenState,
  sequence_number: number,
  duration: Duration,
): OrderChange {
  const change: OrderChange = new OrderChange({
    id: nextId(),
    name: order.trackingNumber + '-' + sequence_number,
    order: order,
    createdAt: DateTime.now().minus(duration),
    sequenceNumber: sequence_number,
    lines: [],
  })

  const items = [...products]
  const nLines = randInt(1, 6)
  for (let i = 0; i < nLines; i++) {
    const itemIndex = randInt(0, items.length)
    const [item] = items.splice(itemIndex, 1)
    const line = generateLine(change, item, state)
    change.lines.push(line)
  }
  return change
}

function randDuration(): Duration {
  const millis = randInt(30, 600) * 1000
  return Duration.fromMillis(millis)
}

export function generateOrder(pos: PosStore, state: KitchenState, sequence_number: number): Order {
  const session_id = 3
  const trackingNumber = session_id * 100 + sequence_number

  const order = new Order(pos, {
    id: nextId(),
    name: '',
    state: random() > 0.8 ? 'paid' : 'draft',
    uid: zero_pad(session_id, 5) + '-001-' + zero_pad(sequence_number, 4),
    trackingNumber: trackingNumber + '',
    changes: [],
    tableId: tables[randInt(0, tables.length)].id,
    userId: users[randInt(0, users.length)].id,
    employeeId: false,
    configId: 0,
    partner_id: false,
    lines: [],
  })
  const nChanges = randInt(2, 6)
  let duration = randDuration()
  for (let i = 0; i < nChanges; i++) {
    const change = generateChange(order, state, nChanges - i, duration)
    order.changes.push(change)
    duration = duration.plus(randDuration())
  }
  return order
}

export function newOrder(store: DevStore, options: Partial<Order>): Order {
  const session_id = 3
  const sequence_number = (store.orders.length % 100) + 1
  const trackingNumber = session_id * 100 + sequence_number

  const order = new Order(store, {
    id: options.id ?? store.nextId(),
    name: '',
    state: options.state ?? 'draft',
    uid: options.uid ?? zero_pad(session_id, 5) + '-001-' + zero_pad(sequence_number, 4),
    trackingNumber: options.trackingNumber ?? trackingNumber + '',
    changes: options.changes ?? [],
    tableId: options.tableId ?? tables[0].id,
    userId: options.userId ?? users[0].id,
    employeeId: false as false | number,
    configId: 0,
    partner_id: options.partner_id ?? false,
    ab_service_type: options.ab_service_type,
    lines: options.lines ?? [],
  })

  store.orders.push(order)
  return order
}

export function newChange(store: DevStore, options: Partial<OrderChange>): OrderChange {
  const order = options.order ?? newOrder(store, {})
  const change = new OrderChange({
    id: options.id ?? store.nextId(),
    name: '',
    order: order,
    createdAt: options.duration
      ? DateTime.now().minus(options.duration)
      : options.createdAt ?? DateTime.now(),
    sequenceNumber: order.changes.length + 1,
    lines: options.lines ?? [],
    priority: options.priority ?? 0,
  })
  order.changes.push(change)
  return change
}

export function newLine(store: DevStore, options: Partial<OrderChangeLine>): OrderChangeLine {
  const change = options.change ?? newChange(store, {})
  const product = options.product ?? store.products[0]
  const line = new OrderChangeLine({
    id: options.id ?? store.nextId(),
    change: change,
    product: product,
    display_name: product.display_name,
    qty: options.qty ?? 1,
    state: options.state ?? 'cooking',
    note: options.note ?? '',
    attribute_value_ids: options.attribute_value_ids || [],
    refs: options.refs ?? [],
    line_uuid: options.line_uuid ?? '',
  })
  change.lines.push(line)
  return line
}

export interface DevStore extends PosStore {
  nextId(): number
}

export function mockPosStore(): DevStore {
  const pos: DevStore = {
    configs: [
      {
        id: 0,
        name: 'Restaurant',
        epson_printer_ip: false,
      },
    ],
    orders: [],
    orderlines: [],
    tables: tables,
    floors: floors,
    categories: [],
    products: products,
    attributes: attributes,
    attrValues: attributeValues,
    // @ts-ignore
    ready: shallowRef(true),
    // @ts-ignore
    updated: shallowRef(0),
    // @ts-ignore
    db: null,
    users: users,
    employees: [],
    partners: partners,
    nextId: nextId,
    print: new PrinterService([
      {
        id: -10,
        name: 'Dev Printer',
        printer_type: 'dev',
        proxy_ip: false,
      },
    ]),
  }

  pos.categories = categories.map(
    (c) =>
      new PosCategory(c, (id) => {
        return pos.db.categoryById(id)
      }),
  )

  pos.db = new Database(pos)
  const { debug } = useState()
  if (debug.value.includes('screenshot')) {
    screenshotData(pos)
  } else {
    generateDevData(pos, {
      cooking: 4,
      ready: 1,
      done: 2,
      cancel: 0,
    })

    const builder = new OrderBuilder(pos)
    const { p, m, av } = builder.helpers

    builder
      .order()
      .change({ duration: m(5) })
      .line({
        product: p('Ice'),
        qty: -1,
        attribute_value_ids: [av('Lipton')!, av('Peach')!, av('Large')!],
        note: 'invisible',
      })
      .change({ duration: m(1) })
      .line({
        product: p('Ice'),
        qty: 2,
        attribute_value_ids: [av('Lipton')!, av('Peach')!, av('Large')!],
        note: 'with ice',
      })
      .change({ duration: m(0) })
      .line({
        product: p('Ice'),
        qty: 0,
        attribute_value_ids: [av('Lipton')!, av('Peach')!, av('Large')!],
        note: '',
      })

    builder
      .order()
      .change({ duration: m(4.5) })
      .line({
        product: p('Cola'),
        qty: 1,
        note: 'S',
        line_uuid: 'A',
      })
      .change({ duration: m(4) })
      .line({
        product: p('Cola'),
        qty: 1,
        note: 'M',
        line_uuid: 'B',
      })

    builder
      .order({ partner_id: 0 })
      .change({
        duration: m(6),
      })
      .line({
        product: p('Cola'),
      })

    builder
      .order({ partner_id: 1, ab_service_type: 'delivery' })
      .change({
        duration: m(7),
      })
      .line({
        product: p('Fanta'),
      })
  }

  return pos
}

function generateDevData(pos: DevStore, count: Record<KitchenState, number>) {
  let seq = 1

  for (const key of Object.keys(count)) {
    const state = key as KitchenState
    for (let i = 0; i < count[state]; i++) {
      pos.orders.push(generateOrder(pos, state, seq++))
    }
  }

  //generate canceled order
  // const canceled = generateOrder(pos, 'cooking', seq++)
  // canceled.state = 'cancel'
  // pos.orders.push(canceled)
}

class OrderBuilder {
  pos: DevStore
  _order?: Order
  _change?: OrderChange
  helpers: {
    p(search: string): Product | undefined
    u(search: string): number | undefined
    m(minutes: number): Duration
    av(search: string): number | undefined
  }

  constructor(pos: DevStore) {
    this.pos = pos

    this.helpers = {
      p: (search: string) => products.find((p) => p.display_name.includes(search)),
      u: (search: string) => users.find((u) => u.name.includes(search))?.id,
      m: (minutes: number) => Duration.fromMillis(minutes * 60 * 1000),
      av: (search: string) => attributeValues.find((av) => av.name.includes(search))?.id,
    }
  }

  order(options: Partial<Order> = {}): OrderBuilder {
    this._order = newOrder(this.pos, options)
    return this
  }

  change(options: Partial<OrderChange> = {}): OrderBuilder {
    this._change = newChange(this.pos, { ...options, order: this._order })
    return this
  }

  line(options: Partial<OrderChangeLine> = {}): OrderBuilder {
    newLine(this.pos, { ...options, change: this._change })
    return this
  }
}

function screenshotData(pos: DevStore) {
  const builder = new OrderBuilder(pos)
  const { u, p, m, av } = builder.helpers

  builder
    .order({ userId: u('Mel'), tableId: tables[1].id })
    .change({ duration: m(23) })
    .line({ product: p('Fanta'), qty: 1 })
    .line({ product: p('Cola'), qty: 2, note: 'no ice' })
    .line({ product: p('Ice'), qty: 1, attribute_value_ids: [av('Peach')!] })
    .change({ duration: m(5) })
    .line({ product: p('Bacon'), qty: 3 })
    .line({ product: p('Chicken'), qty: 1 })

  builder
    .order()
    .change({ duration: m(17) })
    .line({ product: p('Cola'), qty: 1 })
    .line({ product: p('Ice'), qty: 2, attribute_value_ids: [av('Lemon')!] })
    // .line({ product: p('Margherita'), qty: 1, note: 'XL' })
    .line({ product: p('Pasta'), qty: 2 })
    .change({ duration: m(14) })
    .line({ product: p('Margherita'), qty: 1 })
    .line({ product: p('Pasta'), qty: -1 })

  builder
    .order()
    .change({ duration: m(3) })
    .line({ product: p('Club'), qty: 2 })
    .line({ product: p('Fanta'), qty: 1 })
    .line({ product: p('Espresso'), qty: 1 })

  generateDevData(pos, {
    cooking: 0,
    ready: 2,
    done: 3,
    cancel: 0,
  })
}
