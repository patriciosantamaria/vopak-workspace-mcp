import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as child_process from "node:child_process";

// Configuration
const MARKDOWN_FILE = "/home/patricio-santamaria/Projects/flow-forward-with-ai/docs/03_Program_Ops/Strategy/ADD_Enterprise_AI_Agent_Platform_v1.0.md";
const START_INDEX = 1095; // Start of page 4 (after Table of Contents in ADD template)

interface TableData {
  rows: string[][];
}

interface TextBlock {
  type: "heading" | "bullet" | "paragraph" | "table_placeholder";
  level?: number;
  text: string;
  tableIndex?: number;
  boldRanges?: { start: number; end: number }[];
}

function runGwsCommand(args: string[], jsonInput?: any): any {
  const cmd = ["/usr/local/bin/gws", ...args];
  
  if (jsonInput !== undefined) {
    cmd.push("--json", JSON.stringify(jsonInput));
  }
  
  const res = child_process.spawnSync(cmd[0], cmd.slice(1), {
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024 // 50MB buffer to prevent ENOMEM on large docs
  });
  
  if (res.status !== 0 || res.error) {
    console.error("❌ GWS command failed details:");
    console.error("Exit Code:", res.status);
    console.error("Signal:", res.signal);
    console.error("Error object:", res.error);
    console.error("Stdout:", res.stdout);
    console.error("Stderr:", res.stderr);
    throw new Error(`gws command failed with code ${res.status}: ${res.stderr || res.stdout}\nCommand: ${cmd.join(" ")}`);
  }
  
  try {
    return JSON.parse(res.stdout);
  } catch (e) {
    return res.stdout;
  }
}

function parseMarkdown(mdPath: string): { blocks: TextBlock[]; tables: TableData[] } {
  const md = readFileSync(mdPath, "utf-8");
  const lines = md.split(/\r?\n/);
  
  const blocks: TextBlock[] = [];
  const tables: TableData[] = [];
  
  let inMetadata = true;
  let currentTableRows: string[][] = [];
  let inTable = false;
  
  for (const rawLine of lines) {
    const line = rawLine.trim();
    
    // Skip YAML metadata header at the start of the file
    if (inMetadata) {
      if (line === "---") {
        if (blocks.length > 0 || md.indexOf("---") !== md.lastIndexOf("---")) {
          // Second separator marks the end of YAML metadata
          inMetadata = false;
          continue;
        }
      }
      if (line.startsWith("Document Type:") || line.startsWith("Target Audience:") || line.startsWith("Author:") || line.startsWith("Date:") || line.startsWith("Status:") || line.startsWith("Version:")) {
        continue;
      }
      if (line === "" && inMetadata) {
        continue;
      }
    }
    
    // Handle Tables
    if (line.startsWith("|")) {
      inTable = true;
      // Skip separator row like | :--- | :--- |
      if (line.includes("---")) {
        continue;
      }
      const cells = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      currentTableRows.push(cells);
      continue;
    } else if (inTable) {
      // Table ended
      tables.push({ rows: currentTableRows });
      blocks.push({
        type: "table_placeholder",
        text: `[TABLE_PLACEHOLDER_${tables.length - 1}]`,
        tableIndex: tables.length - 1
      });
      currentTableRows = [];
      inTable = false;
    }
    
    if (line === "") {
      continue;
    }
    
    // Handle Headings
    if (line.startsWith("# ")) {
      blocks.push({ type: "heading", level: 1, text: line.substring(2) });
    } else if (line.startsWith("## ")) {
      blocks.push({ type: "heading", level: 2, text: line.substring(3) });
    } else if (line.startsWith("### ")) {
      blocks.push({ type: "heading", level: 3, text: line.substring(4) });
    } else if (line.startsWith("#### ")) {
      blocks.push({ type: "heading", level: 4, text: line.substring(5) });
    }
    // Handle Bullet Lists
    else if (line.startsWith("* ") || line.startsWith("- ")) {
      blocks.push({ type: "bullet", text: line.substring(2) });
    }
    // Handle Horizontal Rule
    else if (line === "---") {
      blocks.push({ type: "paragraph", text: "────────────────────────────────────────────────────────────────────────────────" });
    }
    // Handle standard paragraph
    else {
      // Clean up markdown blockquotes if present
      const cleanText = line.startsWith("> ") ? line.substring(2) : line;
      blocks.push({ type: "paragraph", text: cleanText });
    }
  }
  
  // Clean up if file ends during a table
  if (inTable) {
    tables.push({ rows: currentTableRows });
    blocks.push({
      type: "table_placeholder",
      text: `[TABLE_PLACEHOLDER_${tables.length - 1}]`,
      tableIndex: tables.length - 1
    });
  }
  
  return { blocks, tables };
}

