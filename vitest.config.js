import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.js'

// Configuración de pruebas, separada de vite.config.js para que el build de
// producción no dependa de las herramientas de prueba.
export default defineConfig((entorno) =>
    mergeConfig(
        viteConfig(entorno),
        defineConfig({
            test: {
                environment: 'jsdom',
                include: ['src/**/*.test.{js,jsx}'],
                setupFiles: ['./src/test/setup.js'],
            },
        })
    )
)
