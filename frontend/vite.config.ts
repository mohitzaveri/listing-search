import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Send /api calls to the FastAPI server, so the browser sees one origin (no CORS setup needed).
const proxy = { '/api': 'http://127.0.0.1:8000' };

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy }, // same for `npm run preview` (the production build)
});
