// Small helper layer over docx-js for a Korean technical report (A4).
const fs = require("fs");
const {
  Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  BorderStyle, ShadingType, ImageRun, LevelFormat, Math: DMath, MathRun, VerticalAlign,
} = require("docx");

const FONT = { ascii: "Arial", hAnsi: "Arial", eastAsia: "Malgun Gothic", cs: "Arial" };
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1247;           // A4, 22 mm margins
const CONTENT_W = PAGE_W - 2 * MARGIN;                           // 9412 DXA
const C = { navy: "1F3A5F", ink: "1A1A1A", muted: "5A5A5A", head: "E8EEF5", line: "BFC8D3", accent: "2A78D6" };

let figNo = 0, tabNo = 0;

// "**bold** plain `code`" -> runs
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, font: FONT, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), font: { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "Malgun Gothic" }, size: 18, ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

const P = (text, opt = {}) => new Paragraph({
  children: runs(text, opt.run || {}), spacing: { after: 120, line: 300 },
  alignment: opt.align || AlignmentType.JUSTIFIED, ...(opt.para || {}),
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })], pageBreakBefore: true });
const H1n = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t, font: FONT })] });
const B = (text, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(text), spacing: { after: 60, line: 280 } });
const N = (text, ref = "nums") => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(text), spacing: { after: 60, line: 280 } });

// equation line rendered with Office Math (Cambria Math)
const EQ = (s, note) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 120 },
  children: [new DMath({ children: [new MathRun(s)] }),
    ...(note ? [new TextRun({ text: "   " + note, font: FONT, size: 18, color: C.muted })] : [])],
});

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}

function FIG(file, caption, widthIn = 6.3) {
  const { w, h, data } = pngSize(file);
  const W = Math.round(widthIn * 96), H = Math.round(W * h / w);
  figNo += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data, transformation: { width: W, height: H },
        altText: { title: `그림 ${figNo}`, description: caption, name: `fig${figNo}` } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `그림 ${figNo}. `, bold: true, font: FONT, size: 18, color: C.navy }),
        new TextRun({ text: caption, font: FONT, size: 18, color: C.muted })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: C.line };
const borders = { top: border, bottom: border, left: border, right: border };

// rows: array of arrays of strings; widths in DXA summing to CONTENT_W (scaled automatically)
function TABLE(caption, headers, rows, widths, opt = {}) {
  tabNo += 1;
  const total = widths.reduce((a, b) => a + b, 0);
  const W = widths.map((w) => Math.round(w * CONTENT_W / total));
  W[W.length - 1] += CONTENT_W - W.reduce((a, b) => a + b, 0);
  const size = opt.size || 17;
  const cell = (t, i, head, shade) => new TableCell({
    borders, width: { size: W[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { fill: C.head, type: ShadingType.CLEAR, color: "auto" } : (shade ? { fill: shade, type: ShadingType.CLEAR, color: "auto" } : undefined),
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    children: [new Paragraph({ alignment: (opt.align && opt.align[i]) || AlignmentType.LEFT,
      children: runs(String(t ?? ""), { size, bold: head || undefined }) })],
  });
  const hl = opt.highlightRows || [];
  return [
    new Paragraph({ spacing: { before: 160, after: 60 }, keepNext: true,
      children: [new TextRun({ text: `표 ${tabNo}. `, bold: true, font: FONT, size: 18, color: C.navy }),
        new TextRun({ text: caption, font: FONT, size: 18, color: C.muted })] }),
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: W,
      rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
        ...rows.map((r, ri) => new TableRow({ children: r.map((t, i) => cell(t, i, false, hl.includes(ri) ? "FFF4D6" : null)) }))],
    }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// a shaded call-out box (single-cell table)
function NOTE(title, lines) {
  return [new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: border, bottom: border, left: border, right: border },
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill: "F2F6FB", type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 120, bottom: 120, left: 180, right: 180 },
      children: [new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, font: FONT, color: C.navy })] }),
        ...lines.map((l) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40, line: 280 }, children: runs(l) }))],
    })] })],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}

const numbering = {
  config: [
    { reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 260 } } } }] },
    { reference: "nums", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
    { reference: "nums2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
    { reference: "nums3", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
  ],
};

const styles = {
  default: { document: { run: { font: FONT, size: 20, color: C.ink } } },
  paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 30, bold: true, font: FONT, color: C.navy }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 25, bold: true, font: FONT, color: C.navy }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 22, bold: true, font: FONT, color: "2B4C74" }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
  ],
};

module.exports = { P, H1, H1n, H2, H3, B, N, EQ, FIG, TABLE, NOTE, runs, numbering, styles, FONT, C,
  PAGE_W, PAGE_H, MARGIN, CONTENT_W };
