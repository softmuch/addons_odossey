import { shallowRef } from 'vue'
import {
  PosCategory,
  type Floor,
  type PosStore,
  type Product,
  type Table,
  type PosDB,
  type PosConfig,
  type User,
  type Attribute,
  type AttributeValue,
  type Employee,
  type KitchenScreen,
  type ResPartner,
  type OrderLine,
  type ServiceType,
  Order,
  OrderChange,
  OrderChangeLine,
  type PosCategoryData,
} from './models'
import { useClient } from './odoo'
import * as odooTS from 'odoo-typescript/18.0'
import { DateTime } from 'luxon'
import { mockPosStore } from './dev'
import {
  computeTrackingNumber,
  getOrderDevice,
  groupBy,
  mergeOrderLines,
  notEmpty,
  OrderDevice,
  trackingNumberFromPosReference,
  zero_pad,
} from './util'
import { PrinterService, type EpsonPrinterConfig, type PrinterConfig } from './print'
import { i18n } from './i18n'
import { logger } from './log'

interface PosData {
  'pos.config': PosConfig[]
  'product.product': Product[]
  'pos.category': PosCategoryData[]
  'pos.order': any[]
  'pos.order.line': OrderLine[]
  'ab_pos.order.change': any[]
  'ab_pos.order.change.line': any[]
  'restaurant.floor': Floor[]
  'restaurant.table': Table[]
  'hr.employee'?: Employee[]
  'res.users': User[]
  'pos.printer': PrinterConfig[]
  'product.template.attribute.line': Attribute[]
  'product.template.attribute.value': AttributeValue[]
  'res.partner': ResPartner[]
}

function unknownProduct(): Product {
  const { t } = i18n()
  return {
    id: -1,
    display_name: t('unknown_product'),
    pos_categ_ids: [],
    ab_stock_out_of_stock: undefined,
    type: 'product',
    valid_product_template_attribute_line_ids: [],
    ab_stock_disabled_attributes: [],
  }
}
export class Database implements PosDB {
  productIndex: Record<number, Product>
  categoryIndex: Record<number, PosCategory>
  floorIndex: Record<number, Floor>
  tableIndex: Record<number, Table>
  userIndex: Record<number, User>
  employeeIndex: Record<number, Employee>
  attributeIndex: Record<number, Attribute>
  attributeValueIndex: Record<number, AttributeValue>
  configIndex: Record<number, PosConfig>
  partnerIndex: Record<number, ResPartner>
  orderlineIndex: Record<number, OrderLine>

  constructor({
    products,
    floors,
    categories,
    tables,
    users,
    attributes,
    attrValues,
    configs,
    employees,
    partners,
    orderlines,
  }: PosStore) {
    this.configIndex = Object.fromEntries(configs.map((c) => [c.id, c]))
    this.productIndex = Object.fromEntries(products.map((p) => [p.id, p]))
    this.categoryIndex = Object.fromEntries(categories.map((c) => [c.id, c]))
    this.floorIndex = Object.fromEntries(floors.map((f) => [f.id, f]))
    this.tableIndex = Object.fromEntries(tables.map((t) => [t.id, t]))
    this.userIndex = Object.fromEntries(users.map((u) => [u.id, u]))
    this.employeeIndex = Object.fromEntries(employees.map((e) => [e.id, e]))
    this.attributeIndex = Object.fromEntries(attributes.map((a) => [a.id, a]))
    this.attributeValueIndex = Object.fromEntries(attrValues.map((a) => [a.id, a]))
    this.partnerIndex = Object.fromEntries(partners.map((p) => [p.id, p]))
    this.orderlineIndex = Object.fromEntries(orderlines.map((l) => [l.id, l]))
  }

  attributeById(id: number): Attribute | undefined {
    return this.attributeIndex[id]
  }
  attributeValueById(id: number): AttributeValue | undefined {
    return this.attributeValueIndex[id]
  }

  userById(id: number): User | undefined {
    return this.userIndex[id]
  }

  employeeById(id: number): Employee | undefined {
    return this.employeeIndex[id]
  }

  floorById(id: number): Floor {
    return this.floorIndex[id]
  }

  tableById(id: number | false): Table | undefined {
    if (id === false) {
      return
    }
    return this.tableIndex[id]
  }

  categoryById(id: number): PosCategory {
    return this.categoryIndex[id]
  }

