<template>
  <div>
    <p class="mb-2">{{ $t('cleanup_info') }}</p>
    <ul>
      <li v-for="(c, i) in counts" :key="i" v-html="countHtml(c.value, i)"></li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { i18n } from '@/i18n'
import { useClient } from '@/odoo'
import { ref } from 'vue'

const { t } = i18n()

const queries = [
  {
    model: 'ab_pos.order.change',
    domain: [['order_id.session_id.state', '!=', 'opened']],
  },
  {
    model: 'ab_pos.order.change.line',
    domain: [['change_id.order_id.session_id.state', '!=', 'opened']],
  },
]

const counts = queries.map(() => ref(-1))

async function getCounts(): Promise<void> {
  const { orm } = await useClient()
  for (let i = 0; i < queries.length; i++) {
    const query = queries[i]
    counts[i].value = await orm.searchCount(query.model, query.domain as any)
  }
}
getCounts()

async function deleteAll(): Promise<void> {
  const { orm } = await useClient()
  for (let i = 0; i < queries.length; i++) {
    const query = queries[i]
    const ids = await orm.search(query.model, query.domain as any)
    await orm.unlink(query.model, ids)
  }
}

function countHtml(count: number, i: number): string {
  const format = (s: string) => '<span class="font-mono text-fuchsia-600">' + s + '</span>'

  return t('db_count', {
    table_name: format(queries[i].model),
    count: format(count == -1 ? t('loading').toUpperCase() : count + ''),
  })
}

defineExpose({
  deleteAll: async () => {
    await deleteAll()
    await getCounts()
  },
})
</script>
