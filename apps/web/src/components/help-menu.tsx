"use client";
import { useId, useRef, useState } from "react";
import { CircleHelp } from "lucide-react";
import packageInfo from "../../package.json";
import { buildSignature } from "@/lib/build-info";
import { useDismiss } from "@/lib/use-dismiss";
import { Button } from "./ui/button";

// NEXT_PUBLIC_BUILD_REVISION n'est défini par aucun script de build à ce jour :
// la signature affiche alors « révision non tracée ».
const signature = buildSignature(packageInfo.version, typeof process !== "undefined" ? process.env.NEXT_PUBLIC_BUILD_REVISION : undefined);

/** Raccourcis présents dans le code : workspace.tsx, analysis-panel.tsx, pdf-viewer.tsx et les panneaux modaux. */
const shortcuts: { keys: string[][]; action: string }[] = [
  { keys: [["Ctrl", "B"], ["⌘", "B"]], action: "Replier, masquer ou afficher la bibliothèque ; sous 1 024 px, ouvrir ou fermer son panneau. Sans effet pendant la saisie d'une question." },
  { keys: [["Ctrl", "Entrée"], ["⌘", "Entrée"]], action: "Depuis la zone de saisie : envoyer la question ou lancer la recherche." },
  { keys: [["←"], ["→"], ["Début"], ["Fin"]], action: "Sur un onglet d'analyse (Question, Recherche, Comparer) : passer à un autre onglet." },
  { keys: [["←"], ["→"]], action: "Sur un séparateur de panneaux : élargir ou rétrécir la bibliothèque ou l'analyse." },
  { keys: [["Entrée"]], action: "Dans « Rechercher dans ce document » : aller à la page suivante qui contient l'expression, comme « Chercher plus loin »." },
  { keys: [["Échap"]], action: "Fermer le panneau latéral, le suivi, cette aide, le choix du périmètre ou la boîte de confirmation." },
];

export function HelpMenu() {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const titleId = useId();
  useDismiss(open, container, reason => { setOpen(false); if (reason === "escape") trigger.current?.focus(); });
  return <div className="help-menu" ref={container}>
    <Button ref={trigger} variant="ghost" size="sm" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(value => !value)}><CircleHelp size={16} aria-hidden="true" /><span className="topbar-label">Aide</span></Button>
    {open && <div className="help-popover" id={panelId} role="region" aria-labelledby={titleId}>
      <h2 id={titleId}>Raccourcis clavier</h2>
      <dl className="shortcut-list">
        {shortcuts.map(({ keys, action }) => <div key={action}>
          <dt>{keys.map((combination, index) => <span key={combination.join("+")}>{index > 0 && <span className="shortcut-or"> ou </span>}{combination.map((key, position) => <span key={key}>{position > 0 && " + "}<kbd>{key}</kbd></span>)}</span>)}</dt>
          <dd>{action}</dd>
        </div>)}
      </dl>
      <h2>Version de l'interface</h2>
      <p className="build-signature mono" title={signature.detail}>{signature.label}</p>
      <p className="help-note">{signature.detail}</p>
    </div>}
  </div>;
}
