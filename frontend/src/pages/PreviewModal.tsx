/**
 * PreviewModal — Fullscreen side-by-side PDF + XML preview.
 *
 * Left panel: browser-native PDF rendering with zoom controls.
 * Right panel: pretty-printed, syntax-highlighted XML with zoom + copy.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  X,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Copy,
  Check,
  FileText,
  Code2,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { fetchPdfBlobUrl, getPreviewXml } from '../api/orders';

interface PreviewModalProps {
  orderId: string;
  orderNumber: string | null;
  onClose: () => void;
}

/** Zoom steps shared by both panels. */
const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200, 250, 300];
const DEFAULT_ZOOM_INDEX = 2; // 100%

/** Pretty-print raw XML with proper indentation. */
function formatXml(raw: string): string {
  const INDENT = '  ';
  let formatted = '';
  let indent = 0;

  // Trim leading/trailing whitespace inside every text node so padded
  // values from the backend don't bleed into the display.
  const trimmed = raw.replace(
    /(<[^/][^>]*>)([\s\S]*?)(<\/)/g,
    (_match, open: string, text: string, close: string) =>
      `${open}${text.trim()}${close}`,
  );
  const xml = trimmed.replace(/>\s*</g, '><').trim();

  xml.split(/(<[^>]+>)/g).forEach((node) => {
    if (!node.trim()) return;

    if (node.startsWith('<?')) {
      // XML declaration
      formatted += node + '\n';
    } else if (node.match(/^<\/\w/)) {
      // Closing tag.
      // Key insight: after a text-content node is merged onto the opening tag's
      // line, `formatted` does NOT end with '\n'. In that case the closing tag
      // must be appended directly — adding INDENT spaces first would create the
      // visible gap "[Supplier Name]           </Name>".
      indent = Math.max(0, indent - 1);
      if (formatted.endsWith('\n')) {
        // Closing tag follows child elements — indent on its own line
        formatted += INDENT.repeat(indent) + node + '\n';
      } else {
        // Closing tag follows inline text — no indent padding, just close
        formatted += node + '\n';
      }
    } else if (node.match(/^<\w[^>]*\/\s*>$/)) {
      // Self-closing tag
      formatted += INDENT.repeat(indent) + node + '\n';
    } else if (node.match(/^<\w/)) {
      // Opening tag
      formatted += INDENT.repeat(indent) + node + '\n';
      indent++;
    } else {
      // Text content — merge onto the opening tag's line.
      // For multiline text nodes (embedded \n from ERP spec lines),
      // each continuation line is individually indented so it doesn't appear
      // flush-left at column 0.
      const lastNewline = formatted.lastIndexOf('\n', formatted.length - 2);
      const lastLine = formatted.substring(lastNewline + 1);
      formatted = formatted.substring(0, lastNewline + 1);
      const currentIndent = INDENT.repeat(indent);
      const indentedNode = node
        .split('\n')
        .map((line, i) =>
          i === 0
            ? line.trim()                        // first line: trim only (merged after opening tag)
            : currentIndent + line.trim(),       // continuation lines: re-indent
        )
        .join('\n');
      formatted += lastLine.replace(/\n$/, '') + indentedNode;
    }
  });

  return formatted.trim();
}

