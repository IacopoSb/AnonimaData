// Dashboard.jsx
import React from 'react';
import { Upload, Download, Eye, Database, FileText, Lock, CheckCircle, Clock, Trash } from 'lucide-react';
import { objectsToRows } from '../utils/dataTransformers'; // Import utility

const Dashboard = ({
  datasets,
  stats,
  setCurrentView,
  loadStats, // loadStats is handled in App.jsx but passed down if needed for refresh
  handleDownload,
  handlePreview,
  handleDelete,
  setShowPreviewModal,
  setCurrentPreviewData,
  setCurrentPreviewFilename
}) => {
  // Moved handlePreview logic here for clarity if modal state is passed
  const handlePreviewInternal = (jobId) => {
    const datasetToPreview = datasets.find(d => d.id === jobId);
    if (datasetToPreview && datasetToPreview.anonymizedPreview) {
      // Ensure anonymizedPreview is an array of objects
      const columns = datasetToPreview.anonymizedPreview.length > 0
        ? Object.keys(datasetToPreview.anonymizedPreview[0])
        : [];
      // objectsToRows returns an array of arrays, but PreviewModal expects array of objects for display
      const previewRowsRaw = objectsToRows(datasetToPreview.anonymizedPreview, columns);
      // Transform back to array of objects for PreviewModal
      const previewRows = previewRowsRaw.map(rowArray => {
        const obj = {};
        columns.forEach((col, idx) => {
          obj[col] = rowArray[idx];
        });
        return obj;
      });

      setCurrentPreviewData(previewRows);
      setCurrentPreviewFilename(datasetToPreview.name);
      setShowPreviewModal(true);
    } else {
      console.warn(`Preview data not found for job_id: ${jobId}`);
      setCurrentPreviewData([]);
      setCurrentPreviewFilename('');
      setShowPreviewModal(true); // Still show modal, but with "No data" message
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Dashboard</h2>
        <button
          onClick={() => setCurrentView('upload')}
          className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-6 py-3 rounded-xl font-semibold transition-all duration-300 transform hover:scale-105 flex items-center gap-2"
        >
          <Upload className="w-5 h-5" />
          Upload New Dataset
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Datasets</p>
              <p className="text-3xl font-bold text-gray-900">{stats.totalDatasets}</p>
            </div>
            <Database className="w-8 h-8 text-blue-600" />
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Protected Rows</p>
              <p className="text-3xl font-bold text-gray-900">{stats.dataProtected}</p>
            </div>
            <Lock className="w-8 h-8 text-purple-600" />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Your Anonymized Datasets</h3>
        </div>

        {datasets.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">No datasets yet. Upload your first dataset to get started!</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dataset</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Algorithm</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rows</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Completed / Uploaded</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {datasets.map((dataset) => (
                  <tr key={dataset.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{dataset.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {dataset.algorithm}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {dataset.rows.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {dataset.created}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {dataset.status === 'anonymized' ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          {dataset.status}
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                          <Clock className="w-3 h-3 mr-1" />
                          {dataset.status}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      {dataset.status === 'anonymized' && (
                        <>
                          <button className="text-blue-600 hover:text-blue-900 mr-4"
                            onClick={() => handleDownload(dataset.id, dataset.name)}
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button className="text-purple-600 hover:text-purple-900 mr-4"
                            onClick={() => handlePreviewInternal(dataset.id)}>
                            <Eye className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      <button className="text-red-600 hover:text-red-900"
                        onClick={() => handleDelete(dataset.id, dataset.name)}
                        title="Delete Dataset"
                      >
                        <Trash className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;