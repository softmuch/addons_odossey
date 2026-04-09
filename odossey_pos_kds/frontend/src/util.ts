import {
  kitchenStates,
  OrderChangeLine,
  type KitchenState,
  type Order,
  OrderChange,
  PosCategory,
} from './models'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { lang } from './odoo'
import { messages } from './i18n'
import { createI18n } from 'vue-i18n'
import type { State } from './state'
import { sortChanges } from './sort'
import { useStore } from './store'

// CREDIT: https://stackoverflow.com/a/8076436/3140799
export function hashCode(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i)
    hash = (hash << 5) - hash + code
    hash = hash & hash // Convert to 32bit integer
  }
  return hash
}

let _seed = 1

// CREDIT: https://stackoverflow.com/a/19303725/3140799
export function random() {
  const x = Math.sin(_seed++) * 10000
  return x - Math.floor(x)
}

export function randInt(start: number = 0, end: number = 2): number {
  return start + Math.floor((end - start) * random())
}

// CREDIT: https://stackoverflow.com/a/19279428/3140799
export function replaceSearchParams(params: URLSearchParams) {
  const newurl = window.location.pathname + '?' + params.toString()
  window.history.replaceState(null, '', newurl)
}

export interface LineFilter {
  states?: KitchenState[]
  posCategIds: number[]
  floorIds: number[]
}

export function emptyFilter(): LineFilter {
  return {
    floorIds: [],
    posCategIds: [],
  }
}

export function intersection<T>(a: Set<T>, b: Set<T>): Set<T> {
  return new Set([...a].filter((x) => b.has(x)))
}

function categIdsWithDescendants(categIds: number[]): number[] {
  const store = useStore()

  return categIds
    .map((id) => store.db.categoryById(id))
    .filter(notEmpty)
    .reduce((acc, c) => {
      acc.push(c)
      acc.push(...c.descendants)
      return acc
    }, [] as PosCategory[])
    .map((c) => c.id)
}

export function applyFilter(lines: OrderChangeLine[], filter: LineFilter): OrderChangeLine[] {
  const filterCateg = new Set(categIdsWithDescendants(filter.posCategIds))
  return lines.filter((l) => {
    if (filter.floorIds.length > 0) {
      const order = l.change.order
      const table = order.pos.db.tableById(order.tableId)
      if (!table) {
        return false
      }
      const floorId = table.floor_id
      if (!filter.floorIds.includes(floorId)) {
        return false
      }
    }
    if (filter.states && !filter.states.includes(l.state)) {
      return false
    }
    if (filter.posCategIds.length > 0) {
      const categ = new Set(l.product.pos_categ_ids)
      if (intersection(categ, filterCateg).size == 0) {
        return false
      }
    }
    return true
  })
}

// CREDIT: https://stackoverflow.com/a/70468576/3140799
type KeyFn<T> = (item: T) => string | number | symbol
type GroupedBy<T, K extends Array<KeyFn<T>>> = K extends [
  infer K0 extends KeyFn<T>,
  ...infer KR extends Array<KeyFn<T>>,
]
  ? Record<ReturnType<K0>, GroupedBy<T, KR>>
  : T[]

// call signature
export function groupBy<T, K extends Array<KeyFn<T>>>(
  items: readonly T[],
  ...by: [...K]
): GroupedBy<T, K> {
  if (!by.length) {
    // @ts-expect-error Type 'T[]' is not assignable to type 'GroupedBy<T, K>'
    return [...items]
  }
  const [k0, ...kr] = by
  const topLevelGroups = {} as Record<string | number | symbol, T[]>
  for (const item of items) {
    const k = k0(item)
    if (!topLevelGroups[k]) {
      topLevelGroups[k] = []
    }
    topLevelGroups[k].push(item)
  }
  // @ts-expect-error Type '{ [k: string]: T[]; }' is not assignable to type 'GroupedBy<T, K>'
  return Object.fromEntries(Object.entries(topLevelGroups).map(([k, v]) => [k, groupBy(v, ...kr)]))
}

export function mergeOrderLines(lines: OrderChangeLine[]): OrderChangeLine {
  if (lines.length == 0) {
    throw 'mergeOrderLines() empty lines array'
  }
  const line = Object.assign(new OrderChangeLine(lines[0]), { qty: 0 })
  line.refs = [...lines]
  line.refs.sort((a, b) => b.change.duration.milliseconds - a.change.duration.milliseconds)

  for (const l of line.refs) {
    line.qty += l.qty
    line.note = l.qty >= 0 ? l.note : line.note
    line.attribute_value_ids = l.attribute_value_ids
  }
  return line
}

