import React, { useState, useEffect } from 'react';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || window.location.origin;

function App() {
  const [contractors, setContractors] = useState([]);
  const [stats, setStats] = useState(null);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [location, setLocation] = useState('');
  const [minRating, setMinRating] = useState('');
  const [sortBy, setSortBy] = useState('rating');

  // Pagination
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  // Selected contractor for details
  const [selectedContractor, setSelectedContractor] = useState(null);

  useEffect(() => {
    fetchStats();
    fetchLocations();
  }, []);

  useEffect(() => {
    fetchContractors();
  }, [search, location, minRating, sortBy, page]);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchLocations = async () => {
    try {
      const response = await fetch(`${API_URL}/api/locations`);
      const data = await response.json();
      setLocations(data.locations || []);
    } catch (error) {
      console.error('Error fetching locations:', error);
    }
  };

  const fetchContractors = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: (page * limit).toString(),
        sort_by: sortBy,
        sort_order: 'desc'
      });

      if (search) params.append('search', search);
      if (location) params.append('location', location);
      if (minRating) params.append('min_rating', minRating);

      const response = await fetch(`${API_URL}/api/contractors?${params}`);
      const data = await response.json();
      setContractors((data.contractors || []).filter(c => c !== null));
      setTotal(data.total || 0);
    } catch (error) {
      console.error('Error fetching contractors:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setSearch('');
    setLocation('');
    setMinRating('');
    setSortBy('rating');
    setPage(0);
  };

  return (
    <div className="App">
      <header className="header">
        <h1>🏠 GAF Sales Intelligence Platform</h1>
        <p>Contractor Database & Analytics</p>
      </header>

      {/* Stats Dashboard */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <h3>{stats.total_contractors}</h3>
            <p>Total Contractors</p>
          </div>
          <div className="stat-card">
            <h3>⭐ {stats.average_rating}</h3>
            <p>Average Rating</p>
          </div>
          <div className="stat-card">
            <h3>{stats.recent_scrape_runs?.length || 0}</h3>
            <p>Recent Scrapes</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="filters">
        <input
          type="text"
          placeholder="Search by name or location..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="search-input"
        />

        <select
          value={location}
          onChange={(e) => { setLocation(e.target.value); setPage(0); }}
          className="filter-select"
        >
          <option value="">All Locations</option>
          {locations.map((loc) => (
            <option key={loc} value={loc}>{loc}</option>
          ))}
        </select>

        <select
          value={minRating}
          onChange={(e) => { setMinRating(e.target.value); setPage(0); }}
          className="filter-select"
        >
          <option value="">Any Rating</option>
          <option value="4.5">4.5+ Stars</option>
          <option value="4.0">4.0+ Stars</option>
          <option value="3.0">3.0+ Stars</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="filter-select"
        >
          <option value="rating">Sort by Rating</option>
          <option value="reviews_count">Sort by Reviews</option>
          <option value="name">Sort by Name</option>
        </select>

        <button onClick={handleReset} className="reset-button">Reset Filters</button>
      </div>

      {/* Results */}
      <div className="results-header">
        <p>Showing {contractors.length} of {total} contractors</p>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="contractors-grid">
          {contractors.map((contractor) => (
            <div
              key={contractor.id}
              className="contractor-card"
              onClick={() => setSelectedContractor(contractor)}
            >
              <h3>{contractor.name}</h3>
              <p className="location">📍 {contractor.location}</p>
              <div className="rating-row">
                <span className="rating">⭐ {contractor.rating || 'N/A'}</span>
                <span className="reviews">({contractor.reviews_count || 0} reviews)</span>
              </div>
              {contractor.phone && (
                <p className="phone">📞 {contractor.phone}</p>
              )}
              {contractor.certifications && contractor.certifications.length > 0 && (
                <div className="certifications">
                  {contractor.certifications.slice(0, 2).map((cert, idx) => (
                    <span key={idx} className="cert-badge">{cert}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > limit && (
        <div className="pagination">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            ← Previous
          </button>
          <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={(page + 1) * limit >= total}
          >
            Next →
          </button>
        </div>
      )}

      {/* Modal for contractor details */}
      {selectedContractor && (
        <div className="modal-overlay" onClick={() => setSelectedContractor(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-button" onClick={() => setSelectedContractor(null)}>×</button>

            <h2>{selectedContractor.name}</h2>
            <p className="location">📍 {selectedContractor.location}</p>

            <div className="detail-section">
              <strong>Rating:</strong> ⭐ {selectedContractor.rating || 'N/A'} ({selectedContractor.reviews_count || 0} reviews)
            </div>

            {selectedContractor.phone && (
              <div className="detail-section">
                <strong>Phone:</strong> {selectedContractor.phone}
              </div>
            )}

            {selectedContractor.description && (
              <div className="detail-section">
                <strong>About:</strong>
                <p>{selectedContractor.description}</p>
              </div>
            )}

            {selectedContractor.certifications && selectedContractor.certifications.length > 0 && (
              <div className="detail-section">
                <strong>Certifications:</strong>
                <div className="certifications">
                  {selectedContractor.certifications.map((cert, idx) => (
                    <span key={idx} className="cert-badge">{cert}</span>
                  ))}
                </div>
              </div>
            )}

            {selectedContractor.profile_url && (
              <div className="detail-section">
                <a href={selectedContractor.profile_url} target="_blank" rel="noopener noreferrer" className="profile-link">
                  View on GAF.com →
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
