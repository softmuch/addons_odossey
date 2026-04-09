import { DateTime } from 'luxon'
import type { ShallowRef } from 'vue'
import type { PrinterService } from './print'
import { notEmpty } from './util'
import type { OrderlineGroupData } from './orderline_group'

type DomainTuple = [string, string, any]
export type Domain = DomainTuple[]

export type ProductType = 'consu' | 'service' | 'product' | 'combo'

export interface Product {
  id: number
  display_name: string
  pos_categ_ids: number[]
  ab_stock_out_of_stock?: boolean
  type: ProductType
  valid_product_template_attribute_line_ids: number[]
  ab_stock_disabled_attributes: number[]
}

// https://www.qualdesk.com/blog/2021/type-guard-for-string-union-types-typescript/
export const kitchenStates = ['cooking', 'ready', 'done', 'cancel'] as const
export type KitchenState = (typeof kitchenStates)[number]

export interface KitchenStateProps {
  border: string
  bg: string
}
export const kStateProps: Record<KitchenState, KitchenStateProps> = {
  cooking: {
    border: '!border-neutral-400',
    bg: '!bg-neutral-600/75',
  },
  ready: {
    border: '!border-sky-500',
    bg: '!bg-sky-600/75',
  },
  done: {
    border: '!border-green-500',
    bg: '!bg-green-600/75',
  },
  cancel: {
    border: '!border-red-500',
    bg: '!bg-red-500/75',
  },
}

export function isKitchenState(state: string): state is KitchenState {
  return kitchenStates.includes(state as KitchenState)
}

export class OrderChangeLine {
  change: OrderChange
  id: number
  product: Product
  qty: number
  state: KitchenState
  note: string
  display_name: string
  line_uuid: string = ''
  attribute_value_ids: number[]
  refs: OrderChangeLine[] = []

  constructor(vals: {
    change: OrderChange
    id: number
    product: Product
    qty: number
    state: KitchenState
    note: string
    display_name: string
    attribute_value_ids: number[]
    refs?: OrderChangeLine[]
    line_uuid: string
  }) {
    this.change = vals.change
    this.id = vals.id
    this.product = vals.product
    this.qty = vals.qty
    this.state = vals.state
    this.note = vals.note
    this.display_name = vals.display_name
    this.attribute_value_ids = vals.attribute_value_ids
    this.refs = vals.refs ?? this.refs
    this.line_uuid = vals.line_uuid
  }

  get line(): OrderLine | undefined {
    return this.change.order.orderlineByUUID(this.line_uuid)
  }

  get comboParentId(): number | false {
    return this.line?.combo_parent_id ?? false
  }

  get comboLineIds(): number[] {
    return this.line?.combo_line_ids ?? []
  }

  /**
   * Checks if the line is part of a combo
   * @returns the id of the pos.order.line
   */
  get comboId(): number {
    if (this.comboLineIds.length > 0 && this.comboParentId === false) {
      return this.line?.id ?? -1
    }
    return this.comboParentId === false ? -1 : this.comboParentId
  }
}
export class OrderChange {
  id: number
  name: string = ''
  order: Order
  createdAt: DateTime
  sequenceNumber: number
  lines: OrderChangeLine[] = []
  priority: number = 0

  constructor(vals: {
    id: number
    name?: string
    order: Order
    createdAt: DateTime
    sequenceNumber: number
    lines?: OrderChangeLine[]
    priority?: number
  }) {
    this.id = vals.id
    this.order = vals.order
    this.createdAt = vals.createdAt
    this.sequenceNumber = vals.sequenceNumber
    this.lines = vals.lines ?? this.lines
    this.name = vals.name ?? this.name
    this.priority = vals.priority ?? this.priority
  }

  get duration() {
    return DateTime.now().diff(this.createdAt)
  }
}

export class Order {
  pos: PosStore
  id!: number
  name!: string
  uid!: string
  changes!: OrderChange[]
  trackingNumber!: string
  configId!: number
  state!: string
  userId!: number
  lines!: OrderLine[]
  tableId: number | false = false
  employeeId: false | number = false
  partner_id: number | false = false
  ab_service_type?: ServiceType = 'takeaway'
  takeaway?: boolean = false

  lineIndexUUID: Record<string, OrderLine>
  lineIndex: Record<number, OrderLine>

