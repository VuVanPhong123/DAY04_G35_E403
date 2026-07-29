import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendOrigin = env.BACKEND_ORIGIN || 'http://127.0.0.1:8000';
  const sharedSecret = env.BACKEND_SHARED_SECRET || '';
  const headers = sharedSecret ? { 'X-Internal-API-Key': sharedSecret } : undefined;

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/chat': {
          target: backendOrigin,
          changeOrigin: true,
          headers,
        },
        '/api/health': {
          target: backendOrigin,
          changeOrigin: true,
          headers,
          rewrite: () => '/health',
        },
      },
    },
  };
});

