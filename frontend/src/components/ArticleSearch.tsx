/**
 * ArticleSearch — Premium searchable popover for article/part numbers.
 *
 * Architecture:
 * - AbortController cancels stale requests on new keystrokes
 * - Debounce (300ms) prevents excessive API calls
 * - Keyboard navigation with scroll-into-view
 * - Click-outside dismissal via document listener
 * - Query term highlighting in results
 * - "No results" and "Type to search" empty states
 * - Validation status indicators (✓ valid, ⚠ invalid)
 * - Portal-based popover rendering to escape overflow clipping
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Check, AlertTriangle, Search, X } from 'lucide-react';
import { searchArticles } from '../api/articles';
import type { ArticleResult } from '../api/articles';

/* ── Props ──────────────────────────────────────────────────────────────── */

interface ArticleSearchProps {
  /** Current part number value */
  value: string;
  /** Called when the user types or clears */
  onChange: (value: string) => void;
  /** Called when a specific article is selected from the dropdown */
  onSelect?: (article: ArticleResult) => void;
  /** Validation status: 'valid' | 'invalid' | null */
  validationStatus?: 'valid' | 'invalid' | null;
  /** Read-only mode (shows plain text) */
  readOnly?: boolean;
  /** Container style overrides */
  style?: React.CSSProperties;
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;
const SEARCH_LIMIT = 15;
/** Approximate max height of the popover dropdown. */
const POPOVER_HEIGHT = 320;

/* ── Helpers ────────────────────────────────────────────────────────────── */

/** Highlight matching substring within text. */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;

  return (
    <>
      {text.slice(0, idx)}
      <mark className="article-search-highlight">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

/* ── Portal Popover position helper ─────────────────────────────────── */

interface PopoverPosition {
  top: number;
  left: number;
  width: number;
  flipUp: boolean;
}

function computePopoverPosition(anchor: HTMLElement): PopoverPosition {
  const rect = anchor.getBoundingClientRect();
  const viewportPadding = 16;
  const width = Math.min(
    Math.max(rect.width, 380),
    window.innerWidth - viewportPadding * 2,
  );
  const left = Math.min(
    Math.max(viewportPadding, rect.left),
    window.innerWidth - width - viewportPadding,
  );
  const spaceBelow = window.innerHeight - rect.bottom;
  const flipUp = spaceBelow < POPOVER_HEIGHT;

  return {
    top: flipUp ? rect.top : rect.bottom + 4,
    left,
    width,
    flipUp,
  };
}

/* ── Component ──────────────────────────────────────────────────────────── */

export default function ArticleSearch({
  value,
  onChange,
  onSelect,
  validationStatus = null,
  readOnly = false,
  style,
}: ArticleSearchProps) {
  const [results, setResults] = useState<ArticleResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const [lastQuery, setLastQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState<PopoverPosition | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Recalculate popover position whenever it opens or viewport changes ──

  const updatePosition = useCallback(() => {
    if (!containerRef.current || !isOpen) return;
    setPopoverPosition(computePopoverPosition(containerRef.current));
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    updatePosition();

    // Recalculate on scroll (any ancestor) and resize
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen, updatePosition]);

  // ── Debounced search with AbortController ─────────────────────────────

  const doSearch = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setIsOpen(false);
      setHasSearched(false);
      return;
    }

    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setLastQuery(trimmed);

    try {
      const data = await searchArticles(trimmed, SEARCH_LIMIT);
      // Guard against stale responses
      if (controller.signal.aborted) return;
      setResults(data);
      setIsOpen(true);
      setHasSearched(true);
      setHighlightIndex(-1);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setResults([]);
      setIsOpen(false);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    onChange(newValue);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(newValue), DEBOUNCE_MS);
  };

  const handleClear = () => {
    onChange('');
    setResults([]);
    setIsOpen(false);
    setHasSearched(false);
    inputRef.current?.focus();
  };

  // ── Selection ─────────────────────────────────────────────────────────

  const handleSelect = (article: ArticleResult) => {
    onChange(article.artikelnummer);
    onSelect?.(article);
    setIsOpen(false);
    setResults([]);
    setHasSearched(false);
  };

  // ── Keyboard navigation ───────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      // Re-open dropdown on arrow down if we have results
      if (e.key === 'ArrowDown' && results.length > 0) {
        e.preventDefault();
        setIsOpen(true);
        setHighlightIndex(0);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex((prev) => {
          const next = prev < results.length - 1 ? prev + 1 : 0;
          scrollOptionIntoView(next);
          return next;
        });
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex((prev) => {
          const next = prev > 0 ? prev - 1 : results.length - 1;
          scrollOptionIntoView(next);
          return next;
        });
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex >= 0 && highlightIndex < results.length) {
          const selected = results[highlightIndex];
          if (selected) handleSelect(selected);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        inputRef.current?.blur();
        break;
      case 'Tab':
        setIsOpen(false);
        break;
    }
  };

