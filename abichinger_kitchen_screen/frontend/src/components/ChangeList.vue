<template>
  <div class="!overflow-y-auto h-full" ref="list">
    <div class="flex flex-wrap md:m-4">
      <PosOrderChange
        v-for="change in visibleChanges"
        :key="computeHash(change, merge)"
        :change="change"
        class="w-80 max-w-xl grow m-2"
        :next-state="nextState"
        :prev-state="prevState"
        :is-dark="isDark"
      ></PosOrderChange>
      <div class="m-auto w-full h-52 flex items-center justify-center">
        <span v-if="canLoadMore()" class="text-neutral-500 text-lg">{{ $t('scroll_down') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import PosOrderChange from '@/components/OrderChange.vue'
import { type KitchenState, type OrderChange } from '@/models'
import { useState } from '@/state'
import { fullNameOfTable, useStore } from '@/store'
import { computeHash } from '@/util'
import { useInfiniteScroll } from '@vueuse/core'
import { ref, shallowRef, watch, type PropType, type Ref } from 'vue'

const props = defineProps({
  changes: {
    type: Object as PropType<OrderChange[]>,
    required: true,
  },
  nextState: {
    type: String as PropType<KitchenState | undefined>,
  },
  prevState: {
    type: String as PropType<KitchenState | undefined>,
  },
  search: {
    type: String,
    default: '',
  },
  isDark: {
    type: Boolean,
    default: false,
  },
})

const list = ref<HTMLElement | null>(null)
const visibleChanges: Ref<OrderChange[]> = ref([])
const limit = 15
const { merge } = useState()
const store = useStore()

const searchedChanges: Ref<OrderChange[]> = shallowRef([])
watch(
  [() => props.changes, () => props.search],
  () => {
    const search = props.search.toLowerCase()
    if (!search) {
      searchedChanges.value = props.changes
      return
    }
    searchedChanges.value = props.changes.filter((c) => {
      let str = ''

      const table = store.db.tableById(c.order.tableId)
      if (table) {
        str += fullNameOfTable(table)
      }
      str += c.order.user()?.name ?? ''
      str += c.order.config()?.name ?? ''
      str += c.lines.map((l) => l.display_name + l.note).join('')
      str += c.name
      return str.toLowerCase().includes(search)
    })
  },
  { immediate: true },
)

watch(
  searchedChanges,
  () => {
    visibleChanges.value = searchedChanges.value.slice(0, limit)
  },
  { immediate: true },
)

function canLoadMore() {
  return visibleChanges.value.length < searchedChanges.value.length
}

useInfiniteScroll(
  list,
  () => {
    // load more
    const length = visibleChanges.value.length
    visibleChanges.value.push(...searchedChanges.value.slice(length, length + limit))
  },
  {
    distance: 200,
    canLoadMore: canLoadMore,
  },
)
</script>