import { ref, watch, type Ref } from 'vue'
import { isKitchenState, type KitchenState } from './models'
import { emptyFilter, limit, replaceSearchParams, type LineFilter } from './util'
import { orderOptions, type OrderOption } from './sort'

// CREDIT: https://stackoverflow.com/a/50924506/3140799
type unwrapRef<T> = T extends Ref<infer X> ? X : T

type PartialState = {
  [P in keyof State]?: unwrapRef<State[P]> | undefined
}

export const timeFormats = ['m', 'mm:ss', 'hh:mm:ss'] as const
type TimeFormat = (typeof timeFormats)[number]

export class State {
  key: string = ''
  ksId: number = 0
  name: Ref<string> = ref('Kitchen')
  selected: Ref<KitchenState> = ref('cooking')
  filter: Ref<LineFilter> = ref(emptyFilter())
  showMenu: Ref<boolean> = ref(true)
  showOverview: Ref<boolean> = ref(false)
  theme: Ref<string> = ref('light')
  sound: Ref<string> = ref('none')
  merge: Ref<boolean> = ref(false)
  orderBy: Ref<OrderOption> = ref('duration')
  prepWarn: Ref<number> = ref(0)
  prepDanger: Ref<number> = ref(0)
  timeFormat: Ref<TimeFormat> = ref('m')
  stages: Ref<number> = ref(3)
  printMode: Ref<string> = ref('text')
  zoom: Ref<number> = ref(1)
  debug: Ref<string> = ref('')
  onChange?: (state: State) => void

  constructor(source: PartialState) {
    this.assign(source)

    watch(
      [
        this.name,
        this.selected,
        this.filter,
        this.showMenu,
        this.theme,
        this.showOverview,
        this.sound,
        this.merge,
        this.orderBy,
        this.prepWarn,
        this.debug,
        this.prepDanger,
        this.timeFormat,
        this.stages,
        this.printMode,
        this.zoom,
      ],
      () => {
        this.onChange?.call(this, this)
      },
    )
  }

  assign(source: PartialState) {
    this.key = source.key ?? this.key
    this.ksId = source.ksId ?? this.ksId
    this.name.value = source.name ?? this.name.value
    this.selected.value = source.selected ?? this.selected.value
    this.filter.value = source.filter ?? this.filter.value
    this.showMenu.value = source.showMenu ?? this.showMenu.value
    this.showOverview.value = source.showOverview ?? this.showOverview.value
    this.theme.value = source.theme ?? this.theme.value
    this.sound.value = source.sound ?? this.sound.value
    this.merge.value = source.merge ?? this.merge.value
    this.orderBy.value = source.orderBy ?? this.orderBy.value
    this.prepWarn.value = source.prepWarn ?? this.prepWarn.value
    this.prepDanger.value = source.prepDanger ?? this.prepDanger.value
    this.timeFormat.value = source.timeFormat ?? this.timeFormat.value
    this.stages.value = source.stages ?? this.stages.value
    this.printMode.value = source.printMode ?? this.printMode.value
    this.zoom.value = source.zoom ?? this.zoom.value
    this.debug.value = source.debug ?? this.debug.value
    this.onChange = source.onChange ?? this.onChange
  }

  static _paramsToObject(params: URLSearchParams): PartialState {
    const selected = params.get('select') ?? ''

    const categories = params
      .getAll('categ')
      .map((c) => parseInt(c))
      .filter((c) => !isNaN(c))

    const floors = params
      .getAll('floor')
      .map((f) => parseInt(f))
      .filter((f) => !isNaN(f))

    const filter =
      categories.length + floors.length > 0
        ? {
            posCategIds: categories,
            floorIds: floors,
          }
        : undefined

    const toInt = (s: string | null): number | undefined => {
      const i = parseInt(s ?? '')
      return isNaN(i) ? undefined : i
    }

    const toFloat = (s: string | null): number | undefined => {
      const i = parseFloat(s ?? '')
      return isNaN(i) ? undefined : i
    }

    const stages = toInt(params.get('stages'))

    return {
      ksId: parseInt(params.get('ks') ?? '0'),
      name: params.get('name') ?? undefined,
      selected: isKitchenState(selected) ? selected : undefined,
      filter: filter,
      showMenu: params.has('menu') ? params.get('menu') != 'hide' : undefined,
      showOverview: params.has('overview') ? params.get('overview') == 'show' : undefined,
      theme: params.get('theme') ?? undefined,
      sound: params.get('n') ?? undefined,
      merge: params.has('merge') ? params.get('merge') == 'true' : undefined,
      prepWarn: toInt(params.get('pw')),
      prepDanger: toInt(params.get('pd')),
      orderBy: orderOptions[parseInt(params.get('order') ?? '0')],
      timeFormat: timeFormats.includes(params.get('tf') as TimeFormat)
        ? (params.get('tf') as TimeFormat)
        : undefined,
      stages: stages ? limit(stages, 1, 3) : undefined,
      printMode: params.get('pm') ?? undefined,
      zoom: toFloat(params.get('zoom')),
      debug: params.get('debug') ?? undefined,
    }
  }

