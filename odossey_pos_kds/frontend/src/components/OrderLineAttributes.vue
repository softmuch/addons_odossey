<template>
  <span>
    <el-tag
      v-for="attr in attributes"
      :key="attr.id"
      class="font-semibold m-1 !border-0"
      :class="disabled.includes(attr.id) ? '!text-neutral-500' : '!text-neutral-800'"
      :color="attrColor(attr.id)"
      disable-transitions
      effect="dark"
      round
      @click.stop=""
      @click="() => onClick?.(attr.id)"
    >
      {{ attr.name }}
    </el-tag>
  </span>
</template>

<script setup lang="ts">
import { useStore } from '@/store'
import { notEmpty } from '@/util'
import { computed, type PropType } from 'vue'

const props = defineProps({
  ids: {
    type: Array as PropType<number[]>,
    default: () => [],
  },
  disabled: {
    type: Array as PropType<number[]>,
    default: () => [],
  },
  onClick: {
    type: Function as PropType<(id: number) => void>,
  },
})

const store = useStore()

const attributes = computed(() => {
  return props.ids.map((id) => store.db.attributeValueById(id)).filter(notEmpty)
})

function attrColor(id: number): any {
  if (props.disabled.includes(id)) {
    return 'rgb(235, 235, 235)'
  }
  const types = ['#67C23A', '#E6A23C', '#F56C6C', '#4DD0E1', '#D4E157', '#CE93D8']
  return types[id % types.length]
}
</script>
