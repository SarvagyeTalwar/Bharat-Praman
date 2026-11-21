/**
 * Bharat Praman — Universal Fuzzy Search & Typo Resilience Engine
 * Provides Levenshtein distance, token-level matching, and typo correction
 * across politicians, ministries, budget schemes, and statutory queries.
 */
(function (global) {
  'use strict';

  function levenshtein(a, b) {
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    const aLen = a.length;
    const bLen = b.length;
    let prevRow = Array.from({ length: bLen + 1 }, (_, i) => i);
    let currRow = new Array(bLen + 1);

    for (let i = 1; i <= aLen; i++) {
      currRow[0] = i;
      const aChar = a.charCodeAt(i - 1);
      for (let j = 1; j <= bLen; j++) {
        const cost = aChar === b.charCodeAt(j - 1) ? 0 : 1;
        currRow[j] = Math.min(
          currRow[j - 1] + 1,      // insertion
          prevRow[j] + 1,          // deletion
          prevRow[j - 1] + cost    // substitution
        );
      }
      const tmp = prevRow;
      prevRow = currRow;
      currRow = tmp;
    }
    return prevRow[bLen];
  }

  function cleanString(str) {
    return String(str || '')
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  /**
   * Returns a similarity score between 0.0 (no match) and 1.0 (exact match).
   */
  function score(target, query) {
    const t = cleanString(target);
    const q = cleanString(query);
    if (!q) return 1.0;
    if (!t) return 0.0;
    if (t === q) return 1.0;
    if (t.includes(q)) {
      return 0.85 + 0.15 * (q.length / Math.max(t.length, 1));
    }

    const tTokens = t.split(' ').filter(Boolean);
    const qTokens = q.split(' ').filter(Boolean);
    if (!qTokens.length) return 1.0;

    let matchedTokens = 0;
    let totalScore = 0;

    for (const qTok of qTokens) {
      if (qTok.length === 1) {
        if (tTokens.some((tok) => tok.startsWith(qTok))) {
          matchedTokens++;
          totalScore += 0.5;
        }
        continue;
      }

      let bestTokenScore = 0;
      for (const tTok of tTokens) {
        if (tTok === qTok) {
          bestTokenScore = Math.max(bestTokenScore, 1.0);
          break;
        }
        if (tTok.includes(qTok)) {
          bestTokenScore = Math.max(bestTokenScore, 0.9);
          continue;
        }
        if (qTok.includes(tTok) && tTok.length >= 3) {
          bestTokenScore = Math.max(bestTokenScore, 0.85);
          continue;
        }

        const maxDist = qTok.length <= 4 ? 1 : (qTok.length <= 7 ? 2 : 3);
        const dist = levenshtein(tTok, qTok);
        if (dist <= maxDist) {
          const sim = 1.0 - (dist / Math.max(tTok.length, qTok.length));
          bestTokenScore = Math.max(bestTokenScore, sim * 0.85);
        }
      }

      if (bestTokenScore >= 0.5) {
        matchedTokens++;
        totalScore += bestTokenScore;
      }
    }

    const tokenRatio = matchedTokens / qTokens.length;
    if (tokenRatio < 0.5) return 0.0;
    return (totalScore / qTokens.length) * (0.5 + 0.5 * tokenRatio);
  }

  /**
   * Filter and rank an array of items by fuzzy similarity.
   */
  function filter(items, query, extractTextFn, threshold = 0.45) {
    if (!query || !query.trim()) return items;
    const scored = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const text = extractTextFn ? extractTextFn(item) : String(item);
      const s = score(text, query);
      if (s >= threshold) {
        scored.push({ item, score: s });
      }
    }
    scored.sort((a, b) => b.score - a.score);
    return scored.map((x) => x.item);
  }

  /**
   * Dictionary of standard public authorities, ministries and aliases
   */
  const KNOWN_AUTHORITIES = [
    { name: 'Ministry of Railways', aliases: ['railways', 'railway', 'raliways', 'railwy', 'train', 'irctc'] },
    { name: 'Ministry of Defence', aliases: ['defence', 'defense', 'defenc', 'defens', 'army', 'navy', 'air force', 'drdo'] },
    { name: 'Ministry of Road Transport and Highways', aliases: ['road transport', 'highways', 'morth', 'nhai', 'expressways', 'roads'] },
    { name: 'Ministry of Home Affairs', aliases: ['home affairs', 'mha', 'police', 'crpf', 'bsf', 'cisf', 'border'] },
    { name: 'Ministry of Finance', aliases: ['finance', 'finmin', 'revenue', 'tax', 'gst', 'customs', 'budget'] },
    { name: 'Ministry of Education', aliases: ['education', 'edukashun', 'educashun', 'shiksha', 'ugc', 'cbse', 'samagra'] },
    { name: 'Ministry of Health and Family Welfare', aliases: ['health', 'helth', 'family welfare', 'swasthya', 'aiims', 'ayushman', 'pmjay'] },
    { name: 'Ministry of Agriculture and Farmers Welfare', aliases: ['agriculture', 'agrikulture', 'agri', 'kisan', 'farmers welfare'] },
    { name: 'Ministry of Rural Development', aliases: ['rural development', 'mgnrega', 'pmgsy', 'gramin'] },
    { name: 'Election Commission of India', aliases: ['election commission', 'eci', 'elecon', 'election comision', 'voter'] },
    { name: 'NITI Aayog', aliases: ['niti aayog', 'niti ayog', 'niti ayoug', 'planning commission'] },
    { name: 'Lok Sabha Secretariat', aliases: ['lok sabha', 'loksabha', 'lok shaba', 'parliament', 'sansad'] },
    { name: 'Rajya Sabha Secretariat', aliases: ['rajya sabha', 'rajyasabha', 'council of states'] }
  ];

  /**
   * Checks if input fuzzy-matches a known ministry or public body.
   */
  function resolveKnownAuthority(input) {
    const raw = cleanString(input);
    if (!raw) return null;

    let bestMatch = null;
    let highestScore = 0;

    for (const auth of KNOWN_AUTHORITIES) {
      const nameScore = score(auth.name, raw);
      if (nameScore > highestScore) {
        highestScore = nameScore;
        bestMatch = auth.name;
      }
      for (const alias of auth.aliases) {
        const aliasScore = score(alias, raw);
        if (aliasScore > highestScore) {
          highestScore = aliasScore;
          bestMatch = auth.name;
        }
      }
    }

    if (highestScore >= 0.55) {
      return { matched: bestMatch, score: highestScore };
    }
    return null;
  }

  global.BP_FUZZY = {
    levenshtein,
    score,
    filter,
    resolveKnownAuthority,
    KNOWN_AUTHORITIES
  };

})(typeof window !== 'undefined' ? window : globalThis);
