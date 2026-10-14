import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		// Fail loudly if 5173 is taken (e.g. a stale dev server) instead of
		// silently moving to 5174 and serving from the wrong process.
		strictPort: true,
		// Proxy API calls to FastAPI in dev so the browser hits one origin.
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
