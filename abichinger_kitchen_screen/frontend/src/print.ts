import * as odoo from 'odoo-typescript/18.0'
import { useClient } from './odoo'
import { ElMessage, ElMessageBox } from 'element-plus'
import PrinterMenu from './components/PrinterMenu.vue'
import { h } from 'vue'
import { i18n } from './i18n'
import { notEmpty } from './util'

type BasePrinter = odoo.Import<'@point_of_sale/app/printer/base_printer', 'BasePrinter'>

export interface PrinterConfig {
  id: number
  name: string
  printer_type: string
  proxy_ip: string | false
}

export interface EpsonPrinterConfig extends PrinterConfig {
  epson_printer_ip: string
}

export interface HWPrinterConfig extends PrinterConfig {}
export interface DevPrinterConfig extends PrinterConfig {}
export interface LocalPrinterConfig extends PrinterConfig {}

export function isEpsonPrinter(config: PrinterConfig): config is EpsonPrinterConfig {
  return config.printer_type == 'epson_epos'
}

export function isHWPrinter(config: PrinterConfig): config is HWPrinterConfig {
  return config.printer_type == 'iot'
}

export function isDevPrinter(config: PrinterConfig): config is DevPrinterConfig {
  return config.printer_type == 'dev'
}

export function isLocalPrinter(config: PrinterConfig): config is LocalPrinterConfig {
  return config.printer_type == 'local'
}

export class PrinterService {
  configs: PrinterConfig[]
  printers: BasePrinter[] = []

  constructor(configs: PrinterConfig[]) {
    this.configs = configs
    this.loadPrinters().then((printers) => {
      this.printers = printers
    })
  }

  async loadPrinters(): Promise<BasePrinter[]> {
    const printers = await Promise.all(
      this.configs.map((p) => {
        return this.createPrinter(p)
      }),
    )
    return printers.filter(notEmpty)
  }

  // CREDIT: https://github.com/odoo/odoo/blob/2a2c76a02835578b9edcd73a7cff88a5bab2576e/addons/pos_epson_printer/static/src/overrides/models/models.js#L16
  async createPrinter(config: PrinterConfig): Promise<BasePrinter | undefined> {
    if (isEpsonPrinter(config)) {
      const { EpsonPrinter } = odoo.require('@pos_epson_printer/app/epson_printer')
      // @ts-ignore
      return new EpsonPrinter({ ip: config.epson_printer_ip })
    }
    if (isHWPrinter(config)) {
      const { HWPrinter } = odoo.require('@point_of_sale/app/printer/hw_printer')
      const { deduceUrl } = odoo.require('@point_of_sale/utils')
      const url = deduceUrl(config.proxy_ip || '')

      // @ts-ignore
      return new HWPrinter({ url })
    }
    if (isDevPrinter(config)) {
      return new DevPrinter() as BasePrinter
    }
    if (isLocalPrinter(config)) {
      const { LocalPrinter } = await import('./local_printer')
      // @ts-ignore
      return new LocalPrinter()
    }
  }

  async getPrinter(id?: number) {
    const config = await this.selectConfig(id)
    if (!config) {
      return undefined
    }
    const index = this.configs.indexOf(config)
    return this.printers[index]
  }

  async selectConfig(id?: number): Promise<PrinterConfig | undefined> {
    const { t } = i18n()

    if (this.configs.length == 0) {
      ElMessage.error({
        message: h('p', [
          t('no_printer') + ' ',
          h(
            'a',
            {
              class: 'text-sky-500',
              href: 'https://www.odoo.com/documentation/17.0/applications/sales/point_of_sale/restaurant/kitchen_printing.html#orders-printing',
            },
            ['Orders printing'],
          ),
        ]),
      })
      return
    }

    if (id !== undefined) {
      return this.configs.find((c) => c.id == id)
    }

    if (this.configs.length == 1) {
      return this.configs[0]
    }

    let config: PrinterConfig | undefined
    try {
      await ElMessageBox({
        title: t('select_printer'),
        confirmButtonText: t('close'),
        message: () => {
          const vnode = h(PrinterMenu, {
            configs: this.configs,
            onSelect(selected) {
              config = selected
              // Hack: ElMessageBox.close() does not resolve the promise
              // issue: https://github.com/element-plus/element-plus/issues/12363
              ;(vnode as any).ctx.setupState.handleAction('confirm')
            },
          })
          return vnode
        },
      })
    } catch {
      return
    }

    return config
  }
}

class DevPrinter {
  _t?: ReturnType<typeof setTimeout>
  printReceipt(receipt: string): {
    successful: boolean
    message?: { title: string; body?: string | undefined } | undefined
  } {
    const el = receipt as unknown as HTMLElement
    const container = document.querySelector('.render-container')
    if (container) {
      container.setAttribute('style', 'left: 0px')
      if (this._t) {
        clearTimeout(this._t)
      }
      this._t = setTimeout(() => {
        container.setAttribute('style', 'left: -10000px')
      }, 3000)
      container.innerHTML = el.outerHTML
    }

    return { successful: true }
  }
}
