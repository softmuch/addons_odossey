<template>
  <el-card class="search">
    <div class="flex items-center">
      <el-autocomplete
        :model-value="modelValue"
        @update:model-value="$emit('update:modelValue', $event)"
        :fetch-suggestions="querySearch"
        class="grow"
        :suffix-icon="Search"
        ref="input"
        @keydown.esc="$emit('close')"
        clearable
      ></el-autocomplete>
      <el-button :icon="Close" text @click="$emit('close')"></el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { kitchenStates, type KitchenState, type Order, type OrderChange } from '@/models'
import { useState } from '@/state'
import { fullNameOfTable, useStore } from '@/store'
import { Close, Search } from '@element-plus/icons-vue'
import { onMounted, ref, type PropType, type Ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  changes: {
    type: Object as PropType<Record<KitchenState, OrderChange[]>>,
    default: () => ({}),
  },
})
defineEmits(['update:modelValue', 'close'])

const input: Ref<HTMLElement | null> = ref(null)

onMounted(() => {
  if (!input.value) {
    return
  }
  input.value.focus()
})

const querySearch = (queryString: string, cb: any) => {
  const { tables } = useStore()
  const { stages } = useState()
  const activeStates = new Set(kitchenStates.slice(0, stages.value))

  const orders = Object.keys(props.changes).reduce((orders, kState) => {
    if (!activeStates.has(kState as KitchenState)) {
      return orders
    }
    const changes = props.changes[kState as KitchenState]
    for (const change of changes) {
      orders.add(change.order)
    }

    return orders
  }, new Set<Order>())

  const activeTables = new Set(Array.from(orders).map((o) => o.tableId))
  const items = tables
    .filter((t) => activeTables.has(t.id))
    .map((t) => ({
      value: fullNameOfTable(t),
    }))
  const results = queryString
    ? items.filter(({ value }) => value.toLowerCase().includes(queryString.toLowerCase()))
    : items
  cb(results)
}
</script>

<style>
.search .el-card__body {
  padding: 8px;
}
</style>
