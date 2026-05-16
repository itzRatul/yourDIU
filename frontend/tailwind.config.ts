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
        // yourDIU v2 — DAIC-inspired dark glass-morphism palette
        bg: {
          base:   "#050510",
          deep:   "#030308",
          glass:  "rgba(10, 10, 28, 0.72)",
          hover:  "rgba(255, 255, 255, 0.10)",
        },
        accent: {
          DEFAULT:   "#7c6aef",   // primary purple
          dark:      "#6a58e0",
          glow:      "rgba(124, 106, 239, 0.35)",
          secondary: "#4ecdc4",   // teal companion
        },
        ink: {
          DEFAULT: "rgba(255, 255, 255, 0.93)",
          dim:     "rgba(255, 255, 255, 0.50)",
          muted:   "rgba(255, 255, 255, 0.28)",
          faint:   "rgba(255, 255, 255, 0.12)",
        },
        glass: {
          border:        "rgba(255, 255, 255, 0.06)",
          "border-strong":"rgba(255, 255, 255, 0.14)",
          fill:          "rgba(255, 255, 255, 0.04)",
          "fill-strong": "rgba(255, 255, 255, 0.08)",
        },
        status: {
          success: "#51cf66",
          danger:  "#ff6b6b",
        },
      },
      fontFamily: {
        sans: ["var(--font-poppins)", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "accent-gradient":  "linear-gradient(135deg, #7c6aef 0%, #4ecdc4 100%)",
        "accent-gradient-soft": "linear-gradient(135deg, rgba(124,106,239,0.18) 0%, rgba(78,205,196,0.10) 100%)",
        "ink-fade":         "linear-gradient(135deg, rgba(255,255,255,0.93), #7c6aef)",
      },
      boxShadow: {
        glass:    "0 4px 24px rgba(0, 0, 0, 0.12)",
        "glass-lg":"0 12px 40px rgba(0, 0, 0, 0.35)",
        glow:     "0 0 32px rgba(124, 106, 239, 0.25)",
        "glow-sm":"0 2px 8px rgba(124, 106, 239, 0.25)",
      },
      backdropBlur: {
        glass: "32px",
      },
      borderRadius: {
        glass:    "16px",
        "glass-sm": "10px",
        "glass-xs": "6px",
      },
      animation: {
        "fade-in":   "fadeIn 0.6s ease",
        "msg-in":    "msgIn 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
        "pulse-dot": "pulseDot 2s ease-in-out infinite",
        "blink":     "blink 0.8s step-end infinite",
        "orb-pulse": "orbPulse 1.6s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:    { from: { opacity: "0" }, to: { opacity: "1" } },
        msgIn:     { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        pulseDot:  { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.4" } },
        blink:     { "0%,100%": { opacity: "1" }, "50%": { opacity: "0" } },
        orbPulse:  { "0%,100%": { transform: "translate(-50%, -50%) scale(1)" }, "50%": { transform: "translate(-50%, -50%) scale(1.04)" } },
      },
    },
  },
  plugins: [],
};
export default config;
