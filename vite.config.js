import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
    // El build de producción se niega a compilar sin una dirección de backend segura:
    // es preferible que falle aquí a publicar una app que no puede conectarse
    // (o que enviaría credenciales por una conexión sin cifrar).
    if (mode === 'production') {
        const url = (loadEnv(mode, process.cwd(), '').VITE_API_URL || '').trim().replace(/\/+$/, '')
        const esLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(url)
        if (!url) {
            throw new Error('Falta VITE_API_URL: defínela con la dirección del backend (https://.../api/v1) antes de compilar.')
        }
        if (!url.startsWith('https://') && !esLocal) {
            throw new Error(`VITE_API_URL debe empezar con https:// en producción (valor actual: ${url}).`)
        }
    }

    return {
        plugins: [react()],
        resolve: {
            // Alias "@/..." -> "src/..." (antes lo aportaba el plugin de la plataforma anterior).
            alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
        },
    }
})
