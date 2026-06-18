import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBookStore = defineStore('book', () => {
  const books = ref<any[]>([])
  const currentBook = ref<any | null>(null)
  const recommendations = ref<any[]>([])
  const loading = ref(false)

  const setBooks = (bookList: any[]) => {
    books.value = bookList
  }

  const setCurrentBook = (book: any) => {
    currentBook.value = book
  }

  const setRecommendations = (recs: any[]) => {
    recommendations.value = recs
  }

  return { books, currentBook, recommendations, loading, setBooks, setCurrentBook, setRecommendations }
})
