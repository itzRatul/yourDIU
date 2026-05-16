import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
});

export const metadata: Metadata = {
  title: "yourDIU — Daffodil International University Assistant",
  description: "AI assistant, PDF scrapper, notices, and community for DIU students.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={poppins.variable}>
      <body className="font-sans antialiased">
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "rgba(10, 10, 28, 0.92)",
              color: "rgba(255, 255, 255, 0.93)",
              border: "1px solid rgba(255, 255, 255, 0.10)",
              borderRadius: "12px",
              backdropFilter: "blur(16px)",
              fontSize: "13px",
              padding: "10px 14px",
            },
            success: { iconTheme: { primary: "#51cf66", secondary: "#050510" } },
            error:   { iconTheme: { primary: "#ff6b6b", secondary: "#050510" } },
          }}
        />
      </body>
    </html>
  );
}
