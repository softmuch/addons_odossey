<template>
  <el-checkbox-group
    :model-value="modelValue"
    @update:model-value="$emit('update:model-value', $event)"
  >
    <el-checkbox v-for="filter in filters" :key="filter.value" :value="filter.value">
      {{ filter.text }}
    </el-checkbox>
  </el-checkbox-group>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'

interface Filter {
  text: string
  value: any
}

defineEmits(['update:model-value'])

defineProps({
  modelValue: {
    type: Array as PropType<any[]>,
  },
  filters: {
    type: Array as PropType<Filter[]>,
    required: true,
  },
})
</script>
