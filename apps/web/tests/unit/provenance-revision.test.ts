import assert from "node:assert/strict";
import test from "node:test";
import { blocksKey, blocksPath, citedRevision, outlinePath, revisionActionGuard, verifyPinnedBlocks, verifyPinnedOutline } from "../../src/lib/provenance-revision.ts";
import type { PageBlocks, Source } from "../../src/lib/types.ts";

const citation: Source = { source_id: "S001", query_id: "query-old", document_id: "document", version_id: "same-version", extraction_revision_id: "revision-old", generation_id: "generation-old", text: "Valeur ancienne" };
const old: PageBlocks = { version_id: "same-version", generation_id: "generation-old", extraction_revision_id: "revision-old", page: { page_index: 0, width: 595, height: 842, rotation: 0, crop_box: null, media_box: null }, blocks: [{ id: "block", page_index: 0, text: "Valeur ancienne", raw_text: "Valeur ancienne", precision: "block", extraction_revision_id: "revision-old" }], warnings: [] };

test("registered old citation pins a distinct blocks cache while ordinary navigation remains current", () => {
  const pinned = citedRevision("same-version", citation);
  assert.equal(pinned.revision, "revision-old");
  assert.notDeepEqual(blocksKey("same-version", 0, pinned.revision), blocksKey("same-version", 0, "revision-new"));
  assert.notDeepEqual(blocksKey("same-version", 0, pinned.revision), blocksKey("same-version", 0));
  assert.deepEqual(citedRevision("same-version", null), { revision: null, pinned: false, error: null });
  assert.deepEqual(citedRevision("another-version", citation), { revision: null, pinned: false, error: null });
  assert.deepEqual(citedRevision("same-version", { ...citation, source_id: undefined }), { revision: null, pinned: false, error: null });
});

test("a registered citation without its extraction revision blocks substitution", () => {
  const missing = citedRevision("same-version", { ...citation, extraction_revision_id: undefined });
  assert.equal(missing.pinned, true);
  assert.equal(missing.revision, null);
  assert.match(missing.error!, /ne peuvent pas la remplacer/);
});

test("pinned endpoint paths encode exact revision and preserve the unpinned routes", () => {
  assert.equal(blocksPath("same-version", 0), "/versions/same-version/pages/0/blocks");
  assert.equal(outlinePath("same-version"), "/versions/same-version/outline");
  assert.equal(blocksPath("same-version", 0, "old&other=value"), "/versions/same-version/pages/0/blocks?extraction_revision_id=old%26other%3Dvalue");
  assert.equal(outlinePath("same-version", "revision-old"), "/versions/same-version/outline?extraction_revision_id=revision-old");
});

test("old raw provenance is accepted and a newer revision or mixed block revision is rejected", () => {
  assert.equal(verifyPinnedBlocks(old, "same-version", 0, "revision-old").blocks[0].raw_text, "Valeur ancienne");
  assert.throws(() => verifyPinnedBlocks({ ...old, extraction_revision_id: "revision-new", blocks: [{ ...old.blocks[0], raw_text: "Valeur récente", extraction_revision_id: "revision-new" }] }, "same-version", 0, "revision-old"), /Aucune extraction récente/);
  assert.throws(() => verifyPinnedBlocks({ ...old, blocks: [{ ...old.blocks[0], extraction_revision_id: "revision-new" }] }, "same-version", 0, "revision-old"));
  assert.throws(() => verifyPinnedBlocks(old, "other-version", 0, "revision-old"));
  assert.throws(() => verifyPinnedBlocks(old, "same-version", 1, "revision-old"));
});

test("the outline must also belong to the registered citation revision", () => {
  const outline = { version_id: "same-version", extraction_revision_id: "revision-old", sections: [] };
  assert.equal(verifyPinnedOutline(outline, "same-version", "revision-old"), outline);
  assert.throws(() => verifyPinnedOutline({ ...outline, extraction_revision_id: "revision-new" }, "same-version", "revision-old"));
});

test("page and section actions remain enabled for current citations and require verified latest identity", () => {
  const binding = citedRevision("same-version", citation);
  assert.deepEqual(revisionActionGuard(binding, "revision-old"), { allowed: true, archived: false, reason: null });
  const archived = revisionActionGuard(binding, "revision-new");
  assert.equal(archived.allowed, false);
  assert.equal(archived.archived, true);
  assert.match(archived.reason!, /texte sélectionné ou un bloc/);
  assert.equal(revisionActionGuard(binding, undefined).allowed, false);
  assert.match(revisionActionGuard(binding, undefined, true).reason!, /ne peut pas être vérifiée/);
  assert.equal(revisionActionGuard(citedRevision("same-version", null), undefined).allowed, true);
});
