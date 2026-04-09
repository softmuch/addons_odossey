<template>
  <div class="product-stock">
    <el-alert class="!mb-5" :type="disabled ? 'warning' : 'info'" show-icon :closable="false">
      <template #title>
        <span
          v-if="disabled"
          v-html="$t('stock_module_required', { pos_stock: moduleLink })"
        ></span>
        <span v-else>{{ $t('disable_products_desc') }}</span>
      </template>
    </el-alert>
    <div class="flex mb-3 items-center">
      <span class="grow">{{ $t('attr_toggle_for') }}:</span>
      <el-radio-group v-model="attrMode">
        <el-radio-button :label="$t('this_product')" value="one" />
        <el-radio-button :label="$t('all_products')" value="many" />
      </el-radio-group>
    </div>
    <el-input
      v-model="search"
      class="mb-3"
      :placeholder="$t('product_search')"
      clearable
    ></el-input>
    <div class="flex justify-between font-bold text-sm">
      <span>{{ $t('name') }}</span>

      <el-popover placement="bottom" :width="200" trigger="click" :hide-after="10">
        <template #reference>
          <span class="cursor-pointer" :class="availabilityFilter.length > 0 ? 'is-filtered' : ''">
            {{ $t('available') }}<el-icon class="mx-1"><ArrowDownBold /></el-icon>
          </span>
        </template>
        <CheckboxFilter
          :model-value="availabilityFilter"
          @update:model-value="updateFilter({ availability: $event })"
          :filters="availabilityFilters"
        />
      </el-popover>
    </div>
    <SettingsOption
      v-for="product in filteredProducts"
      :key="product.id"
      class="px-1 py-2"
      :class="disabled ? 'cursor-not-allowed' : 'cursor-pointer'"
      :label="product.display_name"
      justify-between
      @click="disabled || toggleOutOfStock(product)"
    >
      <el-switch
        :model-value="!product.ab_stock_out_of_stock"
        @click="disabled || toggleOutOfStock(product)"
        @click.stop=""
        :disabled="disabled"
        :loading="isLoading(product)"
      />
      <template #append>
        <div
          v-for="attribute in getAttributes(product)"
          :key="attribute.id"
          class="flex items-center"
        >
          <div class="font-bold mr-2">{{ attribute.display_name }}</div>
          <OrderLineAttributes
            :ids="attribute.product_template_value_ids"
            :disabled="product.ab_stock_disabled_attributes"
            :onClick="(id) => toggleAttributeValue(product, id)"
          />
        </div>
      </template>
    </SettingsOption>
  </div>
</template>

<script setup lang="ts">
import type { Attribute, Product } from '@/models'
import { useStore } from '@/store'
import SettingsOption from './SettingsOption.vue'
import { computed, ref, shallowRef, type Ref } from 'vue'
import { useClient } from '@/odoo'
import { ElMessage } from 'element-plus'
import { ArrowDownBold } from '@element-plus/icons-vue'
import { i18n } from '@/i18n'
import CheckboxFilter from './CheckboxFilter.vue'
import OrderLineAttributes from './OrderLineAttributes.vue'
import { notEmpty } from '@/util'

interface Filter {
  availability?: any[]
}

const filter = defineModel<Filter>('filter', { default: () => ({}) })
const module_ab_stock = odoo.ab_modules.abichinger_pos_stock

const store = useStore()
const products = shallowRef([...store.products])
products.value.sort((a, b) => a.display_name.localeCompare(b.display_name))
const search = ref('')
const loading: Ref<number[]> = ref([])
const attrMode = ref('many')

const { t } = i18n()

const availabilityFilters = [
  { text: t('available'), value: module_ab_stock === undefined ? undefined : false },
  { text: t('unavailable'), value: true },
]

const availabilityFilter: Ref<any[]> = computed(() => {
  return filter.value.availability ?? []
})

const filteredProducts = computed(() => {
  // apply availability filter
  return products.value.filter((p) => {
    // hide services
    if (p.type === 'service') {
      return false
    }

    // apply availabilityFilter
    if (
      availabilityFilter.value.length > 0 &&
      !availabilityFilter.value.includes(p.ab_stock_out_of_stock)
    ) {
      return false
    }

    // apply search
    if (search.value && !p.display_name.toLowerCase().includes(search.value.toLowerCase())) {
      return false
    }
    return true
  })
})

