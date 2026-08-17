/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0f0f23',
          card: '#1a1a3e',
          border: '#2a2a5a',
        },
        accent: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        secondary: '#94a3b8',
      }
    },
  },
  plugins: [],
}
