<!--
  🤖 AI 内容创作助手 - 前端界面
  整合：对话、书评、推荐、知识图谱、阅读报告
-->

<template>
  <div class="ai-assistant">
    <!-- 顶部工具栏 -->
    <div class="ai-toolbar">
      <div class="toolbar-left">
        <h1>
          <span class="emoji">🤖</span>
          AI 书籍助手
        </h1>
        <span class="subtitle">你的智能阅读伙伴</span>
      </div>
      <div class="toolbar-right">
        <span class="status-badge" :class="statusMode">
          <span class="dot"></span>
          {{ statusMode === 'llm' ? 'AI 在线' : '智能模式' }}
        </span>
      </div>
    </div>

    <!-- 功能切换 Tab -->
    <div class="feature-tabs" :class="{ 'tabs-animating': isTabSwitching }">
      <button
        v-for="(tab, index) in featureTabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        :style="{ animationDelay: `${index * 50}ms` }"
        @click="switchTab(tab.id)"
      >
        <span class="tab-emoji">{{ tab.emoji }}</span>
        <span class="tab-name">{{ tab.name }}</span>
      </button>
    </div>

    <!-- 搜索栏 -->
    <div v-if="activeTab === 'chat'" class="search-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索书籍..."
        class="search-input"
        @keyup.enter="searchBooks"
      />
      <button class="search-btn" @click="searchBooks">🔍</button>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searchResults.length > 0" class="search-results">
      <div
        v-for="book in searchResults"
        :key="book.id"
        class="search-result-item"
        @click="selectBook(book)"
      >
        <span class="book-title">《{{ book.title }}》</span>
        <span class="book-author">{{ book.author }}</span>
      </div>
    </div>

    <!-- 聊天对话界面 -->
    <div v-if="activeTab === 'chat'" class="chat-panel">
      <!-- 消息区 -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- 欢迎消息 -->
        <div class="message ai-message welcome-message" v-if="messages.length === 0">
          <div class="msg-avatar">🤖</div>
          <div class="msg-content">
            <div class="msg-header">AI 助手</div>
            <div class="msg-text">
              你好！我是你的书籍 AI 助手 📚
              <br /><br />
              我可以帮你：
              <br />• 生成个性化书评
              <br />• 推荐适合的书籍
              <br />• 分析书籍主题和知识图谱
              <br />• 生成你的阅读报告
              <br /><br />
              试试看，问我点什么吧！
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message"
          :class="[
            msg.role === 'user' ? 'user-message' : 'ai-message',
            msg.isTyping ? 'typing-message' : '',
            'slide-in-' + (index % 2 === 0 ? 'left' : 'right')
          ]"
        >
          <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="msg-content">
            <div class="msg-header">
              {{ msg.role === 'user' ? '你' : 'AI 助手' }}
              <span class="msg-time">{{ msg.time }}</span>
            </div>
            <!-- 打字机效果显示AI回复 -->
            <div class="msg-text" v-if="msg.role === 'assistant'">
              <span v-if="!msg.isTyping" v-html="formatMessage(msg.content)"></span>
              <span v-else class="typing-cursor">{{ displayedTexts[index] || '' }}</span>
            </div>
            <div class="msg-text" v-else v-html="formatMessage(msg.content)"></div>

            <!-- 推荐操作 -->
            <div v-if="msg.suggestedActions && !msg.isTyping" class="suggested-actions">
              <button
                v-for="action in msg.suggestedActions"
                :key="action.text"
                class="suggestion-btn"
                @click="sendMessage(action.text)"
              >
                <span>{{ action.icon }} {{ action.text }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 加载指示器 -->
        <div class="message ai-message loading" v-if="isLoading">
          <div class="msg-avatar">🤖</div>
          <div class="msg-content">
            <div class="msg-header">AI 助手 <span class="typing">正在思考...</span></div>
            <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="quick-actions">
        <button class="quick-btn" @click="quickAction('review')">📝 写书评</button>
        <button class="quick-btn" @click="quickAction('recommend')">🎯 推荐书籍</button>
        <button class="quick-btn" @click="quickAction('analyze')">🔍 分析书籍</button>
        <button class="quick-btn" @click="quickAction('report')">📊 阅读报告</button>
      </div>

      <!-- 输入框 -->
      <div class="chat-input-area">
        <textarea
          v-model="inputMessage"
          placeholder="输入消息，或试试：给《三体》写一篇书评..."
          class="chat-input"
          rows="2"
          @keydown.enter.exact.prevent="sendMessage()"
          @keydown.enter.shift.exact="inputMessage += '\n'"
        ></textarea>
        <button
          class="send-btn"
          :disabled="isLoading || !inputMessage.trim()"
          @click="sendMessage()"
        >
          <span>发送</span>
          <span class="send-emoji">➤</span>
        </button>
      </div>
    </div>

    <!-- 书评生成面板 -->
    <div v-if="activeTab === 'review'" class="review-panel panel-content">
      <div class="panel-section">
        <h3>📝 生成书评</h3>
        <div class="input-group">
          <label>书籍ID</label>
          <input v-model="reviewBookId" type="number" placeholder="输入书籍 ID（例如 5）" />
        </div>
        <div class="input-group">
          <label>书评风格</label>
          <select v-model="reviewStyle">
            <option value="personal">💭 个人读后感</option>
            <option value="professional">📖 专业书评</option>
            <option value="humorous">😄 幽默吐槽</option>
            <option value="academic">🎓 学术分析</option>
          </select>
        </div>
        <button class="primary-btn" :disabled="isGenerating" @click="generateReview">
          <span v-if="!isGenerating">✨</span>
          <span :class="{ 'btn-loading': isGenerating }">
            {{ isGenerating ? '生成中...' : '生成书评' }}
          </span>
        </button>
      </div>

      <!-- 书评结果 -->
      <div class="panel-section result-section" v-if="generatedReview">
        <h3>{{ generatedReview.title }}</h3>
        <div class="meta-info">
          <span>📚 《{{ generatedReview.book_title }}》</span>
          <span>✍️ {{ generatedReview.author }}</span>
          <span>⭐ {{ generatedReview.rating }}/10</span>
        </div>
        <div class="tags">
          <span v-for="tag in generatedReview.tags" :key="tag" class="tag">#{{ tag }}</span>
        </div>
        <div class="highlights">
          <h4>🌟 亮点</h4>
          <ul>
            <li v-for="h in generatedReview.highlights" :key="h">{{ h }}</li>
          </ul>
        </div>
        <div class="content" v-html="formatMessage(generatedReview.content)"></div>
        <div class="target-readers">
          <strong>🎯 适合读者：</strong> {{ generatedReview.target_readers }}
        </div>
        <div class="generation-info">
          生成方式: {{ generatedReview.mode === 'llm' ? 'AI 生成' : '智能模板' }} ·
          模型: {{ generatedReview.model }}
        </div>
      </div>
    </div>

    <!-- 知识图谱面板 -->
    <div v-if="activeTab === 'knowledge'" class="knowledge-panel panel-content">
      <div class="panel-section">
        <h3>🧠 书籍知识图谱</h3>
        <div class="input-group">
          <label>书籍ID</label>
          <input v-model="kgBookId" type="number" placeholder="输入书籍 ID" />
        </div>
        <button class="primary-btn" :disabled="isGenerating" @click="generateKnowledgeGraph">
          <span v-if="!isGenerating">🔗</span>
          <span :class="{ 'btn-loading': isGenerating }">
            {{ isGenerating ? '分析中...' : '生成知识图谱' }}
          </span>
        </button>
      </div>

      <div class="panel-section result-section" v-if="knowledgeGraph">
        <h3>《{{ knowledgeGraph.book_title }}》知识图谱</h3>
        <p class="summary">{{ knowledgeGraph.summary }}</p>

        <!-- 主题标签 -->
        <div class="themes-section">
          <h4>📌 核心主题</h4>
          <div class="themes">
            <span v-for="theme in knowledgeGraph.themes" :key="theme" class="theme-tag">
              {{ theme }}
            </span>
          </div>
        </div>

        <!-- Mermaid 思维导图 -->
        <div class="mermaid-container">
          <h4>🗺️ 思维导图</h4>
          <pre class="mermaid-code">{{ knowledgeGraphMermaid }}</pre>
        </div>

        <!-- 节点和边 -->
        <div class="graph-stats">
          <div class="stat-card">
            <div class="stat-number">{{ knowledgeGraph.nodes.length }}</div>
            <div class="stat-label">节点</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ knowledgeGraph.edges.length }}</div>
            <div class="stat-label">关系</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ knowledgeGraph.tags.length }}</div>
            <div class="stat-label">标签</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 阅读报告面板 -->
    <div v-if="activeTab === 'report'" class="report-panel panel-content">
      <div class="panel-section">
        <h3>📊 我的阅读报告</h3>
        <p class="hint">分析你的阅读数据，生成个性化报告</p>
        <button class="primary-btn" :disabled="isGenerating" @click="generateReport">
          <span v-if="!isGenerating">📈</span>
          <span :class="{ 'btn-loading': isGenerating }">
            {{ isGenerating ? '生成中...' : '生成阅读报告' }}
          </span>
        </button>
      </div>

      <div class="panel-section result-section" v-if="readingReport">
        <h3>阅读报告</h3>
        <p class="personality">{{ readingReport.personality_type }}</p>

        <!-- 统计卡片 -->
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-number">{{ readingReport.stats.total_books }}</div>
            <div class="stat-label">已读书籍</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ readingReport.stats.avg_rating }}</div>
            <div class="stat-label">平均评分</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ readingReport.stats.highest_rating }}</div>
            <div class="stat-label">最高评分</div>
          </div>
        </div>

        <!-- 个性化洞察 -->
        <div class="insights-section">
          <h4>🔍 个性化洞察</h4>
          <ul>
            <li v-for="insight in readingReport.insights" :key="insight">{{ insight }}</li>
          </ul>
        </div>

        <!-- 摘要 -->
        <div class="report-summary">
          <h4>📝 报告摘要</h4>
          <div v-html="formatMessage(readingReport.summary)"></div>
        </div>

        <!-- 推荐书籍 -->
        <div class="recommendations-section">
          <h4>📚 为你推荐</h4>
          <div class="recommendation-card" v-for="rec in readingReport.recommendations" :key="rec.title">
            <div class="rec-title">《{{ rec.title }}》</div>
            <div class="rec-author">{{ rec.author }}</div>
            <div class="rec-reason">{{ rec.reason }}</div>
            <div class="rec-score">匹配度: {{ rec.match_score }}%</div>
          </div>
        </div>

        <div class="generation-info">
          模型: {{ readingReport.model }}
        </div>
      </div>
    </div>

    <!-- 书籍摘要面板 -->
    <div v-if="activeTab === 'summary'" class="summary-panel panel-content">
      <div class="panel-section">
        <h3>📖 书籍摘要</h3>
        <div class="input-group">
          <label>书籍ID</label>
          <input v-model="summaryBookId" type="number" placeholder="输入书籍 ID" />
        </div>
        <button class="primary-btn" :disabled="isGenerating" @click="generateSummary">
          <span v-if="!isGenerating">📝</span>
          <span :class="{ 'btn-loading': isGenerating }">
            {{ isGenerating ? '生成中...' : '生成摘要' }}
          </span>
        </button>
      </div>

      <div class="panel-section result-section" v-if="bookSummary">
        <h3>《{{ bookSummary.title }}》</h3>
        <p class="one-line">{{ bookSummary.one_line }}</p>

        <div class="summary-section">
          <h4>📋 概述</h4>
          <p>{{ bookSummary.overview }}</p>
        </div>

        <div class="themes-section">
          <h4>🎯 核心主题</h4>
          <div class="tags">
            <span v-for="theme in bookSummary.themes" :key="theme" class="tag">{{ theme }}</span>
          </div>
        </div>

        <div class="summary-section">
          <h4>⭐ 亮点</h4>
          <ul>
            <li v-for="(highlight, i) in bookSummary.highlights" :key="i">{{ highlight }}</li>
          </ul>
        </div>

        <div class="target-section">
          <h4>👥 目标读者</h4>
          <p>{{ bookSummary.target_audience }}</p>
        </div>

        <div class="guide-section">
          <h4>📖 阅读建议</h4>
          <p>{{ bookSummary.reading_guide }}</p>
        </div>

        <div class="generation-info">
          生成方式: {{ bookSummary.mode === 'llm' ? 'AI 生成' : '智能模板' }}
        </div>
      </div>
    </div>

    <!-- 完整分析面板 -->
    <div v-if="activeTab === 'analyze'" class="analyze-panel panel-content">
      <div class="panel-section">
        <h3>🔍 完整书籍分析</h3>
        <div class="input-group">
          <label>书籍ID</label>
          <input v-model="analyzeBookId" type="number" placeholder="输入书籍 ID" />
        </div>
        <button class="primary-btn" :disabled="isGenerating" @click="generateAnalysis">
          <span v-if="!isGenerating">🔍</span>
          <span :class="{ 'btn-loading': isGenerating }">
            {{ isGenerating ? '分析中...' : '开始分析' }}
          </span>
        </button>
      </div>

      <div class="panel-section result-section" v-if="bookAnalysis">
        <!-- 书籍画像 -->
        <div v-if="bookAnalysis.profile" class="profile-section">
          <h3>《{{ bookAnalysis.profile.title }}》</h3>
          <div class="meta-info">
            <span>✍️ {{ bookAnalysis.profile.author }}</span>
            <span v-if="bookAnalysis.profile.publisher">{{ bookAnalysis.profile.publisher }}</span>
            <span>⭐ {{ bookAnalysis.profile.avg_rating }}/10</span>
            <span>👥 {{ bookAnalysis.profile.rating_count }}人评价</span>
          </div>
          <div class="tags">
            <span v-for="tag in bookAnalysis.profile.tags" :key="tag" class="tag">#{{ tag }}</span>
          </div>
        </div>

        <!-- 摘要 -->
        <div v-if="bookAnalysis.summary" class="summary-section">
          <h4>📖 摘要</h4>
          <p class="one-line">{{ bookAnalysis.summary.one_line }}</p>
          <p>{{ bookAnalysis.summary.overview }}</p>
        </div>

        <!-- 相似书籍 -->
        <div v-if="bookAnalysis.similar_books && bookAnalysis.similar_books.length > 0" class="similar-section">
          <h4>📚 相似书籍</h4>
          <div class="similar-books">
            <div v-for="book in bookAnalysis.similar_books" :key="book.book_id" class="similar-book-card">
              <div class="similar-title">《{{ book.title }}》</div>
              <div class="similar-author">{{ book.author }}</div>
              <div class="similar-score">相似度: {{ (book.similarity * 100).toFixed(0) }}%</div>
            </div>
          </div>
        </div>

        <!-- 统计 -->
        <div class="graph-stats">
          <div class="stat-card">
            <div class="stat-number">{{ bookAnalysis.profile?.rating_count || 0 }}</div>
            <div class="stat-label">评价人数</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ bookAnalysis.profile?.avg_rating || 0 }}</div>
            <div class="stat-label">平均评分</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{{ bookAnalysis.similar_books?.length || 0 }}</div>
            <div class="stat-label">相似书籍</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'