const disabled = computed(() => !module_ab_stock)
const moduleLink =
  '<a class="text-sky-500" target="_blank" href="https://apps.odoo.com/apps/modules/17.0/abichinger_pos_stock">POS Stock Sync</a>'

function updateFilter(source: Filter) {
  filter.value = Object.assign({}, filter.value, source)
}

function updateProduct(product: Product, update: Partial<Product>) {
  Object.assign(product, update)
  // trigger update
  products.value = [...products.value]
}
function isLoading(product: Product) {
  return loading.value.includes(product.id)
}
function setLoading(product: Product, value: boolean) {
  if (value && !isLoading(product)) {
    loading.value.push(product.id)
  } else if (!value && isLoading(product)) {
    loading.value.splice(loading.value.indexOf(product.id), 1)
  }
}

async function _toggleOutOfStock(product: Product) {
  if (disabled.value) {
    return
  }
  const oldValue = !!product.ab_stock_out_of_stock
  const newValue = !oldValue

  // const templateId = product.product_tmpl_id
  // if (!templateId) {
  //   return
  // }
  // updateProduct(product, data)
  // const { orm } = await useClient()

  updateProduct(product, { ab_stock_out_of_stock: newValue })
  const { orm } = await useClient()

  // disable in pos and self order
  try {
    const res: any = await orm.write('product.product', [product.id], {
      ab_stock_out_of_stock: newValue,
      self_order_available: !newValue,
    })
    if (res.error) {
      throw res.error
    }
  } catch (err: any) {
    ElMessage.error({
      message: err?.data?.message ?? t('unexpected_error'),
    })
    updateProduct(product, { ab_stock_out_of_stock: oldValue })
  }
}

function toggleOutOfStock(product: Product) {
  if (isLoading(product)) {
    return
  }
  setLoading(product, true)
  return _toggleOutOfStock(product).finally(() => {
    setLoading(product, false)
  })
}

function getAttributes(product: Product): Attribute[] {
  return product.valid_product_template_attribute_line_ids
    .map((attributeId) => store.db.attributeById(attributeId))
    .filter(notEmpty)
}

function getAttributeValues(attribute: Attribute) {
  return attribute.product_template_value_ids
    .map((valueId) => store.db.attributeValueById(valueId))
    .filter(notEmpty)
}

async function _toggleManyAttributeValues(valueId: number, command: number) {
  const { orm } = await useClient()

  const res: any = await orm.call('product.product', 'ab_stock_disable_same_attributes', [
    valueId,
    command,
  ])
  if (res.error) {
    throw res.error
  }
  for (const update of res) {
    const product = store.db.productById(update.id)
    Object.assign(product, update)
  }
  // trigger update
  products.value = [...products.value]
}

async function _toggleAttributeValue(product: Product, valueId: number) {
  if (disabled.value) {
    return
  }

  const isDisabled = product.ab_stock_disabled_attributes.includes(valueId)
  const oldValue = [...product.ab_stock_disabled_attributes]
  const newValue = isDisabled
    ? product.ab_stock_disabled_attributes.filter((id) => id !== valueId)
    : [...oldValue, valueId]

  updateProduct(product, { ab_stock_disabled_attributes: newValue })

  // 3: unlink, 4: link
  const command = isDisabled ? 3 : 4
  const { orm } = await useClient()
  try {
    if (attrMode.value == 'one') {
      const res: any = await orm.write('product.product', [product.id], {
        ab_stock_disabled_attributes: [[command, valueId, 0]],
      })
      if (res.error) {
        throw res.error
      }
    } else {
      await _toggleManyAttributeValues(valueId, command)
    }
  } catch (err: any) {
    ElMessage.error({
      message: err?.data?.message ?? t('unexpected_error'),
    })
    updateProduct(product, { ab_stock_disabled_attributes: oldValue })
  }
}

function toggleAttributeValue(product: Product, valueId: number) {
  if (isLoading(product)) {
    return
  }
  setLoading(product, true)
  return _toggleAttributeValue(product, valueId).finally(() => {
    setLoading(product, false)
  })
}
</script>

<style>
.product-stock .is-filtered {
  color: var(--el-color-primary);
}
</style>
