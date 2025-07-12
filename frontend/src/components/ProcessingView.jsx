import React from 'react';
import { CircleAlert, InfoIcon } from 'lucide-react';
import LoadingSpinner from './LoadingSpinner';

const ProcessingView = ({
  processingMessage,
  errorMessage,
  uploadProgress,
  jobId,
  pollingInterval,
  setPollingInterval,
  setCurrentView,
  setProcessingStatus 
}) => {
  const handleCancel = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setCurrentView('dashboard');
    setProcessingStatus('idle');
  };

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-bold text-gray-900">Processing Dataset</h2>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="text-center">
          <div className='flex justify-center mb-4'>
          { errorMessage ? (<CircleAlert size={64} />) : (<LoadingSpinner size={64} />)}
          </div>

          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            {processingMessage}
          </h3>

          

          <p className="text-gray-500 mb-6">
            {errorMessage || "Please wait while we process your dataset. This may take a few minutes."}
          </p>

          <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
            <InfoIcon className="w-4 h-4" />
            <span>Job ID: {jobId}</span>
          </div>
        </div>
      </div>

      <div className="flex justify-center">
        <button
          onClick={handleCancel}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
        >
          Return to Dashboard
        </button>
      </div>
    </div>
  );
};

export default ProcessingView;