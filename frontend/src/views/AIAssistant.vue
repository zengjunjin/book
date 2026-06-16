<template>
  <div class="ai-app">
    <!-- 动态背景光晕 -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>
    <div class="bg-noise"></div>

    <!-- 顶部栏 -->
    <header class="ai-header">
      <div class="header-left">
        <div class="brand-logo" @click="clearChat">
          <svg viewBox="0 0 32 32" class="logo-svg">
            <defs>
              <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#a855f7"/>
                <stop offset="50%" style="stop-color:#3b82f6"/>
                <stop offset="100%" style="stop-color:#06b6d4"/>
              </linearGradient>
            </defs>
            <rect x="4" y="4" width="24" height="24" rx="7" fill="url(#lg1)"/>
            <circle cx="13" cy="14" r="2.5" fill="#fff"/>
            <circle cx="19" cy="18" r="2.5" fill="#fff" opacity="0.7"/>
            <path d="M10 22 Q16 16 22 22" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.9"/>
          </svg>
        </div>
        <div class="brand-text">
          <div class="brand-title">Book AI</div>
          <div class="brand-sub">
            <span class="status-dot" :class="{online: ollamaOnline}"></span>
            {{ ollamaOnline ? '已连接本地模型' : '智能模式' }}
            · 全馆 {{ totalBooks.toLocaleString() }} 册可检索
          </div>
        </div>
      </div>

      <div class="header-right">
        <button class="chip-btn" @click="clearChat" title="清空对话">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          <span>新对话</span>
        </button>
        <button class="chip-btn ghost" @click="goHome" title="返回">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
      </div>
    </header>

    <!-- 对话主内容 -->
    <main class="chat-main" ref="chatScrollRef">
      <!-- 欢迎页 -->
      <div v-if="messages.length === 0" class="welcome-wrap">
        <div class="welcome-card">
          <div class="welcome-hero">
            <div class="hero-icon">
              <svg viewBox="0 0 48 48" width="48" height="48">
                <defs>
                  <linearGradient id="hero-g" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#a855f7"/>
                    <stop offset="100%" style="stop-color:#06b6d4"/>
                  </linearGradient>
                </defs>
                <circle cx="24" cy="24" r="22" fill="url(#hero-g)" opacity="0.25"/>
                <circle cx="24" cy="24" r="22" fill="none" stroke="url(#hero-g)" stroke-width="1.5" opacity="0.6"/>
                <text x="24" y="31" text-anchor="middle" font-size="22" font-weight="700" fill="#fff">📚</text>
              </svg>
            </div>
            <h1>你好，让我帮你探索好书</h1>
            <p class="hero-sub">输入书名查询详情 · 按主题推荐 · 找同类型作品</p>
          </div>

          <!-- 推荐提示 -->
          <div class="prompt-grid">
            <button v-for="(p, i) in quickPrompts" :key="i" class="prompt-card"
              :style="{animationDelay: (i * 60) + 'ms'}" @click="sendMessage(p.text)">
              <span class="prompt-emoji">{{ p.icon }}</span>
              <span class="prompt-text">{{ p.text }}</span>
              <span class="prompt-arrow">→</span>
            </button>
          </div>

          <!-- 热门书籍预览 -->
          <div v-if="hotBooks.length" class="hot-row">
            <div class="hot-row-header">
              <span class="hot-title">🔥 热门高分</span>
              <span class="hot-sub">来自 {{ totalBooks.toLocaleString() }} 册馆藏</span>
            </div>
            <div class="hot-book-row">
              <div v-for="(b, i) in hotBooks" :key="(b.book_id || b.id) + '-' + i"
                class="hot-book-card"
                :style="{animationDelay: (180 + i * 70) + 'ms'}"
                @click="sendMessage('介绍一下《' + b.title + '》')">
                <div class="hbc-cover" :style="coverStyle(b)">
                  <span class="hbc-letter">{{ bookLetter(b) }}</span>
                </div>
                <div class="hbc-info">
                  <div class="hbc-title" :title="b.title">{{ b.title }}</div>
                  <div class="hbc-author">{{ b.author || '未知作者' }}</div>
                  <div class="hbc-rating">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="#f59e0b"><path d="M12 2l3 7h7l-5.5 4.5L18 21l-6-4.5L6 21l1.5-7.5L2 9h7z"/></svg>
                    <span>{{ (b.avg_rating || 0).toFixed(1) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-else class="messages-wrap">
        <TransitionGroup name="msg">
          <div v-for="(msg, idx) in messages" :key="msg.id" class="msg-row" :class="msg.role">
            <div class="msg-avatar" :class="msg.role">
              <span v-if="msg.role === 'user'">{{ userInitial }}</span>
              <svg v-else viewBox="0 0 24 24" width="18" height="18">
                <defs>
                  <linearGradient :id="'av' + idx" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#a855f7"/>
                    <stop offset="100%" style="stop-color:#06b6d4"/>
                  </linearGradient>
                </defs>
                <circle cx="12" cy="12" r="11" :fill="'url(#av' + idx + ')'" opacity="0.25"/>
                <circle cx="12" cy="12" r="11" fill="none" :stroke="'url(#av' + idx + ')'" stroke-width="1.5" opacity="0.8"/>
                <text x="12" y="16" text-anchor="middle" font-size="11">🤖</text>
              </svg>
            </div>
            <div class="msg-body">
              <div class="msg-meta">
                <span class="msg-sender">{{ msg.role === 'user' ? '你' : 'Book AI' }}</span>
                <span class="msg-time">{{ msg.time }}</span>
                <span v-if="msg.intent" class="msg-intent">{{ intentLabel(msg.intent) }}</span>
              </div>
              <!-- 文本回复 -->
              <div v-if="msg.text" class="msg-bubble" :class="{typing: msg.isTyping}">
                <pre>{{ msg.text }}</pre>
                <span v-if="msg.isTyping" class="caret"></span>
              </div>
              <!-- 错误 -->
              <div v-if="msg.error" class="msg-error">
                <span class="err-icon">⚠</span>
                <span>{{ msg.error }}</span>
              </div>
              <!-- 书籍卡片 -->
              <div v-if="msg.books && msg.books.length" class="books-grid">
                <div v-for="(b, bi) in msg.books" :key="(b.book_id || b.id) + '-' + bi"
                  class="book-card"
                  :style="{animationDelay: (bi * 70) + 'ms'}"
                  @click="openBook(b)">
                  <div class="bc-cover" :style="coverStyle(b)">
                    <span class="bc-letter">{{ bookLetter(b) }}</span>
                    <div v-if="b.avg_rating" class="bc-rating">
                      <svg viewBox="0 0 24 24" width="10" height="10" fill="#f59e0b"><path d="M12 2l3 7h7l-5.5 4.5L18 21l-6-4.5L6 21l1.5-7.5L2 9h7z"/></svg>
                      {{ (b.avg_rating || 0).toFixed(1) }}
                    </div>
                  </div>
                  <div class="bc-info">
                    <div class="bc-title" :title="b.title">{{ b.title }}</div>
                    <div class="bc-author">{{ b.author || '未知作者' }}</div>
                    <div class="bc-meta">
                      <span v-if="b.year">{{ b.year }}</span>
                      <span v-if="b.rating_count" class="meta-dot">{{ b.rating_count }} 评价</span>
                    </div>
                    <div v-if="b.match_reason" class="bc-tag">{{ b.match_reason }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </TransitionGroup>

        <!-- AI正在输入提示 -->
        <div v-if="aiThinking" class="msg-row ai thinking">
          <div class="msg-avatar ai">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <circle cx="12" cy="12" r="11" fill="#a855f7" opacity="0.25"/>
              <circle cx="12" cy="12" r="11" fill="none" stroke="#a855f7" stroke-width="1.5" opacity="0.8"/>
              <text x="12" y="16" text-anchor="middle" font-size="11">🤖</text>
            </svg>
          </div>
          <div class="msg-body">
            <div class="thinking-box">
              <div class="thinking-dots"><span></span><span></span><span></span></div>
              <span>{{ thinkingText }}</span>
            </div>
          </div>
        </div>
        <div ref="scrollAnchor"></div>
      </div>
    </main>

    <!-- 输入区 -->
    <footer class="ai-footer">
      <div class="input-container">
        <div class="input-row">
          <textarea v-model="inputText" ref="inputRef" rows="1"
            placeholder="试试：《Harry Potter》讲什么？ 或 推荐几本科幻小说..."
            @keydown.enter.exact.prevent="onSend"
            @input="autoGrow"
            :disabled="isSending"
            class="chat-textarea"></textarea>
          <button class="send-btn" :disabled="isSending || !inputText.trim()" @click="onSend" :class="{active: inputText.trim()}">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7"/>
            </svg>
          </button>
        </div>
        <div class="quick-row">
          <button v-for="(q, i) in footerQuick" :key="i" class="quick-chip"
            @click="sendMessage(q)" :disabled="isSending">{{ q }}</button>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, computed } from 'vue'
import { aiAPI } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const messages = ref([])
const inputText = ref('')
const isSending = ref(false)
const aiThinking = ref(false)
const ollamaOnline = ref(false)
const hotBooks = ref([])
const totalBooks = ref(0)
const chatScrollRef = ref(null)
const inputRef = ref(null)
let msgId = 0

// 快速提示
const quickPrompts = [
  { icon: '🔍', text: '《Harry Potter》这本书讲什么？' },
  { icon: '💡', text: '推荐 5 本科幻小说经典' },
  { icon: '📖', text: '我想看历史主题的书，有哪些推荐？' },
  { icon: '🎯', text: '类似《The Da Vinci Code》的悬疑作品' },
]

const footerQuick = [
  'Harry Potter',
  '科幻小说',
  '历史书籍',
  '悬疑推理',
  '经典文学',
]

const userInitial = '我'

function intentLabel(i) {
  const map = { greeting: '问候', detail: '书籍详情', recommend: '推荐', similar: '相似', search: '搜索', unknown: '对话' }
  return map[i] || '对话'
}

// 封面颜色
const palettes = [
  ['#a855f7', '#3b82f6'], ['#ec4899', '#f97316'], ['#06b6d4', '#22c55e'],
  ['#f59e0b', '#ef4444'], ['#8b5cf6', '#06b6d4'], ['#10b981', '#3b82f6'],
  ['#f43f5e', '#8b5cf6'], ['#0ea5e9', '#14b8a6'], ['#fb923c', '#ec4899'],
]
function coverStyle(b) {
  const id = Number(b.book_id || b.id || b.title?.length || 1) || 1
  const [c1, c2] = palettes[id % palettes.length]
  return { background: `linear-gradient(135deg, ${c1} 0%, ${c2} 100%)` }
}
function bookLetter(b) {
  const t = (b.title || '?').trim()
  return t.charAt(0).toUpperCase()
}

function nowTime() {
  const d = new Date()
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
}
function scrollToBottom() {
  nextTick(() => {
    const el = chatScrollRef.value
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  })
}
function autoGrow() {
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  })
}

