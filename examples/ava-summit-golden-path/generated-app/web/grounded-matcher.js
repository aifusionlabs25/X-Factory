(function attachGroundedMatcher(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.XAgentGroundedMatcher = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createGroundedMatcher() {
  "use strict";
  const STOPWORDS = new Set(["the","and","can","you","your","what","with","for","from","that","this","are","have","does","how","who","why","when","where","will","would","could","please","tell","give","about","someone","something","service","services","provide","customer","customers","home","homes","need","needed","new","my","me","our"]);
  const SERVICE_ENTITIES = ["waterheater", "airconditioning", "plumbing", "electrical", "heating"];
  const POLICY_MARKERS = ["pricing", "hours", "availability"];
  const CAPABILITY_QUERY = /(?:what|which).{0,30}(?:service|services|capabilities).{0,30}(?:offer|provide|available|have)|(?:service|services|capabilities).{0,20}(?:offer|provide|available)|what can you help with/i;
  const LOCATION_QUERY = /\b(?:work\s+in|serve|served|serving|located|location|area)\b/i;

  function normalized(text) {
    return String(text || "").toLowerCase()
      .replace(/water[\s-]*heaters?\b/g, " waterheater ")
      .replace(/\b(?:a\s*\/\s*c|ac|air[\s-]*conditioning|hvac)\b/g, " airconditioning ")
      .replace(/\b(?:fix|fixes|fixed|fixing|repair|repairs|repaired|repairing|service|services|serviced|servicing)\b/g, " repair ")
      .replace(/\b(?:price|prices|pricing|cost|costs|costing|quote|quotes|estimate|estimates|pay|expensive|run)\b/g, " pricing ")
      .replace(/\b(?:hours|hour|open|opened|opening|close|closed|closing)\b/g, " hours ")
      .replace(/\b(?:availability|available|appointment|appointments|guarantee|guaranteed|promise|promised|tonight|after[\s-]*hours)\b/g, " availability ")
      .replace(/\b(?:install|installs|installed|installing|installation|installations)\b/g, " install ")
      .replace(/\b(?:replace|replaces|replaced|replacing|replacement|replacements)\b/g, " replace ")
      .replace(/\b(?:remodel|remodels|remodeled|remodeling)\b/g, " remodel ")
      .replace(/\b(?:maintain|maintains|maintained|maintaining|maintenance)\b/g, " maintain ")
      .replace(/\b(?:inspect|inspects|inspected|inspecting|inspection|inspections)\b/g, " inspect ")
      .replace(/\s+/g, " ").trim();
  }

  function canonicalTerm(term) {
    const irregular = {cabinets:"cabinet",kitchens:"kitchen",bathrooms:"bathroom",windows:"window",doors:"door",fixtures:"fixture",appliances:"appliance",fans:"fan",floors:"floor",repairs:"repair",offerings:"offer",capabilities:"capability",hours:"hours"};
    if (irregular[term]) return irregular[term];
    if (term.endsWith("ies") && term.length > 5) return `${term.slice(0, -3)}y`;
    if (term.endsWith("s") && !term.endsWith("ss") && !term.endsWith("us") && term.length > 4) return term.slice(0, -1);
    return term;
  }

  function terms(text) {
    const found = normalized(text).match(/[a-z0-9]{3,}/g) || [];
    return new Set(found.map(canonicalTerm).filter((term) => !STOPWORDS.has(term)));
  }

  function overlap(left, right) {
    let count = 0;
    left.forEach((term) => { if (right.has(term)) count += 1; });
    return count;
  }

  function match(entries, message, contract = {}) {
    const clean = String(message || "").replace(/\s+/g, " ").trim();
    const query = normalized(clean);
    const queryTerms = terms(clean);
    const prepared = entries.map((entry) => ({entry, titleTerms: terms(entry.title), statementTerms: terms(entry.statement)}));
    const exact = prepared.find((item) => normalized(item.entry.title) === query);
    if (exact) return {entry: exact.entry, reason: "EXACT_APPROVED_TITLE"};

    for (const marker of POLICY_MARKERS) {
      if (!queryTerms.has(marker)) continue;
      const title = prepared.filter((item) => item.titleTerms.has(marker));
      const candidates = title.length ? title : prepared.filter((item) => item.statementTerms.has(marker));
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        return {entry: candidates[0].entry, reason: `APPROVED_${marker.toUpperCase()}_POLICY`};
      }
    }

    const entities = SERVICE_ENTITIES.filter((entity) => queryTerms.has(entity));
    if (entities.length) {
      const candidates = prepared.filter((item) => entities.some((entity) => item.statementTerms.has(entity)));
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        const entity = entities.find((item) => candidates[0].statementTerms.has(item));
        return {entry: candidates[0].entry, reason: `APPROVED_SERVICE_ENTITY_${entity.toUpperCase()}`};
      }
    }

    if (CAPABILITY_QUERY.test(clean)) {
      const capabilities = prepared.filter((item) => item.entry.kind === "CAPABILITY");
      if (capabilities.length) {
        capabilities.sort((a, b) => String(b.entry.statement).length - String(a.entry.statement).length);
        return {entry: capabilities[0].entry, reason: "APPROVED_CAPABILITY_SUMMARY"};
      }
    }

    if (LOCATION_QUERY.test(clean)) {
      const candidates = prepared.filter((item) => overlap(queryTerms, item.statementTerms) >= 1);
      if (candidates.length) {
        candidates.sort((a, b) => overlap(queryTerms, new Set([...b.titleTerms, ...b.statementTerms])) - overlap(queryTerms, new Set([...a.titleTerms, ...a.statementTerms])));
        return {entry: candidates[0].entry, reason: "APPROVED_LOCATION_TERM"};
      }
    }

    let best = null;
    let bestScore = 0;
    let bestOverlap = 0;
    prepared.forEach((item) => {
      const titleOverlap = overlap(queryTerms, item.titleTerms);
      const statementOverlap = overlap(queryTerms, item.statementTerms);
      const score = titleOverlap * (contract.title_term_weight || 3) + statementOverlap * (contract.statement_term_weight || 1);
      if (score > bestScore) { best = item.entry; bestScore = score; bestOverlap = overlap(queryTerms, new Set([...item.titleTerms, ...item.statementTerms])); }
    });
    const queryCoverage = bestOverlap / Math.max(1, queryTerms.size);
    if (best && bestOverlap >= (contract.minimum_distinct_term_overlap || 2) && bestScore >= (contract.minimum_weighted_score || 2) && queryCoverage >= (contract.minimum_query_coverage || 0.6)) {
      return {entry: best, reason: "CONSERVATIVE_APPROVED_TERM_OVERLAP"};
    }
    return {entry: null, reason: "NO_APPROVED_MATCH"};
  }

  return {normalized, terms, match};
});