// Helper to remove markdown bold indicators and extract ranges
function processBoldRanges(text: string): { cleanText: string; boldRanges: { start: number; end: number }[] } {
  let cleanText = "";
  const boldRanges: { start: number; end: number }[] = [];
  let remaining = text;
  
  while (remaining.includes("**")) {
    const startIdx = remaining.indexOf("**");
    cleanText += remaining.substring(0, startIdx);
    const endIdx = remaining.indexOf("**", startIdx + 2);
    if (endIdx === -1) {
      // Malformed bold, treat as plain text
      cleanText += remaining.substring(startIdx);
      remaining = "";
      break;
    }
    const boldText = remaining.substring(startIdx + 2, endIdx);
    const boldStart = cleanText.length;
    cleanText += boldText;
    const boldEnd = cleanText.length;
    boldRanges.push({ start: boldStart, end: boldEnd });
    remaining = remaining.substring(endIdx + 2);
  }
  cleanText += remaining;
  
  // Clean up markdown links like [text](url) to "text (url)"
  let linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;
  while ((match = linkRegex.exec(cleanText)) !== null) {
    const fullMatch = match[0];
    const linkText = match[1];
    const linkUrl = match[2];
    const replacement = `${linkText} (${linkUrl})`;
    const matchStart = match.index;
    cleanText = cleanText.substring(0, matchStart) + replacement + cleanText.substring(matchStart + fullMatch.length);
    // Shift any bold ranges that come after this match
    const diff = replacement.length - fullMatch.length;
    for (const range of boldRanges) {
      if (range.start > matchStart) {
        range.start += diff;
        range.end += diff;
      }
    }
    linkRegex.lastIndex = matchStart + replacement.length;
  }

  return { cleanText, boldRanges };
}

function findTableAtIndex(doc: any, placeholderIndex: number): any {
  for (const elem of doc.body.content || []) {
    if (elem.table && elem.startIndex >= placeholderIndex && elem.startIndex <= placeholderIndex + 2) {
      return elem;
    }
  }
  throw new Error(`Failed to locate table at or near index ${placeholderIndex}`);
}

