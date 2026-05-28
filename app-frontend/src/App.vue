<template>
  <div class="app-layout" :class="{ 'auth-layout': !authStore.isAuthenticated }">
    <!-- Authenticated Layout Shell -->
    <template v-if="authStore.isAuthenticated">
      <Sidebar />
      <div class="main-wrapper">
        <Header />
        <main class="content-body">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </template>
    
    <!-- Non-Authenticated Layout (Login/Register/404) -->
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import { useAuthStore } from './store/auth'

const authStore = useAuthStore()
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  width: 100%;
}

.auth-layout {
  display: block;
  background-color: var(--bg-base);
}

.main-wrapper {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100vh;
  overflow: hidden;
}

.content-body {
  flex-grow: 1;
  padding: 2rem;
  overflow-y: auto;
  background-color: var(--bg-base);
}

/* Page Transition Animations */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
