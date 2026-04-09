<template>
  <div>
    <!-- <SettingsOption :label="$t('name')">
      <el-input
        v-model="name"
        :placeholder="$t('name_placeholder')"
        @change="state.name.value = name"
      />
    </SettingsOption> -->
    <SettingsOption :label="$t('products')" class="cursor-pointer" @click="productDialog = true">
      <span class="text-neutral-500">{{ $t('disable_products_desc') }}</span>
    </SettingsOption>
    <el-dialog v-model="productDialog" :title="$t('products')" class="!w-full md:!w-2/3 2xl:!w-1/3">
      <ProductStock v-model:filter="stockFilter"></ProductStock>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="productDialog = false">{{ $t('close') }}</el-button>
        </div>
      </template>
    </el-dialog>
    <SettingsOption :label="$t('wait_time') + ': ' + prepFormat(waitTime)">
      <el-slider
        v-model="waitTime"
        :step="5"
        :max="60"
        :format-tooltip="prepFormat"
        @change="updateWaitTime"
      />
    </SettingsOption>
    <SettingsOption
      v-if="showDeliveryTime"
      :label="$t('delivery_time') + ': ' + prepFormat(waitTime + deliveryTime)"
    >
      <el-slider
        :modelValue="waitTime + deliveryTime"
        @update:modelValue="onInputDeliveryTime"
        :step="5"
        :min="waitTime"
        :max="waitTime + 60"
        :format-tooltip="prepFormat"
        @change="updateDeliveryTime"
      />
    </SettingsOption>
    <SettingsOption :label="$t('zoom') + ': ' + percentage(state.zoom.value)">
      <el-slider
        v-model="state.zoom.value"
        :step="0.1"
        :max="2"
        :min="0.7"
        :format-tooltip="percentage"
        @change="updateZoom"
      />
    </SettingsOption>

    <h3 class="font-bold text-sm mt-4 mb-1 ml-5 settings-group">{{ $t('filter') }}</h3>
    <div v-for="checkable in checkables" :key="checkable.i18n">
      <SettingsOption :label="$t(checkable.i18n)">
        <el-check-tag
          v-for="item in checkable.items"
          :checked="checkable.checked(item)"
          class="m-1"
          @change="checkable.toggle(item)"
          :key="item.key"
          >{{ checkable.itemText ? item[checkable.itemText] : item.name }}</el-check-tag
        >
      </SettingsOption>
    </div>

    <h3 class="font-bold text-sm mt-4 mb-1 ml-5 settings-group">{{ $t('orders') }}</h3>
    <SettingsOption
      class="cursor-pointer"
      :label="$t('merge_order_changes')"
      justify-between
      @click="state.merge.value = !state.merge.value"
    >
      <el-switch v-model="state.merge.value" @click.stop="" />
    </SettingsOption>
    <SettingsOption :label="$t('notification_sound')">
      <el-select v-model="state.sound.value">
        <el-option
          v-for="s in sounds"
          :key="s.id"
          :label="$t('sounds.' + s.id)"
          :value="s.id"
          @click="play(s)"
        ></el-option>
      </el-select>
    </SettingsOption>
    <SettingsOption :label="$t('order_of_orders')">
      <el-select v-model="state.orderBy.value">
        <el-option
          v-for="orderBy in orderOptions"
          :key="orderBy"
          :label="$t('orderBy.' + orderBy)"
          :value="orderBy"
        ></el-option>
      </el-select>
    </SettingsOption>

    <SettingsOption class="cursor-pointer" :label="$t('prep_time')" @click="prepDialog = true">
      <span class="font-bold text-sm">
        {{ prepFormat(state.prepWarn.value) + '/' + prepFormat(state.prepDanger.value) }}
      </span>
    </SettingsOption>
    <el-dialog v-model="prepDialog" :title="$t('prep_time')" class="!w-full md:!w-2/3 2xl:!w-1/3">
      <p class="mb-5">{{ $t('prep_time_desc') }}</p>
      <SettingsOption :label="$t('orange_hl')">
        <el-slider
          v-model="state.prepWarn.value"
          :step="5"
          :max="60"
          :format-tooltip="prepFormat"
        />
      </SettingsOption>
      <SettingsOption :label="$t('red_hl')">
        <el-slider
          v-model="state.prepDanger.value"
          :step="5"
          :max="60"
          :format-tooltip="prepFormat"
        />
      </SettingsOption>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="prepDialog = false">{{ $t('close') }}</el-button>
        </div>
      </template>
    </el-dialog>

    <SettingsOption :label="$t('time_format')">
      <el-select v-model="state.timeFormat.value">
        <el-option
          v-for="format in timeFormats"
          :key="format"
          :label="$t('format.' + format)"
          :value="format"
        ></el-option>
      </el-select>
    </SettingsOption>

    <SettingsOption :label="$t('stages')">
      <el-select v-model="state.stages.value">
        <el-option v-for="n in [1, 2, 3]" :key="n" :label="n" :value="n"></el-option>
      </el-select>
    </SettingsOption>

    <h3 class="font-bold text-sm mt-4 mb-1 ml-5 settings-group">{{ $t('technical') }}</h3>
    <SettingsOption :label="$t('print_mode')">
      <el-select v-model="state.printMode.value">
        <el-option
          v-for="mode in ['text', 'img']"
          :key="mode"
          :label="$t('pm.' + mode)"
          :value="mode"
        ></el-option>
      </el-select>
    </SettingsOption>

    <SettingsOption class="cursor-pointer" :label="$t('cleanup')" @click="cleanupDialog = true">
      <span class="text-neutral-500">{{ $t('cleanup_desc') }}</span>
    </SettingsOption>

    <el-dialog v-model="cleanupDialog" :title="$t('cleanup')" class="!w-full md:!w-2/3 2xl:!w-1/3">
      <CleanupInfo ref="cleanup" />
      <template #footer>
        <div class="dialog-footer">
          <el-button type="danger" @click="cleanup?.deleteAll()">{{ $t('delete_all') }}</el-button>
          <el-button type="primary" @click="cleanupDialog = false">{{ $t('close') }}</el-button>
        </div>
      </template>
    </el-dialog>

    <div class="p-5">
      <el-button @click="state.resetSettings()">{{ $t('reset') }}</el-button>
      <el-alert
        class="!mt-16"
        :title="$t('settings_hint')"
        type="info"
        show-icon
        :closable="false"
      />

      <div v-if="module" class="mt-5 text-neutral-500 text-sm">
        {{ module.display_name }} - {{ module.installed_version }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Floor, PosCategory } from '@/models'
