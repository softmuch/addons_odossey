import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config'

const config = defineConfig((config) =>
  mergeConfig(baseConfig(config), {
    define: {
      __DEMO__: true,
    },
    base: '/abichinger_kitchen_screen_demo/',
    build: {
      outDir: 'demo',
      emptyOutDir: true,
    },
  }),
)

export default config
