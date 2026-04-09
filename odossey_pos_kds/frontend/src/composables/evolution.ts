import { ref, watch, type ComputedRef, type Ref } from 'vue'

interface Evolution<T> {
  at: number | (() => number)
  value: T
}
export function useEvolution<T>({
  initial,
  evolutions,
  interval,
}: {
  initial: T
  evolutions: ComputedRef<Evolution<T>[]>
  interval: Ref<number>
}) {
  const value = ref<T>(initial) as Ref<T>

  watch(
    interval,
    () => {
      const items = evolutions.value
      if (items.length == 0) {
        value.value = initial
        return
      }
      const now = new Date().getTime()
      const next = items
        .map((e) => (typeof e.at === 'number' ? e.at : e.at()))
        .findIndex((at) => at > now)
      if (next > 0) {
        value.value = items[next - 1].value
      } else if (next == -1) {
        value.value = items[items.length - 1].value
      } else {
        value.value = initial
      }
    },
    { immediate: true },
  )

  return value
}
