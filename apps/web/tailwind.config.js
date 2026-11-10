/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#090d16',
        card: '#101726',
        border: '#1f293d',
        primary: '#3b82f6',
        destructive: '#ef4444',
        warning: '#f59e0b',
        success: '#10b981',
      }
    },
  },
  plugins: [],
}
