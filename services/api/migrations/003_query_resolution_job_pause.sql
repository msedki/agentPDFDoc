-- Colonnes autrefois ajoutées à chaud par Database.initialize. Une base neuve les reçoit déjà de 001 ;
-- le runner ignore un ADD COLUMN existant, ce qui rend ce script idempotent sur une base v2 patchée.
-- Retour arrière : restaurer la sauvegarde prise avant démarrage du code v3 (aucune migration descendante).
ALTER TABLE query_runs ADD COLUMN resolution_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE jobs ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0;
INSERT OR IGNORE INTO schema_version VALUES(3);
