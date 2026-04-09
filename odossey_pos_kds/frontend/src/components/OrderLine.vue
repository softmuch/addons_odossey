<template>
  <el-tooltip
    :hide-after="50"
    placement="right-start"
    effect="light"
    :disabled="!merge"
    :persistent="false"
    :teleported="false"
  >
    <template #content>
      <OrderLineTimeline :line="line"></OrderLineTimeline>
    </template>
    <div class="rounded-md px-2 py-2" :class="classes">
      <div class="flex items-center">
        <el-checkbox @change="$emit('check')"></el-checkbox>
        <div class="ml-1 pl-1 grow">
          <!-- <span class="ml-1 pl-1" :class="{'border-l-4 border-red-600': line.qty < 0}"> -->
          {{ line.display_name ?? line.product.display_name }}

          <el-icon
            v-if="containsNegative(line.refs)"
            class="align-middle pb-1"
            :color="isDark ? '#E53935' : '#C62828'"
            size="20"
          >
            <Delete v-if="line.qty <= 0" />
            <EditPen v-else />
          </el-icon>
          <el-icon v-else-if="line.refs.length >= 2" class="align-middle pb-1" size="20">
            <EditPen />
          </el-icon>

          <OrderLineAttributes :ids="line.attribute_value_ids" />
          <el-alert
            v-if="line.note"
            :title="line.note"
            effect="dark"
            :closable="false"
            type="info"
            show-icon
            class="!mr-2 !my-1 !bg-sky-200 !text-sky-700 !rounded-md !w-auto"
          />
        </div>
        <span class="font-semibold">{{ line.qty }}</span>
      </div>
    </div>
  </el-tooltip>
</template>

<script setup lang="ts">
import type { OrderChangeLine } from '@/models'
import { useState } from '@/state'
import { containsNegative } from '@/util'
import { computed, type PropType } from 'vue'
import { Delete, EditPen } from '@element-plus/icons-vue'
import OrderLineTimeline from './OrderLineTimeline.vue'

const props = defineProps({
  line: {
    type: Object as PropType<OrderChangeLine>,
    required: true,
  },
  even: {
    type: Boolean,
    default: true,
  },
  isDark: {
    type: Boolean,
    default: false,
  },
})

const classes = computed(() => {
  const res = []
  if (props.even) {
    res.push('bg-neutral-500/15')
  }
  if (props.line.comboParentId !== false) {
    res.push('ml-4 rounded-l-none border-l-2')
    res.push(props.isDark ? 'border-neutral-300' : 'border-neutral-700')
  }
  return res
})

const { merge } = useState()
</script>
