#!/usr/bin/env npx tsx
/**
 * md2gdoc — Convert Markdown to a branded Google Doc
 *
 * Pipeline: Markdown → Styled HTML → CSS Inlining → Google Drive upload (MIME conversion)
 *
 * Usage:
 *   npx tsx md2gdoc.ts <input.md> [options]
 *
 * Options:
 *   --folder-id <id>   Google Drive folder ID (default: "root")
 *   --name <title>     Document title (default: derived from H1 or filename)
 *   --css <path>       Custom CSS file (default: ../templates/vopak_doc.css)
 *   --meta <json>      Corporate front-matter metadata as JSON string.
 *                      Fields: documentType (required), documentTopic, author,
 *                      version, status, documentNumber, logoUrl
 *   --dry-run          Output HTML to stdout without uploading
 *   --output <path>    Save HTML to a local file instead of (or in addition to) uploading
 *
 * Auth: Uses Application Default Credentials (ADC) via google-auth-library.
 *       Run `gcloud auth application-default login` first if not authenticated.
 *
 * Examples:
 *   npx tsx md2gdoc.ts /tmp/report.md --folder-id 1abc123 --name "Q1 Report"
 *   npx tsx md2gdoc.ts /tmp/tdd.md --meta '{"documentType":"Technical Design Document"}'
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { Marked } from "marked";
import juice from "juice";
import { GoogleAuth } from "google-auth-library";

// ─── CLI Argument Parsing ────────────────────────────────────────────────────

interface DocumentMeta {
  documentType: string;
  documentTopic?: string;
  author?: string;
  version?: string;
  status?: string;
  date?: string;
  documentNumber?: string;
  logoUrl?: string;
}

interface Args {
  inputFile: string;
  folderId: string;
  name: string;
  cssPath: string;
  dryRun: boolean;
  outputPath: string | null;
  meta: DocumentMeta | null;
}

function parseArgs(): Args {
  const args = process.argv.slice(2);
  const result: Args = {
    inputFile: "",
    folderId: "root",
    name: "",
    cssPath: join(decodeURIComponent(dirname(new URL(import.meta.url).pathname)), "..", "templates", "vopak_doc.css"),
    dryRun: false,
    outputPath: null,
    meta: null,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--folder-id":
        result.folderId = args[++i];
        break;
      case "--name":
        result.name = args[++i];
        break;
      case "--css":
        result.cssPath = resolve(args[++i]);
        break;
      case "--dry-run":
        result.dryRun = true;
        break;
      case "--output":
        result.outputPath = args[++i];
        break;
      case "--meta":
        try {
          result.meta = JSON.parse(args[++i]) as DocumentMeta;
          if (!result.meta.documentType) {
            console.error("❌ --meta JSON must include 'documentType' field.");
            process.exit(1);
          }
        } catch (e) {
          console.error(`❌ Invalid --meta JSON: ${(e as Error).message}`);
          process.exit(1);
        }
        break;
      default:
        if (!args[i].startsWith("--")) {
          result.inputFile = resolve(args[i]);
        }
    }
  }

  if (!result.inputFile) {
    console.error("Usage: npx tsx md2gdoc.ts <input.md> [--folder-id <id>] [--name <title>] [--dry-run]");
    process.exit(1);
  }

  return result;
}

// ─── Markdown → HTML Conversion ──────────────────────────────────────────────

function convertMarkdownToHtml(markdown: string): string {
  const marked = new Marked();
  return marked.parse(markdown) as string;
}

// ─── HTML Assembly with Vopak Branding ───────────────────────────────────────

function assembleHtml(bodyHtml: string, css: string, title: string, coverHtml: string = ""): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${escapeHtml(title)}</title>
  <style>
${css}
  </style>
</head>
<body>
${coverHtml}
${bodyHtml}
</body>
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Extract Title from Markdown ─────────────────────────────────────────────

function extractTitle(markdown: string, fallbackFilename: string): string {
  // Try to extract H1
  const h1Match = markdown.match(/^#\s+(.+)$/m);
  if (h1Match) return h1Match[1].trim();

  // Fallback: use filename without extension
  return basename(fallbackFilename, ".md").replace(/[_-]/g, " ");
}

// ─── OAuth Token via google-auth-library (ADC) ──────────────────────────────

async function getAccessToken(): Promise<string> {
  try {
    const auth = new GoogleAuth({
      scopes: [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
      ],
    });
    const client = await auth.getClient();
    const tokenResponse = await client.getAccessToken();

    if (!tokenResponse.token) {
      throw new Error("Empty token returned from ADC");
    }

    return tokenResponse.token;
  } catch (error) {
    console.error("❌ Could not get OAuth token via Application Default Credentials.");
    console.error("   Run: gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/documents");
    console.error(`   Error: ${(error as Error).message}`);
    process.exit(1);
  }
}

// ─── Upload to Google Drive ──────────────────────────────────────────────────

interface UploadResult {
  id: string;
  name: string;
  mimeType: string;
  url: string;
}

async function uploadToGoogleDrive(
  html: string,
  title: string,
  folderId: string,
  token: string
): Promise<UploadResult> {
  const boundary = "----md2gdocBoundary" + Date.now();

  const metadata = JSON.stringify({
    name: title,
    mimeType: "application/vnd.google-apps.document",
    parents: [folderId],
  });

  // Build multipart body
  const bodyParts = [
    `--${boundary}\r\n`,
    `Content-Type: application/json; charset=UTF-8\r\n\r\n`,
    `${metadata}\r\n`,
    `--${boundary}\r\n`,
    `Content-Type: text/html; charset=UTF-8\r\n\r\n`,
    html,
    `\r\n--${boundary}--`,
  ];

  const body = bodyParts.join("");

  const url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true";

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": `multipart/related; boundary=${boundary}`,
    },
    body: body,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Drive API error ${response.status}: ${errorText}`);
  }

  const result = await response.json() as { id: string; name: string; mimeType: string };

  return {
    id: result.id,
    name: result.name,
    mimeType: result.mimeType,
    url: `https://docs.google.com/document/d/${result.id}/edit`,
  };
}

// ─── Set A4 Portrait Page Size ───────────────────────────────────────────────

/** A4 dimensions: 210mm x 297mm = 595.28pt x 841.89pt */
async function setA4Portrait(documentId: string, token: string): Promise<void> {
  const url = `https://docs.googleapis.com/v1/documents/${documentId}:batchUpdate`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      requests: [
        {
          updateDocumentStyle: {
            documentStyle: {
              pageSize: {
                height: { magnitude: 841.8897637795276, unit: "PT" },
                width: { magnitude: 595.2755905511812, unit: "PT" },
              },
              marginTop: { magnitude: 72, unit: "PT" },
              marginBottom: { magnitude: 72, unit: "PT" },
              marginLeft: { magnitude: 72, unit: "PT" },
              marginRight: { magnitude: 72, unit: "PT" },
            },
            fields: "pageSize,marginTop,marginBottom,marginLeft,marginRight",
          },
        },
      ],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.warn(`⚠️  Could not set A4 page size: ${response.status} — ${errorText}`);
  } else {
    console.log("📐 Page size set to A4 portrait (210×297mm)");
  }
}

