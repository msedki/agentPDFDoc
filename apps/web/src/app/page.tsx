import Link from "next/link";
export default function Home() { return <main className="home"><p className="eyebrow">Poste local</p><h1>Atelier documentaire</h1><p>Lire, retrouver et vérifier les sources de vos documents.</p><Link href="/workspace/" className="home-link">Ouvrir l'espace de travail →</Link></main>; }
