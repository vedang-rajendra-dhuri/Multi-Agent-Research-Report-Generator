/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7F9FC",
        ink: "#172033",
        muted: "#667085",
        line: "#E4E9F1",
        brand: "#315EFB",
      },
    },
  },
  plugins: [],
};