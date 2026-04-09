<template>
  <div class="sidebar drop-shadow p-5">
    <header class="flex items-center">
      <span class="grow text-neutral-500">{{ $t('overview') }}</span>
      <el-button text class="!p-1" @click="$emit('close')">
        <el-icon size="20" color="rgb(115 115 115)"><Close /></el-icon>
      </el-button>
    </header>
    <div v-for="({ category, products }, i) in count" :key="category?.id ?? i">
      <div class="mt-10"></div>
      <h3 v-if="category" class="font-bold text-xl">
        {{ category.fullName }}
      </h3>
      <div v-for="{ product, line } in products" :key="product.id">
        <div class="flex mr-2 mt-2">
          <div class="grow">
            <span>
              {{ line.display_name }}
            </span>
            <OrderLineAttributes :ids="line.attribute_value_ids"></OrderLineAttributes>
          </div>
          <span class="font-semibold">{{ line.qty }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrderChangeLine, PosCategory, Product } from '@/models'
import { useStore } from '@/store'
import { groupBy, mergeOrderLines } from '@/util'
import { Close } from '@element-plus/icons-vue'
import { ref, watch, type PropType, type Ref } from 'vue'
import OrderLineAttributes from './OrderLineAttributes.vue'

const props = defineProps({
  lines: {
    type: Object as PropType<OrderChangeLine[]>,
    required: true,
  },
})

const store = useStore()

const count: Ref<
  {
    category?: PosCategory
    products: {
      product: Product
      line: OrderChangeLine
    }[]
  }[]
> = ref([])

watch(
  [() => props.lines, store.ready],
  () => {
    if (!store.ready.value) {
      return
    }
    const grouped = groupBy(
      props.lines,
      (l) =>
        l.product.pos_categ_ids.find((cid) => store.db.categoryById(cid)) ??
        l.product.pos_categ_ids[0],
      (line) => line.product.id + line.attribute_value_ids.join(','),
    )

    count.value = Object.entries(grouped)
      .map(([categId, lineMap]) => {
        return {
          category: store.db.categoryById(parseInt(categId)),
          products: Object.values(lineMap).map((lines) => {
            const line = mergeOrderLines(lines)
            return { line, product: line.product }
          }),
        }
      })
      .sort((a, b) => (a.category?.toString() > b.category?.toString() ? 1 : -1))
  },
  { immediate: true },
)
</script>

<style>
.sidebar {
  background-color: var(--el-bg-color);
  border-right: 1px solid var(--el-menu-border-color);
}
</style>
