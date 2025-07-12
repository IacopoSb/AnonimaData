import React from 'react';
import { CheckCircle, AlertCircle, InfoIcon } from 'lucide-react';

const PreviewResults = ({
  processingStatus,
  processingMessage,
  anonymizedPreview,
  selectedAlgorithm,
  jobId,
  handleDownload,
  handleSave,
  setCurrentView
}) => {
  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-bold text-gray-900">Anonymization Results</h2>

      {processingStatus === 'processing' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">{processingMessage}</h3>
          <p className="text-gray-500">Job ID: {jobId}</p>
        </div>
      )}

      {processingStatus === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-8 h-8 text-red-600" />
            <div>
              <h3 className="text-lg font-semibold text-red-900">Processing Failed</h3>
              <p className="text-red-700">{processingMessage}</p>
            </div>
          </div>
          <div className="mt-4 flex gap-4">
            <button
              onClick={() => setCurrentView('configure')}
              className="px-6 py-3 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => setCurrentView('dashboard')}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      )}

      {processingStatus === 'completed' && anonymizedPreview && (
        <div className="space-y-6">
          { /* Algorithm is not null only if the view is rendered from the processing view, if so show the succeded banner */ }
          { selectedAlgorithm && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-6">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-8 h-8 text-green-600" />
              <div>
                <h3 className="text-lg font-semibold text-green-900">Anonymization Completed</h3>
                <p className="text-green-700">Your dataset has been successfully anonymized using {selectedAlgorithm}.</p>
              </div>
            </div>
          </div>
          )}
          <div className="grid grid-cols-1 gap-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Anonymized Data Preview</h3>

              {(!Array.isArray(anonymizedPreview.rows) || anonymizedPreview.rows.length === 0) && (
                <div className="mb-4 p-4 bg-red-100 border border-red-200 rounded text-red-700 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-red-500" />
                  <span>No anonymized data found in the response. Please contact support.</span>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      {anonymizedPreview.columns.map((col) => (
                        <th key={col} className="text-left p-2 font-medium text-gray-900">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(anonymizedPreview.rows) && anonymizedPreview.rows.length > 0 ? (
                      anonymizedPreview.rows.slice(0, 9).map((row, idx) => (
                        <tr key={idx} className="border-b">
                          {anonymizedPreview.columns.map((col, cellIdx) => (
                            <td key={cellIdx} className="p-2 text-blue-600 font-medium">
                              {row[col] !== undefined ? String(row[col]) : ''}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={anonymizedPreview?.columns?.length || 1} className="p-2 text-gray-400 text-center">
                          No data available for preview.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="flex gap-4 justify-center">
            <button
              onClick={() => handleDownload(jobId, 'anonymized_data')}
              className="bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 text-white px-8 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center gap-2"
            >
              Download Anonymized Data
            </button>
            <button
              onClick={handleSave}
              className="bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 text-white px-8 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center gap-2"
            >
              Close
            </button>
          </div>
          <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
            <InfoIcon className="w-4 h-4" />
            <span>Job ID: {jobId}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default PreviewResults;