function addMessage(role, text = '', opts = {}) {
  const msg = {
    id: ++msgId,
    role,
    text,
    time: nowTime(),
    books: opts.books || [],
    intent: opts.intent || null,
    isTyping: false,
    error: opts.error || null,
  }
  messages.value.push(msg)
  scrollToBottom()
  return msg
}

// 打字机效果
async function typeText(msg, fullText, speed = 12) {
  msg.isTyping = true
  msg.text = ''
  for (let i = 0; i < fullText.length; i++) {
    msg.text += fullText[i]
    if (i % 3 === 0) await new Promise(r => setTimeout(r, speed))
  }
  msg.isTyping = false
}

async function onSend() {
  const txt = inputText.value.trim()
  if (!txt || isSending.value) return
  inputText.value = ''
  autoGrow()
  sendMessage(txt)
}

const thinkingText = computed(() => {
  const texts = ['正在检索馆藏...', '正在理解你的问题...', '正在生成回复...', '查询中...']
  return texts[Math.floor(Date.now() / 2000) % texts.length]
})

async function sendMessage(text) {
  if (!text || isSending.value) return
  addMessage('user', text)
  aiThinking.value = true
  isSending.value = true
  try {
    const data = await aiAPI.chat(text)
    aiThinking.value = false
    const aiMsg = addMessage('ai', '', { intent: data.intent })
    const reply = data.reply || (data.books && data.books.length ? '为你找到以下书籍：' : '抱歉，我没有找到相关信息。')
    const books = (data.books || []).slice(0, 8).filter(b => b && (b.book_id || b.id) && b.title)
    if (books.length) aiMsg.books = books
    // 打字机
    await typeText(aiMsg, reply, 10)
  } catch (err) {
    aiThinking.value = false
    addMessage('ai', '', { error: '无法连接到 AI 服务，请稍后重试。' })
    console.error(err)
  } finally {
    isSending.value = false
    nextTick(() => {
      const el = inputRef.value
      if (el) el.focus()
    })
  }
}

