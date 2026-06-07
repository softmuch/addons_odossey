<template>
  <div ref="root">
    <el-card :class="cardClass" class="!border-2">
      <template #header>
        <div class="flex">
          <div>
            <div
              class="px-2 py-1 rounded bg-black/30 flex items-center cursor-pointer"
              @click="togglePriority"
            >
              <el-icon v-if="change.priority == 0" size="24" class="mr-1"><Star /></el-icon>
              <el-icon v-else size="25" class="mr-1" color="#FFCA28"><StarFilled /></el-icon>
              <span class="font-semibold text-2xl underline text-white text-nowrap">{{
                table ? fullNameOfTable(table) : change.name
              }}</span>
            </div>
            <el-tag
              v-if="paid || invoiced"
              :effect="tagEffect"
              class="font-semibold mt-1 !text-sm"
              type="success"
              disable-transitions
            >
              {{ paid ? $t('paid') : $t('invoiced') }} ✓
            </el-tag>
          </div>
          <span class="grow min-w-3"></span>
          <div class="tags flex flex-wrap flex-row-reverse">
            <ElapsedTime :effect="tagEffect" :datetime="change.createdAt"></ElapsedTime>

            <el-tag
              v-if="change.modified && !change.allRemoved"
              :effect="tagEffect"
              class="font-semibold ml-1 mb-1 !text-sm"
              :class="isDark ? '!text-amber-300' : '!text-amber-600'"
              type="warning"
              disable-transitions
            >
              {{ $t('modified') }}
            </el-tag>

            <el-tag
              v-if="canceled || change.allRemoved"
              :effect="tagEffect"
              class="font-semibold ml-1 mb-1 !text-sm"
              type="danger"
              disable-transitions
            >
              {{ $t('state.cancel') }}
            </el-tag>

            <el-tooltip :persistent="false" :teleported="false">
              <el-tag
                :effect="tagEffect"
                class="font-semibold ml-1 mb-1 !text-xs"
                :class="isDark ? '!text-neutral-300' : '!text-neutral-700'"
                type="info"
                disable-transitions
              >
                {{ change.name }}
              </el-tag>
              <template #content>
                <div>{{ change.order.uid }}</div>
                <div v-if="!merge">{{ $t('sequence_number') }}: {{ change.sequenceNumber }}</div>
              </template>
            </el-tooltip>

            <el-tag
              v-if="change.order.takeaway"
              :effect="tagEffect"
              class="font-semibold ml-1 mb-1 !text-sm"
              :class="isDark ? '!text-amber-300' : '!text-amber-600'"
              type="info"
              disable-transitions
            >
              {{ $t('takeaway') }}
            </el-tag>

            <el-tag
              v-if="config"
              :effect="tagEffect"
              class="font-semibold ml-1 mb-1 !text-sm"
              :class="isDark ? '!text-neutral-300' : '!text-neutral-700'"
              type="info"
              disable-transitions
            >
              {{ config.name }}
            </el-tag>

            <el-tag
              v-if="change.order.ab_service_type === 'delivery'"
              :effect="tagEffect"
              class="font-semibold ml-1 mb-1 !text-sm"
              :class="isDark ? '!text-amber-300' : '!text-amber-600'"
              type="info"
              disable-transitions
            >
              {{ $t('delivery') }}
            </el-tag>
          </div>
        </div>
        <div v-if="user" class="text-right text-neutral-100 text-sm mt-1">
          <span>{{ user.name }}</span>
        </div>
      </template>

      <!-- Customer Details -->
      <div v-if="partner">
        <div class="flex flex-row">
          <!--<span class="text-sm font-semibold">Customer details</span>-->
          <div class="my-1 mr-4">
            <el-icon size="24">
              <Avatar />
            </el-icon>
          </div>
          <div>
            <p>{{ partner?.name }}</p>
            <a v-if="partner?.phone" :href="'tel:' + partner?.phone" class="block">
              <el-tag
                :effect="tagEffect"
                class="font-semibold ml-1 my-1 !text-sm"
                :class="isDark ? '!text-neutral-300' : '!text-neutral-700'"
                disable-transitions
              >
                <el-icon class="mr-0.5 align-sub" size="20"><Phone /></el-icon>
                {{ partner.phone }}
              </el-tag>
            </a>

            <a v-if="partner?.email" :href="'mailto:' + partner?.email" class="block">
              <el-tag
                :effect="tagEffect"
                class="font-semibold ml-1 my-1 !text-sm"
                :class="isDark ? '!text-neutral-300' : '!text-neutral-700'"
                disable-transitions
              >
                <el-icon class="mr-0.5 align-sub" size="20"><Message /></el-icon>
                {{ partner.email }}
              </el-tag>
            </a>

            <template v-if="partner.comment" v-html="partner.comment"></template>
          </div>
        </div>
        <hr class="h-px my-3 bg-gray-200 border-0 dark:bg-gray-700" />
      </div>

      <!-- Customer Address -->
      <div v-if="hasAddress(change) && change.order.ab_service_type == 'delivery'">
        <div class="flex flex-row">
          <!--<span class="text-sm font-semibold">Customer details</span>-->
          <div class="my-1 mr-4">
            <el-icon size="24">
              <Location />
            </el-icon>
          </div>
          <div>
            <p v-if="partner?.street">{{ partner?.street }}</p>
            <p v-if="partner?.city">{{ partner?.city }}</p>
            <p v-if="partner?.zip">{{ partner?.zip }}</p>
          </div>
        </div>
        <hr class="h-px my-3 bg-gray-200 border-0 dark:bg-gray-700" />
      </div>

      <div v-for="({ group, lines }, i) in groupedLines" :key="group?.id">
        <div v-if="group" class="text-xl font-bold mb-2">{{ group.name }}</div>
        <OrderLine
          v-for="(line, i) in lines"
          :key="line.id"
          :line="line"
          :even="i % 2 == 0"
          :is-dark="isDark"
          @check="forwardLine(line)"
          @checkOne="forwardLineOne(line)"
        />
        <hr
          v-if="i < groupedLines.length - 1"
          class="h-px my-3 bg-gray-200 border-0 dark:bg-gray-700"
        />
      </div>

      <template #footer v-if="nextState || prevState || change.order.is_delivery">
        <div class="flex items-center">
          <el-button :loading="printing" size="large" circle @click="print">
            <el-icon v-if="!printing" :size="24"><Printer /></el-icon>
          </el-button>
          <el-tag
            v-if="change.order.is_delivery"
            effect="dark"
            type="warning"
            class="font-semibold ml-2 !text-sm"
            disable-transitions
          >
            🏍️ {{ $t('delivery') }}
          </el-tag>
          <div class="grow"></div>
          <el-button v-if="!canceled && prevState" @click="returnAll">
            {{ $t(`state.${prevState}`) }}
          </el-button>
          <el-button v-if="!canceled && nextState" type="primary" @click="forwardAll">
            <template v-if="nextState != 'cancel'">
              {{ $t(`state.${nextState}`) }}
            </template>
            <template v-else>
              {{ $t('hide') }}
            </template>
          </el-button>
          <el-button v-if="canceled" @click="hide">
            {{ $t('hide') }}
          </el-button>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script lang="ts">
