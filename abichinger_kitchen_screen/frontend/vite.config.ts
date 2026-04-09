import { URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  return {
    define: {
      __DEMO__: false,
      __LOGGER__: process.env.LOGGER || mode == 'development' ? true : false,
    },
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
      }),
      Components({
        resolvers: [ElementPlusResolver()],
      }),
    ],
    resolve: {
      alias: {
        '@/': new URL('./src/', import.meta.url).pathname,
      },
    },
    base: 'abichinger_kitchen_screen/static/app/',
    build: {
      outDir: '../static/app',
      emptyOutDir: true,
      minify: mode == 'development' ? false : true,
    },
  }
})