export function idsOf(lines: OrderChangeLine[]): number[] {
  const ids = []
  const q = [...lines]
  while (q.length > 0) {
    const [line] = q.splice(0, 1)
    if (line.refs.length == 0) {
      ids.push(line.id)
    }
    q.push(...line.refs)
  }
  return ids
}

export function findOldestOrderLine(lines: OrderChangeLine[]): OrderChangeLine {
  if (lines.length == 0) {
    throw 'findOldestOrderLine() empty lines array'
  }
  let current = lines[0]
  for (const line of lines) {
    if (current.change.duration < line.change.duration) {
      current = line
    }
  }
  return current
}

export function containsNegative(lines: OrderChangeLine[]): boolean {
  return lines.find((l) => l.qty < 0) !== undefined
}

export function computeHash(change: OrderChange, merge: boolean): number {
  return hashCode(
    change.order.state +
      change.priority +
      merge +
      change.lines.map((l) => [l.id, l.note, l.product, l.qty, l.state].join(',')).join(';'),
  )
}

export function zero_pad(num: number, size: number) {
  let s = '' + num
  while (s.length < size) {
    s = '0' + s
  }
  return s
}

export function minutesToMillis(minutes: number = 1): number {
  return minutes * 60 * 1000
}

type P = Parameters<typeof createSSRApp>
export async function renderToHtml(component: P[0], props: P[1]): Promise<string> {
  const i18n = createI18n({
    legacy: false,
    locale: (await lang()).split('_')[0],
    fallbackLocale: 'en',
    messages,
  })

  const app = createSSRApp(component, props)
  app.use(i18n)
  return await renderToString(app)
}

export function parseHTML(html: string): HTMLElement {
  const el = document.createElement('div')
  el.innerHTML = html
  return el.children[0] as HTMLElement
}

// CREDIT: https://stackoverflow.com/a/46700791/3140799
export function notEmpty<TValue>(value: TValue | null | undefined): value is TValue {
  return value !== null && value !== undefined
}

export function limit(n: number, min: number, max: number): number {
  return Math.min(Math.max(parseInt(n as any), min), max)
}

export function splitChanges(orders: Order[], state: State): Record<KitchenState, OrderChange[]> {
  // create map order changes to seperate changes by state
  const result: Record<string, OrderChange[]> = Object.fromEntries(
    kitchenStates.map((state: KitchenState) => [state, []]),
  )

  const lineByLineId: Record<number, OrderChangeLine> = {}
  for (const order of orders) {
    for (const change of order.changes) {
      for (const line of change.lines) {
        lineByLineId[line.line?.id ?? -1] = line
      }
    }
  }

  // assign refunds to the original order
  const REFUND_SEQ = -2
  const refundsByOrderId: Record<number, OrderChange[]> = {}
  for (const order of orders) {
    for (const change of order.changes) {
      const refundLines = change.lines.filter(
        (line) =>
          typeof line.line?.refunded_orderline_id === 'number' &&
          lineByLineId[line.line?.refunded_orderline_id || -1],
      )
      if (refundLines.length > 0) {
        const targetChange = lineByLineId[refundLines[0].line?.refunded_orderline_id || -1]?.change
        const targetOrder = targetChange.order
        const refundChange = new OrderChange({
          ...change,
          lines: [],
          sequenceNumber: REFUND_SEQ,
          order: targetOrder,
        })
        refundChange.lines = refundLines.map((line) => {
          const targetLine = lineByLineId[line.line?.refunded_orderline_id || -1]
          return new OrderChangeLine({
            ...line,
            line_uuid: targetLine.line_uuid,
            change: refundChange,
          })
        })
        if (!refundsByOrderId[targetOrder.id]) {
          refundsByOrderId[targetOrder.id] = []
        }
        refundsByOrderId[targetOrder.id].push(refundChange)
      }
    }
  }

  // process each order
  for (const order of orders) {
    // combine all order lines
    // and remove service lines
    const refundChanges = refundsByOrderId[order.id] ?? []
    const lines = [...order.changes, ...refundChanges]
      .reduce((acc, change) => {
        acc.push(...change.lines)
        return acc
      }, [] as OrderChangeLine[])
      .filter(
        (line) =>
          line.product.type !== 'service' && typeof line.line?.refunded_orderline_id !== 'number',
      )

    // group order lines by state and change id if not merged
    const grouped = groupBy(
      lines,
      (line) => {
        return state.merge.value ? line.state : line.state + ',' + line.change.id
      },
      (line) => line.product.id + line.attribute_value_ids.join(',') + line.line_uuid,
    )

    // create changes
    const changes = Object.entries(grouped).map(([, lineMap]) => {
      const groupedLines = Object.values(lineMap)
      const template = findOldestOrderLine(groupedLines.flat()).change
      const sequenceNumber = template.sequenceNumber == REFUND_SEQ ? 'R' : template.sequenceNumber
      const change = Object.assign(new OrderChange(template), {
        name: template.order.trackingNumber + (state.merge.value ? '' : '-' + sequenceNumber),
      })

      change.lines = []
      for (const lines of groupedLines) {
        // merge and filter lines
        const filtered = applyFilter(lines, state.filter.value)
        if (filtered.length == 0) {
          continue
        }
        change.lines.push(mergeOrderLines(filtered))
      }
      return change
    })

    // add non empty changes to kitchen state map
    for (const change of changes) {
      if (change.lines.length == 0) {
        continue
      }
      result[change.lines[0].state].push(change)
    }
  }

  // sort changes by duration descending
  for (const changes of Object.values(result)) {
    sortChanges(changes, state.orderBy.value)
  }

  return result
}