function openBook(b) {
  const id = b.book_id || b.id
  if (id) router.push('/book/' + id)
  else sendMessage('介绍一下《' + b.title + '》')
}

function clearChat() {
  messages.value = []
  inputText.value = ''
}

function goHome() {
  router.push('/')
}

onMounted(async () => {
  try {
    const data = await aiAPI.getStatus()
    ollamaOnline.value = !!(data && data.ollama && data.ollama.available)
    if (data && data.library) totalBooks.value = Number(data.library.total_books) || 0
  } catch(e) { console.warn(e) }

  try {
    const hot = await aiAPI.getPopular(6)
    hotBooks.value = (hot && hot.books || []).filter(b => b && (b.book_id || b.id) && b.title).slice(0, 6)
  } catch(e) { console.warn(e) }
})
</script>

<style>
/* 基础重置 */
.ai-app, .ai-app * { box-sizing: border-box; }
</style>

<style scoped>
/* ============ 全局 ============ */
.ai-app {
  position: relative;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0a0a0f;
  color: #e4e4e7;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 背景光晕 */
.bg-orbs {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  animation: orb-float 18s ease-in-out infinite;
}
.orb-1 {
  width: 520px; height: 520px;
  background: radial-gradient(circle, #a855f7 0%, transparent 70%);
  top: -120px; left: -100px;
}
.orb-2 {
  width: 480px; height: 480px;
  background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
  top: 30%; right: -120px;
  animation-delay: -6s;
}
.orb-3 {
  width: 440px; height: 440px;
  background: radial-gradient(circle, #3b82f6 0%, transparent 70%);
  bottom: -150px; left: 30%;
  animation-delay: -12s;
}
@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -30px) scale(1.1); }
  66% { transform: translate(-30px, 40px) scale(0.95); }
}
.bg-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 3px 3px;
  z-index: 1;
  opacity: 0.4;
}

