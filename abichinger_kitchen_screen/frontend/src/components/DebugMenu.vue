<template>
  <el-button @click="createOrders(1)">Create one Order</el-button>
  <el-button @click="createOrders(100)">Create 100 Order</el-button>
</template>

<script setup lang="ts">
import { createOrders } from '@/debug'
</script>