// ========== 状态 ==========
const activeTab = ref('chat')
const inputMessage = ref('')
const messages = ref([])
const isLoading = ref(false)
const statusMode = ref('simulate')
const conversationId = ref(null)
const isTabSwitching = ref(false)
const displayedTexts = ref({})

// 书评
const reviewBookId = ref(5)
const reviewStyle = ref('personal')
const generatedReview = ref(null)
const isGenerating = ref(false)

// 知识图谱
const kgBookId = ref(5)
const knowledgeGraph = ref(null)
const knowledgeGraphMermaid = ref('')

// 阅读报告
const readingReport = ref(null)

// 搜索相关
const searchQuery = ref('')
const searchResults = ref([])

// 书籍摘要
const summaryBookId = ref(5)
const bookSummary = ref(null)

// 完整分析
const analyzeBookId = ref(5)
const bookAnalysis = ref(null)

const messagesContainer = ref(null)

// ========== Tab 配置 ==========
const featureTabs = [
  { id: 'chat', name: 'AI 对话', emoji: '💬' },
  { id: 'review', name: '书评生成', emoji: '📝' },
  { id: 'summary', name: '书籍摘要', emoji: '📖' },
  { id: 'analyze', name: '完整分析', emoji: '🔍' },
  { id: 'knowledge', name: '知识图谱', emoji: '🧠' },
  { id: 'report', name: '阅读报告', emoji: '📊' },
]

