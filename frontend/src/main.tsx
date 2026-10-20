import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { supabase } from './services/supabase'
import { useAuthStore } from './store/useAuthStore'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

// Supabase session (Google OAuth redirect, token refresh) -> backend ke liye bearer token
supabase?.auth.onAuthStateChange((_event, session) => {
  const { setToken, logout, token } = useAuthStore.getState()
  if (session?.access_token) {
    if (session.access_token !== token) setToken(session.access_token)
  } else if (token && token.split('.').length === 3 && JSON.parse(atob(token.split('.')[1])).iss?.endsWith('/auth/v1')) {
    logout()
  }
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
