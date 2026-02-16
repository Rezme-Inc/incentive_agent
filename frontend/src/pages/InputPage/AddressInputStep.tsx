import { useState, useEffect, useRef } from 'react';
import { useWizard } from '../../context/WizardContext';
import { addressAutocomplete } from '../../services/api';
import { TaxDesignationDropdown } from '../../components/TaxDesignationDropdown';
import { AnnualRevenueInput } from '../../components/AnnualRevenueInput';
import { TotalEmployeesInput } from '../../components/TotalEmployeesInput';

export const AddressInputStep = () => {
  const { state, setAddress } = useWizard();
  const [localAddress, setLocalAddress] = useState(state.address);
  const [taxDesignation, setTaxDesignation] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [totalEmployees, setTotalEmployees] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchSuggestions = (query: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      if (query.length < 2) {
        setSuggestions([]);
        setShowSuggestions(false);
        return;
      }
      try {
        const results = await addressAutocomplete(query);
        setSuggestions(results);
        setShowSuggestions(results.length > 0);
        setActiveSuggestion(-1);
      } catch {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    }, 200);
  };

  const handleAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocalAddress(value);
    setAddress(value);
    fetchSuggestions(value);
  };

  const selectSuggestion = (suggestion: string) => {
    setLocalAddress(suggestion);
    setAddress(suggestion);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSuggestion((prev) => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSuggestion((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && activeSuggestion >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[activeSuggestion]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Address Input */}
      <div ref={wrapperRef} className="relative">
        <label
          htmlFor="address-input"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Company Address <span className="text-red-500">*</span>
        </label>
        <input
          id="address-input"
          type="text"
          value={localAddress}
          onChange={handleAddressChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder="Enter full company address (e.g., 233 S Wacker Dr, Chicago, IL 60606)"
          autoComplete="off"
          className="block w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        />

        {/* Autocomplete dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
            {suggestions.map((suggestion, idx) => (
              <li
                key={idx}
                onClick={() => selectSuggestion(suggestion)}
                className={`px-4 py-2 text-sm cursor-pointer ${
                  idx === activeSuggestion
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {suggestion}
                </div>
              </li>
            ))}
          </ul>
        )}

        <p className="mt-2 text-sm text-gray-500">
          We'll discover government entities (city, county, state, federal) that control this address
          and search for available incentive programs.
        </p>
      </div>

      {/* Tax Designation */}
      <TaxDesignationDropdown
        value={taxDesignation}
        onChange={setTaxDesignation}
      />

      {/* Company Information Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <AnnualRevenueInput
          value={annualRevenue}
          onChange={setAnnualRevenue}
        />
        <TotalEmployeesInput
          value={totalEmployees}
          onChange={setTotalEmployees}
        />
      </div>
    </div>
  );
};
