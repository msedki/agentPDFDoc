import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : "L'opération a échoué sans message exploitable. Réessayez ; si l'échec persiste, consultez le journal du service : la commande .\\rag.ps1 logs en donne l'emplacement."; }