// ========== 初始化 ==========
onMounted(async () => {
  try {
    const response = await fetch('/api/ai/status')
    const data = await response.json()
    statusMode.value = data.status.mode
  } catch (e) {
    statusMode.value = 'simulate'
  }
  conversationId.value = `conv_${Date.now()}`
})

// ========== Tab 切换 ==========
function switchTab(tabId) {
  if (tabId === activeTab.value) return
  isTabSwitching.value = true
  setTimeout(() => {
    activeTab.value = tabId
    setTimeout(() => {
      isTabSwitching.value = false
    }, 300)
  }, 100)
}

// ========== 消息格式化 ==========
function formatMessage(text) {
  if (!text) return ''

  // 简单的 markdown 支持
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 加粗
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // 换行
  html = html.replace(/\n/g, '<br />')

  // 列表项
  html = html.replace(/(?:^|\n)\s*[•\-]\s+(.+?)(?=\n|$)/g, '<li>$1</li>')

  return html
}

// ========== 打字机效果 ==========
async function typeText(index, text) {
  const message = messages.value[index]
  if (!message) return

  message.isTyping = true
  displayedTexts.value[index] = ''
  const chars = text.split('')

  for (let i = 0; i < chars.length; i++) {
    await new Promise(resolve => setTimeout(resolve, 15 + Math.random() * 10))
    displayedTexts.value[index] = text.substring(0, i + 1)
  }

  message.isTyping = false
  displayedTexts.value[index] = ''
}

