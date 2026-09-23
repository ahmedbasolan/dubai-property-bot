import type { Metadata } from "next";
import { Cinzel, Josefin_Sans, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { DataSourceProvider } from "@/components/data-source-provider";

const cinzel = Cinzel({
  variable: "--font-cinzel",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const josefinSans = Josefin_Sans({
  variable: "--font-josefin",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dubai Property Investment Assistant",
  description: "AI-powered investment scoring and Q&A for Dubai real estate",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${cinzel.variable} ${josefinSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex bg-background text-foreground font-sans">
        <DataSourceProvider>
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </DataSourceProvider>
      </body>
    </html>
  );
}
