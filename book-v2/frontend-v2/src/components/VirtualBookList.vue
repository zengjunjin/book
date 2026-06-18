<template>
  <div class="virtual-book-list" ref="listRef">
    <!-- 顶部占位：撑开容器 -->
    <div :style="{ height: offsetY + 'px' }"></div>

    <!-- 可视卡片网格 -->
    <div
      class="virtual-grid"
      :style="{
        gridTemplateColumns: `repeat(auto-fill, minmax(${itemWidth}px, 1fr))`,
        gap: gap + 'px'
      }"
    >
      <BookCard
        v-for="item in visibleItems"
        :key="item.book.id"
        :book="item.book"
        :search-keyword="searchKeyword"
        :style="item.style"
        class="virtual-card"
        @click.stop="handleClick(item.book)"
      />
    </div>

    <!-- 底部占位 -->
    <div :style="{ height: bottomPad + 'px' }"></div>

    <!-- 滚动位置指示 -->
    <div v-if="scrollHint" class="scroll-hint">
      正在浏览 {{ books.length }} 本书
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import BookCard from './BookCard.vue'

const props = defineProps({
  books: { type: Array, required: true },
  itemHeight: { type: Number, default: 280 },
  itemWidth: { type: Number, default: 200 },
  gap: { type: Number, default: 20 },
  buffer: { type: Number, default: 3 },
  searchKeyword: { type: String, default: '' }
})

const emit = defineEmits(['click-book'])

const listRef = ref(null)

// 响应式列数（根据容器宽度计算）
const columns = ref(4)
const viewportTop = ref(0)
const viewportBottom = ref(0)
const showHint = ref(false)
let hintTimer = null

const scrollHint = computed(() => showHint.value)

// 计算总行数
const totalRows = computed(() => {
  const n = props.books.length
  if (n === 0) return 0
  return Math.ceil(n / columns.value)
})

// 计算每一行高度（卡片高度 + gap）
const rowHeight = computed(() => props.itemHeight + props.gap)

// 可视区域的 start / end 行索引
const startRow = computed(() => {
  const s = Math.floor(viewportTop.value / rowHeight.value) - props.buffer
  return Math.max(0, s)
})

const endRow = computed(() => {
  const e = Math.ceil(viewportBottom.value / rowHeight.value) + props.buffer
  return Math.min(totalRows.value, e)
})

// 顶部占位（未渲染的上方行）
const offsetY = computed(() => startRow.value * rowHeight.value)

// 底部占位（未渲染的下方行）
const bottomPad = computed(() => {
  const remaining = totalRows.value - endRow.value
  return Math.max(0, remaining * rowHeight.value)
})

// 可视 item 列表
const visibleItems = computed(() => {
  const start = startRow.value * columns.value
  const end = endRow.value * columns.value
  const slice = props.books.slice(start, end)
  return slice.map((book) => ({
    book,
    style: {}
  }))
})

// 测量列数
function measureColumns() {
  if (!listRef.value) return
  const width = listRef.value.clientWidth
  if (!width) return
  const colW = props.itemWidth + props.gap
  const cols = Math.max(1, Math.floor((width + props.gap) / colW))
  columns.value = cols
}

// 更新可视窗口（监听 window 滚动 + 元素位置）
function updateViewport() {
  if (!listRef.value) return
  const rect = listRef.value.getBoundingClientRect()
  const vh = window.innerHeight || document.documentElement.clientHeight

  // 列表顶部相对视口的偏移（负值表示滚过顶部）
  const listTopInViewport = rect.top
  const listHeight = rect.height

  // 可视区域相对列表的 top / bottom（px）
  const top = Math.max(0, -listTopInViewport)
  const bottom = Math.min(listHeight, vh - listTopInViewport)

  viewportTop.value = top
  viewportBottom.value = bottom
}

// 短暂显示滚动提示
function flashHint() {
  showHint.value = true
  if (hintTimer) clearTimeout(hintTimer)
  hintTimer = setTimeout(() => {
    showHint.value = false
  }, 800)
}

let rafId = null
function onScroll() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    updateViewport()
    flashHint()
  })
}

let resizeTimer = null
function onResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    measureColumns()
    updateViewport()
  }, 80)
}

function handleClick(book) {
  emit('click-book', book)
}

onMounted(() => {
  measureColumns()
  nextTick(() => {
    updateViewport()
  })
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', onResize)
  if (rafId) cancelAnimationFrame(rafId)
  if (hintTimer) clearTimeout(hintTimer)
  if (resizeTimer) clearTimeout(resizeTimer)
})

// books 变化时重新测量列数并更新视口
watch(
  () => props.books.length,
  () => {
    nextTick(() => {
      measureColumns()
      updateViewport()
    })
  }
)
</script>

<style scoped>
.virtual-book-list {
  position: relative;
  width: 100%;
}

.virtual-grid {
  display: grid;
}

.virtual-card {
  /* 让卡片高度保持一致，对齐虚拟滚动的 itemHeight */
  height: v-bind('itemHeight + "px"');
}

.scroll-hint {
  position: fixed;
  right: 24px;
  bottom: 24px;
  padding: 8px 14px;
  background: rgba(249, 115, 22, 0.9);
  color: #fff;
  font-size: 12px;
  border-radius: 20px;
  pointer-events: none;
  z-index: 100;
  animation: hintFadeIn 0.3s ease-out;
}

@keyframes hintFadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .scroll-hint {
    right: 12px;
    bottom: 12px;
    font-size: 11px;
    padding: 6px 12px;
  }
}
</style>