  constructor(
    pos: PosStore,
    vals: {
      id: number
      name: string
      uid: string
      changes: OrderChange[]
      trackingNumber: string
      configId: number
      state: string
      userId: number
      lines: OrderLine[]
    } & Partial<Order>,
  ) {
    this.pos = pos
    Object.assign(this, vals)

    this.lineIndexUUID = Object.fromEntries(this.lines.map((l) => [l.uuid, l]))
    this.lineIndex = Object.fromEntries(this.lines.map((l) => [l.id, l]))
  }

  user(): User | undefined {
    const employeeId = this.employeeId !== false ? this.employeeId : -1
    const employee = this.pos.db.employeeById(employeeId)
    if (employee) {
      return {
        id: employee.user_id,
        name: employee.name,
        employee_id: employee.id,
      }
    }
    return this.pos.db.userById(this.userId)
  }
  config(): PosConfig | undefined {
    return this.pos.db.configById(this.configId)
  }
  partner(): ResPartner | undefined {
    const partnerId = this.partner_id !== false ? this.partner_id : -1
    return this.pos.db.partnerById(partnerId)
  }
  orderlineByUUID(uuid: string): OrderLine | undefined {
    return this.lineIndexUUID[uuid]
  }
  orderlineByID(id: number): OrderLine | undefined {
    return this.lineIndex[id]
  }
}

export type ServiceType = 'eat-in' | 'takeaway' | 'delivery'

export interface OrderLine {
  id: number
  uuid: string
  combo_line_ids: number[]
  combo_parent_id: number | false
  refunded_qty: number
  refunded_orderline_id: number | false
}
export interface PosCategoryData {
  id: number
  parent_id: number | false
  child_ids: number[]
  name: string
}

export class PosCategory {
  categoryById: (id: number) => PosCategory | undefined
  data: PosCategoryData

  constructor(data: PosCategoryData, categoryById: (id: number) => PosCategory | undefined) {
    this.data = data
    this.categoryById = categoryById
  }

  get parent(): PosCategory | undefined {
    if (this.data.parent_id === false) {
      return
    }
    return this.categoryById(this.data.parent_id)
  }

  get children(): PosCategory[] {
    return this.data.child_ids.map((id) => this.categoryById(id)).filter(notEmpty)
  }

  get descendants(): PosCategory[] {
    const children = this.children
    return [
      ...children,
      ...children.reduce((acc, child) => {
        acc.push(...child.descendants)
        return acc
      }, [] as PosCategory[]),
    ]
  }

  get id() {
    return this.data.id
  }

  get name() {
    return this.data.name
  }

  get fullName(): string {
    const parent = this.parent
    return (parent ? parent.fullName + '/' : '') + this.name
  }

  toString(): string {
    return this.fullName
  }
}

export interface Floor {
  id: number
  name: string
}

export interface Table {
  id: number
  table_number: number
  floor_id: number
}

// TODO: make all return types union undefined
export interface PosDB {
  categoryById(id: number): PosCategory
  productById(id: number): Product
  floorById(id: number): Floor | undefined
  tableById(id: number | false): Table | undefined
  userById(id: number): User | undefined
  attributeById(id: number): Attribute | undefined
  attributeValueById(id: number): AttributeValue | undefined
  employeeById(id: number): Employee | undefined
  configById(id: number): PosConfig | undefined
  partnerById(id: number): ResPartner | undefined
  orderlineById(id: number): OrderLine | undefined
}

export interface PosConfig {
  id: number
  name: string
  epson_printer_ip: string | false
}
export interface PosStore {
  configs: PosConfig[]
  orders: Order[]
  orderlines: OrderLine[]
  ready: ShallowRef<boolean>
  updated: ShallowRef<number>
  floors: Floor[]
  categories: PosCategory[]
  tables: Table[]
  products: Product[]
  users: User[]
  employees: Employee[]
  attributes: Attribute[]
  attrValues: AttributeValue[]
  partners: ResPartner[]
  db: PosDB
  print: PrinterService
}

export interface User {
  id: number
  name: string
  lang?: string
  employee_id: number
}

export interface Employee {
  id: number
  name: string
  user_id: number
}

export interface ResPartner {
  id: number
  name: string
  phone?: string
  email?: string
  street?: string
  zip?: string
  city?: string
  comment?: string
}

export interface Module {
  display_name: string
  installed_version: string
  latest_version: string
}

export interface Attribute {
  id: number
  display_name: string
  product_template_value_ids: number[]
}

export interface AttributeValue {
  id: number
  name: string
}

export interface KitchenScreen {
  id: number
  name: string
  config_ids: number[] | false
  channel: string
  wait_time: number
  delivery_time?: number
  orderline_groups: OrderlineGroupData[]
}
