import type { Metadata } from "next";
import "./globals.css";
import "./pdf-text-layer.css";
export const metadata: Metadata = { title: "Atelier documentaire", description: "Poste documentaire local : lecture des PDF, recherche de passages et questions avec sources citées." };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body>{children}</body></html>;
}
