import type { Program } from '../services/types';

interface ProgramCardProps {
  program: Program;
  selected?: boolean;
  onSelect?: (programId: string) => void;
}

const getStatusColor = (status: Program['status_tag']) => {
  switch (status) {
    case 'ACTIVE':
      return 'bg-green-50 border-green-200';
    case 'EXPIRED':
      return 'bg-yellow-50 border-yellow-200';
    case 'NON-INCENTIVE':
      return 'bg-gray-50 border-gray-200';
    default:
      return 'bg-gray-50 border-gray-200';
  }
};

const getStatusBadgeColor = (status: Program['status_tag']) => {
  switch (status) {
    case 'ACTIVE':
      return 'bg-green-100 text-green-800';
    case 'EXPIRED':
      return 'bg-yellow-100 text-yellow-800';
    case 'NON-INCENTIVE':
      return 'bg-gray-100 text-gray-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

const getBenefitTypeBadgeColor = (benefitType: Program['benefit_type']) => {
  switch (benefitType) {
    case 'tax_credit':
      return 'bg-blue-100 text-blue-700';
    case 'wage_subsidy':
      return 'bg-purple-100 text-purple-700';
    case 'training_grant':
      return 'bg-indigo-100 text-indigo-700';
    case 'bonding':
      return 'bg-teal-100 text-teal-700';
    default:
      return 'bg-gray-100 text-gray-700';
  }
};

const getGovernmentLevelBadgeColor = (level: Program['government_level']) => {
  switch (level) {
    case 'federal':
      return 'bg-red-100 text-red-700';
    case 'state':
      return 'bg-orange-100 text-orange-700';
    case 'county':
      return 'bg-cyan-100 text-cyan-700';
    case 'city':
      return 'bg-pink-100 text-pink-700';
    default:
      return 'bg-gray-100 text-gray-700';
  }
};

export function ProgramCard({ program, selected = false, onSelect }: ProgramCardProps) {
  return (
    <div
      className={`border rounded-lg p-5 mb-4 ${getStatusColor(program.status_tag)} ${
        selected ? 'ring-2 ring-blue-500' : ''
      }`}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">
            {program.program_name}
          </h3>
          {program.agency && (
            <p className="text-sm text-gray-600">
              {program.agency}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onSelect(program.id)}
              className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
          )}
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusBadgeColor(
              program.status_tag
            )}`}
          >
            {program.status_tag}
          </span>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        {program.max_value && (
          <div>
            <span className="text-gray-600 font-medium">Max Value:</span>
            <span className="ml-2 text-gray-900">{program.max_value}</span>
          </div>
        )}
        <div>
          <span className="text-gray-600 font-medium">Government Level:</span>
          <span className="ml-2">
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${getGovernmentLevelBadgeColor(
                program.government_level
              )}`}
            >
              {program.government_level.toUpperCase()}
            </span>
          </span>
        </div>
        <div>
          <span className="text-gray-600 font-medium">Benefit Type:</span>
          <span className="ml-2">
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${getBenefitTypeBadgeColor(
                program.benefit_type
              )}`}
            >
              {program.benefit_type.replace('_', ' ').toUpperCase()}
            </span>
          </span>
        </div>
        <div>
          <span className="text-gray-600 font-medium">Confidence:</span>
          <span className="ml-2 text-gray-900 capitalize">{program.confidence}</span>
        </div>
      </div>

      {/* Description */}
      {program.description && (
        <div className="mb-3 p-3 bg-white bg-opacity-60 rounded">
          <h4 className="text-sm font-semibold text-gray-700 mb-1">
            Description:
          </h4>
          <p className="text-sm text-gray-800">{program.description}</p>
        </div>
      )}

      {/* Target Populations */}
      {program.target_populations && program.target_populations.length > 0 && (
        <div className="mb-3">
          <span className="text-xs text-gray-600 font-medium">Target Populations:</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {program.target_populations.map((pop, idx) => (
              <span
                key={idx}
                className="inline-block px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs"
              >
                {pop.replace('_', ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source URL */}
      {program.official_source_url && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <a
            href={program.official_source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:text-blue-800 underline"
          >
            View Official Source →
          </a>
        </div>
      )}
    </div>
  );
}

