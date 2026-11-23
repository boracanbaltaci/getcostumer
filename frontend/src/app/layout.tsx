import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "Ankara Business Radar",
  description: "Yeni kurulan işletmeleri tespit eden, analiz eden ve satış sürecini yöneten platform",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>
        <AuthProvider>
          <Shell>{children}</Shell>
        </AuthProvider>
      </body>
    </html>
  );
}
