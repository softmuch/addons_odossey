import type { OrderChange } from './models'
import { zero_pad } from './util'

export const orderOptions = ['duration', 'name'] as const
export type OrderOption = (typeof orderOptions)[number]

export const stageSortOptions = ['duration_desc', 'duration_asc'] as const
export type StageSortOption = (typeof stageSortOptions)[number]

export function isStageSortOption(value: string): value is StageSortOption {
  return stageSortOptions.includes(value as StageSortOption)
}

// comparable name
function compName(name: string) {
  const [n, seq] = name.split('-')
  if (!seq) {
    return n
  }
  return n + zero_pad(parseInt(seq), 2)
}

export function sortChanges(changes: OrderChange[], orderBy: OrderOption | StageSortOption): void {
  changes.sort((a, b) => {
    if (a.priority != b.priority) {
      return b.priority - a.priority
    }

    switch (orderBy) {
      case 'duration':
      case 'duration_desc':
        return b.duration.milliseconds - a.duration.milliseconds
      case 'duration_asc':
        return a.duration.milliseconds - b.duration.milliseconds
      case 'name':
        return compName(a.name).localeCompare(compName(b.name))
    }
  })
}
