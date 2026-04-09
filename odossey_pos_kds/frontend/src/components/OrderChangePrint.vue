<template>
  <div class="order-change-print text-center p-6 text-2xl">
    <h1 class="text-4xl font-bold">{{ change.name }}</h1>
    <span>{{ change.order.uid }}</span>
    <div class="font-bold mt-5 flex justify-between">
      <div>{{ tableName }}</div>
      <div>{{ time }}</div>
    </div>

    <div v-if="partner" class="text-3xl font-bold text-center mt-7 mb-2">
      {{ $t('customer_details').toUpperCase() }}
    </div>

    <!-- Customer details -->
    <div v-if="partner" class="text-left mt-2">
      <p>{{ partner.name }}</p>
      <p v-if="partner.phone">{{ partner.phone }}</p>
      <p v-if="partner.email">{{ partner.email }}</p>
      <template v-if="partner.comment" v-html="partner.comment"></template>
    </div>

    <!-- Customer address -->
    <template v-if="hasAddress(change) && change.order.ab_service_type == 'delivery'">
      <div class="text-3xl font-bold text-center mt-7">
        {{ $t('delivery_address').toUpperCase() }}
      </div>
      <div class="text-left mt-2">
        <p v-if="partner?.street">{{ partner.street }}</p>
        <p v-if="partner?.city">{{ partner.city }}</p>
        <p v-if="partner?.zip">{{ partner.zip }}</p>
      </div>
    </template>

    <div v-for="group in groups" :key="group.id" class="mt-7 text-left">
      <div class="text-3xl font-bold text-center mb-2">{{ $t(group.id).toUpperCase() }}</div>
      <div v-for="line in sortedLines.filter(group.fn)" :key="line.id" class="mb-1">
        <span v-if="line.comboParentId !== false">&bull;&nbsp;&nbsp;&nbsp;&nbsp;</span>
        <span>{{ Math.abs(line.qty) }}</span>
        <span class="ml-3">{{ line.display_name }}</span>
        <p v-if="attributes(line).length">
          TYPE:
          {{
            attributes(line)
              .map((a) => a.name)
              .join(', ')
          }}
        </p>
        <p v-if="line.note">NOTE: {{ line.note }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrderChange, OrderChangeLine } from '@/models'
import { useStore, fullNameOfTable } from '@/store'
import { compareLines, hasAddress, notEmpty } from '@/util'
import { DateTime } from 'luxon'
import type { PropType } from 'vue'

const props = defineProps({
  change: {
    type: Object as PropType<OrderChange>,
    required: true,
  },
})

const sortedLines = [...props.change.lines].sort(compareLines)

const partner = props.change.order.partner()
const time = props.change.createdAt.toLocaleString(DateTime.TIME_SIMPLE)

const { db } = useStore()
const table = db.tableById(props.change.order.tableId)
const tableName = table ? fullNameOfTable(table) : ''

let groups = [
  {
    id: 'canceled',
    fn(line: OrderChangeLine) {
      return line.qty <= 0
    },
  },
  {
    id: 'ordered',
    fn(line: OrderChangeLine) {
      return line.qty > 0
    },
  },
].filter((group) => {
  return props.change.lines.filter(group.fn).length > 0
})

function attributes(line: OrderChangeLine) {
  return line.attribute_value_ids.map((a) => db.attributeValueById(a)).filter(notEmpty)
}
</script>

<style>
.order-change-print {
  background-color: white;
  width: 512px;
  color: black;
}
</style>
