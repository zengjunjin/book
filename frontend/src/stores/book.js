import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBookStore = defineStore('book', () => {
  const books = ref([])
  const currentBook = ref(null)
  const recommendations = ref([])
  const loading = ref(false)

  const setBooks = (bookList) => {
    books.value = bookList
  }

  const setCurrentBook = (book) => {
    currentBook.value = book
  }

  const setRecommendations = (recs) => {
    recommendations.value = recs
  }

  return { books, currentBook, recommendations, loading, setBooks, setCurrentBook, setRecommendations }
})