/* ============ 顶部栏 ============ */
.ai-header {
  position: relative;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: rgba(15, 15, 25, 0.6);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.header-left {
  display: flex; align-items: center; gap: 14px;
}
.brand-logo {
  width: 42px; height: 42px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: transform 0.2s;
}
.brand-logo:hover { transform: scale(1.05); }
.logo-svg { width: 42px; height: 42px; filter: drop-shadow(0 4px 14px rgba(168, 85, 247, 0.4)); }
.brand-text .brand-title {
  font-size: 17px; font-weight: 700;
  background: linear-gradient(135deg, #fff 0%, #c4b5fd 60%, #67e8f9 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.3px;
}
.brand-sub {
  font-size: 12px; color: #71717a; margin-top: 2px; display: flex; align-items: center; gap: 6px;
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #52525b;
  display: inline-block; position: relative;
}
.status-dot.online { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); }

.header-right { display: flex; gap: 10px; align-items: center; }
.chip-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 8px 14px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  color: #e4e4e7;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.chip-btn:hover {
  background: rgba(168, 85, 247, 0.15);
  border-color: rgba(168, 85, 247, 0.35);
  color: #fff;
  transform: translateY(-1px);
}
.chip-btn.ghost { padding: 8px 10px; }

/* ============ 对话区 ============ */
.chat-main {
  position: relative;
  z-index: 5;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}
.chat-main::-webkit-scrollbar { width: 6px; }
.chat-main::-webkit-scrollbar-track { background: transparent; }
.chat-main::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
.chat-main::-webkit-scrollbar-thumb:hover { background: rgba(168,85,247,0.3); }

