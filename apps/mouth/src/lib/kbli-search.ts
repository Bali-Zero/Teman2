// =============================================================================
// KBLI 2025 Search Algorithm
// Client-side 3-tier search: exact code -> relevance scoring -> fuzzy matching
// =============================================================================

import type {
  KBLICode,
  KBLISearchResult,
  KBLIPmaStatus,
  KBLIRiskCategory,
} from "./kbli-types";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Optional filters applied before scoring */
export interface KBLISearchFilters {
  pmaStatus?: KBLIPmaStatus;
  riskCategory?: KBLIRiskCategory;
}

/** Suggestion entry for "Did You Mean?" */
export interface KBLISuggestion {
  code: KBLICode;
  distance: number;
  matchedOn: string;
}

// -----------------------------------------------------------------------------
// Levenshtein Distance
// -----------------------------------------------------------------------------

/**
 * Compute Levenshtein edit distance between two strings.
 * Uses Wagner-Fischer dynamic programming with O(min(m,n)) space.
 */
function levenshtein(a: string, b: string): number {
  const la = a.length;
  const lb = b.length;

  // Short-circuit trivial cases
  if (la === 0) return lb;
  if (lb === 0) return la;
  if (a === b) return 0;

  // Ensure b is the shorter string for space optimization
  if (la < lb) return levenshtein(b, a);

  // Previous and current row of distances
  let prev = new Array<number>(lb + 1);
  let curr = new Array<number>(lb + 1);

  for (let j = 0; j <= lb; j++) prev[j] = j;

  for (let i = 1; i <= la; i++) {
    curr[0] = i;
    for (let j = 1; j <= lb; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1, // deletion
        curr[j - 1] + 1, // insertion
        prev[j - 1] + cost, // substitution
      );
    }
    [prev, curr] = [curr, prev];
  }

  return prev[lb];
}

// -----------------------------------------------------------------------------
// Text Normalization
// -----------------------------------------------------------------------------

/** Normalize text for comparison: lowercase, trim, collapse whitespace */
function normalize(text: string): string {
  return text.toLowerCase().trim().replace(/\s+/g, " ");
}

/** Split text into individual words, filtering out empties */
function toWords(text: string): string[] {
  return normalize(text).split(" ").filter(Boolean);
}

// -----------------------------------------------------------------------------
// Filtering
// -----------------------------------------------------------------------------

/**
 * Apply optional filters to the code list before scoring.
 * Filters on PMA status and/or risk category.
 */
function applyFilters(
  codes: KBLICode[],
  filters?: KBLISearchFilters,
): KBLICode[] {
  if (!filters) return codes;

  return codes.filter((code) => {
    if (filters.pmaStatus && code.pma.status !== filters.pmaStatus) {
      return false;
    }
    if (filters.riskCategory) {
      // A code passes the risk filter if ANY of its licensing scales
      // match the requested risk category
      const hasMatchingRisk = code.licensing.some(
        (lic) => lic.riskCategory === filters.riskCategory,
      );
      if (!hasMatchingRisk) return false;
    }
    return true;
  });
}

// -----------------------------------------------------------------------------
// Tier 1: Exact Code Match
// -----------------------------------------------------------------------------

/**
 * Check for exact or prefix match on the KBLI code itself.
 * - Full match (e.g. "56101") = score 100
 * - Prefix match (e.g. "561" matches "56101") = score 80 + length bonus
 */
function exactCodeSearch(codes: KBLICode[], query: string): KBLISearchResult[] {
  const cleaned = query.replace(/[.\-\s]/g, "");
  if (!/^\d+$/.test(cleaned)) return [];

  const results: KBLISearchResult[] = [];

  for (const code of codes) {
    if (code.code === cleaned) {
      // Perfect match
      results.push({ code, score: 100, matchType: "exact_code" });
    } else if (code.code.startsWith(cleaned) && cleaned.length >= 2) {
      // Prefix match — longer prefix = higher score
      const lengthBonus = (cleaned.length / code.code.length) * 20;
      results.push({
        code,
        score: 80 + lengthBonus,
        matchType: "exact_code",
      });
    }
  }

  return results.sort((a, b) => b.score - a.score);
}

// -----------------------------------------------------------------------------
// Tier 2: Relevance Scoring
// -----------------------------------------------------------------------------

/**
 * Score a single KBLI code against a search query.
 *
 * Scoring factors:
 *   Code match:       exact +80, startsWith +40
 *   Title EN match:   contains full query +50, any word +30
 *   Title ID match:   contains full query +50, any word +20
 *   Keyword matching: all words match +40, each word +10
 *   Phrase bonus:     exact phrase in title/description +15
 *   Length penalty:    -0.5 per 100 chars of description over 500
 *   PMA open bonus:   +3
 *   Gold tier bonus:  +5
 */
