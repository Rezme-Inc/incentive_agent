import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { WizardStepper } from '../../components/common/WizardStepper';
import { getPrograms, submitShortlist } from '../../services/api';
import type { Program, ROICalculation } from '../../services/types';
import { ProgramList } from './ProgramList';
import { ShortlistView } from './ShortlistView';
import { ROIQuestions } from './ROIQuestions';
import { ROISpreadsheet } from './ROISpreadsheet';

const STEPS = [
  { label: 'Program List', description: 'Select programs for ROI analysis' },
  { label: 'Shortlist Review', description: 'Review selected programs' },
  { label: 'ROI Questions', description: 'Answer questions for ROI calculation' },
  { label: 'ROI Spreadsheet', description: 'View and download ROI calculations' },
];

export const ReportPage = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [selectedProgramIds, setSelectedProgramIds] = useState<string[]>([]);
  const [shortlistedPrograms, setShortlistedPrograms] = useState<Program[]>([]);
  const [roiCalculations, setRoiCalculations] = useState<ROICalculation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrograms = async () => {
      if (!sessionId) {
        setError('No session ID provided');
        setLoading(false);
        return;
      }

      try {
        const data = await getPrograms(sessionId);
        setPrograms(data.programs);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load programs');
      } finally {
        setLoading(false);
      }
    };

    fetchPrograms();
  }, [sessionId]);

  const handleSelectProgram = (programId: string) => {
    setSelectedProgramIds((prev) => [...prev, programId]);
  };

  const handleDeselectProgram = (programId: string) => {
    setSelectedProgramIds((prev) => prev.filter((id) => id !== programId));
  };

  const handleContinueToShortlist = async () => {
    if (!sessionId || selectedProgramIds.length === 0) {
      setError('Please select at least one program');
      return;
    }

    try {
      const response = await submitShortlist(sessionId, selectedProgramIds);
      setShortlistedPrograms(response.shortlisted);
      setCurrentStep(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit shortlist');
    }
  };

  const handleRemoveFromShortlist = (programId: string) => {
    setShortlistedPrograms((prev) => prev.filter((p) => p.id !== programId));
    setSelectedProgramIds((prev) => prev.filter((id) => id !== programId));
  };

  const handleContinueToROI = () => {
    setCurrentStep(2);
  };

  const handleROIAnswersSubmitted = (calculations: ROICalculation[]) => {
    setRoiCalculations(calculations);
    setCurrentStep(3);
  };

  const handleStepClick = (step: number) => {
    // Only allow going back, not forward
    if (step < currentStep) {
      setCurrentStep(step);
    }
  };

  const isStepComplete = (step: number): boolean => {
    switch (step) {
      case 0:
        return selectedProgramIds.length > 0;
      case 1:
        return shortlistedPrograms.length > 0;
      case 2:
        return roiCalculations.length > 0;
      case 3:
        return roiCalculations.length > 0;
      default:
        return false;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <PageHeader title="Loading Programs..." />
          <div className="flex justify-center py-12">
            <svg className="w-8 h-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  if (error && !programs.length) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <PageHeader title="Error Loading Programs" />
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="text-red-700">{error}</p>
            <button
              onClick={() => navigate('/input')}
              className="mt-4 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
            >
              Start New Discovery
            </button>
          </div>
        </div>
      </div>
    );
  }

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <ProgramList
            programs={programs}
            selectedProgramIds={selectedProgramIds}
            onSelectProgram={handleSelectProgram}
            onDeselectProgram={handleDeselectProgram}
          />
        );
      case 1:
        return (
          <ShortlistView
            programs={shortlistedPrograms}
            onRemoveProgram={handleRemoveFromShortlist}
            onContinue={handleContinueToROI}
          />
        );
      case 2:
        return (
          <ROIQuestions
            sessionId={sessionId!}
            onAnswersSubmitted={handleROIAnswersSubmitted}
          />
        );
      case 3:
        return (
          <ROISpreadsheet
            sessionId={sessionId!}
            calculations={roiCalculations}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <PageHeader
          title="Incentive Programs Report"
          subtitle={`Session: ${sessionId}`}
        />

        {/* Wizard Stepper */}
        <div className="mb-8 bg-white rounded-lg shadow-md p-6">
          <WizardStepper
            steps={STEPS}
            currentStep={currentStep}
            onStepClick={handleStepClick}
            isStepComplete={isStepComplete}
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center">
              <svg
                className="w-5 h-5 text-red-600 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Step Content */}
        {renderStep()}

        {/* Navigation Buttons */}
        {currentStep < STEPS.length - 1 && currentStep !== 1 && (
          <div className="mt-6 flex justify-between">
            <button
              onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
              disabled={currentStep === 0}
              className="px-6 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            {currentStep === 0 && (
              <button
                onClick={handleContinueToShortlist}
                disabled={selectedProgramIds.length === 0}
                className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue to Shortlist →
              </button>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-center gap-4">
          <button
            onClick={() => navigate('/input')}
            className="px-6 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            New Discovery
          </button>
        </div>
      </div>
    </div>
  );
};
