<template>
  <div class="book-card" @click="$router.push(`/book/${book.id}`)">
    <div class="cover">
      <img v-if="book.image_url" :src="book.image_url" :alt="book.title" />
      <div v-else class="no-cover">暂无封面</div>
    </div>
    <div class="info">
      <h3 class="title">{{ book.title }}</h3>
      <p class="author">{{ book.author || '未知作者' }}</p>
      <div class="rating">
        <span class="avg">{{ book.avg_rating?.toFixed(1) || 'N/A' }}</span>
        <span class="count">({{ book.rating_count }}人)</span>
      </div>
      <div class="interactions" @click.stop>
        <button
          :class="{ active: interactions.liked }"
          @click="toggleLike"
          title="喜欢"
        >
          {{ interactions.liked ? '❤️' : '🤍' }}
        </button>
        <button
          :class="{ active: interactions.wanted }"
          @click="toggleWant"
          title="想读"
        >
          {{ interactions.wanted ? '👀' : '📖' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '../api/client'

interface Book {
  id: number
  title: string
  author?: string
  image_url?: string
  avg_rating?: number
  rating_count: number
}

interface Interactions {
  liked: boolean
  wanted: boolean
}

const props = withDefaults(defineProps<{
  book: Book
  initialInteractions?: Interactions
}>(), {
  initialInteractions: () => ({ liked: false, wanted: false })
})

const interactions = ref<Interactions>({
  liked: props.initialInteractions?.liked || false,
  wanted: props.initialInteractions?.wanted || false
})

const emit = defineEmits(['interaction-change'])

const toggleLike = async () => {
  try {
    await api.post('/interactions', {
      book_id: props.book.id,
      interaction_type: 'like'
    })
    interactions.value.liked = !interactions.value.liked
    emit('interaction-change', { type: 'like', value: interactions.value.liked })
  } catch (error) {
    console.error('Failed to toggle like:', error)
  }
}

const toggleWant = async () => {
  try {
    await api.post('/interactions', {
      book_id: props.book.id,
      interaction_type: 'want_to_read'
    })
    interactions.value.wanted = !interactions.value.wanted
    emit('interaction-change', { type: 'want_to_read', value: interactions.value.wanted })
  } catch (error) {
    console.error('Failed to toggle want:', error)
  }
}
</script>

<style scoped>
.book-card {
  background: #1f1f28;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.book-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.cover img {
  width: 100%;
  height: 200px;
  object-fit: cover;
}

.no-cover {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #27272f;
  color: #71717a;
}

.info {
  padding: 12px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #e4e4e7;
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.author {
  font-size: 12px;
  color: #a1a1aa;
  margin: 0 0 8px;
}

.rating {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}

.avg {
  color: #f97316;
  font-weight: 600;
}

.count {
  color: #71717a;
  font-size: 12px;
}

.interactions {
  display: flex;
  gap: 8px;
}

.interactions button {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s, transform 0.2s;
}

.interactions button:hover {
  opacity: 1;
  transform: scale(1.2);
}

.interactions button.active {
  opacity: 1;
}
</style>
