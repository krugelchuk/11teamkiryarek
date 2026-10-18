import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Разрешённые dev-origins backend: 5173, 3000, 4173 (localhost и 127.0.0.1).
export default defineConfig({
  plugins: [react()],
  server: { host: 'localhost', port: 5173, strictPort: true },
  preview: { host: 'localhost', port: 4173, strictPort: true },
});