// ========== 对话功能 ==========
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function sendMessage(message) {
  const msg = message || inputMessage.value.trim()
  if (!msg || isLoading.value) return

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: msg,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
  })
  inputMessage.value = ''
  isLoading.value = true
  scrollToBottom()

  // 先添加一个占位的 AI 消息，用于流式填充
  const aiMsgIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    suggestedActions: [],
    isTyping: true,
  })
  displayedTexts.value[aiMsgIndex] = ''
  scrollToBottom()

  let streamSucceeded = false

  try {
    // ===== 1. 优先尝试 SSE 流式接口 =====
    const streamResponse = await fetch('/api/ai/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        conversation_id: conversationId.value,
        user_id: 8,
      }),
    })

    if (streamResponse.ok && streamResponse.body) {
      const reader = streamResponse.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      let fullText = ''
      let receivedStart = false
      let gotError = false
      let errorMsg = ''
      let done = false

      while (!done) {
        const { value, done: chunkDone } = await reader.read()
        if (chunkDone) {
          done = true
          break
        }
        buffer += decoder.decode(value, { stream: true })

        // 按行解析 SSE（每个事件由空行分隔）
        let lineBreakIndex
        while ((lineBreakIndex = buffer.indexOf('\n')) !== -1) {
          const rawLine = buffer.slice(0, lineBreakIndex)
          buffer = buffer.slice(lineBreakIndex + 1)
          const line = rawLine.replace(/\r$/, '').trim()

          if (line === '') continue

          // 解析 "data: xxx" 或自定义标记
          let payload = line
          if (line.startsWith('data:')) {
            payload = line.slice(5).trim()
          } else if (line.startsWith('event:')) {
            // 事件名，忽略
            continue
          }

          if (!payload) continue

          // 自定义标记：开始 / 结束 / 错误
          if (payload === '[START]') {
            receivedStart = true
            fullText = ''
            displayedTexts.value[aiMsgIndex] = ''
            messages.value[aiMsgIndex].content = ''
            scrollToBottom()
            continue
          }
          if (payload === '[DONE]') {
            done = true
            break
          }
          if (payload.startsWith('[ERROR]')) {
            gotError = true
            errorMsg = payload.slice(7).trim() || 'AI 服务返回错误'
            done = true
            break
          }

          // 普通内容：逐字累积
          if (receivedStart || fullText.length > 0) {
            fullText += payload
          } else {
            // 兼容未发送 [START] 的情况
            receivedStart = true
            fullText = payload
          }
          displayedTexts.value[aiMsgIndex] = fullText
          messages.value[aiMsgIndex].content = fullText
          scrollToBottom()
        }
      }

      // 最终清理 decoder
      const tail = decoder.decode()
      if (tail) {
        fullText += tail
        displayedTexts.value[aiMsgIndex] = fullText
        messages.value[aiMsgIndex].content = fullText
      }

      if (gotError) {
        messages.value[aiMsgIndex].content = `⚠️ ${errorMsg}`
        messages.value[aiMsgIndex].isTyping = false
        displayedTexts.value[aiMsgIndex] = ''
      } else if (fullText.length > 0) {
        streamSucceeded = true
        messages.value[aiMsgIndex].isTyping = false
        displayedTexts.value[aiMsgIndex] = ''
      }

      isLoading.value = false
      scrollToBottom()
      return
    }

    // 流式不可用，抛错走降级
    throw new Error('stream endpoint not available')
  } catch (streamErr) {
    console.warn('SSE 流失败，回退到普通请求:', streamErr)
  }

  // ===== 2. 回退：普通 POST 请求 =====
  try {
    const response = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        conversation_id: conversationId.value,
        user_id: 8,
      }),
    })

    const data = await response.json()

    if (data.success) {
      messages.value[aiMsgIndex].content = data.response.content
      messages.value[aiMsgIndex].suggestedActions = data.suggested_actions || []
      messages.value[aiMsgIndex].isTyping = false
      statusMode.value = data.response.mode
      await typeText(aiMsgIndex, data.response.content)
    } else {
      messages.value[aiMsgIndex].content = '抱歉，出了点问题。请稍后再试。'
      messages.value[aiMsgIndex].isTyping = false
    }
  } catch (err) {
    messages.value[aiMsgIndex].content = '无法连接到 AI 服务，请检查网络。'
    messages.value[aiMsgIndex].isTyping = false
  }

  isLoading.value = false
  scrollToBottom()
}