function scoreCode(code: KBLICode, query: string): number {
  const q = normalize(query);
  const qWords = toWords(query);
  if (qWords.length === 0) return 0;

  let score = 0;

  // --- Code match ---
  const cleanedQuery = q.replace(/[.\-\s]/g, "");
  if (/^\d+$/.test(cleanedQuery)) {
    if (code.code === cleanedQuery) {
      score += 80;
    } else if (code.code.startsWith(cleanedQuery)) {
      score += 40;
    }
  }

  // --- Title EN match ---
  const titleEn = normalize(code.titleEn);
  if (titleEn.includes(q)) {
    score += 50;
  } else {
    const titleEnWords = toWords(code.titleEn);
    if (qWords.some((w) => titleEnWords.includes(w))) {
      score += 30;
    }
  }

  // --- Title ID match ---
  const titleId = normalize(code.titleId);
  if (titleId.includes(q)) {
    score += 50;
  } else {
    const titleIdWords = toWords(code.titleId);
    if (qWords.some((w) => titleIdWords.includes(w))) {
      score += 20;
    }
  }

  // --- Keyword matching ---
  if (code.keywords.length > 0) {
    const kwNormalized = code.keywords.map((k) => normalize(k));
    const matchedWords = qWords.filter((w) =>
      kwNormalized.some((kw) => kw.includes(w) || w.includes(kw)),
    );

    if (matchedWords.length === qWords.length && qWords.length > 0) {
      score += 40;
    } else {
      score += matchedWords.length * 10;
    }
  }

  // --- Phrase bonus ---
  if (qWords.length > 1) {
    const desc = normalize(code.description);
    if (titleEn.includes(q) || titleId.includes(q) || desc.includes(q)) {
      score += 15;
    }
  }

  // --- Length penalty ---
  if (code.description.length > 500) {
    score -= Math.floor((code.description.length - 500) / 100) * 0.5;
  }

  // --- PMA open bonus ---
  if (code.pma.status === "open") {
    score += 3;
  }

  // --- Gold tier bonus ---
  if (code.tier === "gold") {
    score += 5;
  }

  return score;
}

/**
 * Relevance-scored search across all codes.
 * Returns codes with score > 0, sorted descending.
 */
function relevanceSearch(codes: KBLICode[], query: string): KBLISearchResult[] {
  const results: KBLISearchResult[] = [];

  for (const code of codes) {
    const score = scoreCode(code, query);
    if (score > 0) {
      results.push({ code, score, matchType: "keyword" });
    }
  }

  return results.sort((a, b) => b.score - a.score);
}

// -----------------------------------------------------------------------------
// Tier 3: Fuzzy Search (Levenshtein)
// -----------------------------------------------------------------------------

/**
 * Fuzzy search using Levenshtein distance.
 * Scans title words (EN + ID) and keyword words.
 * Matches when distance <= 2 for words of length >= 4,
 * or distance <= 1 for shorter words.
 */
function fuzzySearch(codes: KBLICode[], query: string): KBLISearchResult[] {
  const qWords = toWords(query);
  if (qWords.length === 0) return [];

  const results: KBLISearchResult[] = [];

  for (const code of codes) {
    // Collect all candidate words from this code
    const candidateWords = new Set<string>();
    for (const w of toWords(code.titleEn)) candidateWords.add(w);
    for (const w of toWords(code.titleId)) candidateWords.add(w);
    for (const kw of code.keywords) {
      for (const w of toWords(kw)) candidateWords.add(w);
    }

    let bestDistance = Infinity;
    let totalMatchScore = 0;

    for (const qw of qWords) {
      const maxDist = qw.length >= 4 ? 2 : 1;
      let wordBestDist = Infinity;

      for (const cw of candidateWords) {
        // Skip if length difference alone exceeds threshold
        if (Math.abs(cw.length - qw.length) > maxDist) continue;

        const dist = levenshtein(qw, cw);
        if (dist <= maxDist && dist < wordBestDist) {
          wordBestDist = dist;
        }
      }

      if (wordBestDist !== Infinity) {
        totalMatchScore += (maxDist + 1 - wordBestDist) * 10;
        bestDistance = Math.min(bestDistance, wordBestDist);
      }
    }

    if (totalMatchScore > 0) {
      // Fuzzy results get lower base scores than relevance results
      const score = totalMatchScore;
      results.push({ code, score, matchType: "semantic" });
    }
  }

  return results.sort((a, b) => b.score - a.score);
}

