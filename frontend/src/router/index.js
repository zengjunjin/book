import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue')
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/book/:id',
    name: 'BookDetail',
    component: () => import('../views/BookDetailView.vue')
  },
  {
    path: '/recommend',
    name: 'Recommend',
    component: () => import('../views/RecommendView.vue')
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('../views/CompareView.vue')
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue')
  },
  {
    path: '/ai',
    name: 'AI',
    component: () => import('../views/AIAssistant.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
