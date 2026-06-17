<template>
  <div class="app">
    <template v-if="isAIPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </template>
    <template v-else-if="isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </template>
    <template v-else>
      <el-container>
        <AppSidebar />
        <el-main>
          <router-view v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'

const route = useRoute()
const isAuthPage = computed(() => {
  return route.path === '/login' || route.path === '/register'
})
const isAIPage = computed(() => {
  return route.path === '/ai' || route.path.startsWith('/ai')
})
</script>

<style>
.el-main {
  padding: 0;
  background-color: var(--bg-primary);
  min-height: 100vh;
}
</style>
