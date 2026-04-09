import * as odooTS from 'odoo-typescript/18.0'
import { mockClient } from './dev'
import type { titleService } from 'odoo-typescript/18.0/dist/addons/web/core/browser/title_service'
import type { busService } from 'odoo-typescript/18.0/dist/addons/bus/services/bus_service'
import type { ORM } from 'odoo-typescript/18.0/dist/addons/web/core/orm_service'

export interface Client {
  env: any
  orm: ORM
  user: any
  bus: ReturnType<typeof busService.start>
}

let client: Promise<Client> | null = null

async function init(mode?: string, title?: string): Promise<Client> {
  if (import.meta.env.DEV || __DEMO__ || mode == 'development') {
    return mockClient()
  }

  // wait until all services are registered
  await Promise.resolve()

  // start services
  const { makeEnv, startServices } = odooTS.require('@web/env')
  const env = await makeEnv()
  await startServices(env)

  // monkey patch title_service
  const tService: ReturnType<typeof titleService.start> = env.services['title']
  // set title once
  tService.setParts({ one: title ?? odoo.kitchen.name })
  // make setParts a noop to prevent title changes
  tService.setParts = function () {}

  return {
    env: env,
    user: odooTS.require('@web/core/user').user,
    orm: env.services['orm'],
    bus: env.services['bus_service'],
  }
}

export async function useClient(): Promise<Client> {
  if (client === null) {
    client = init()
  }
  return await client
}

export function _t(msgid: string) {
  return odooTS.require('@web/core/l10n/translation')._t(msgid)
}

export async function lang(): Promise<string> {
  const { user } = await useClient()
  return user.lang || navigator.language.replace(/-/g, '_')
}
