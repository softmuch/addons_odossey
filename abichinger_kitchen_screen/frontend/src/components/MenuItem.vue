<template>
  <el-menu-item :index="state" @click="$emit('click')">
    <span class="font-semibold">{{ $t(`state.${state}`) }}</span>
    <span>
      <span class="ml-2 py-1 px-2 text-white font-bold rounded" :class="kStateProps[state].bg">
        {{ count }}
      </span>
    </span>
  </el-menu-item>
</template>

<script setup lang="ts">
import { kStateProps, type KitchenState } from '@/models'
import type { PropType } from 'vue'

defineProps({
  state: {
    type: String as PropType<KitchenState>,
    required: true,
  },
  count: {
    type: Number,
    default: 0,
  },
})
</script>
