import { mockPosStore, newLine } from '@/dev'
import type { OrderChangeLine } from '@/models'
import { groupBy, idsOf } from '@/util'
import { describe, expect, it } from 'vitest'

describe('util', () => {
  it('idsOf', async () => {
    const store = mockPosStore()
    const lines: OrderChangeLine[] = [
      newLine(store, { id: 0 }),
      newLine(store, { id: 1 }),
      newLine(store, { id: 2 }),
    ]

    expect(idsOf(lines.slice(0, 1)).sort()).toEqual([0].sort())
    expect(idsOf(lines).sort()).toEqual([0, 1, 2].sort())

    const l1 = newLine(store, { refs: [lines[0], lines[1]] })
    expect(idsOf([l1]).sort()).toEqual([0, 1].sort())

    const l2 = newLine(store, { refs: [l1, lines[2]] })
    expect(idsOf([l2]).sort()).toEqual([0, 1, 2].sort())
  })

  it('groupBy', async () => {
    const items = [
      { str: 'a', num: 1, bool: true },
      { str: 'a', num: 1, bool: false },
      { str: 'a', num: 2, bool: true },
    ]

    const grouped = groupBy(
      items,
      (item) => item.str,
      (item) => item.num,
    )

    expect(Object.keys(grouped)).toEqual(['a'])

    const groupA = grouped['a']
    expect(Object.keys(groupA).sort()).toEqual(['1', '2'])
  })
})