// ─── Corporate Front-Matter Generator (standalone) ───────────────────────────

/**
 * Generates 3-page Vopak corporate front-matter as HTML.
 * This is a standalone version for the CLI script (cannot import from src/shared/).
 */
function generateCoverPagesLocal(meta: DocumentMeta, title: string): string {
  const today = new Date().toISOString().split("T")[0];
  const topic = meta.documentTopic ?? title;
  const version = meta.version ?? "0.1";
  const status = meta.status ?? "Draft";
  const date = meta.date ?? today;
  const author = meta.author ?? "";
  const docNumber = meta.documentNumber ?? "";

  // SVG-based Vopak logo (self-contained, no external deps)
  const logoSvg = `data:image/svg+xml;base64,${Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80"><rect width="400" height="80" fill="white"/><text x="10" y="58" font-family="Arial, sans-serif" font-size="52" font-weight="bold" fill="#0a2373" letter-spacing="8">VOPAK</text></svg>`).toString("base64")}`;
  const logoUrl = meta.logoUrl ?? logoSvg;

  const adminRow = (label: string, value: string) => `
      <tr>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0; font-weight: bold; background-color: #f0f5fa; width: 35%;">${label}</td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">${value}</td>
      </tr>`;

  // Page 1: Cover
  const page1 = `
