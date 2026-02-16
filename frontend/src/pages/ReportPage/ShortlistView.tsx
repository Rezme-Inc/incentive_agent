import { ProgramCard } from '../../components/ProgramCard';
import type { Program } from '../../services/types';

interface ShortlistViewProps {
  programs: Program[];
  onRemoveProgram: (programId: string) => void;
  onContinue: () => void;
}

export const ShortlistView = ({
  programs,
  onRemoveProgram,
  onContinue,
}: ShortlistViewProps) => {
  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Shortlisted Programs
        </h3>
        <p className="text-sm text-gray-600">
          {programs.length} program{programs.length !== 1 ? 's' : ''} selected for ROI analysis
        </p>
      </div>

      {/* Program Cards */}
      {programs.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md p-12 text-center">
          <p className="text-gray-500">No programs selected. Please go back and select programs.</p>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {programs.map((program) => (
              <ProgramCard
                key={program.id}
                program={program}
                selected={true}
                onSelect={() => onRemoveProgram(program.id)}
              />
            ))}
          </div>

          {/* Continue Button */}
          <div className="flex justify-end">
            <button
              onClick={onContinue}
              className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              Continue to ROI Questions →
            </button>
          </div>
        </>
      )}
    </div>
  );
};