import { orderOptions } from '@/sort'
import { getSounds, play } from '@/sounds'
import { timeFormats, type State } from '@/state'
import { ref, watch, type PropType, type Ref } from 'vue'
import SettingsOption from '@/components/SettingsOption.vue'
import { useI18n } from 'vue-i18n'
import ProductStock from './ProductStock.vue'
import CleanupInfo from './CleanupInfo.vue'
import { useClient } from '@/odoo'
import { ElMessage } from 'element-plus'
import type { Arrayable } from '@vueuse/core'
import { updateZoom } from '../state'

const { t } = useI18n()

const props = defineProps({
  state: {
    type: Object as PropType<State>,
    required: true,
  },
  floors: {
    type: Array<Floor>,
    default: () => [],
  },
  categories: {
    type: Array<PosCategory>,
    default: () => [],
  },
})

const prepDialog = ref(false)
const productDialog = ref(false)
const cleanupDialog = ref(false)
const cleanup: Ref<typeof CleanupInfo | null> = ref(null)
const name = ref(props.state.name.value)
const stockFilter = ref({})
const waitTime = ref(odoo.kitchen.wait_time)
const deliveryTime = ref(odoo.kitchen.delivery_time ?? 0)
const showDeliveryTime =
  odoo.ab_modules.ab_pos_self_order_checkout && typeof odoo.kitchen.delivery_time === 'number'

watch(props.state.name, (value) => {
  name.value = value
})

watch(productDialog, (value) => {
  if (value === false) {
    stockFilter.value = {}
  }
})

const updateWaitTime = async (arr: Arrayable<number>) => {
  const value = Array.isArray(arr) ? arr[0] : arr
  const { orm } = await useClient()

  try {
    const res: any = await orm.write('ab_pos.kitchen_screen', [odoo.kitchen.id], {
      wait_time: value,
    })
    if (res.error) {
      throw res.error
    }
  } catch (err: any) {
    ElMessage.error({
      message: err?.data?.message ?? t('unexpected_error'),
    })
  }
}

const onInputDeliveryTime = (arr: Arrayable<number>) => {
  const value = Array.isArray(arr) ? arr[0] : arr
  deliveryTime.value = value - waitTime.value
}

const updateDeliveryTime = async () => {
  const { orm } = await useClient()
  try {
    await orm.call('ab_pos.kitchen_screen', 'set_delivery_time', [
      odoo.kitchen.id,
      deliveryTime.value,
    ])
  } catch (err: any) {
    ElMessage.error({
      message: err?.data?.message ?? t('unexpected_error'),
    })
  }
}

interface Checkable<T> {
  i18n: string
  items: T[]
  itemText?: string
  checked: (item: T) => boolean
  toggle: (item: T) => void
}

const filter = props.state.filter
const checkables: Checkable<any>[] = [
  {
    i18n: 'product_categories',
    items: props.categories
      .filter((c) => {
        return c.id != 0 // ignore root category
      })
      .sort(),
    itemText: 'fullName',
    checked: (item: PosCategory) => {
      return filter.value.posCategIds.includes(item.id)
    },
    toggle: (item: PosCategory) => {
      const posCategIds = filter.value.posCategIds
      const newIds = posCategIds.includes(item.id)
        ? posCategIds.filter((id) => id != item.id)
        : [...posCategIds, item.id]
      props.state.updateFilter({
        posCategIds: newIds,
      })
    },
  },
  {
    i18n: 'floors',
    items: props.floors,
    checked: (item: Floor) => {
      return filter.value.floorIds.includes(item.id)
    },
    toggle: (item: Floor) => {
      const floorIds = filter.value.floorIds
      const newIds = floorIds.includes(item.id)
        ? floorIds.filter((id) => id != item.id)
        : [...floorIds, item.id]
      props.state.updateFilter({
        floorIds: newIds,
      })
    },
  },
]

const module = odoo.ab_modules.abichinger_kitchen_screen
const sounds = getSounds()

function prepFormat(value: number): string {
  return value == 0 ? t('disabled') : value + 'm'
}

function percentage(value: number): string {
  return (value * 100).toFixed(0) + '%'
}
</script>

<style>
.el-drawer__body {
  padding: 0px !important;
}
.settings-group {
  color: var(--el-menu-active-color);
}
</style>