/* ============ 欢迎页 ============ */
.welcome-wrap {
  max-width: 860px;
  margin: 0 auto;
  padding: 5vh 32px 48px;
}
.welcome-card {
  animation: hero-in 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes hero-in {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.welcome-hero {
  text-align: center;
  padding: 40px 20px 28px;
}
.hero-icon { display: inline-block; margin-bottom: 18px; }
.welcome-hero h1 {
  font-size: 32px; font-weight: 700;
  margin: 0 0 10px;
  background: linear-gradient(135deg, #fff 0%, #c4b5fd 50%, #67e8f9 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}
.hero-sub { color: #71717a; font-size: 14px; margin: 0; }

/* 快速提示卡片 */
.prompt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin: 28px 0;
}
.prompt-card {
  display: flex; align-items: center; gap: 12px;
  padding: 18px 20px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  text-align: left;
  color: #e4e4e7;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  animation: card-in 0.5s forwards;
  font-family: inherit;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.prompt-card:hover {
  background: rgba(168, 85, 247, 0.08);
  border-color: rgba(168, 85, 247, 0.3);
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(168, 85, 247, 0.15);
}
.prompt-emoji { font-size: 20px; }
.prompt-text { flex: 1; font-size: 13.5px; color: #d4d4d8; font-weight: 500; line-height: 1.45; }
.prompt-arrow { color: #a1a1aa; font-size: 16px; transition: transform 0.2s, color 0.2s; font-weight: 600; }
.prompt-card:hover .prompt-arrow { color: #c4b5fd; transform: translateX(4px); }

/* 热门书籍行 */
.hot-row {
  margin-top: 32px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 20px;
  padding: 24px;
}
.hot-row-header {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 18px;
}
.hot-title { font-size: 15px; font-weight: 600; color: #f4f4f5; }
.hot-sub { font-size: 12px; color: #71717a; }

.hot-book-row {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px;
}
.hot-book-card {
  display: flex; gap: 12px;
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  animation: card-in 0.5s forwards;
}
.hot-book-card:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(168, 85, 247, 0.3);
  transform: translateY(-3px);
  box-shadow: 0 10px 28px rgba(0,0,0,0.3);
}
.hbc-cover {
  width: 52px; height: 70px;
  border-radius: 8px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 14px rgba(0,0,0,0.3);
  position: relative;
}
.hbc-letter { font-size: 22px; font-weight: 800; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.hbc-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.hbc-title {
  font-size: 13px; font-weight: 600; color: #e4e4e7;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  line-height: 1.4;
}
.hbc-author { font-size: 11.5px; color: #71717a; }
.hbc-rating { display: flex; align-items: center; gap: 3px; font-size: 11.5px; color: #fbbf24; font-weight: 600; margin-top: auto; }

/* ============ 消息 ============ */
.messages-wrap {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 32px 32px;
  display: flex; flex-direction: column; gap: 28px;
}

.msg-row { display: flex; gap: 14px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }

.msg-avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
}
.msg-avatar.user {
  background: linear-gradient(135deg, #475569 0%, #1e293b 100%);
  color: #e2e8f0;
  border: 1px solid rgba(255,255,255,0.08);
}
.msg-avatar.ai {
  background: transparent;
}

.msg-body { max-width: calc(100% - 50px); }
.msg-meta {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px;
  font-size: 11.5px;
  color: #71717a;
}
.msg-row.user .msg-meta { justify-content: flex-end; }
.msg-sender { font-weight: 600; color: #a1a1aa; font-size: 12px; }
.msg-time { color: #52525b; }
.msg-intent {
  padding: 2px 8px;
  background: rgba(168, 85, 247, 0.15);
  color: #c4b5fd;
  border-radius: 100px;
  font-size: 10.5px;
  font-weight: 500;
}

.msg-bubble {
  padding: 14px 18px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  font-size: 14.5px;
  line-height: 1.7;
  color: #e4e4e7;
  white-space: pre-wrap;
  word-wrap: break-word;
  position: relative;
}
.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.18) 0%, rgba(59, 130, 246, 0.18) 100%);
  border: 1px solid rgba(168, 85, 247, 0.25);
  color: #f4f4f5;
}
.msg-bubble pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  font-size: inherit;
  line-height: inherit;
  color: inherit;
}
.msg-bubble.typing .caret {
  display: inline-block; width: 2px; height: 1.1em;
  background: #c4b5fd; vertical-align: text-bottom;
  margin-left: 2px;
  animation: blink 0.8s steps(2) infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* 错误 */
.msg-error {
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 12px;
  font-size: 13.5px;
  color: #fca5a5;
  display: flex; gap: 10px; align-items: center;
}

/* ============ 书籍卡片网格 ============ */
.books-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.book-card {
  display: flex; gap: 12px;
  padding: 14px;
  background: rgba(255,255,255,0.035);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  animation: card-in 0.5s forwards;
}
.book-card:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(168, 85, 247, 0.3);
  transform: translateY(-3px);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.25);
}
.bc-cover {
  width: 58px; height: 78px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(0,0,0,0.3);
  position: relative;
}
.bc-letter { font-size: 22px; font-weight: 800; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.bc-rating {
  position: absolute;
  bottom: -8px; right: -8px;
  background: rgba(15,15,25,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  padding: 2px 7px;
  border-radius: 100px;
  font-size: 10.5px;
  font-weight: 700;
  color: #fbbf24;
  display: inline-flex; align-items: center; gap: 2px;
}
.bc-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.bc-title {
  font-size: 13.5px; font-weight: 600; color: #e4e4e7;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  line-height: 1.4;
}
.bc-author { font-size: 11.5px; color: #71717a; }
.bc-meta { font-size: 11px; color: #52525b; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.meta-dot::before { content: '·'; margin-right: 6px; color: #3f3f46; }
.bc-tag {
  margin-top: auto;
  padding: 3px 8px;
  background: rgba(168, 85, 247, 0.12);
  border-radius: 6px;
  font-size: 10.5px;
  color: #c4b5fd;
  font-weight: 500;
  align-self: flex-start;
}

/* ============ 消息动画 ============ */
.msg-enter-active, .msg-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.msg-enter-from { opacity: 0; transform: translateY(10px); }
.msg-leave-to { opacity: 0; }

/* ============ 正在思考 ============ */
.thinking-box {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 14px 18px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  font-size: 13.5px;
  color: #a1a1aa;
}
.thinking-dots { display: inline-flex; gap: 4px; }
.thinking-dots span {
  width: 6px; height: 6px;
  background: linear-gradient(135deg, #a855f7, #06b6d4);
  border-radius: 50%;
  animation: bounce-dot 1.4s ease-in-out infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce-dot {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.6; }
  30% { transform: translateY(-5px); opacity: 1; }
}

/* ============ 底部输入 ============ */
.ai-footer {
  position: relative;
  z-index: 10;
  padding: 20px 32px 28px;
  background: linear-gradient(180deg, transparent 0%, rgba(10, 10, 15, 0.85) 40%);
}
.input-container { max-width: 860px; margin: 0 auto; }
.input-row {
  display: flex; align-items: flex-end; gap: 10px;
  padding: 10px 10px 10px 20px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  transition: all 0.2s;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
.input-row:focus-within {
  border-color: rgba(168, 85, 247, 0.4);
  box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.1), 0 8px 32px rgba(0,0,0,0.3);
}
.chat-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #e4e4e7;
  font-size: 14.5px;
  font-family: inherit;
  line-height: 1.6;
  resize: none;
  padding: 6px 0;
  min-height: 26px;
  max-height: 180px;
}
.chat-textarea::placeholder { color: #52525b; }
.chat-textarea:disabled { opacity: 0.5; }

.send-btn {
  width: 40px; height: 40px;
  border-radius: 14px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: #a1a1aa;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { transform: translateY(-1px); }
.send-btn.active {
  background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 6px 18px rgba(168, 85, 247, 0.35);
}
.send-btn.active:hover:not(:disabled) {
  box-shadow: 0 8px 24px rgba(168, 85, 247, 0.45);
}
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 底部快速按钮 */
.quick-row {
  display: flex; gap: 8px; justify-content: center;
  margin-top: 14px; flex-wrap: wrap;
}
.quick-chip {
  padding: 7px 14px;
  background: transparent;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 100px;
  color: #a1a1aa;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.quick-chip:hover:not(:disabled) {
  background: rgba(168, 85, 247, 0.1);
  border-color: rgba(168, 85, 247, 0.3);
  color: #c4b5fd;
  transform: translateY(-1px);
}
.quick-chip:disabled { opacity: 0.4; cursor: not-allowed; }

/* ============ 响应式 ============ */
@media (max-width: 768px) {
  .ai-header { padding: 14px 16px; }
  .welcome-wrap { padding: 4vh 16px 32px; }
  .messages-wrap { padding: 24px 16px; }
  .ai-footer { padding: 14px 16px 20px; }
  .welcome-hero h1 { font-size: 24px; }
  .brand-sub { display: none; }
  .books-grid { grid-template-columns: 1fr; }
}
</style>
