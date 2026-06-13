#!/usr/bin/env npx tsx
/**
 * inspect_doc.ts — Inspect a Google Doc's structure via the Docs API.
 * Usage: npx tsx inspect_doc.ts <documentId>
 */

import { GoogleAuth } from "google-auth-library";

const documentId = process.argv[2];
if (!documentId) {
  console.error("Usage: npx tsx inspect_doc.ts <documentId>");
  process.exit(1);
}

const auth = new GoogleAuth({
  scopes: ["https://www.googleapis.com/auth/documents.readonly"],
});
const client = await auth.getClient();
const tokenRes = await client.getAccessToken();
if (!tokenRes.token) { console.error("❌ No token"); process.exit(1); }

const res = await fetch(`https://docs.googleapis.com/v1/documents/${documentId}`, {
  headers: { Authorization: `Bearer ${tokenRes.token}` },
});

if (!res.ok) {
  console.error(`❌ ${res.status}: ${await res.text()}`);
  process.exit(1);
}

const doc = await res.json() as any;

console.log(`📄 Title: ${doc.title}`);
console.log(`📐 Page size: ${JSON.stringify(doc.documentStyle?.pageSize)}`);
console.log(`📏 Margins: T=${doc.documentStyle?.marginTop?.magnitude}pt B=${doc.documentStyle?.marginBottom?.magnitude}pt L=${doc.documentStyle?.marginLeft?.magnitude}pt R=${doc.documentStyle?.marginRight?.magnitude}pt`);

// Count structural elements
const body = doc.body?.content || [];
console.log(`\n📊 Total structural elements: ${body.length}`);

// Walk through elements and log summary
let pageBreaks = 0;
let paragraphs = 0;
let tables = 0;
let sectionBreaks = 0;

for (const elem of body) {
  if (elem.paragraph) {
    paragraphs++;
    // Check for page breaks
    for (const el of elem.paragraph.elements || []) {
      if (el.pageBreak) pageBreaks++;
    }
    // Log text content (first 100 chars)
    const text = (elem.paragraph.elements || [])
      .map((e: any) => e.textRun?.content || "")
      .join("")
      .trim();
    if (text) {
      const style = elem.paragraph.paragraphStyle?.namedStyleType || "";
      const heading = elem.paragraph.paragraphStyle?.headingId ? ` [H:${elem.paragraph.paragraphStyle.headingId}]` : "";
      console.log(`  P[${style}]${heading}: "${text.substring(0, 120)}${text.length > 120 ? "..." : ""}"`);
    } else if (elem.paragraph.elements?.some((e: any) => e.pageBreak)) {
      console.log(`  --- PAGE BREAK ---`);
    } else if (elem.paragraph.elements?.some((e: any) => e.inlineObjectElement)) {
      const objId = elem.paragraph.elements.find((e: any) => e.inlineObjectElement)?.inlineObjectElement?.inlineObjectId;
      console.log(`  [IMAGE: ${objId}]`);
    } else {
      console.log(`  (empty paragraph)`);
    }
  } else if (elem.table) {
    tables++;
    const rows = elem.table.rows;
    const cols = elem.table.columns;
    console.log(`  TABLE: ${rows}×${cols}`);
    // Print first row content as headers
    if (elem.table.tableRows?.[0]) {
      const headerCells = elem.table.tableRows[0].tableCells || [];
      const headers = headerCells.map((cell: any) => {
        const cellText = (cell.content || [])
          .flatMap((p: any) => (p.paragraph?.elements || []))
          .map((e: any) => e.textRun?.content || "")
          .join("")
          .trim();
        return cellText;
      });
      console.log(`    Headers: [${headers.join(" | ")}]`);
    }
    // Print subsequent row content
    for (let r = 1; r < (elem.table.tableRows?.length || 0); r++) {
      const row = elem.table.tableRows[r];
      const cells = (row.tableCells || []).map((cell: any) => {
        const cellText = (cell.content || [])
          .flatMap((p: any) => (p.paragraph?.elements || []))
          .map((e: any) => e.textRun?.content || "")
          .join("")
          .trim();
        return cellText;
      });
      console.log(`    Row ${r}: [${cells.join(" | ")}]`);
    }
  } else if (elem.sectionBreak) {
    sectionBreaks++;
    console.log(`  === SECTION BREAK ===`);
  }
}

console.log(`\n📋 Summary: ${paragraphs} paragraphs, ${tables} tables, ${pageBreaks} page breaks, ${sectionBreaks} section breaks`);

// Check headers/footers
if (doc.headers) {
  console.log(`\n📑 Headers: ${Object.keys(doc.headers).length}`);
  for (const [id, header] of Object.entries(doc.headers) as any) {
    const text = (header.content || [])
      .flatMap((e: any) => (e.paragraph?.elements || []))
      .map((e: any) => e.textRun?.content || "")
      .join("")
      .trim();
    console.log(`  ${id}: "${text.substring(0, 80)}"`);
  }
}

if (doc.footers) {
  console.log(`\n🦶 Footers: ${Object.keys(doc.footers).length}`);
  for (const [id, footer] of Object.entries(doc.footers) as any) {
    const text = (footer.content || [])
      .flatMap((e: any) => (e.paragraph?.elements || []))
      .map((e: any) => e.textRun?.content || "")
      .join("")
      .trim();
    console.log(`  ${id}: "${text.substring(0, 80)}"`);
  }
}

// Check inline objects (images)
if (doc.inlineObjects) {
  console.log(`\n🖼️ Inline objects: ${Object.keys(doc.inlineObjects).length}`);
  for (const [id, obj] of Object.entries(doc.inlineObjects) as any) {
    const props = obj.inlineObjectProperties?.embeddedObject;
    console.log(`  ${id}: ${props?.title || "(no title)"} — ${props?.imageProperties?.contentUri?.substring(0, 60) || "(no uri)"}...`);
  }
}

// Save full JSON for deep analysis
const fs = await import("node:fs");
fs.writeFileSync("/tmp/template_doc_structure.json", JSON.stringify(doc, null, 2));
console.log("\n💾 Full document JSON saved to /tmp/template_doc_structure.json");
