import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/ethers/')) return 'ethers';
          if (id.includes('node_modules/bitcoinjs-lib/') || id.includes('node_modules/bip32/') || id.includes('node_modules/tiny-secp256k1/')) return 'bitcoin';
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) return 'vendor';
        },
      },
    },
  },
})
