import { shallowRef, watch, type Ref } from 'vue'
import { useClient } from './odoo'
import { useStore } from './store'
import { logger } from './log'
import type { WORKER_STATE } from 'odoo-typescript/18.0/dist/addons/bus/workers/websocket_worker'

const TAG = '[WebSocket]'
const workerEvents = ['connect', 'reconnect', 'disconnect', 'reconnecting'] as const
type WorkerState = typeof WORKER_STATE

interface WebsocketInfo {
  connected: boolean
  workerState?: WorkerState[keyof WorkerState]
}

const store = useStore()
const wsInfo: Ref<WebsocketInfo> = shallowRef({ connected: false })

// wait until bus is ready
watch(store.ready, async (ready) => {
  if (!ready) {
    return
  }
  const { bus } = await useClient()

  const updateState = () => {
    const workerState = bus.workerState
    wsInfo.value = {
      workerState: workerState,
      connected: workerState == 'CONNECTED',
    }
  }

  for (const evt of workerEvents) {
    bus.addEventListener(evt, () => {
      logger?.info(TAG, evt + ' event')
      updateState()
    })
  }

  // get initial state
  updateState()
})

export function useWebsocketInfo() {
  return wsInfo
}
