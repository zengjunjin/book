<template>
  <div class="tag-selector">
    <h3>选择你感兴趣的书籍类型</h3>
    <p class="hint">选择 3-5 个标签，帮助我们为你推荐好书</p>
    <div class="tag-cloud">
      <button
        v-for="tag in availableTags"
        :key="tag"
        :class="{ selected: selectedTags.includes(tag) }"
        @click="toggleTag(tag)"
      >
        {{ tag }}
      </button>
    </div>
    <div class="selected-info">
      已选择: {{ selectedTags.length }}/5
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits(['update:modelValue'])

const availableTags = [
  '科幻', '奇幻', '悬疑', '推理', '爱情', '历史', '心理',
  '哲学', '社会', '经济', '励志', '旅行', '科技', '编程',
  '艺术', '儿童', '漫画', '武侠', '美国文学', '经典'
]

const selectedTags = ref<string[]>([...props.modelValue])

const toggleTag = (tag: string) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else if (selectedTags.value.length < 5) {
    selectedTags.value.push(tag)
  }
  emit('update:modelValue', selectedTags.value)
}

watch(() => props.modelValue, (newVal) => {
  selectedTags.value = [...newVal]
})
</script>

<style scoped>
.tag-selector {
  padding: 20px;
}

.tag-selector h3 {
  color: #e4e4e7;
  margin-bottom: 8px;
}

.hint {
  color: #71717a;
  font-size: 14px;
  margin-bottom: 20px;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.tag-cloud button {
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid #3f3f46;
  background: #27272f;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-cloud button:hover {
  border-color: #f97316;
  color: #e4e4e7;
}

.tag-cloud button.selected {
  background: #f97316;
  border-color: #f97316;
  color: white;
}

.selected-info {
  color: #71717a;
  font-size: 14px;
}
</style>