function updateDocument(documentId: string) {
  console.log(`\n🔍 Fetching document ${documentId} via gws CLI...`);
  const doc = runGwsCommand(["docs", "documents", "get", "--params", JSON.stringify({ documentId })]);
  
  const content = doc.body.content || [];
  const lastElem = content[content.length - 1];
  const totalLength = lastElem.endIndex;
  
  console.log(`   Document total index length: ${totalLength}`);
  
  // Parse Markdown
  console.log("📝 Parsing markdown file...");
  const { blocks, tables } = parseMarkdown(MARKDOWN_FILE);
  console.log(`   Found ${blocks.length} text blocks and ${tables.length} tables.`);
  
  // Step 1: Delete all text from START_INDEX to totalLength - 1
  if (totalLength > START_INDEX + 1) {
    console.log(`🗑️ Deleting old briefing content (index ${START_INDEX} to ${totalLength - 1})...`);
    const deleteRequest = {
      deleteContentRange: {
        range: {
          startIndex: START_INDEX,
          endIndex: totalLength - 1
        }
      }
    };
    
    runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
      requests: [deleteRequest]
    });
    console.log("   Deletion complete.");
  } else {
    console.log("   No content to delete (briefing is already empty).");
  }
  
  // Step 2: Insert text only (reverse order at START_INDEX)
  console.log("📤 Staging text insertion requests (reverse order at START_INDEX)...");
  const insertRequests: any[] = [];
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    const { cleanText } = processBoldRanges(block.text);
    insertRequests.push({
      insertText: {
        location: { index: START_INDEX },
        text: cleanText + "\n"
      }
    });
  }
  
  console.log(`   Sending batch update for ${insertRequests.length} text insertions...`);
  runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
    requests: insertRequests
  });
  console.log("   Text insertion complete.");
  
  // Step 3: Fetch doc to get the actual updated length/indices and apply body formatting
  console.log("🔄 Fetching document to calculate exact paragraph style ranges...");
  const styleDoc = runGwsCommand(["docs", "documents", "get", "--params", JSON.stringify({ documentId })]);
  
  console.log("📤 Staging text formatting and style requests...");
  const styleRequests: any[] = [];
  let currentIndex = START_INDEX;
  
  for (const block of blocks) {
    const { cleanText, boldRanges } = processBoldRanges(block.text);
    const insertLength = cleanText.length + 1; // +1 for the trailing newline
    
    // Set paragraph formatting (Headings)
    if (block.type === "heading") {
      let style = "NORMAL_TEXT";
      if (block.level === 1) style = "HEADING_1";
      else if (block.level === 2) style = "HEADING_2";
      else if (block.level === 3) style = "HEADING_3";
      else if (block.level === 4) style = "HEADING_4";
      
      styleRequests.push({
        updateParagraphStyle: {
          paragraphStyle: { namedStyleType: style },
          range: { startIndex: currentIndex, endIndex: currentIndex + insertLength },
          fields: "namedStyleType"
        }
      });
    } 
    // Set bullet lists
    else if (block.type === "bullet") {
      styleRequests.push({
        createParagraphBullets: {
          bulletPreset: "BULLET_DISC_CIRCLE_SQUARE",
          range: { startIndex: currentIndex, endIndex: currentIndex + insertLength }
        }
      });
    }
    
    // Set bold styling for specific ranges inside this text run
    for (const range of boldRanges) {
      styleRequests.push({
        updateTextStyle: {
          textStyle: { bold: true, foregroundColor: { color: { rgbColor: { red: 10/255, green: 35/255, blue: 115/255 } } } }, // Vopak Deep Blue for bold text runs
          range: {
            startIndex: currentIndex + range.start,
            endIndex: currentIndex + range.end
          },
          fields: "bold,foregroundColor"
        }
      });
    }
    
    currentIndex += insertLength;
  }
  
  console.log(`   Sending batch update for ${styleRequests.length} styling requests...`);
  runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
    requests: styleRequests
  });
  console.log("   Text formatting complete.");
  
  // Step 4: Insert Native Tables in place of [TABLE_PLACEHOLDER_i]
  for (let i = 0; i < tables.length; i++) {
    const table = tables[i];
    const placeholder = `[TABLE_PLACEHOLDER_${i}]`;
    console.log(`📊 Processing native table for ${placeholder}...`);
    
    // Fetch doc again to locate placeholder index
    const refDoc = runGwsCommand(["docs", "documents", "get", "--params", JSON.stringify({ documentId })]);
    let placeholderIndex = -1;
    for (const elem of refDoc.body.content || []) {
      if (elem.paragraph) {
        const text = (elem.paragraph.elements || [])
          .map((e: any) => e.textRun?.content || "")
          .join("");
        if (text.includes(placeholder)) {
          placeholderIndex = elem.startIndex;
          break;
        }
      }
    }
    
    if (placeholderIndex === -1) {
      console.warn(`⚠️  Could not find placeholder ${placeholder}`);
      continue;
    }
    
    const rowsCount = table.rows.length;
    const colsCount = table.rows[0].length;
    
    // Replace placeholder with table:
    // First delete the placeholder line (excluding final newline)
    const deletePlaceholderReq = {
      deleteContentRange: {
        range: {
          startIndex: placeholderIndex,
          endIndex: placeholderIndex + placeholder.length
        }
      }
    };
    
    // Insert table request
    const insertTableReq = {
      insertTable: {
        rows: rowsCount,
        columns: colsCount,
        location: { index: placeholderIndex }
      }
    };
    
    console.log(`   Inserting empty table of size ${rowsCount}×${colsCount} at index ${placeholderIndex}...`);
    runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
      requests: [deletePlaceholderReq, insertTableReq]
    });
    
    // Fetch document again to get table cell structural indices!
    let tableDoc = runGwsCommand(["docs", "documents", "get", "--params", JSON.stringify({ documentId })]);
    let tableElem = findTableAtIndex(tableDoc, placeholderIndex);
    const actualTableStartIndex = tableElem.startIndex; // This remains static during cell text insertion
    const tableObj = tableElem.table;
    
    // Step C: Insert cell texts only (no style formatting in this batch)
    console.log("   Inserting cell text payloads...");
    const cellInsertRequests: any[] = [];
    for (let r = rowsCount - 1; r >= 0; r--) {
      const cells = tableObj.tableRows[r].tableCells;
      for (let c = colsCount - 1; c >= 0; c--) {
        const cell = cells[c];
        const cellText = table.rows[r][c];
        const { cleanText } = processBoldRanges(cellText);
        if (cleanText.length > 0) {
          cellInsertRequests.push({
            insertText: {
              location: { index: cell.startIndex + 1 },
              text: cleanText
            }
          });
        }
      }
    }
    
    if (cellInsertRequests.length > 0) {
      runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
        requests: cellInsertRequests
      });
    }
    
    // Step D: Fetch document again to get updated cell indices with inserted text
    console.log("   Applying cell typography and properties formatting...");
    tableDoc = runGwsCommand(["docs", "documents", "get", "--params", JSON.stringify({ documentId })]);
    tableElem = findTableAtIndex(tableDoc, actualTableStartIndex);
    const tableObjUpdated = tableElem.table;
    
    // Step E: Apply formatting and cell styling
    const cellFormatRequests: any[] = [];
    for (let r = 0; r < rowsCount; r++) {
      const isHeader = r === 0;
      const cells = tableObjUpdated.tableRows[r].tableCells;
      
      // Update cell properties (background color)
      const bgColor = isHeader 
        ? { color: { rgbColor: { red: 10/255, green: 35/255, blue: 115/255 } } } // Deep Blue
        : (r % 2 === 0 
            ? { color: { rgbColor: { red: 240/255, green: 245/255, blue: 250/255 } } } // Alternating light gray-blue
            : { color: { rgbColor: { red: 1.0, green: 1.0, blue: 1.0 } } }); // White
        
      cellFormatRequests.push({
        updateTableCellStyle: {
          tableCellStyle: { backgroundColor: bgColor },
          tableRange: {
            tableCellLocation: {
              tableStartLocation: { index: actualTableStartIndex },
              rowIndex: r,
              columnIndex: 0
            },
            rowSpan: 1,
            columnSpan: colsCount
          },
          fields: "backgroundColor"
        }
      });
      
      // Update text style for each cell
      for (let c = 0; c < colsCount; c++) {
        const cell = cells[c];
        const cellText = table.rows[r][c];
        const { cleanText, boldRanges } = processBoldRanges(cellText);
        
        const cellContentStart = cell.startIndex + 1;
        
        // If the cell text is empty, nothing to style
        if (cleanText.length === 0) continue;
        
        if (isHeader) {
          cellFormatRequests.push({
            updateTextStyle: {
              textStyle: { bold: true, fontSize: { magnitude: 9, unit: "PT" }, foregroundColor: { color: { rgbColor: { red: 1.0, green: 1.0, blue: 1.0 } } } },
              range: { startIndex: cellContentStart, endIndex: cellContentStart + cleanText.length },
              fields: "bold,fontSize,foregroundColor"
            }
          });
        } else {
          cellFormatRequests.push({
            updateTextStyle: {
              textStyle: { fontSize: { magnitude: 9, unit: "PT" }, foregroundColor: { color: { rgbColor: { red: 0.2, green: 0.2, blue: 0.2 } } } },
              range: { startIndex: cellContentStart, endIndex: cellContentStart + cleanText.length },
              fields: "fontSize,foregroundColor"
            }
          });
          
          for (const range of boldRanges) {
            cellFormatRequests.push({
              updateTextStyle: {
                textStyle: { bold: true, foregroundColor: { color: { rgbColor: { red: 10/255, green: 35/255, blue: 115/255 } } } }, // Vopak Deep Blue
                range: {
                  startIndex: cellContentStart + range.start,
                  endIndex: cellContentStart + range.end
                },
                fields: "bold,foregroundColor"
              }
            });
          }
        }
      }
    }
    
    runGwsCommand(["docs", "documents", "batchUpdate", "--params", JSON.stringify({ documentId })], {
      requests: cellFormatRequests
    });
    console.log(`   Table ${placeholder} formatted successfully.`);
  }
}

function main() {
  const documentId = process.argv[2];
  if (!documentId) {
    console.error("Usage: npx tsx update_add.ts <documentId>");
    process.exit(1);
  }
  
  try {
    updateDocument(documentId);
    console.log("\n🚀 ADD document updated successfully via gws CLI!");
  } catch (error) {
    console.error("\n❌ Error updating document:", error);
    process.exit(1);
  }
}

main();
