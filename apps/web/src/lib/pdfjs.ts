import type * as PdfJs from "pdfjs-dist";

/**
 * Chargement de PDF.js dans le navigateur, depuis la copie locale de la version verrouillée de
 * `pdfjs-dist` (scripts/prepare-assets.mjs → public/pdfjs/, servie sous /pdfjs/ avec le worker,
 * les cmaps, les polices standard et les modules wasm).
 *
 * Le module n'est pas empaqueté par le bundler : webpack (5.98.0, compilé dans Next 16.3.7)
 * remplace `import.meta.url` par l'URL `file://` absolue du fichier source au moment du build.
 * `build/pdf.mjs` emploie `import.meta.url` dans sa fabrique de canvas réservée à Node.js : le chemin
 * de node_modules sur le poste de build était ainsi inscrit dans l'export statique. Chargé par le
 * navigateur, le module garde son `import.meta.url` réel (l'URL servie) et rien du poste n'est livré.
 */
export const PDFJS_ASSET_ROOT = "/pdfjs/";
/** Nom du module principal copié par prepare-assets.mjs depuis `pdfjs-dist/build/pdf.min.mjs`. */
export const PDFJS_MODULE_URL = `${PDFJS_ASSET_ROOT}pdf.min.mjs`;
export const PDFJS_WORKER_URL = `${PDFJS_ASSET_ROOT}pdf.worker.min.mjs`;

export type PdfJsModule = typeof PdfJs;

/** Message affiché quand le navigateur n'a pas pu charger le module PDF.js copié dans l'export. */
export const PDFJS_LOAD_MESSAGE = "Les fichiers du lecteur PDF n'ont pas été chargés (/pdfjs/pdf.min.mjs). Rechargez la page ; si l'échec persiste, vérifiez l'installation de l'interface : le dossier pdfjs de l'export doit être présent.";
/** Échec de chargement du module PDF.js ; l'erreur du navigateur, en anglais, reste disponible dans `cause`. */
export class PdfJsLoadError extends Error {
  constructor(cause: unknown) {
    super(PDFJS_LOAD_MESSAGE, { cause });
    this.name = "PdfJsLoadError";
  }
}
type ModuleImporter = (url: string) => Promise<unknown>;

/**
 * Chargeur unique : le même module (donc les mêmes GlobalWorkerOptions) sert au document et au
 * TextLayer. Un échec de chargement n'est pas mémorisé, pour qu'une nouvelle ouverture réessaie.
 */
export function createPdfJsLoader(importModule: ModuleImporter): () => Promise<PdfJsModule> {
  let pending: Promise<PdfJsModule> | undefined;
  return () => {
    pending ??= importModule(PDFJS_MODULE_URL).then(value => {
      const pdfjs = value as PdfJsModule;
      pdfjs.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_URL;
      return pdfjs;
    }, (error: unknown) => {
      pending = undefined;
      throw new PdfJsLoadError(error);
    });
    return pending;
  };
}

// webpackIgnore (documenté par Next.js pour webpack et Turbopack) : l'import reste natif dans l'export.
export const loadPdfJs = createPdfJsLoader(url => import(/* webpackIgnore: true */ url));
