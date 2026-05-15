import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // DIU brand palette — matches diutoolkit.xyz dark theme
        diu: {
          green:     "#00A86B",   // primary action / accent
          "green-dark": "#007A4E",
          "green-light": "#00D68F",
          blue:      "#1A73E8",   // secondary / links
          "bg-base": "#0F1117",   // page background
          "bg-card": "#1A1D27",   // card / panel
          "bg-hover": "#22263A",  // hover state
          border:    "#2A2E42",   // subtle borders
          "border-bright": "#3A3F57",
          muted:     "#6B7280",   // placeholder / metadata
          text:      "#E2E8F0",   // primary text
          "text-dim":"#9CA3AF",   // secondary text
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "fade-in":  "fadeIn 0.2s ease-out",
        "slide-up": "slideUp 0.25s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn:  { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
};
export default config;
