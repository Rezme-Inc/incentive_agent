import { useState, useMemo } from 'react';
import { ProgramCard } from '../../components/ProgramCard';
import type { Program } from '../../services/types';

interface ProgramListProps {
  programs: Program[];
  selectedProgramIds: string[];
  onSelectProgram: (programId: string) => void;
  onDeselectProgram: (programId: string) => void;
}

export const ProgramList = ({
  programs,
  selectedProgramIds,
  onSelectProgram,
  onDeselectProgram,
}: ProgramListProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [benefitTypeFilter, setBenefitTypeFilter] = useState<string>('all');

  const filteredPrograms = useMemo(() => {
    return programs.filter((program) => {
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        if (
          !program.program_name.toLowerCase().includes(query) &&
          !program.agency?.toLowerCase().includes(query) &&
          !program.description?.toLowerCase().includes(query)
        ) {
          return false;
        }
      }

      // Level filter
      if (levelFilter !== 'all' && program.government_level !== levelFilter) {
        return false;
      }

      // Benefit type filter
      if (benefitTypeFilter !== 'all' && program.benefit_type !== benefitTypeFilter) {
        return false;
      }

      return true;
    });
  }, [programs, searchQuery, levelFilter, benefitTypeFilter]);

  const handleToggleProgram = (programId: string) => {
    if (selectedProgramIds.includes(programId)) {
      onDeselectProgram(programId);
    } else {
      onSelectProgram(programId);
    }
  };

  const levelOptions = ['all', 'city', 'county', 'state', 'federal'];
  const benefitTypeOptions = ['all', 'tax_credit', 'wage_subsidy', 'training_grant', 'bonding', 'unknown'];

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filters</h3>
        
        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            placeholder="Search programs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Filter dropdowns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Government Level
            </label>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              {levelOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All Levels' : option.charAt(0).toUpperCase() + option.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Benefit Type
            </label>
            <select
              value={benefitTypeFilter}
              onChange={(e) => setBenefitTypeFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              {benefitTypeOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All Types' : option.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Results count */}
        <div className="mt-4 text-sm text-gray-600">
          Showing {filteredPrograms.length} of {programs.length} programs
          {selectedProgramIds.length > 0 && (
            <span className="ml-2 text-blue-600 font-medium">
              ({selectedProgramIds.length} selected)
            </span>
          )}
        </div>
      </div>

      {/* Program Cards */}
      <div>
        {filteredPrograms.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <p className="text-gray-500">No programs match your filters.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredPrograms.map((program) => (
              <ProgramCard
                key={program.id}
                program={program}
                selected={selectedProgramIds.includes(program.id)}
                onSelect={handleToggleProgram}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

