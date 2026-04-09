<template>
  <el-menu class="!border-0">
    <el-menu-item
      class="!h-16"
      v-for="config of configs"
      :key="config.id"
      @click="$emit('select', config)"
    >
      <div>
        <p>{{ config.name }}</p>
        <p class="text-neutral-500">{{ description(config) }}</p>
      </div>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { i18n } from '@/i18n'
import { type PrinterConfig } from '@/print'
import type { PropType } from 'vue'

const { t } = i18n()

defineProps({
  configs: {
    type: Array as PropType<PrinterConfig[]>,
    defaul: () => [],
  },
})

defineEmits({
  select(config: PrinterConfig) {
    return config ? true : false
  },
})

function description(config: PrinterConfig): string {
  return t('printer.' + config.printer_type, config as any)
}
</script>

<style>
.el-message-box__container {
  display: block !important;
}
</style>