  /** Scroll the highlighted option into the visible area of the dropdown. */
  const scrollOptionIntoView = (index: number) => {
    requestAnimationFrame(() => {
      const dropdown = dropdownRef.current;
      if (!dropdown) return;
      const option = dropdown.children[index] as HTMLElement | undefined;
      option?.scrollIntoView({ block: 'nearest' });
    });
  };

  // ── Click outside to close ────────────────────────────────────────────

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        // Also check if the click is inside the portal popover
        const portalPopover = document.getElementById('article-search-portal-popover');
        if (portalPopover && portalPopover.contains(e.target as Node)) return;
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Cleanup on unmount ────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, []);

  // ── Render ────────────────────────────────────────────────────────────

  if (readOnly) {
    return <span>{value || '—'}</span>;
  }

  const showClear = value.length > 0;
  const showDropdown = isOpen && (results.length > 0 || (hasSearched && !isLoading));

  // Build the popover content to render via portal
  const popoverContent = showDropdown && popoverPosition ? (
    <div
      id="article-search-portal-popover"
      className={`article-search-popover${popoverPosition.flipUp ? ' article-search-popover-flip' : ''}`}
      style={{
        position: 'fixed',
        top: popoverPosition.flipUp ? undefined : popoverPosition.top,
        bottom: popoverPosition.flipUp
          ? window.innerHeight - popoverPosition.top + 4
          : undefined,
        left: popoverPosition.left,
        width: popoverPosition.width,
      }}
    >
      {results.length > 0 ? (
        <>
          <div className="article-search-popover-header">
            <span className="article-search-result-count">
              {results.length} result{results.length !== 1 ? 's' : ''}
            </span>
            <span className="article-search-hint">
              ↑↓ navigate · Enter select · Esc close
            </span>
          </div>
          <ul
            ref={dropdownRef}
            className="article-search-dropdown"
            role="listbox"
          >
            {results.map((article, idx) => (
              <li
                key={article.id}
                className={`article-search-option ${
                  idx === highlightIndex ? 'article-search-option-active' : ''
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(article);
                }}
                onMouseEnter={() => setHighlightIndex(idx)}
                role="option"
                aria-selected={idx === highlightIndex}
              >
                <span className="article-search-option-code">
                  <HighlightMatch text={article.artikelnummer} query={lastQuery} />
                </span>
                <span className="article-search-option-separator">—</span>
                <span className="article-search-option-name">
                  <HighlightMatch text={article.artikelbenamning} query={lastQuery} />
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : hasSearched && !isLoading ? (
        <div className="article-search-empty">
          <AlertTriangle size={16} />
          <span>No articles match "<strong>{lastQuery}</strong>"</span>
        </div>
      ) : null}
    </div>
  ) : null;

  return (
    <div
      ref={containerRef}
      className="article-search-container"
      style={style}
    >
      {/* ── Input with icons ──────────────────────────────────────────── */}
      <div className="article-search-input-wrapper">
        <div className="article-search-leading-icon">
          {isLoading ? (
            <div className="article-search-spinner" />
          ) : (
            <Search size={14} className="article-search-search" />
          )}
        </div>
        <input
          ref={inputRef}
          type="text"
          className={`form-input article-search-input ${
            validationStatus === 'valid'
              ? 'article-search-valid'
              : validationStatus === 'invalid'
                ? 'article-search-invalid'
                : ''
          }`}
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          placeholder="Search article…"
          autoComplete="off"
          spellCheck={false}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          role="combobox"
        />
        <div className="article-search-trailing-icon">
          {showClear ? (
            <button
              type="button"
              className="article-search-clear-btn"
              onClick={handleClear}
              tabIndex={-1}
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          ) : validationStatus === 'valid' ? (
            <Check size={14} className="article-search-check" />
          ) : validationStatus === 'invalid' ? (
            <AlertTriangle size={14} className="article-search-warn" />
          ) : null}
        </div>
      </div>

      {/* ── Popover dropdown (rendered via portal to escape overflow clipping) ── */}
      {popoverContent && createPortal(popoverContent, document.body)}
    </div>
  );
}
