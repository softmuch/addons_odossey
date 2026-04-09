<template>
  <div class="settings-option py-3 px-5">
    <div :class="justifyBetween ? ['flex', 'justify-between', 'items-center'] : []">
      <h4 v-if="label" class="mb-1 text-base">{{ label }}</h4>
      <div>
        <slot name="default"></slot>
      </div>
    </div>
    <slot name="append"></slot>
  </div>
</template>

<script setup lang="ts">
defineProps({
  label: {
    type: String,
    default: '',
  },
  justifyBetween: {
    type: Boolean,
    default: false,
  },
})
</script>

<style lang="css">
.settings-option:hover {
  background-color: var(--el-menu-hover-bg-color);
}
</style>