export enum OrderDevice {
  POS = 'pos',
  Kiosk = 'kiosk',
  Mobile = 'mobile',
}

export function getOrderDevice(posReference: string): OrderDevice {
  if (posReference.includes('Kiosk')) {
    return OrderDevice.Kiosk
  }
  if (posReference.includes('Self-Order')) {
    return OrderDevice.Mobile
  }
  return OrderDevice.POS
}

export function computeTrackingNumber(sessionId: number, sequence: number): string {
  const n = (sessionId % 10) * 100 + (sequence % 100)
  return zero_pad(n, 3)
}

export function parsePosReference(posReference: string) {
  const arr = posReference.split(' ')[1].split('-')
  return {
    sessionId: parseInt(arr[0]),
    configId: parseInt(arr[1]),
    sequence: parseInt(arr[2]),
  }
}

// CREDIT: https://github.com/odoo/odoo/blob/67a5213238ca95ea6cdab2c40943cc593b2308e5/addons/pos_self_order/static/src/app/models/order.js#L58
export function trackingNumberFromPosReference(posReference: string): string {
  const { sessionId, sequence } = parsePosReference(posReference)
  return computeTrackingNumber(sessionId, sequence)
}

export function hasAddress(change: OrderChange): boolean {
  const partner = change.order.partner()
  if (partner) {
    return !!partner.city || !!partner.street || !!partner.zip
  }
  return false
}

export function compareLines(a: OrderChangeLine, b: OrderChangeLine): number {
  if (a.comboId !== b.comboId) {
    return b.comboId - a.comboId
  }
  if (a.comboParentId !== b.comboParentId) {
    return a.comboParentId === false ? -1 : 1
  }

  return a.display_name.localeCompare(b.display_name)
}

// CREDIT: https://github.com/lukehorvat/computed-style-to-inline-style/blob/master/lib/index.ts
function _computedStyleToInlineStyle(
  element: HTMLElement | SVGElement,
  options?: {
    recursive?: boolean
    properties?: string[]
  },
): void {
  if (!element) {
    throw new Error('No element specified.')
  }

  if (options?.recursive) {
    Array.prototype.forEach.call(element.children, (child) => {
      _computedStyleToInlineStyle(child, options)
    })
  }

  const computedStyle = getComputedStyle(element, null)
  Array.prototype.forEach.call(options?.properties || computedStyle, (property) => {
    element.style[property] = computedStyle.getPropertyValue(property)
  })
}
/**
 * A function that iterates through the computed style properties of a HTML
 * element and redefines them as inline styles.
 * @returns a copy of the given element with inline styles
 */
export function computedStyleToInlineStyle(
  element: HTMLElement | SVGElement,
  options?: {
    recursive?: boolean
    properties?: string[]
  },
): HTMLElement {
  const clone = element.cloneNode(true) as HTMLElement
  // getComputedStyle only works if element is part of the document
  // SOURCE: https://stackoverflow.com/a/35432063/3140799
  document.body.appendChild(clone)
  _computedStyleToInlineStyle(clone, options)
  document.body.removeChild(clone)
  return clone
}
