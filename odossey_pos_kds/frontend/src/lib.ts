import { i18n, messages } from './i18n'
import { useClient, lang } from './odoo'
import { orderOptions } from './sort'
import { useState, State } from './state'
import { useStore } from './store'
import { splitChanges } from './util'
import SettingsOption from '@/components/SettingsOption.vue'

export * from './models'
export type * from './models'

export {
  useStore,
  useState,
  State,
  i18n,
  useClient,
  messages,
  lang,
  splitChanges,
  SettingsOption,
  orderOptions,
}
