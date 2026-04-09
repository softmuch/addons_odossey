<template>
  <el-tooltip
    :content="$t('created_at_desc', { minutes: minutes })"
    :persistent="false"
    :teleported="false"
  >
    <el-tag :effect="effect" class="font-semibold ml-1 mb-1 !text-sm" disable-transitions>
      <el-icon class="mr-0.5 align-sub" size="20"><Clock /></el-icon>
      {{ time }}{{ timeFormat == 'm' ? 'm' : '' }}
    </el-tag>
  </el-tooltip>
</template>

<script lang="ts">
import { counter } from '@/composables/globals'
import { useState } from '@/state'
import { Clock } from '@element-plus/icons-vue'
import { DateTime } from 'luxon'
import { defineComponent, ref, watch, type PropType } from 'vue'

export type ElEffect = 'light' | 'dark' | 'plain'

export default defineComponent({
  components: {
    Clock,
  },
  props: {
    datetime: {
      type: Object as PropType<DateTime>,
      required: true,
    },
    effect: {
      type: String as PropType<ElEffect>,
      default: 'light',
    },
  },
  setup(props) {
    const { timeFormat } = useState()
    let minutes = ref('')
    let time = ref('')

    watch(
      [counter, timeFormat],
      () => {
        const duration = DateTime.now().diff(props.datetime)
        minutes.value = duration.toFormat('m')
        time.value = duration.toFormat(timeFormat.value)
      },
      { immediate: true },
    )

    return {
      timeFormat,
      time,
      minutes,
    }
  },
})
</script>
