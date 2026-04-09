import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config'
import dts from 'vite-plugin-dts'

const config = defineConfig((config) =>
  mergeConfig(baseConfig(config), {
    plugins: [dts({ tsconfigPath: './tsconfig.app.json', rollupTypes: true })],
    build: {
      outDir: 'lib',
      emptyOutDir: true,
      lib: {
        entry: 'src/lib.ts',
        fileName: 'index',
        formats: ['es'],
      },
      rollupOptions: {
        external: ['vue', 'vue-i18n', 'odoo-typescript', 'element-plus'],
      },
      minify: false,
    },
  }),
)

export default config
