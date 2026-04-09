import './assets/main.css'
import { createApp } from 'vue'
import App from './App.vue'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import { lang } from './odoo'
import { createI18n } from 'vue-i18n'
import { messages } from '@/i18n'
import { logger } from './log'

async function main() {
  const locale = (await lang()).split('_')[0]

  const i18n = createI18n({
    legacy: false,
    locale: locale,
    fallbackLocale: 'en',
    messages,
  })

  const app = createApp(App)
  app.use(i18n)
  logger?.info('Mounting Vue app')
  app.mount('#kitchen_screen_app')
}
main()
