const DATA = window.BOOKS.reduce((acc, b) => {
  acc[b.genre] = acc[b.genre] || [];
  acc[b.genre].push(b);
  return acc;
}, {});

function fmt(n) {
  return parseInt(n).toLocaleString('en-GB');
}

// ── Table view ──────────────────────────────────────────
function applyFilters() {
  const genre  = document.getElementById('filter-genre').value;
  const year   = document.getElementById('filter-year').value;
  const sortBy = document.getElementById('sort-by').value;
  const show   = document.getElementById('filter-show').value;

  let books = [...window.BOOKS];
  if (genre) books = books.filter(b => b.genre === genre);
  if (year)  books = books.filter(b => String(b.year) === year);

  if (sortBy === 'votes')  books.sort((a, b) => parseInt(b.votes) - parseInt(a.votes));
  if (sortBy === 'rating')  books.sort((a, b) => parseFloat(b.rating) - parseFloat(a.rating));
  if (sortBy === 'title')  books.sort((a, b) => a.title.localeCompare(b.title));
  if (sortBy === 'author') books.sort((a, b) => a.author.localeCompare(b.author));

  if (show !== "all") books = books.slice(0, parseInt(show));

  document.getElementById('results-count').textContent = `Result # ${books.length}`;

  const tbody = document.getElementById('table-body');
  if (!books.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="no-results">No results found.</td></tr>`;
    return;
  }

  tbody.innerHTML = books.map((b, i) => `
    <tr>
      <td class="rank-col">${i + 1}</td>
      <td class="title-col">
        <a href="${b.book_url}" target="_blank" rel="noopener noreferrer">${b.title}</a>
      </td>
      <td class="author-col">${b.author}</td>
      <td class="rating-col">${b.rating}</td>
      <td><span class="genre-pill">${b.genre}</span></td>
      <td class="year-col">${b.year}</td>
      <td class="votes-col">${fmt(b.votes)}</td>
    </tr>
  `).join('');
}

// ── Card / tab view ─────────────────────────────────────
let active = Object.keys(DATA)[0];

function renderTabs() {
  const el = document.getElementById('tabs');
  if (!el) return;
  el.innerHTML = Object.keys(DATA).map(g => `
    <button class="tab ${g === active ? 'active' : ''}"
            onclick="active='${g}';renderTabs();render()">${g}</button>
  `).join('');
}

function render() {
  const el = document.getElementById('list');
  if (!el) return;

  const books = [...(DATA[active] || [])];
  const sortEl = document.getElementById('sort');
  const sort   = sortEl ? sortEl.value : 'rank';

  if (!books.length) {
    el.innerHTML = `<p class="empty">No data for ${active} yet.</p>`;
    return;
  }

  if (sort === 'votes')  books.sort((a, b) => parseInt(b.votes) - parseInt(a.votes));
  if (sort === 'rating')  books.sort((a, b) => parseFloat(b.rating) - parseFloat(a.rating));
  if (sort === 'title')  books.sort((a, b) => a.title.localeCompare(b.title));
  if (sort === 'author') books.sort((a, b) => a.author.localeCompare(b.author));
  if (sort === 'rank')   books.sort((a, b) => a.rank - b.rank);

  el.innerHTML = books.map(b => `
      <div class="rank">${b.rank}</div>
      <div class="book-info">
        <div class="book-title">${b.title}</div>
        <div class="book-author">${b.author}</div>
      </div>
      <div class="book-votes">
        <strong>${fmt(b.votes)}</strong> votes
      </div>
    </div>
  `).join('');
}

// ── Convert result json data to .cvs ────────────────────
function exportCSV() {
    const rows = [...document.querySelectorAll('#table-body tr')].map(tr => {
        const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
        return cells;
    });

    if (!rows.length) return;

    const headers = ["Rank", "Title", "Author", "Rating", "Genre", "Year", "Votes"];
    const csv = [headers, ...rows].map(r => r.map(cell => `"${cell}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "books.csv";
    a.click();
}

// ── Init ────────────────────────────────────────────────
applyFilters();
renderTabs();
render();