// -----------------------------------------------------------------------------
// Main Search Function
// -----------------------------------------------------------------------------

/**
 * Search KBLI codes with a 3-tier algorithm:
 *
 * 1. **Exact code match** — If query looks numeric, try direct code lookup.
 *    Returns immediately if a perfect match is found.
 * 2. **Relevance scoring** — Score all codes by title, keyword, and attribute
 *    matching. Returns if any results found.
 * 3. **Fuzzy search** — Levenshtein-based fallback for typos and near-misses.
 *
 * @param codes - Full array of KBLI codes (passed from server component)
 * @param query - User search query
 * @param filters - Optional PMA/risk category filters
 * @returns Sorted array of search results with scores
 */
export function searchCodes(
  codes: KBLICode[],
  query: string,
  filters?: KBLISearchFilters,
): KBLISearchResult[] {
  const trimmed = query.trim();
  if (!trimmed) return [];

  // Apply filters first
  const filtered = applyFilters(codes, filters);

  // Tier 1: Exact code match
  const exactResults = exactCodeSearch(filtered, trimmed);
  if (exactResults.length > 0 && exactResults[0].score === 100) {
    // Perfect code match found — return exact + any prefix matches
    return exactResults;
  }

  // Tier 2: Relevance scoring
  const relevanceResults = relevanceSearch(filtered, trimmed);
  if (relevanceResults.length > 0) {
    // Merge exact code prefix matches (if any) with relevance results,
    // deduplicating by code
    if (exactResults.length > 0) {
      const seen = new Set(exactResults.map((r) => r.code.code));
      const merged = [
        ...exactResults,
        ...relevanceResults.filter((r) => !seen.has(r.code.code)),
      ];
      return merged.sort((a, b) => b.score - a.score);
    }
    return relevanceResults;
  }

  // Tier 3: Fuzzy search (fallback for typos)
  return fuzzySearch(filtered, trimmed);
}

// -----------------------------------------------------------------------------
// Suggestions ("Did You Mean?")
// -----------------------------------------------------------------------------

/**
 * Generate "Did You Mean?" suggestions when search returns no results.
 * Uses Levenshtein distance against title and keyword words.
 *
 * @param codes - Full array of KBLI codes
 * @param query - User search query that returned no results
 * @param limit - Maximum number of suggestions (default 5)
 * @returns Array of suggestions sorted by edit distance (closest first)
 */
export function getSuggestions(
  codes: KBLICode[],
  query: string,
  limit: number = 5,
): KBLISuggestion[] {
  const trimmed = query.trim();
  if (!trimmed) return [];

  const qWords = toWords(trimmed);
  if (qWords.length === 0) return [];

  const suggestions: KBLISuggestion[] = [];

  for (const code of codes) {
    let bestDistance = Infinity;
    let matchedOn = "";

    // Check against title EN words
    for (const word of toWords(code.titleEn)) {
      for (const qw of qWords) {
        if (Math.abs(word.length - qw.length) > 3) continue;
        const dist = levenshtein(qw, word);
        if (dist < bestDistance && dist <= 3) {
          bestDistance = dist;
          matchedOn = code.titleEn;
        }
      }
    }

    // Check against title ID words
    for (const word of toWords(code.titleId)) {
      for (const qw of qWords) {
        if (Math.abs(word.length - qw.length) > 3) continue;
        const dist = levenshtein(qw, word);
        if (dist < bestDistance && dist <= 3) {
          bestDistance = dist;
          matchedOn = code.titleId;
        }
      }
    }

    // Check against keyword words
    for (const kw of code.keywords) {
      for (const kwWord of toWords(kw)) {
        for (const qw of qWords) {
          if (Math.abs(kwWord.length - qw.length) > 3) continue;
          const dist = levenshtein(qw, kwWord);
          if (dist < bestDistance && dist <= 3) {
            bestDistance = dist;
            matchedOn = kw;
          }
        }
      }
    }

    if (bestDistance <= 3) {
      suggestions.push({ code, distance: bestDistance, matchedOn });
    }
  }

  // Sort by distance (closest first), then by tier (gold first)
  suggestions.sort((a, b) => {
    if (a.distance !== b.distance) return a.distance - b.distance;
    // Prefer gold tier when distances are equal
    const tierOrder: Record<string, number> = { gold: 0, silver: 1, bronze: 2 };
    return (tierOrder[a.code.tier] ?? 2) - (tierOrder[b.code.tier] ?? 2);
  });

  return suggestions.slice(0, limit);
}
