import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { AppThemeProvider } from './contexts/theme-context';
import { MotionProvider } from './animations/motion-provider';
import './styles/global.css';
import './styles/touch-enhancements.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <MotionProvider>
          <App />
        </MotionProvider>
      </AppThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
