import type { OrderChangeLine } from './models'
import { groupBy } from './util'

export interface OrderlineGroupData {
  id: number
  sequence: number
  name: string
  category_ids: number[]
  attribute_ids: number[]
}

export class OrderlineGroup {
  data: OrderlineGroupData
  _attributeIds: Set<number>
  _categoryIds: Set<number>

  constructor(data: OrderlineGroupData) {
    this.data = data
    this._attributeIds = new Set(data.attribute_ids)
    this._categoryIds = new Set(data.category_ids)
  }

  get id() {
    return this.data.id
  }

  get name() {
    return this.data.name
  }

  get sequence() {
    return this.data.sequence
  }

  matchByAttribute(line: OrderChangeLine) {
    return line.attribute_value_ids.find((aid) => this._attributeIds.has(aid)) !== undefined
  }

  matchByCategory(line: OrderChangeLine) {
    return line.product.pos_categ_ids.find((pid) => this._categoryIds.has(pid)) !== undefined
  }
}

interface UseOrderlineGroups {
  groups: OrderlineGroup[]
  findGroupByLine: (line: OrderChangeLine) => OrderlineGroup | undefined
  groupOrderlines: (
    lines: OrderChangeLine[],
  ) => { group: OrderlineGroup | undefined; lines: OrderChangeLine[] }[]
}

let cache: UseOrderlineGroups | undefined = undefined

export function useOrderlineGroups(): UseOrderlineGroups {
  if (cache) {
    return cache
  }
  const kitchen = import.meta.env.DEV
    ? {
        orderline_groups: [],
      }
    : odoo.kitchen
  const groups = kitchen.orderline_groups.map((data) => new OrderlineGroup(data))
  const groupIndex = Object.fromEntries(groups.map((g) => [g.id, g]))

  function findGroupByLine(line: OrderChangeLine) {
    return (
      groups.find((group) => group.matchByAttribute(line)) ||
      groups.find((group) => group.matchByCategory(line))
    )
  }

  function groupOrderlines(sortedLines: OrderChangeLine[]) {
    const comboGroup: Record<number, string> = {}
    const lineMap = groupBy(sortedLines, (l) => {
      const gid = findGroupByLine(l)?.id + ''

      if (l.comboId !== -1 && l.comboLineIds.length > 0) {
        comboGroup[l.comboId] = gid
      }

      return comboGroup[l.comboId] ?? gid
    })

    return Object.entries(lineMap)
      .map(([gid, lines]) => {
        return { group: groupIndex[gid], lines }
      })
      .sort((a, b) => {
        if (!a.group) {
          return 1
        }
        if (!b.group) {
          return -1
        }

        return a.group.sequence - b.group.sequence
      })
  }

  cache = {
    groups,
    findGroupByLine,
    groupOrderlines,
  }
  return cache
}
