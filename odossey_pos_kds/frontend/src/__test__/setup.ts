import * as i18n from '@/i18n'
import { useClient } from '@/odoo'
import { config } from '@vue/test-utils'
import { vi } from 'vitest'

config.global.mocks = {
  $t: (key: string) => key,
}

await useClient()

const spy = vi.spyOn(i18n, 'i18n')
// @ts-ignore
spy.mockImplementation(() => ({ t: (key: string) => key }))