function quickAction(type) {
  const actions = {
    review: '帮我写一篇书评，可以先输入一个书籍ID吗？',
    recommend: '我想看一些推荐的书籍，你能推荐一些适合我的吗？',
    analyze: '我想让你分析一本书的核心主题',
    report: '生成我的阅读报告',
  }
  sendMessage(actions[type] || '你能做什么？')
}

// ========== 书评生成 ==========
async function generateReview() {
  if (!reviewBookId.value || isGenerating.value) return

  isGenerating.value = true
  generatedReview.value = null

  try {
    const response = await fetch(`/api/ai/review/${reviewBookId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style: reviewStyle.value }),
    })
    const data = await response.json()

    if (data.success) {
      generatedReview.value = data.review
    }
  } catch (err) {
    console.error('生成书评失败:', err)
  }

  isGenerating.value = false
}

// ========== 知识图谱生成 ==========
async function generateKnowledgeGraph() {
  if (!kgBookId.value || isGenerating.value) return

  isGenerating.value = true
  knowledgeGraph.value = null

  try {
    const response = await fetch(`/api/ai/knowledge/${kgBookId.value}`, {
      method: 'POST',
    })
    const data = await response.json()

    if (data.success) {
      knowledgeGraph.value = data.graph
      knowledgeGraphMermaid.value = data.mermaid
    }
  } catch (err) {
    console.error('生成知识图谱失败:', err)
  }

  isGenerating.value = false
}

// ========== 阅读报告生成 ==========
async function generateReport() {
  if (isGenerating.value) return

  isGenerating.value = true
  readingReport.value = null

  try {
    const response = await fetch('/api/ai/report/8', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_llm: true }),
    })
    const data = await response.json()

    if (data.success) {
      readingReport.value = data.report
    }
  } catch (err) {
    console.error('生成报告失败:', err)
  }

  isGenerating.value = false
}

// ========== 书籍搜索 ==========
async function searchBooks() {
  if (!searchQuery.value.trim()) return

  try {
    const response = await fetch(`/api/ai/search?q=${encodeURIComponent(searchQuery.value)}&limit=10`)
    const data = await response.json()

    if (data.success) {
      searchResults.value = data.books
    }
  } catch (err) {
    console.error('搜索失败:', err)
  }
}

function selectBook(book) {
  // 将选中的书名发送到聊天
  const msg = `给我介绍《${book.title}》这本书`
  sendMessage(msg)
  searchResults.value = []
  searchQuery.value = ''
}

function selectBookForAnalysis(bookId) {
  summaryBookId.value = bookId
  analyzeBookId.value = bookId
}

// ========== 书籍摘要生成 ==========
async function generateSummary() {
  if (!summaryBookId.value || isGenerating.value) return

  isGenerating.value = true
  bookSummary.value = null

  try {
    const response = await fetch(`/api/ai/summary/${summaryBookId.value}`, {
      method: 'GET',
    })
    const data = await response.json()

    if (data.success) {
      bookSummary.value = data.summary
    }
  } catch (err) {
    console.error('生成摘要失败:', err)
  }

  isGenerating.value = false
}

// ========== 完整分析 ==========
async function generateAnalysis() {
  if (!analyzeBookId.value || isGenerating.value) return

  isGenerating.value = true
  bookAnalysis.value = null

  try {
    const response = await fetch(`/api/ai/analyze/${analyzeBookId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_llm: false }),
    })
    const data = await response.json()

    if (data.success) {
      bookAnalysis.value = data.analysis
    }
  } catch (err) {
    console.error('分析失败:', err)
  }

  isGenerating.value = false
}