<div style="page-break-after: always; padding: 40px; min-height: 700px;">
  <div style="margin-bottom: 120px;">
    <img src="${escapeHtml(logoUrl)}" alt="Vopak" style="width: 200px; height: auto;" />
  </div>
  <div style="margin-top: 160px;">
    <p style="font-size: 36pt; font-weight: bold; color: #0a2373; margin: 0; line-height: 1.2; font-family: Arial, sans-serif;">
      ${escapeHtml(meta.documentType)}
    </p>
    <p style="font-size: 16pt; font-weight: bold; color: #0a2373; margin-top: 16px; font-family: Arial, sans-serif;">
      ${escapeHtml(topic)}
    </p>
  </div>
</div>`;

  // Page 2: Document Administration
  const page2 = `
<div style="page-break-after: always;">
  <h1 style="color: #0a2373; font-size: 16pt; font-weight: bold; border-bottom: 2px solid #0a2373; padding-bottom: 6px; margin-bottom: 16px; font-family: Arial, sans-serif;">Document Administration</h1>
  <h2 style="color: #0a2373; font-size: 13pt; font-weight: bold; margin-top: 16px; margin-bottom: 10px; font-family: Arial, sans-serif;">Document information</h2>
  <table style="border-collapse: collapse; width: 100%; font-size: 9pt; font-family: Arial, sans-serif; margin-bottom: 24px;">
    <tbody>
      ${adminRow("Document name", `GIT--Other - ${escapeHtml(title)}`)}
      ${adminRow("Document number", escapeHtml(docNumber))}
      ${adminRow("Document type", escapeHtml(meta.documentType))}
      ${adminRow("Status", escapeHtml(status))}
      ${adminRow("Version", escapeHtml(version))}
      ${adminRow("Last update", escapeHtml(date))}
      ${adminRow("Revision date", "")}
      ${adminRow("Document creator", escapeHtml(author))}
      ${adminRow("Document owner", "")}
      ${adminRow("Document approver", "")}
    </tbody>
  </table>
  <h2 style="color: #0a2373; font-size: 13pt; font-weight: bold; margin-top: 24px; margin-bottom: 10px; font-family: Arial, sans-serif;">Authors and contributors</h2>
  <table style="border-collapse: collapse; width: 100%; font-size: 9pt; font-family: Arial, sans-serif;">
    <thead>
      <tr>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373;">Name</th>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373;">Contribution</th>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373;">Contact details</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">${escapeHtml(author)}</td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">${author ? "Author" : ""}</td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
      </tr>
      <tr>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
      </tr>
    </tbody>
  </table>
</div>`;

  // Page 3: Revision History + TOC
  const page3 = `
<div style="page-break-after: always;">
  <h2 style="color: #0a2373; font-size: 13pt; font-weight: bold; margin-top: 16px; margin-bottom: 10px; font-family: Arial, sans-serif;">Revision history</h2>
  <table style="border-collapse: collapse; width: 100%; font-size: 9pt; font-family: Arial, sans-serif; margin-bottom: 40px;">
    <thead>
      <tr>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373; width: 15%;">Version</th>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373; width: 20%;">Date</th>
        <th style="background-color: #0a2373; color: #ffffff; font-weight: bold; padding: 8px 10px; text-align: left; border: 1px solid #0a2373;">Change description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">${escapeHtml(version)}</td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">${escapeHtml(date)}</td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;">Initial version</td>
      </tr>
      <tr>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
        <td style="padding: 6px 10px; border: 1px solid #d0d0d0;"></td>
      </tr>
    </tbody>
  </table>
  <h1 style="color: #0a2373; font-size: 16pt; font-weight: bold; border-bottom: 2px solid #0a2373; padding-bottom: 6px; margin-top: 40px; font-family: Arial, sans-serif;">Table of contents</h1>
  <p style="font-size: 10pt; color: #666666; font-style: italic; font-family: Arial, sans-serif;">(Update table of contents manually in Google Docs: Insert → Table of contents)</p>