/** Parse an XML line into React spans with syntax coloring. */
function renderXmlLine(line: string, lineNum: number): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let key = 0;

  const push = (text: string, cls?: string) => {
    if (!text) return;
    parts.push(
      cls ? (
        <span key={key++} className={cls}>{text}</span>
      ) : (
        <span key={key++}>{text}</span>
      ),
    );
  };

  // Preserve leading indentation — emit it verbatim before any tag parsing.
  // Without this, the while-loop's text-content branch trims the spaces away,
  // collapsing every line to the left margin.
  const indentLen = /^[ \t]*/.exec(line)?.[0].length ?? 0;
  if (indentLen > 0) {
    push(line.slice(0, indentLen));
  }
  let remaining = line.slice(indentLen);

  while (remaining.length > 0) {
    // XML declaration <?...?>
    if (remaining.startsWith('<?')) {
      const end = remaining.indexOf('?>');
      if (end !== -1) {
        push(remaining.slice(0, end + 2), 'xml-decl');
        remaining = remaining.slice(end + 2);
        continue;
      }
    }

    // Closing tag </Tag>
    if (remaining.startsWith('</')) {
      const end = remaining.indexOf('>');
      if (end !== -1) {
        const tagContent = remaining.slice(0, end + 1);
        const match = tagContent.match(/^(<\/)([\w:]+)(>)$/);
        if (match) {
          push(match[1] ?? '</', 'xml-bracket');
          push(match[2] ?? '', 'xml-tag');
          push(match[3] ?? '>', 'xml-bracket');
        } else {
          push(tagContent, 'xml-bracket');
        }
        remaining = remaining.slice(end + 1);
        continue;
      }
    }

    // Opening tag <Tag ...> or <Tag ... />
    if (remaining.startsWith('<') && !remaining.startsWith('</')) {
      const end = remaining.indexOf('>');
      if (end !== -1) {
        const tagContent = remaining.slice(0, end + 1);
        const selfClosing = tagContent.endsWith('/>');

        const tagMatch = tagContent.match(/^<([\w:]+)/);
        if (tagMatch) {
          push('<', 'xml-bracket');
          push(tagMatch[1] ?? '', 'xml-tag');

          let attrStr = tagContent.slice(1 + (tagMatch[1] ?? '').length);
          if (selfClosing) {
            attrStr = attrStr.slice(0, -2);
          } else {
            attrStr = attrStr.slice(0, -1);
          }

          const attrRegex = /\s+([\w:]+)="([^"]*)"/g;
          let attrMatch: RegExpExecArray | null;
          let lastIdx = 0;
          while ((attrMatch = attrRegex.exec(attrStr)) !== null) {
            if (attrMatch.index > lastIdx) {
              push(attrStr.slice(lastIdx, attrMatch.index));
            }
            push(' ');
            push(attrMatch[1] ?? '', 'xml-attr-name');
            push('=');
            push(`"${attrMatch[2] ?? ''}"`, 'xml-attr-val');
            lastIdx = attrMatch.index + attrMatch[0].length;
          }
          if (lastIdx < attrStr.length) {
            push(attrStr.slice(lastIdx));
          }

          if (selfClosing) {
            push(' />', 'xml-bracket');
          } else {
            push('>', 'xml-bracket');
          }
        } else {
          push(tagContent, 'xml-bracket');
        }
        remaining = remaining.slice(end + 1);
        continue;
      }
    }

    // Text content — do NOT trim; formatXml already trims text nodes.
    // Trimming here is what destroyed indentation in the first place.
    const nextTag = remaining.indexOf('<');
    if (nextTag === -1) {
      push(remaining, 'xml-text');
      remaining = '';
    } else if (nextTag > 0) {
      push(remaining.slice(0, nextTag), 'xml-text');
      remaining = remaining.slice(nextTag);
    } else {
      push(remaining[0] ?? '', 'xml-text');
      remaining = remaining.slice(1);
    }
  }

  return (
    <div key={lineNum} className="xml-line">
      <span className="xml-line-num">{lineNum + 1}</span>
      <span className="xml-line-content">{parts}</span>
    </div>
  );
}