  productById(id: number): Product {
    return this.productIndex[id] ?? unknownProduct()
  }

  configById(id: number): PosConfig | undefined {
    return this.configIndex[id]
  }

  partnerById(id: number): ResPartner | undefined {
    return this.partnerIndex[id]
  }

  orderlineById(id: number): OrderLine | undefined {
    return this.orderlineIndex[id]
  }
}

interface SyncOrdersMessage {
  order_ids: number[]
  kitchen_id: number
}

class Store implements PosStore {
  orders: Order[] = []
  orderlines: OrderLine[] = []
  ready = shallowRef(false)
  updated = shallowRef(0)
  floors: Floor[] = []
  categories: PosCategory[] = []
  tables: Table[] = []
  products: Product[] = []
  users: User[] = []
  employees: Employee[] = []
  attributes: Attribute[] = []
  attrValues: AttributeValue[] = []
  partners: ResPartner[] = []
  db!: Database
  data!: PosData
  configs!: PosConfig[]
  print!: PrinterService

  constructor() {
    this.setup()
  }

  async setup(): Promise<void> {
    const data = await this.fetchAll()
    console.debug(data)
    this.data = data
    this.configs = data['pos.config']
    this.products = data['product.product']
    this.categories = data['pos.category'].map(
      (c: PosCategoryData) =>
        new PosCategory(c, (id) => {
          return this.db.categoryById(id)
        }),
    )
    this.floors = data['restaurant.floor']
    this.users = data['res.users']
    this.employees = data['hr.employee'] ?? []
    this.attributes = data['product.template.attribute.line']
    this.attrValues = data['product.template.attribute.value']
    this.tables = data['restaurant.table']
    this.partners = data['res.partner']
    this.orderlines = data['pos.order.line']

    this.db = new Database(this)
    this.orders = this.parseOrders(data)
    console.debug('orders', this.orders)

    this.setupBus()
    const epos: EpsonPrinterConfig[] = this.configs
      .filter((c) => c.epson_printer_ip)
      .map((c) => {
        return {
          id: -1,
          name: `ePOS Printer ${c.name}`, //TODO i18n,
          printer_type: 'epson_epos',
          proxy_ip: false,
          epson_printer_ip: c.epson_printer_ip as string,
        }
      })

    // .epson_printer_ip
    //   ? [
    //       {
    //         id: -1,
    //         name: 'ePOS Printer', //TODO i18n,
    //         printer_type: 'epson_epos',
    //         proxy_ip: false,
    //         epson_printer_ip: this.config.epson_printer_ip,
    //       },
    //     ]
    //   : []
    this.print = new PrinterService([
      ...epos,
      ...data['pos.printer'],
      { id: -2, name: 'Local Printer', printer_type: 'local', proxy_ip: false },
    ])
    this.ready.value = true
  }

  parseOrders(data: PosData) {
    const orders: Order[] = data['pos.order'].map((o) => {
      return this.parseOrder(o)
    })

    this._parseChanges(data, Object.fromEntries(orders.map((o) => [o.id, o])))

    return orders
  }

  _parseChanges(data: PosData, ordersById: Record<number, Order>) {
    const changes: OrderChange[] = data['ab_pos.order.change'].map((c) => {
      const order = ordersById[c.order_id]
      const change = this.parseChange(c, order)
      order.changes.push(change)
      return change
    })

    this._parseLines(data, Object.fromEntries(changes.map((c) => [c.id, c])))
  }

  _parseLines(data: PosData, changesById: Record<number, OrderChange>) {
    for (const l of data['ab_pos.order.change.line']) {
      const change = changesById[l.change_id]
      change.lines.push(this.parseLine(l, change))
    }
  }

  parseOrder(json: any): Order {
    const device = getOrderDevice(json.pos_reference)
    const trackingNumber =
      device == OrderDevice.POS
        ? json.tracking_number
        : trackingNumberFromPosReference(json.pos_reference)
    const prefix = device == OrderDevice.POS ? '' : 'S'

    return new Order(this, {
      id: json.id,
      name: json.name,
      pos: this,
      uid: json.pos_reference,
      trackingNumber: prefix + trackingNumber,
      tableId: json.table_id,
      state: json.state,
      changes: [],
      userId: json.user_id,
      employeeId: json.employee_id,
      configId: json.config_id,
      partner_id: json.partner_id,
      ab_service_type: json.ab_service_type,
      takeaway: json.takeaway,
      lines: json.lines.map((id: number) => this.db.orderlineById(id)).filter(notEmpty),
    })
  }

