<template>
  <div class="fixed z-10 render-container"></div>

  <div class="flex flex-col h-screen">
    <header class="flex-none shadow-md">
      <el-alert
        v-if="wsInfo.workerState !== undefined && !wsInfo.connected"
        show-icon
        type="warning"
        :closable="false"
        ><span v-html="$t('ws_disconnected')"></span
      ></el-alert>
      <el-alert
        v-if="soundBlocked && state.sound.value !== 'none'"
        show-icon
        type="info"
        :closable="false"
        class="cursor-pointer"
        @click="enableSound"
      >
        <template #title>
          <span class="flex items-center gap-2">
            <el-icon><Bell /></el-icon>
            {{ $t('click_to_enable_sound') }}
          </span>
        </template>
      </el-alert>
      <div class="flex p-4">
        <el-button text class="!px-1" @click="goBack">
          <el-icon size="24"><Back /></el-icon>
        </el-button>
        <!-- <h1 class="pl-2 font-semibold text-lg">{{ ksName }} - {{ state.name.value }}</h1> -->
        <h1 class="pl-2 font-semibold text-lg">{{ ksName }}</h1>
        <span class="grow"></span>
        <el-button v-if="state.debug.value != ''" @click="openDebugMenu">
          <el-icon size="24"><Cpu /></el-icon>
        </el-button>
        <el-switch v-model="isDark" :active-action-icon="Moon" :inactive-action-icon="Sunny" />
        <OrderStatus />
        <el-button text circle class="ml-3 mr-1" @click="drawer = true"
          ><el-icon size="24"><Setting /></el-icon
        ></el-button>
      </div>

      <div class="relative">
        <div class="absolute right-0 mt-3 mr-5 z-10 flex items-center gap-1">
          <el-button text circle class="!p-3" @click="showSearch = !showSearch"
            ><el-icon size="24"><SearchIcon /></el-icon
          ></el-button>
          <el-button
            v-if="canForwardAll"
            type="primary"
            @click="forwardAllOrders"
          >
            <el-icon class="mr-1"><DArrowRight /></el-icon>
            {{ $t('forward_all') }}
          </el-button>
        </div>
      </div>
      <el-menu
        v-if="state.showMenu.value"
        mode="horizontal"
        class="items-center !pr-10"
        :default-active="state.selected.value"
        ref="menu"
      >
        <el-button text class="!p-2 mx-3" @click="state.toggleOverview()">
          <el-icon size="24">
            <Expand v-if="!state.showOverview.value" />
            <Fold v-else />
          </el-icon>
        </el-button>
        <MenuItem
          v-for="state in visibleStates"
          :key="state"
          :state="state"
          :count="getChanges(state).length"
          @click="setActiveState(state)"
        >
          {{ $t(`state.${state}`) }}
        </MenuItem>
      </el-menu>
    </header>

    <main class="grow" :style="{ backgroundColor: '#00000032' }">
      <div class="flex flex-row h-full">
        <transition name="slide-fade">
          <Overview
            v-if="state.showOverview.value"
            class="!w-full md:!w-80 transition-all duration-300"
            :lines="lines"
            @close="state.toggleOverview()"
          ></Overview>
        </transition>

        <div class="flex flex-col grow">
          <div class="relative z-10">
            <transition name="slide-fade">
              <div v-if="showSearch" class="w-full md:w-96 p-2 absolute right-0 md:pr-6">
                <Search v-model="search" :changes="changes" @close="showSearch = false"></Search>
              </div>
            </transition>
          </div>

          <el-carousel
            :autoplay="false"
            :loop="false"
            indicator-position="none"
            arrow="never"
            :initial-index="kStates.indexOf(state.selected.value)"
            trigger="click"
            ref="carousel"
            height="100%"
            class="h-full grow"
            @change="carouselChange"
          >
            <el-progress
              v-if="!store.ready.value"
              :percentage="100"
              :duration="2"
              :format="() => ''"
              :indeterminate="true"
              :text-inside="true"
            />
            <el-carousel-item
              v-for="(kState, i) in visibleStates"
              :key="kState"
              :name="kState"
              class="h-full"
            >
              <ChangeList
                :changes="getChanges(kState)"
                :next-state="nextState(i)"
                :prev-state="prevState(i)"
                :search="search"
                :is-dark="isDark"
              ></ChangeList>
            </el-carousel-item>
          </el-carousel>
        </div>
      </div>
    </main>

    <el-drawer v-model="drawer" :title="$t('settings')" class="!w-full md:!w-96">
      <Settings :state="state" :floors="floors" :categories="categories"></Settings>
    </el-drawer>

    <el-dialog v-model="soundDialog" :title="$t('notification_sound')">
      <span>{{ $t('autoplay_error') }}</span>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="enableSound">{{ $t('enable') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import ChangeList from '@/components/ChangeList.vue'
import Settings from '@/components/Settings.vue'
import MenuItem from '@/components/MenuItem.vue'
import Overview from '@/components/Overview.vue'
import { useState } from '@/state'
import { splitChanges, idsOf } from '@/util'
import { setKitchenState } from '@/api'
import {
  Back,
  Bell,
  DArrowRight,
  Expand,
  Fold,
  Moon,
  Search as SearchIcon,
  Setting,
  Sunny,
  Cpu,
} from '@element-plus/icons-vue'
import { useDark } from '@vueuse/core'
import { computed, ref, shallowRef, watch, type ShallowRef } from 'vue'
import {
  type Floor,
  type KitchenState,
  kitchenStates,
  type Order,
  type OrderChange,
  type PosCategory,
  type OrderChangeLine,
} from './models'
import { useStore } from './store'
import { play, soundById, unlockAudio, isAudioUnlocked } from './sounds'
import { i18n } from './i18n'
import Search from '@/components/Search.vue'
import OrderStatus from '@/components/OrderStatus.vue'
import { useWebsocketInfo } from './websocket'
import { logger } from './log'

// i18n needs to be called once inside a setup
i18n()

const kStates = kitchenStates

function nextState(currentIndex: number): KitchenState | undefined {
  if (currentIndex + 1 >= kStates.length) {
    return
  }
  return kStates[currentIndex + 1]
}

function prevState(currentIndex: number): KitchenState | undefined {
  if (currentIndex <= 0) {
    return
  }
  return kStates[currentIndex - 1]
}

const store = useStore()

const state = useState()
const orders: ShallowRef<Order[]> = shallowRef([])
const floors: ShallowRef<Floor[]> = shallowRef([])
const categories: ShallowRef<PosCategory[]> = shallowRef([])
const changes: ShallowRef<Record<KitchenState, OrderChange[]>> = shallowRef({} as any)
const menu = ref()
const carousel = ref()
const drawer = ref(false)
const ksName = ref('')
const soundDialog = ref(false)
const soundBlocked = ref(false)
const search = ref('')
const showSearch = ref(false)
const wsInfo = useWebsocketInfo()

watch(orders, (newOrders) => {
  logger?.debug('watch orders', newOrders)
  const newChanges = splitChanges(newOrders, state)
  handleNotifications(newChanges, changes.value)
  changes.value = newChanges
})

watch([state.merge, state.filter, state.orderByCooking, state.orderByReady, state.orderByDone], () => {
  changes.value = splitChanges(orders.value, state)
})

watch(showSearch, (value) => {
  if (value === false) {
    search.value = ''
  }
})

function getChanges(state: KitchenState): OrderChange[] {
  return changes.value[state] ?? []
}

function initialized(): boolean {
  return Object.keys(changes.value).length > 0
}

async function handleNotifications(
  newChanges: Record<KitchenState, OrderChange[]>,
  oldChanges: Record<KitchenState, OrderChange[]>,
) {
  if (!initialized()) {
    return
  }
  const countLines = (changeMap: Record<KitchenState, OrderChange[]>) =>
    (['cooking', 'ready'] as const).reduce(
      (acc, stage) => acc + (changeMap[stage] ?? []).reduce((a, c) => a + c.lines.reduce((s, l) => s + l.qty, 0), 0),
      0,
    )

  const countModified = (changeMap: Record<KitchenState, OrderChange[]>) =>
    Object.values(changeMap).reduce((acc, list) => acc + list.filter((c) => c.modified).length, 0)

  if (countLines(newChanges) > countLines(oldChanges) || countModified(newChanges) > countModified(oldChanges)) {
    const sound = soundById(state.sound.value)
    if (sound) {
      play(sound).catch(() => {
        soundBlocked.value = true
        soundDialog.value = true
      })
    }
  }
}

async function enableSound() {
  const sound = soundById(state.sound.value)
  await unlockAudio(sound)
  soundBlocked.value = false
  soundDialog.value = false
}

watch(
  store.ready,
  (ready) => {
    if (!ready) {
      return
    }
    floors.value = store.floors
    categories.value = store.categories
    orders.value = [...store.orders]
    ksName.value = odoo.kitchen.name

    // remove deleted filters
    const filter = state.filter.value
    state.filter.value = {
      ...filter,
      floorIds: filter.floorIds.filter((id) => !!store.db.floorById(id)),
      posCategIds: filter.posCategIds.filter((id) => !!store.db.categoryById(id)),
    }
  },
  { immediate: true },
)

watch(store.updated, () => {
  orders.value = [...store.orders]
})

const lines = computed(() => {
  const res: OrderChangeLine[] = []
  for (const change of changes.value[state.selected.value] ?? []) {
    res.push(...change.lines)
  }
  return res
})

const visibleStates = computed(() => {
  return kStates.slice(0, state.stages.value)
})

function setActiveState(state: KitchenState) {
  carousel.value.setActiveItem(state)
}

function carouselChange(current: number) {
  state.selected.value = kStates[current]
}

const isDark = useDark()
watch(isDark, (isDark) => {
  state.theme.value = isDark ? 'dark' : 'light'
})

function goBack() {
  window.history.back()
}

async function openDebugMenu() {
  const { debugMenu } = await import('@/debug')
  await debugMenu()
}

const canForwardAll = computed(() => {
  const idx = visibleStates.value.indexOf(state.selected.value)
  return nextState(idx) !== undefined && getChanges(state.selected.value).length > 0
})

function forwardAllOrders() {
  const idx = visibleStates.value.indexOf(state.selected.value)
  const ns = nextState(idx)
  if (!ns) return
  for (const change of getChanges(state.selected.value)) {
    const ids = idsOf(change.lines)
    if (ids.length === 0) continue
    for (const line of change.lines) {
      for (const l of line.refs) {
        if (ids.includes(l.id)) {
          l.state = ns
        }
      }
    }
    setKitchenState(change.id, ids, ns)
  }
  store.updated.value++
}
</script>

<style>
.render-container {
  left: -10000px;
}
</style>
