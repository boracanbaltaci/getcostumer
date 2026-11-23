import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef4fb", 100: "#d6e4f4", 500: "#2f6db5", 600: "#24589a", 700: "#1f3a5f", 900: "#13243b" },
      },
    },
  },
  plugins: [],
};
export default config;