  parseChange(json: any, order: Order): OrderChange {
    const { deserializeDateTime } = odooTS.require('@web/core/l10n/dates')
    const createdAt: DateTime = deserializeDateTime(json.created_at)

    const change = new OrderChange({
      id: json.id,
      name: '',
      order: order,
      createdAt: createdAt,
      sequenceNumber: json.sequence_number,
      lines: [] as OrderChangeLine[],
      priority: json.priority,
    })

    return change
  }

  parseLine(json: any, change: OrderChange): OrderChangeLine {
    const product = this.db.productById(json.product_id)
    const line = new OrderChangeLine({
      change: change,
      id: json.id,
      product: product,
      display_name: product.display_name,
      qty: json.qty,
      state: json.state,
      note: json.note,
      attribute_value_ids: json.attribute_value_ids || [],
      refs: [],
      line_uuid: json.line_uuid,
    })
    return line
  }

  // CREDIT: addons/point_of_sale/static/src/app/bus/pos_bus_service.js
  async setupBus(): Promise<void> {
    const { bus } = await useClient()
    bus.addChannel(odoo.kitchen.channel)
    bus.subscribe('SYNC_ORDERS', this.syncOrders.bind(this))
  }

  async syncOrders(message: SyncOrdersMessage) {
    logger?.debug('SYNC ORDERS', message)

    if (message.kitchen_id !== odoo.kitchen.id) {
      return
    }

    const orderData = await this.getOrdersById(message.order_ids)

    const partners = orderData['res.partner'] ?? []
    this.updatePartners(partners)

    const orderlines = orderData['pos.order.line'] ?? []
    this.updateOrderlines(orderlines)

    const orders = this.parseOrders(orderData)
    console.log(orders)
    this.updateOrders(orders)
  }

  updatePartners(partners: ResPartner[]) {
    for (const p of partners) {
      if (this.db.partnerById(p.id) === undefined) {
        this.partners.push(p)
      }
      this.db.partnerIndex[p.id] = p
    }
  }

  updateOrderlines(lines: OrderLine[]) {
    for (const l of lines) {
      if (this.db.orderlineById(l.id) === undefined) {
        this.orderlines.push(l)
      }
      this.db.orderlineIndex[l.id] = l
    }
  }

  updateOrders(orders: Order[]) {
    const orderToUpdate = new Set(orders.map((o) => o.id))
    this.orders = [...this.orders.filter((o) => !orderToUpdate.has(o.id)), ...orders]
    this.sortOrders()
    this.updated.value++
  }

  sortOrders() {
    this.orders.sort((a, b) => (a.name > b.name ? 1 : -1))
  }

  async getOrdersById(orderIds: number[]): Promise<any> {
    const { orm } = await useClient()
    const domain = [['id', 'in', orderIds]]
    return orm.call('ab_pos.kitchen_screen', 'load_orders', [odoo.kitchen.id, domain])
  }

  async fetchAll(): Promise<PosData> {
    const { orm } = await useClient()
    return orm.call('ab_pos.kitchen_screen', 'load_data', [[odoo.kitchen.id]]) as Promise<PosData>
  }
}

let _store: PosStore | null = null

export function useStore(mode?: string): PosStore {
  if (_store === null) {
    if (import.meta.env.DEV || __DEMO__ || mode == 'development') {
      globalThis.odoo = {
        kitchen: {
          id: 2,
          name: 'Dev Kitchen',
          config_ids: [1, 2, 3],
          channel: '',
          wait_time: 5,
          orderline_groups: [],
        },
        ab_modules: {
          abichinger_kitchen_screen: {
            display_name: 'POS Kitchen Screen',
            installed_version: 'dev',
            latest_version: '',
          },
        },
      }

      _store = mockPosStore()
    } else {
      _store = new Store()
    }
  }

  return _store
}

export function fullNameOfTable(table: Table) {
  const store = useStore()
  const floor = store.db.floorById(table.floor_id)
  if (floor) {
    return floor.name + '/' + table.table_number
  }
  return table.table_number + ''
}
