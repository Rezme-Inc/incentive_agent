import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWizard } from '../../context/WizardContext';
import { Layout } from '../../components/common/Layout';
import { AddressInputStep } from './AddressInputStep';
import { discoverIncentives } from '../../services/api';

export const InputPage = () => {
  const navigate = useNavigate();
  const { state, setSessionId, canProceed } = useWizard();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!state.address || state.address.trim().length === 0) {
      setError('Please enter a company address');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await discoverIncentives(state.address);
      setSessionId(response.session_id);
      
      // Navigate to processing page with session ID
      navigate(`/processing/${response.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start discovery');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Incentive Program Discovery</h1>
          <p className="text-gray-600">AI-powered discovery of employer hiring incentive programs</p>
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

        {/* Address Input Form */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <AddressInputStep />
        </div>

        {/* Submit Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={!canProceed() || isSubmitting}
            className="px-6 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Starting Discovery...' : 'Discover Programs'}
          </button>
        </div>

        {/* Info Panel */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-blue-900 mb-2">
            How it works
          </h4>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>We'll identify government entities (city, county, state, federal) for your address</li>
            <li>Search for incentive programs at each government level</li>
            <li>Merge and deduplicate results to show you unique programs</li>
            <li>You can then shortlist programs and calculate ROI</li>
          </ul>
        </div>
      </div>
    </Layout>
  );
};
