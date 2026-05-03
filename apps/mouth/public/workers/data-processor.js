/**
 * Web Worker per processamento dati pesanti
 * Migliora INP (Interaction to Next Paint) offloadando task dal main thread
 */

self.addEventListener("message", (event) => {
  const { type, data, id } = event.data;

  switch (type) {
    case "SORT_ARTICLES":
      // Sort articoli senza bloccare main thread
      const sorted = data.sort((a, b) => {
        return (
          new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
        );
      });
      self.postMessage({ type: "SORT_COMPLETE", result: sorted, id });
      break;

    case "FILTER_ARTICLES":
      // Filtro articoli pesante
      const { articles, query, filters } = data;
      const filtered = articles.filter((article) => {
        const matchesQuery =
          !query ||
          article.title.toLowerCase().includes(query.toLowerCase()) ||
          article.excerpt.toLowerCase().includes(query.toLowerCase());

        const matchesCategory =
          !filters?.category || article.category === filters.category;

        return matchesQuery && matchesCategory;
      });
      self.postMessage({ type: "FILTER_COMPLETE", result: filtered, id });
      break;

    case "PROCESS_CONVERSATIONS":
      // Processa lista conversazioni per virtual scroll
      const { conversations, page, pageSize } = data;
      const start = page * pageSize;
      const paginated = conversations.slice(start, start + pageSize);
      self.postMessage({ type: "PROCESS_COMPLETE", result: paginated, id });
      break;

    case "CALCULATE_STATS":
      // Calcoli statistici pesanti
      const numbers = data;
      const stats = {
        count: numbers.length,
        sum: numbers.reduce((a, b) => a + b, 0),
        avg: numbers.reduce((a, b) => a + b, 0) / numbers.length,
        min: Math.min(...numbers),
        max: Math.max(...numbers),
      };
      self.postMessage({ type: "STATS_COMPLETE", result: stats, id });
      break;

    default:
      self.postMessage({ type: "ERROR", error: "Unknown type", id });
  }
});