import { setKitchenState, splitAndSetKitchenState, updatePriority } from '@/api'
import ElapsedTime, { type ElEffect } from '@/components/ElapsedTime.vue'
import { type KitchenState, type Table, kStateProps } from '@/models'
import { computed, defineComponent, onMounted, ref, watch, type PropType } from 'vue'
import type { OrderChange, OrderChangeLine } from '@/models'
import {
  idsOf,
  minutesToMillis,
  parseHTML,
  renderToHtml,
  hasAddress,
  compareLines,
  computedStyleToInlineStyle,
} from '@/util'
import { fullNameOfTable, useStore } from '@/store'
import { useState } from '@/state'
import OrderLine from './OrderLine.vue'
import { useEvolution } from '@/composables/evolution'
import { counter } from '@/composables/globals'
import OrderChangePrint from './OrderChangePrint.vue'
import {
  Printer,
  Phone,
  Location,
  Message,
  Avatar,
  Star,
  StarFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { i18n } from '@/i18n'
import { useOrderlineGroups } from '@/orderline_group'

export default defineComponent({
  components: {
    ElapsedTime,
    OrderLine,
    Printer,
    Phone,
    Location,
    Message,
    Avatar,
    Star,
    StarFilled,
  },
  props: {
    change: {
      type: Object as PropType<OrderChange>,
      required: true,
    },
    nextState: {
      type: String as PropType<KitchenState | undefined>,
    },
    prevState: {
      type: String as PropType<KitchenState | undefined>,
    },
    isDark: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { change } = props
    const root = ref<HTMLDivElement | null>(null)
    const store = useStore()
    const settings = useState()
    const kState = change.lines[0].state
    const canceled = change.order.state == 'cancel'
    const table = computed<Table | undefined>(() => store.db.tableById(props.change.order.tableId))
    const printing = ref(false)
    const { groupOrderlines } = useOrderlineGroups()

    const sortedLines = computed(() => {
      return [...change.lines].sort(compareLines)
    })

    const groupedLines = computed(() => {
      return groupOrderlines(sortedLines.value)
    })

    const bgEvolution = (minutes: number, value: string) => {
      if (minutes <= 0) {
        return []
      }
      return [
        {
          at: () => change.createdAt.toMillis() + minutesToMillis(minutes),
          value: value,
        },
      ]
    }
    const evolutions = computed(() => {
      return [
        ...bgEvolution(settings.prepWarn.value, 'bg-warning'),
        ...bgEvolution(settings.prepDanger.value, 'bg-red-700'),
      ].sort((a, b) => a.at() - b.at())
    })
    const bgColor =
      kState == 'cooking'
        ? useEvolution({
            initial: kStateProps[kState].bg,
            interval: counter,
            evolutions: evolutions,
          })
        : ref(kStateProps[kState].bg)

    const cardClass = canceled || change.allRemoved
      ? '!border-red-500'
      : change.modified
        ? '!border-amber-400'
        : kStateProps[kState].border

    onMounted(() => {
      setHeaderColor(bgColor.value)
    })

    const setHeaderColor = (newColor: string, oldColor?: string) => {
      const header = root.value?.querySelector('.el-card__header')
      if (header) {
        if (oldColor) {
          header.classList.remove(oldColor)
        }
        header.classList.add(newColor)
      }
    }

    watch(bgColor, setHeaderColor)

    const forward = async (ids: number[]) => {
      if (!props.nextState) {
        return
      }
      setState(ids, props.nextState)
    }

    const forwardLine = (line: OrderChangeLine) => {
      let lines =
        line.comboLineIds.length > 0
          ? sortedLines.value.filter((l) => l.comboId == line.comboId)
          : [line]
      return forward(idsOf(lines))
    }

    const forwardLineOne = (line: OrderChangeLine) => {
      if (!props.nextState) return

      // Get raw refs (actual DB records); in non-merge mode refs = [line itself]
      const rawRefs = line.refs.length > 0 ? line.refs : [line]
      const ref = rawRefs.find((r) => r.state === line.state) ?? rawRefs[0]
      if (!ref) return

      // Optimistic local update
      if (ref.qty <= 1) {
        ref.state = props.nextState
      } else {
        ref.qty -= 1
      }
      store.updated.value++

      splitAndSetKitchenState(ref.id, 1, props.nextState)
    }

    const forwardAll = () => {
      const ids = idsOf(change.lines)
      return forward(ids)
    }

    const returnAll = () => {
      if (!props.prevState) {
        return
      }
      const ids = idsOf(change.lines)
      return setState(ids, props.prevState)
    }

    const hide = () => {
      const ids = idsOf(change.lines)
      setState(ids, 'cancel')
    }

    const setState = (ids: number[], state: KitchenState) => {
      // update local values
      for (let line of change.lines) {
        for (let l of line.refs) {
          if (ids.includes(l.id)) {
            l.state = state
          }
        }
      }
      store.updated.value++

      // sync changes to server
      setKitchenState(change.id, ids, state)
    }

    const _print = async () => {
      const { LocalPrinter } = await import('@/local_printer')
      const { t } = i18n()
      const html = await renderToHtml(OrderChangePrint, { change: change })
      const el = parseHTML(html)

      const { print } = useStore()
      const printer = await print.getPrinter()
      if (!printer) {
        return
      }

      if (printer instanceof LocalPrinter && settings.printMode.value === 'text') {
        const styledEl = computedStyleToInlineStyle(el, { recursive: true })
        await printer.printElement(styledEl)
      } else {
        const res = await printer.printReceipt(el as any)
        if (!res?.successful) {
          ElMessage.error({
            message: res?.message ? res.message.title + ': ' + res.message.body : t('print_error'),
          })
        } else {
          ElMessage.success({
            message: t('print_success'),
          })
        }
      }
    }

    const print = async () => {
      printing.value = true
      try {
        await _print()
      } finally {
        printing.value = false
      }
    }

    function togglePriority() {
      const newPriority = change.priority == 0 ? 5 : 0

      const merge = settings.merge.value
      const order = store.orders.find((o) => o.id == change.order.id)!
      if (merge) {
        for (const c of order.changes) {
          c.priority = newPriority
        }
      } else {
        const c = order.changes.find((c) => c.id == change.id)!
        c.priority = newPriority
      }
      store.updated.value++ // force refresh

      // sync changes to server
      const id = merge ? change.order.id : change.id
      const model = merge ? 'pos.order' : 'ab_pos.order.change'
      updatePriority([id], model, newPriority)
    }

    return {
      user: change.order.user(),
      idsOf,
      forwardLine,
      forwardLineOne,
      forwardAll,
      returnAll,
      hide,
      table,
      kStateProps,
      canceled,
      paid: change.order.state == 'paid',
      invoiced: change.order.state == 'invoiced',
      cardClass,
      merge: settings.merge,
      root: root,
      kState: kState,
      tagEffect: 'light' as ElEffect,
      print,
      Printer,
      printing,
      fullNameOfTable,
      config: store.configs.length > 1 ? change.order.config() : undefined,
      partner: change.order.partner(),
      hasAddress,
      sortedLines,
      togglePriority,
      groupedLines,
    }
  },
})
</script>

<style>
.bg-warning {
  background-color: #f57c00;
}
</style>