watch(messages, () => {
  scrollToBottom()
}, { deep: true })
</script>

<style scoped>
.ai-assistant {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  background: var(--color-bg-card);
  min-height: calc(100vh - 120px);
  border-radius: 12px;
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 顶部栏 */
.ai-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  border-radius: 12px;
  color: white;
  margin-bottom: 20px;
}

.toolbar-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.emoji { font-size: 28px; }
.subtitle { font-size: 14px; opacity: 0.9; margin-left: 8px; }

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(255,255,255,0.2);
  border-radius: 20px;
  font-size: 14px;
}

.status-badge .dot {
  width: 8px;
  height: 8px;
  background: #4ade80;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Tab 栏 */
.feature-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  overflow-x: auto;
  transition: all 0.3s ease;
}

.feature-tabs.tabs-animating {
  opacity: 0.7;
  transform: scale(0.98);
}

.tab-btn {
  flex: 1;
  min-width: 120px;
  padding: 12px 20px;
  background: var(--color-bg-secondary);
  border: 2px solid transparent;
  border-radius: 8px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  animation: tabSlideIn 0.4s ease-out forwards;
  opacity: 0;
}

@keyframes tabSlideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.tab-btn:hover {
  background: var(--color-bg-input);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.tab-btn.active {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  border-color: var(--color-primary);
  color: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(249, 115, 22, 0.3);
}

.tab-emoji { font-size: 18px; }
.tab-name { font-size: 14px; font-weight: 500; }

/* 聊天界面 */
.chat-panel {
  background: var(--color-bg);
  border-radius: 12px;
  padding: 16px;
}

.chat-messages {
  min-height: 400px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 16px;
  background: var(--color-bg-card);
  border-radius: 8px;
  margin-bottom: 16px;
}

/* 对话气泡动画 */
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: flex-start;
  animation: messageSlideIn 0.4s ease-out forwards;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.slide-in-left {
  animation: slideInLeft 0.4s ease-out forwards;
}

@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-30px); }
  to { opacity: 1; transform: translateX(0); }
}

