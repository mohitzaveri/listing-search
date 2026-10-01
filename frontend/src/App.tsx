import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, prefetchListings, searchListings } from './api';
import { Results } from './Results';
import type { Filters, SearchResponse } from './types';

const EMPTY_FILTERS: Filters = {
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  city: '',
  keyword: '',
  targetBudget: '',
  pageSize: '5',
};

const FIELDS: { name: keyof Filters; label: string; placeholder: string; numeric?: boolean }[] = [
  { name: 'targetBudget', label: 'Target budget ($)', placeholder: 'e.g. 450000', numeric: true },
  { name: 'minPrice', label: 'Min price ($)', placeholder: 'Any', numeric: true },
  { name: 'maxPrice', label: 'Max price ($)', placeholder: 'Any', numeric: true },
  { name: 'minBedrooms', label: 'Min bedrooms', placeholder: 'Any', numeric: true },
  { name: 'city', label: 'City', placeholder: 'Any' },
  { name: 'keyword', label: 'Keyword', placeholder: 'e.g. kitchen' },
];

export function App() {
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS); // what is typed in the form
  const [submitted, setSubmitted] = useState<Filters>(EMPTY_FILTERS); // what the results are for
  const [page, setPage] = useState(1);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Search again whenever the submitted filters or the page change.
  useEffect(() => {
    let current = true; // set to false when a newer search starts, so a slow old answer is ignored
    setLoading(true);
    setError(null);
    searchListings(submitted, page)
      .then((response) => {
        if (!current) return;
        setData(response);
        if (response.page < response.totalPages) prefetchListings(submitted, page + 1);
      })
      .catch((err: unknown) => {
        if (!current) return;
        setData(null);
        setError(err instanceof ApiError ? err : new ApiError('Something went wrong. Please try again.'));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [submitted, page]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitted({ ...draft });
    setPage(1);
  }

  function handleClear() {
    const cleared = { ...EMPTY_FILTERS, pageSize: submitted.pageSize };
    setDraft(cleared);
    setSubmitted(cleared);
    setPage(1);
  }

  function handlePageSize(pageSize: string) {
    setDraft((previous) => ({ ...previous, pageSize }));
    setSubmitted((previous) => ({ ...previous, pageSize }));
    setPage(1);
  }

  return (
    <main className="app">
      <header className="header">
        <h1>Listing Search</h1>
        <p className="muted">Homes from every MLS feed, ranked by budget fit and how recently they were listed.</p>
      </header>

      <form className="card filters" onSubmit={handleSubmit} noValidate>
        <div className="fields">
          {FIELDS.map((field) => (
            <label className="field" key={field.name}>
              <span>{field.label}</span>
              <input
                value={draft[field.name]}
                placeholder={field.placeholder}
                inputMode={field.numeric ? 'decimal' : undefined}
                aria-invalid={error?.field === field.name}
                onChange={(event) => {
                  const { value } = event.target;
                  setDraft((previous) => ({ ...previous, [field.name]: value }));
                }}
              />
            </label>
          ))}
        </div>
        <div className="actions">
          <button type="button" className="button" onClick={handleClear}>
            Clear
          </button>
          <button type="submit" className="button primary">
            Search
          </button>
        </div>
      </form>

      {error ? (
        <p role="alert" className="alert">
          {error.message}
        </p>
      ) : (
        <Results
          data={data}
          loading={loading}
          page={page}
          pageSize={submitted.pageSize}
          rankedByBudget={submitted.targetBudget.trim() !== ''}
          onPageChange={setPage}
          onPageSizeChange={handlePageSize}
        />
      )}
    </main>
  );
}
