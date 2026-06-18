import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresGuest: true }  // 已登录用户重定向到首页
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue'),
    meta: { requiresGuest: true }
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
    component: () => import('../views/RecommendView.vue'),
    meta: { requiresAuth: true }  // 需要登录
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('../views/CompareView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai',
    name: 'AI',
    component: () => import('../views/AIAssistant.vue')
  },
  // 捕获所有未匹配路由，重定向到首页
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  // 需要登录的页面
  if (to.meta.requiresAuth) {
    if (!userStore.isLoggedIn) {
      // 未登录，重定向到登录页
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
  }

  // 已登录用户访问登录/注册页，重定向到首页
  if (to.meta.requiresGuest && userStore.isLoggedIn) {
    next({ name: 'Home' })
    return
  }

  next()
})

export default router