export default function PreviewModal({
  orderId,
  orderNumber,
  onClose,
}: PreviewModalProps) {
  const [xmlContent, setXmlContent] = useState<string>('');
  const [xmlLoading, setXmlLoading] = useState(true);
  const [xmlError, setXmlError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(true);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pdfZoomIndex, setPdfZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [xmlZoomIndex, setXmlZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [copied, setCopied] = useState(false);

  const pdfZoom = ZOOM_LEVELS[pdfZoomIndex] ?? 100;
  const xmlZoom = ZOOM_LEVELS[xmlZoomIndex] ?? 100;

  // Load PDF blob via authenticated request
  useEffect(() => {
    let cancelled = false;
    const loadPdf = async () => {
      setPdfLoading(true);
      setPdfError(null);
      try {
        const blobUrl = await fetchPdfBlobUrl(orderId);
        if (!cancelled) setPdfBlobUrl(blobUrl);
      } catch (err) {
        if (!cancelled) {
          setPdfError(
            err instanceof Error ? err.message : 'Failed to load PDF',
          );
        }
      } finally {
        if (!cancelled) setPdfLoading(false);
      }
    };
    void loadPdf();
    return () => {
      cancelled = true;
      // Clean up blob URL to avoid memory leak
      setPdfBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [orderId]);

  // Load XML preview on mount
  useEffect(() => {
    let cancelled = false;
    const loadXml = async () => {
      setXmlLoading(true);
      setXmlError(null);
      try {
        const raw = await getPreviewXml(orderId);
        if (!cancelled) setXmlContent(raw);
      } catch (err) {
        if (!cancelled) {
          setXmlError(
            err instanceof Error ? err.message : 'Failed to generate XML preview',
          );
        }
      } finally {
        if (!cancelled) setXmlLoading(false);
      }
    };
    void loadXml();
    return () => { cancelled = true; };
  }, [orderId]);

  // Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const handleCopyXml = useCallback(async () => {
    try {
      const formatted = formatXml(xmlContent);
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn('Clipboard write failed:', err);
    }
  }, [xmlContent]);

  const formattedXml = useMemo(
    () => (xmlContent ? formatXml(xmlContent) : ''),
    [xmlContent],
  );

  const xmlLines = useMemo(
    () => formattedXml.split('\n').map((line, i) => renderXmlLine(line, i)),
    [formattedXml],
  );

  /** Reusable zoom toolbar */
  const ZoomToolbar = ({
    zoomIndex,
    zoomLevel,
    onZoomIn,
    onZoomOut,
    onReset,
    prefix,
  }: {
    zoomIndex: number;
    zoomLevel: number;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onReset: () => void;
    prefix: string;
  }) => (
    <div className="preview-zoom-controls">
      <button
        type="button"
        className="preview-zoom-btn"
        onClick={onZoomOut}
        disabled={zoomIndex === 0}
        title="Zoom Out"
        aria-label="Zoom out"
        id={`${prefix}-zoom-out`}
      >
        <ZoomOut size={14} />
      </button>
      <span className="preview-zoom-level">{zoomLevel}%</span>
      <button
        type="button"
        className="preview-zoom-btn"
        onClick={onZoomIn}
        disabled={zoomIndex === ZOOM_LEVELS.length - 1}
        title="Zoom In"
        aria-label="Zoom in"
        id={`${prefix}-zoom-in`}
      >
        <ZoomIn size={14} />
      </button>
      <div className="preview-zoom-divider" />
      <button
        type="button"
        className="preview-zoom-btn"
        onClick={onReset}
        title="Reset to 100%"
        aria-label="Reset zoom"
        id={`${prefix}-zoom-fit`}
      >
        <Maximize2 size={14} />
      </button>
    </div>
  );

  return (
    <div className="preview-overlay" id="preview-modal">
      {/* Header */}
      <div className="preview-header">
        <div className="preview-header-left">
          <FileText size={18} />
          <span className="preview-title">
            Preview - Order {orderNumber ?? orderId.slice(0, 8)}
          </span>
        </div>
        <button
          type="button"
          className="preview-close-btn"
          onClick={onClose}
          title="Close (Esc)"
          aria-label="Close preview"
          id="preview-close-btn"
        >
          <X size={18} />
          <span className="preview-close-label">Close</span>
        </button>
      </div>

      {/* Panels */}
      <div className="preview-panels">
        {/* ── Left: PDF ──────────────────────────────────────────── */}
        <div className="preview-panel preview-panel-pdf">
          <div className="preview-panel-toolbar">
            <div className="preview-panel-label">
              <FileText size={14} />
              Source PDF
            </div>
            <ZoomToolbar
              zoomIndex={pdfZoomIndex}
              zoomLevel={pdfZoom}
              onZoomIn={() => setPdfZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1))}
              onZoomOut={() => setPdfZoomIndex((i) => Math.max(i - 1, 0))}
              onReset={() => setPdfZoomIndex(DEFAULT_ZOOM_INDEX)}
              prefix="pdf"
            />
          </div>
          <div className="preview-pdf-container">
            {pdfLoading ? (
              <div className="preview-xml-loading">
                <Loader2 size={24} className="spin" />
                <span>Loading PDF...</span>
              </div>
            ) : pdfError ? (
              <div className="preview-xml-error">
                <AlertCircle size={20} />
                <span>{pdfError}</span>
              </div>
            ) : pdfBlobUrl ? (
              <div
                className="preview-pdf-scroller"
                style={{
                  transform: `scale(${pdfZoom / 100})`,
                  transformOrigin: 'top left',
                  width: `${10000 / pdfZoom}%`,
                  height: `${10000 / pdfZoom}%`,
                }}
              >
                <iframe
                  src={pdfBlobUrl}
                  className="preview-pdf-iframe"
                  title="PDF Preview"
                  id="pdf-preview-iframe"
                />
              </div>
            ) : null}
          </div>
        </div>

        {/* ── Divider ────────────────────────────────────────────── */}
        <div className="preview-divider" />

        {/* ── Right: XML ─────────────────────────────────────────── */}
        <div className="preview-panel preview-panel-xml">
          <div className="preview-panel-toolbar">
            <div className="preview-panel-label">
              <Code2 size={14} />
              XML Preview
            </div>
            <div className="preview-toolbar-actions">
              <ZoomToolbar
                zoomIndex={xmlZoomIndex}
                zoomLevel={xmlZoom}
                onZoomIn={() => setXmlZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1))}
                onZoomOut={() => setXmlZoomIndex((i) => Math.max(i - 1, 0))}
                onReset={() => setXmlZoomIndex(DEFAULT_ZOOM_INDEX)}
                prefix="xml"
              />
              {xmlContent && (
                <button
                  type="button"
                  className="preview-copy-btn"
                  onClick={() => void handleCopyXml()}
                  aria-label="Copy XML"
                  id="xml-copy-btn"
                >
                  {copied ? (
                    <><Check size={14} /> Copied!</>
                  ) : (
                    <><Copy size={14} /> Copy</>
                  )}
                </button>
              )}
            </div>
          </div>
          <div className="preview-xml-container">
            {xmlLoading ? (
              <div className="preview-xml-loading">
                <Loader2 size={24} className="spin" />
                <span>Generating XML preview...</span>
              </div>
            ) : xmlError ? (
              <div className="preview-xml-error">
                <AlertCircle size={20} />
                <span>{xmlError}</span>
              </div>
            ) : (
              <div
                className="preview-xml-scroll"
                style={{
                  transform: `scale(${xmlZoom / 100})`,
                  transformOrigin: 'top left',
                  width: `${10000 / xmlZoom}%`,
                }}
              >
                <pre className="preview-xml-code" id="xml-preview-code">
                  <code>{xmlLines}</code>
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
