import type { OrderChange } from './models'
import { zero_pad } from './util'

export const orderOptions = ['duration', 'name'] as const
export type OrderOption = (typeof orderOptions)[number]

// comparable name
function compName(name: string) {
  const [n, seq] = name.split('-')
  if (!seq) {
    return n
  }
  return n + zero_pad(parseInt(seq), 2)
}

export function sortChanges(changes: OrderChange[], orderBy: OrderOption): void {
  changes.sort((a, b) => {
    if (a.priority != b.priority) {
      return b.priority - a.priority
    }

    switch (orderBy) {
      case 'duration':
        return b.duration.milliseconds - a.duration.milliseconds
      case 'name':
        return compName(a.name).localeCompare(compName(b.name))
    }
  })
}