</div>`;

  return page1 + page2 + page3;
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();

  // 1. Read input files
  console.log(`📄 Reading: ${args.inputFile}`);
  if (!existsSync(args.inputFile)) {
    console.error(`❌ File not found: ${args.inputFile}`);
    process.exit(1);
  }
  const markdown = readFileSync(args.inputFile, "utf-8");

  console.log(`🎨 Reading CSS: ${args.cssPath}`);
  if (!existsSync(args.cssPath)) {
    console.error(`❌ CSS file not found: ${args.cssPath}`);
    console.error(`   Expected at: ${args.cssPath}`);
    process.exit(1);
  }
  const css = readFileSync(args.cssPath, "utf-8");

  // 2. Determine title
  const title = args.name || extractTitle(markdown, args.inputFile);
  console.log(`📝 Title: ${title}`);

  // 3. Convert MD → HTML
  console.log("🔄 Converting Markdown → HTML...");
  const bodyHtml = convertMarkdownToHtml(markdown);

  // Count elements for reporting
  const tableCount = (bodyHtml.match(/<table>/g) || []).length;
  const headingCount = (bodyHtml.match(/<h[1-6]>/g) || []).length;
  console.log(`   Found: ${tableCount} tables, ${headingCount} headings`);

  // 4. Generate corporate front-matter if --meta provided
  let coverHtml = "";
  if (args.meta) {
    console.log("📋 Generating corporate front-matter (3 pages)...");
    coverHtml = generateCoverPagesLocal(args.meta, title);
  }

  // 5. Assemble full HTML with branding
  const fullHtml = assembleHtml(bodyHtml, css, title, coverHtml);

  // 5. Inline CSS (Google Docs ignores <style> blocks — only preserves inline style="" attributes)
  console.log("🔧 Inlining CSS for Google Docs compatibility...");
  const inlinedHtml = juice(fullHtml, {
    removeStyleTags: true,
    preserveMediaQueries: false,
  });
  console.log(`   HTML size: ${(inlinedHtml.length / 1024).toFixed(1)} KB`);

  // 6. Save locally if requested
  if (args.outputPath) {
    writeFileSync(args.outputPath, inlinedHtml, "utf-8");
    console.log(`💾 Saved HTML to: ${args.outputPath}`);
  }

  // 7. Dry run → output and exit
  if (args.dryRun) {
    if (!args.outputPath) {
      console.log("\n--- HTML Output (dry run) ---\n");
      console.log(inlinedHtml);
    }
    console.log("\n✅ Dry run complete. No upload performed.");
    return;
  }

  // 8. Get OAuth token via ADC (google-auth-library)
  console.log("🔑 Getting OAuth token via ADC...");
  const token = await getAccessToken();

  // 9. Upload to Google Drive
  console.log(`📤 Uploading to Google Drive (folder: ${args.folderId})...`);
  try {
    const result = await uploadToGoogleDrive(inlinedHtml, title, args.folderId, token);

    // 10. Set A4 portrait page size (Google Docs defaults to Letter landscape on HTML import)
    await setA4Portrait(result.id, token);

    console.log(`\n✅ Google Doc created successfully!`);
    console.log(`   📄 Title: ${result.name}`);
    console.log(`   🆔 ID: ${result.id}`);
    console.log(`   📋 MIME: ${result.mimeType}`);
    console.log(`   🔗 URL: ${result.url}`);

    // Output just the URL for easy piping
    if (process.env.QUIET) {
      process.stdout.write(result.url);
    }
  } catch (error) {
    console.error(`\n❌ Upload failed: ${(error as Error).message}`);
    // Save HTML locally as fallback
    const fallbackPath = `/tmp/${title.replace(/[^a-zA-Z0-9]/g, "_")}.html`;
    writeFileSync(fallbackPath, inlinedHtml, "utf-8");
    console.error(`💾 HTML saved to: ${fallbackPath} (upload manually)`);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