.slide-in-right {
  animation: slideInRight 0.4s ease-out forwards;
}

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(30px); }
  to { opacity: 1; transform: translateX(0); }
}

/* 欢迎消息动画 */
.welcome-message {
  animation: welcomeFadeIn 0.6s ease-out forwards;
}

@keyframes welcomeFadeIn {
  0% { opacity: 0; transform: translateY(20px); }
  100% { opacity: 1; transform: translateY(0); }
}

.msg-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: var(--color-primary);
  flex-shrink: 0;
  transition: transform 0.3s ease;
}

.message:hover .msg-avatar {
  transform: scale(1.1);
}

.user-message .msg-avatar {
  background: var(--color-secondary);
}

.msg-content {
  flex: 1;
  max-width: 80%;
}

.msg-header {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--color-text);
}

.msg-time {
  font-weight: 400;
  font-size: 12px;
  color: var(--color-text-muted);
  margin-left: 8px;
}

.msg-text {
  background: var(--color-bg-secondary);
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.7;
  transition: all 0.3s ease;
}

.user-message .msg-text {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.ai-message .msg-text {
  border-bottom-left-radius: 4px;
}

.message:hover .msg-text {
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

/* 打字机光标 */
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-primary);
  margin-left: 2px;
  animation: blink 0.8s infinite;
  vertical-align: middle;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 打字消息样式 */
.typing-message .msg-text {
  min-height: 40px;
}

.suggested-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  animation: fadeInUp 0.4s ease-out 0.3s forwards;
  opacity: 0;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.suggestion-btn {
  padding: 8px 14px;
  background: var(--color-accent);
  border: 1px solid var(--color-border);
  border-radius: 20px;
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.suggestion-btn:hover {
  background: var(--color-primary);
  color: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
}

/* 加载动画 */
.loading-dots {
  display: flex;
  gap: 6px;
  padding: 16px;
}

.loading-dots span {
  width: 10px;
  height: 10px;
  background: var(--color-primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.typing { color: var(--color-text-muted); font-weight: 400; font-size: 12px; }

/* 快捷操作 */
.quick-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.quick-btn {
  padding: 10px 18px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.quick-btn:hover {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
}

/* 输入区 */
.chat-input-area {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
}

.chat-input {
  flex: 1;
  padding: 12px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  font-size: 14px;
  resize: none;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.chat-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
}

.send-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(249, 115, 22, 0.4);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-emoji { font-size: 16px; }

/* 通用面板 */
.panel-content {
  animation: panelFadeIn 0.4s ease-out;
}

@keyframes panelFadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-section {
  background: var(--color-bg-card);
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 20px;
  transition: all 0.3s ease;
}

.panel-section:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.result-section {
  animation: resultSlideIn 0.5s ease-out;
  border: 1px solid var(--color-border);
}

@keyframes resultSlideIn {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-section h3 {
  margin-top: 0;
  color: var(--color-text);
  font-size: 20px;
}

.hint {
  color: var(--color-text-muted);
  font-size: 14px;
}

.input-group {
  margin-bottom: 16px;
}

.input-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: var(--color-text);
}

.input-group input,
.input-group select {
  width: 100%;
  padding: 12px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.input-group input:focus,
.input-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.primary-btn {
  padding: 14px 28px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-weight: 500;
  font-size: 15px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-loading {
  position: relative;
}

.btn-loading::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 书评样式 */
.meta-info {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  color: var(--color-text-muted);
  font-size: 14px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.tag {
  padding: 6px 12px;
  background: var(--color-accent);
  border-radius: 16px;
  font-size: 13px;
  transition: all 0.2s ease;
}

.tag:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.highlights {
  background: var(--color-bg-secondary);
  padding: 16px 24px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.highlights h4 { margin-top: 0; }

.content {
  line-height: 1.8;
  margin-bottom: 16px;
}

.target-readers {
  padding: 12px 16px;
  background: var(--color-accent);
  border-radius: 8px;
  margin-bottom: 16px;
}

.generation-info {
  font-size: 12px;
  color: var(--color-text-muted);
  text-align: right;
}

/* 知识图谱 */
.summary {
  font-size: 15px;
  line-height: 1.8;
  padding: 16px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  border-left: 4px solid var(--color-primary);
}

.themes-section {
  margin: 20px 0;
}

.themes {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.theme-tag {
  padding: 8px 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
  color: white;
  border-radius: 20px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.theme-tag:hover {
  transform: scale(1.05);
}

.mermaid-container {
  margin: 20px 0;
}

.mermaid-code {
  background: var(--color-bg-input);
  padding: 16px;
  border-radius: 8px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.6;
}

.graph-stats {
  display: flex;
  gap: 20px;
  margin-top: 20px;
}

.stat-card {
  flex: 1;
  padding: 20px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  text-align: center;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

.stat-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-top: 4px;
}

/* 报告 */
.personality {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary);
  padding: 16px;
  background: var(--color-accent);
  border-radius: 8px;
  margin-bottom: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.insights-section {
  background: var(--color-bg-secondary);
  padding: 20px 24px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.insights-section ul {
  margin: 12px 0 0 0;
  padding-left: 20px;
}

.insights-section li {
  margin-bottom: 8px;
  line-height: 1.6;
}

.report-summary {
  background: var(--color-bg-secondary);
  padding: 20px 24px;
  border-radius: 8px;
  margin-bottom: 20px;
  line-height: 1.8;
}

.recommendations-section {
  margin-top: 20px;
}

.recommendation-card {
  padding: 16px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  margin-bottom: 12px;
  border-left: 4px solid var(--color-primary);
  transition: all 0.2s ease;
  animation: cardSlideIn 0.4s ease-out forwards;
}

.recommendation-card:hover {
  transform: translateX(5px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

@keyframes cardSlideIn {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

.rec-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--color-text);
}

.rec-author {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 4px 0;
}

.rec-reason {
  font-size: 14px;
  line-height: 1.6;
  margin: 8px 0;
}

.rec-score {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

/* 滚动条 */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--color-bg); }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 4px; transition: background 0.2s; }
::-webkit-scrollbar-thumb:hover { background: var(--color-primary); }

/* 搜索栏 */
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  padding: 12px 16px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.search-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.search-btn {
  padding: 12px 20px;
  background: var(--color-primary);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
}

.search-btn:hover {
  background: var(--color-secondary);
  transform: scale(1.05);
}

/* 搜索结果 */
.search-results {
  background: var(--color-bg-card);
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.search-result-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-result-item:hover {
  background: var(--color-bg-secondary);
}

.search-result-item:last-child {
  border-bottom: none;
}

.book-title {
  font-weight: 500;
  color: var(--color-text);
}

.book-author {
  font-size: 13px;
  color: var(--color-text-muted);
}

/* 摘要面板 */
.one-line {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary);
  padding: 16px;
  background: var(--color-accent);
  border-radius: 8px;
  margin: 16px 0;
}

.summary-section,
.target-section,
.guide-section {
  background: var(--color-bg-secondary);
  padding: 20px;
  border-radius: 8px;
  margin: 16px 0;
}

.summary-section h4,
.target-section h4,
.guide-section h4 {
  margin-top: 0;
  color: var(--color-text);
}

.summary-section p,
.target-section p,
.guide-section p {
  line-height: 1.8;
  margin: 8px 0;
}

/* 完整分析 */
.profile-section {
  margin-bottom: 20px;
}

.profile-section h3 {
  margin-bottom: 12px;
}

.similar-section {
  background: var(--color-bg-secondary);
  padding: 20px;
  border-radius: 8px;
  margin: 16px 0;
}

.similar-section h4 {
  margin-top: 0;
}

.similar-books {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.similar-book-card {
  background: var(--color-bg);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  transition: all 0.2s ease;
}

.similar-book-card:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

.similar-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
  color: var(--color-text);
}

.similar-author {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.similar-score {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .ai-toolbar {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }

  .toolbar-left h1 {
    font-size: 20px;
  }

  .feature-tabs {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .tab-btn {
    min-width: 100px;
    padding: 10px 16px;
  }

  .tab-name {
    font-size: 12px;
  }

  .chat-messages {
    min-height: 300px;
  }

  .msg-content {
    max-width: 90%;
  }

  .quick-actions {
    justify-content: center;
  }

  .quick-btn {
    flex: 1;
    min-width: 45%;
  }

  .chat-input-area {
    flex-direction: column;
  }

  .send-btn {
    width: 100%;
    justify-content: center;
  }

  .meta-info {
    flex-direction: column;
    gap: 8px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .graph-stats {
    flex-direction: column;
  }

  .similar-books {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .ai-assistant {
    padding: 12px;
  }

  .panel-section {
    padding: 16px;
  }

  .primary-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
