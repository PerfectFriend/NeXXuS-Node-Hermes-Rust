
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E1A",
        surface: "#14162a",
        border: "#2A2E4A",
        muted: "#6B7094",
        text: "#C9CBE0",
        bright: "#E4E5F1",
        accent: "#8C6CFF",
        cyan: "#22D3C8",
        gold: "#E8B94A",
      },
    },
  },
  plugins: [],
};
