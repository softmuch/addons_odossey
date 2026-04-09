<template>
  <el-tooltip :content="$t('order_status_screen')" :persistent="false" :teleported="false">
    <el-button text circle class="ml-4" @click="enabled ? openOrderStatus() : openDialog()"
      ><el-icon size="24"><Monitor /></el-icon
    ></el-button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { i18n } from '@/i18n'
import { useState } from '@/state'
import { Monitor } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed } from 'vue'

const state = useState()
const enabled = computed(() => odoo.ab_modules.ab_pos_order_status !== undefined)

const moduleLink =
  '<a class="text-sky-500" target="_blank" href="https://apps.odoo.com/apps/modules/17.0/ab_pos_order_status">POS Order Status Screen</a>'

function openOrderStatus() {
  const url = new URL(window.location.origin + '/ab_pos_order_status/app/?ks=' + state.ksId)
  window.open(url, '_blank')?.focus()
}

function openDialog() {
  const { t } = i18n()

  ElMessageBox.alert(t('module_required', { module: moduleLink }), {
    dangerouslyUseHTMLString: true,
  })
}
</script>
