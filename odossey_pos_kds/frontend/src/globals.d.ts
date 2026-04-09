import type { KitchenScreen, Module } from './models'

export {}

interface Odoo {
  kitchen: KitchenScreen
  ab_modules: {
    odossey_pos_kds: Module
    abichinger_pos_stock?: Module
    ab_pos_order_status?: Module
    ab_pos_self_order_checkout?: Module
  }
}

declare global {
  var odoo: Odoo

  interface Window {
    opera?: any
  }
}
