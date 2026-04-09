import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config'

const config = defineConfig((config) =>
  mergeConfig(baseConfig(config), {
    define: {
      __DEMO__: true,
    },
    base: '/odossey_pos_kds_demo/',
    build: {
      outDir: 'demo',
      emptyOutDir: true,
    },
  }),
)

export default config
