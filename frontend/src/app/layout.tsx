import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "yourDIU",
  description: "Your all-in-one DIU campus assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#1A1D27",
              color: "#E2E8F0",
              border: "1px solid #2A2E42",
            },
          }}
        />
      </body>
    </html>
  );
}