  static fromParams(
    params: URLSearchParams,
    key: string,
    onChange?: (state: State) => void,
  ): State {
    const source = State._paramsToObject(params)
    source.onChange = onChange
    source.key = key

    return new State(source)
  }

  toParams(): URLSearchParams {
    const params = new URLSearchParams({
      ks: this.ksId + '',
      name: this.name.value,
      select: this.selected.value,
    })

    if (!this.showMenu.value) {
      params.set('menu', 'hide')
    }
    if (this.showOverview.value) {
      params.set('overview', 'show')
    }
    if (this.theme.value !== 'light') {
      params.set('theme', this.theme.value)
    }
    if (this.sound.value !== 'none') {
      params.set('n', this.sound.value)
    }
    if (this.merge.value) {
      params.set('merge', 'true')
    }
    if (this.orderBy.value != orderOptions[0]) {
      params.set('order', orderOptions.indexOf(this.orderBy.value) + '')
    }
    if (this.prepWarn.value !== 0) {
      params.set('pw', this.prepWarn.value + '')
    }
    if (this.prepDanger.value !== 0) {
      params.set('pd', this.prepDanger.value + '')
    }
    if (this.timeFormat.value !== 'm') {
      params.set('tf', this.timeFormat.value)
    }
    if (this.stages.value !== 3) {
      params.set('stages', this.stages.value + '')
    }
    if (this.printMode.value !== 'text') {
      params.set('pm', this.printMode.value)
    }
    if (this.zoom.value !== 1) {
      params.set('zoom', this.zoom.value + '')
    }
    if (this.debug.value) {
      params.set('debug', this.debug.value)
    }

    this.filter.value.posCategIds.forEach((c) => params.append('categ', c + ''))
    this.filter.value.floorIds.forEach((f) => params.append('floor', f + ''))

    return params
  }

  save() {
    localStorage.setItem(this.key, this.toParams().toString())
  }

  static load(key: string, onChange?: (state: State) => void): State | undefined {
    const search = localStorage.getItem(key)
    if (!search) {
      return
    }
    return State.fromParams(new URLSearchParams(search), key, onChange)
  }

  updateFilter(update: Partial<LineFilter>) {
    this.filter.value = Object.assign({}, this.filter.value, update)
  }

  toggleOverview() {
    this.showOverview.value = !this.showOverview.value
  }

  resetSettings() {
    this.assign({
      name: 'Kitchen',
      filter: emptyFilter(),
      sound: 'none',
      merge: false,
      orderBy: orderOptions[0],
      prepWarn: 0,
      prepDanger: 0,
      timeFormat: 'm',
      stages: 3,
      printMode: 'text',
      zoom: 1,
      debug: '',
    })
  }
}

let state: State | undefined

export function useState(key: string = 'ab_pos_state:', defaults: PartialState = {}): State {
  if (state) {
    return state
  }

  let storageKey = key + '0'
  const onChange = (state: State) => {
    replaceSearchParams(state.toParams())
    state.save()
  }

  // init state
  const params = new URLSearchParams(window.location.search)
  if (params.has('ks')) {
    try {
      storageKey = key + parseInt(params.get('ks') ?? '0')
      state = State.load(storageKey, onChange)
    } catch (e) {
      console.error('Failed to load settings')
    }
  }

  state = state ?? new State({ key: storageKey, onChange: onChange, ...defaults })
  state.assign(State._paramsToObject(params))

  // initial zoom
  setTimeout(() => {
    updateZoom(state!.zoom.value)
  }, 10)

  return state
}

export function updateZoom(value: number[] | number): void {
  value = Array.isArray(value) ? value[0] : value
  const app = document.getElementById('kitchen_screen_app')
  const el = app?.querySelector<HTMLDivElement>('div.flex-col')
  if (!app || !el) return

  app.style.zoom = String(value)
  el.style.height = `${window.innerHeight / value}px`
  document.documentElement.style.setProperty('--zoom', String(value))
}
