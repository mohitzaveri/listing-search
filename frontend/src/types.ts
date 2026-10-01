export interface Listing {
  id: string;
  source: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  price: number;
  bedrooms: number;
  bathrooms: number;
  sqft: number;
  latitude: number;
  longitude: number;
  listedDate: string;
  status: 'active' | 'pending' | 'sold';
  description: string;
  score: number;
}

export interface SearchResponse {
  results: Listing[];
  page: number;
  pageSize: number;
  totalResults: number;
  totalPages: number;
}

/** Form values are kept as strings; the API does all number checks. */
export interface Filters {
  minPrice: string;
  maxPrice: string;
  minBedrooms: string;
  city: string;
  keyword: string;
  targetBudget: string;
  pageSize: string;
}
