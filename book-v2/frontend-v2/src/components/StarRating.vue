<template>
  <div class="star-rating">
    <el-rate
      v-model="rating"
      :max="10"
      show-score
      text-color="#ff9900"
      @change="handleChange"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  initialRating: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['rate'])

const rating = ref(props.initialRating)

watch(() => props.initialRating, (newVal) => {
  rating.value = newVal
})

const handleChange = (value) => {
  emit('rate', value)
}
</script>

<style scoped>
.star-rating {
  display: inline-block;
}
</style>
