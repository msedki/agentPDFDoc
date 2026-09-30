/**
 * Signature de build affichée dans le menu Aide.
 *
 * La version vient de apps/web/package.json. La révision n'est connue que si
 * la construction l'injecte (variable NEXT_PUBLIC_BUILD_REVISION) ; sans elle,
 * la signature l'écrit plutôt que d'afficher une provenance supposée.
 */
export type BuildSignature = { version: string | null; revision: string | null; label: string; detail: string };

export function buildSignature(version: unknown, revision: unknown): BuildSignature {
  const knownVersion = typeof version === "string" && /^\d+\.\d+\.\d+(?:[-+][\w.-]+)?$/.test(version) ? version : null;
  const cleanRevision = typeof revision === "string" ? revision.trim().toLowerCase() : "";
  const knownRevision = /^[0-9a-f]{7,40}$/.test(cleanRevision) ? cleanRevision : null;
  const versionText = knownVersion ? `version ${knownVersion}` : "version inconnue";
  const revisionText = knownRevision ? `révision ${knownRevision.slice(0, 12)}` : "révision non tracée";
  return {
    version: knownVersion,
    revision: knownRevision,
    label: `Atelier documentaire · ${versionText} · ${revisionText}`,
    detail: knownRevision
      ? `Révision complète ${knownRevision}, injectée à la construction.`
      : "Aucune révision n'a été injectée à la construction : cette interface ne peut pas être rattachée à un commit précis.",
  };
}
