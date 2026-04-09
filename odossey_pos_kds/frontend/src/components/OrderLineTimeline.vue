<template>
  <div class="m-5">
    <h3 class="font-bold text-sm mb-5">{{ $t('changes') }}</h3>
    <el-timeline>
      <el-timeline-item
        v-for="line of refs"
        :key="line.id"
        :timestamp="line.change.createdAt.toLocaleString(DateTime.TIME_SIMPLE)"
        :color="line.qty < 0 ? 'red' : undefined"
      >
        {{ line.qty > 0 ? '+' + line.qty : line.qty }}
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script setup lang="ts">
import type { OrderChangeLine } from '@/models'
import { DateTime } from 'luxon'
import type { PropType } from 'vue'

const props = defineProps({
  line: {
    type: Object as PropType<OrderChangeLine>,
    required: true,
  },
})

const refs = props.line.refs
</script>
