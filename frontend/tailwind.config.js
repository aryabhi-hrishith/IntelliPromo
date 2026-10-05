/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#f8fafc',
        primary: '#3b82f6',
        secondary: '#64748b',
        accent: '#8b5cf6',
      }
    },
  },
  plugins: [],
}
