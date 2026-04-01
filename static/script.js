// ─────────────────────────────────────────────
// Data (injected from Flask)
// ─────────────────────────────────────────────
const BOOKS = window.BOOKS || [];

// ─────────────────────────────────────────────
// Extract unique individual genres for table dropdown
// ─────────────────────────────────────────────
const genreSet = new Set();
BOOKS.forEach(b => {
  (b.genre || "Unknown")
    .split(',')
    .map(g => g.trim())
    .forEach(g => genreSet.add(g));
});
const INDIVIDUAL_GENRES = ["All", ...[...genreSet].sort()];

// Populate genre filter dropdown
const genreSelect = document.getElementById('filter-genre');
if (genreSelect) {
  genreSelect.innerHTML = INDIVIDUAL_GENRES.map(g => `
    <option value="${g === "All" ? "" : g}">${g}</option>
  `).join('');
}

// ─────────────────────────────────────────────
// Group books by full genre for tab view
// ─────────────────────────────────────────────
const DATA = BOOKS.reduce((acc, b) => {
  const genre = b.genre || "Unknown";
  acc[genre] = acc[genre] || [];
  acc[genre].push(b);
  return acc;
}, {});

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
function fmt(n) {
  return (n || 0).toLocaleString('en-GB');
}

// Ranking score (weighted)
function getScore(b) {
  return (b.rating || 0) * 0.7 + (b.readinglog || 0) * 0.3;
}

// ─────────────────────────────────────────────
// Table view (main rankings)
// ─────────────────────────────────────────────
function applyFilters() {
  console.log("BOOKS count:", BOOKS.length);
  console.log("Sample book:", BOOKS[0]);
  const genre = document.getElementById('filter-genre').value;
  console.log("Selected genre:", genre);
  const sortBy = document.getElementById('sort-by').value;
  const show   = document.getElementById('filter-show').value;

  let books = [...BOOKS];

  // Filter by individual genre
  if (genre) {
    books = books.filter(b => 
      (b.genre || "")
        .split(',')
        .map(g => g.trim())
        .includes(genre)
    );
  }

  // Compute score
  books.forEach(b => b.score = getScore(b));

  // Sorting
  if (sortBy === 'readinglog')  books.sort((a, b) => (b.readinglog || 0) - (a.readinglog || 0));
  else if (sortBy === 'rating') books.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  else if (sortBy === 'title')  books.sort((a, b) => a.title.localeCompare(b.title));
  else if (sortBy === 'author') books.sort((a, b) => a.author.localeCompare(b.author));
  else books.sort((a, b) => b.score - a.score); // default smart ranking

  // Limit results
  if (show !== "all") books = books.slice(0, parseInt(show));

  // Display count
  document.getElementById('results-count').textContent = `${books.length} books`;

  const tbody = document.getElementById('table-body');
  if (!books.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="no-results">No results found.</td></tr>`;
    return;
  }

  // Render table rows
  tbody.innerHTML = books.map((b, i) => `
    <tr>
      <td class="rank-col">${i + 1}</td>
      <td class="title-col">
        <a href="${b.book_url || '#'}" target="_blank" rel="noopener noreferrer">
          ${b.title}
        </a>
      </td>
      <td class="author-col">${b.author || ""}</td>
      <td class="rating-col">
        <span class="rating-badge">
          <span class="star">★</span>
          ${b.rating ? b.rating.toFixed(2) : "-"}
        </span>
      </td>
      <td><span class="genre-pill">${b.genre || ""}</span></td>
      <td class="year-col">${b.year || ""}</td>
      <td class="readinglog-col">${fmt(b.readinglog)}</td>
    </tr>
  `).join('');
}

// ─────────────────────────────────────────────
// Card / tab view
// ─────────────────────────────────────────────
let active = Object.keys(DATA)[0];

function renderTabs() {
  const el = document.getElementById('tabs');
  if (!el) return;

  el.innerHTML = Object.keys(DATA).map(g => `
    <button class="tab ${g === active ? 'active' : ''}"
      onclick="active='${g}'; renderTabs(); render()">
      ${g}
    </button>
  `).join('');
}

function render() {
  const el = document.getElementById('list');
  if (!el) return;

  const books = [...(DATA[active] || [])];
  const sortEl = document.getElementById('sort');
  const sort = sortEl ? sortEl.value : 'rank';

  if (!books.length) {
    el.innerHTML = `<p class="empty">No data for ${active} yet.</p>`;
    return;
  }

  // Sorting
  if (sort === 'readinglog')  books.sort((a, b) => (b.readinglog || 0) - (a.readinglog || 0));
  else if (sort === 'rating') books.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  else if (sort === 'title')  books.sort((a, b) => a.title.localeCompare(b.title));
  else if (sort === 'author') books.sort((a, b) => a.author.localeCompare(b.author));
  else books.sort((a, b) => getScore(b) - getScore(a));

  // Render cards
  el.innerHTML = books.map((b, i) => `
    <div class="card-row">
      <div class="rank">${i + 1}</div>
      <div class="book-info">
        <div class="book-title">${b.title}</div>
        <div class="book-author">${b.author || ""}</div>
      </div>
      <div class="book-readinglog">
        <strong>${fmt(b.readinglog)}</strong> readinglog
      </div>
    </div>
  `).join('');
}

// ─────────────────────────────────────────────
// Export CSV
// ─────────────────────────────────────────────
function exportCSV() {
  const rows = [...document.querySelectorAll('#table-body tr')].map(tr => {
    const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
    return cells;
  });

  if (!rows.length) return;

  const headers = ["Rank", "Title", "Author", "Rating", "Genre", "Year", "Readinglog"];

  const csv = [headers, ...rows]
    .map(r => r.map(cell => `"${cell}"`).join(","))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv" });

  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "books.csv";
  a.click();
}

// ─────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────
applyFilters();
renderTabs();
render();