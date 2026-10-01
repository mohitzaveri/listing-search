import type { Listing, SearchResponse } from './types';

const PAGE_SIZES = ['5', '10', '20'];

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

// listedDate is a plain date ("2026-09-04"). Format it in UTC so it never shows
// as the day before in US time zones.
const day = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

interface ResultsProps {
  data: SearchResponse | null;
  loading: boolean;
  page: number;
  pageSize: string;
  rankedByBudget: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: string) => void;
}

export function Results({
  data,
  loading,
  page,
  pageSize,
  rankedByBudget,
  onPageChange,
  onPageSizeChange,
}: ResultsProps) {
  // First load: show placeholder rows instead of an empty page.
  if (!data) return loading ? <Skeleton rows={Number(pageSize)} /> : null;

  const firstRank = (data.page - 1) * data.pageSize + 1;

  return (
    // While a new page loads, the old one stays on screen (dimmed), so nothing jumps.
    <section className="card results" aria-busy={loading}>
      <div className="toolbar">
        <p>
          <strong>{data.totalResults}</strong> {data.totalResults === 1 ? 'result' : 'results'}
          {data.totalResults > 0 && (
            <span className="muted">
              {' · '}
              {rankedByBudget ? 'ranked by budget fit and newness' : 'newest first; add a target budget to rank by price'}
            </span>
          )}
        </p>
        <label className="page-size">
          Per page
          <select value={pageSize} onChange={(event) => onPageSizeChange(event.target.value)}>
            {PAGE_SIZES.map((size) => (
              <option key={size}>{size}</option>
            ))}
          </select>
        </label>
      </div>

      {data.totalResults === 0 ? (
        <div className="empty">
          <p>
            <strong>No listings match your filters.</strong>
          </p>
          <p className="muted">Try a wider price range, fewer bedrooms, or a different keyword.</p>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="hide-sm">#</th>
                  <th>Address</th>
                  <th className="num">Price</th>
                  <th className="num">Beds</th>
                  <th className="num hide-sm">Baths</th>
                  <th className="hide-sm">Listed</th>
                  <th>Status</th>
                  <th className="num">Score</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((listing, index) => (
                  <ResultRow key={`${listing.source}-${listing.id}`} listing={listing} rank={firstRank + index} />
                ))}
              </tbody>
            </table>
          </div>

          <nav className="pagination" aria-label="Pagination">
            <button className="button" disabled={loading || page <= 1} onClick={() => onPageChange(page - 1)}>
              ← Previous
            </button>
            <span className="muted">
              Page {data.page} of {data.totalPages}
            </span>
            <button
              className="button"
              disabled={loading || page >= data.totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              Next →
            </button>
          </nav>
        </>
      )}
    </section>
  );
}

function ResultRow({ listing, rank }: { listing: Listing; rank: number }) {
  return (
    <tr>
      <td className="muted hide-sm">{rank}</td>
      <td>
        <div className="address">{listing.address}</div>
        <div className="muted small">
          {listing.city}, {listing.state} {listing.zip} · {listing.source}
        </div>
      </td>
      <td className="num price">{money.format(listing.price)}</td>
      <td className="num">{listing.bedrooms}</td>
      <td className="num hide-sm">{listing.bathrooms}</td>
      <td className="hide-sm nowrap">{day.format(new Date(listing.listedDate))}</td>
      <td>
        <span className={`badge ${listing.status}`}>{listing.status}</span>
      </td>
      <td className="num">
        <span className="score">
          {listing.score.toFixed(1)}
          <span className="meter" aria-hidden="true">
            <span style={{ width: `${listing.score}%` }} />
          </span>
        </span>
      </td>
    </tr>
  );
}

function Skeleton({ rows }: { rows: number }) {
  return (
    <section className="card results" aria-busy="true" aria-label="Loading results">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton-row" />
      ))}
    </section>
  );
}
