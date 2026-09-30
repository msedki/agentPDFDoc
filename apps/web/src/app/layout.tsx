import type { Metadata } from "next";
import "./globals.css";
import "./pdf-text-layer.css";
export const metadata: Metadata = { title: "Atelier documentaire local", description: "Lecture et analyse documentaire avec sources vérifiables." };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body>{children}</body></html>;
}
