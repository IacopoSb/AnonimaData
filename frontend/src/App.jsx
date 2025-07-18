// App.jsx (Main Component)
import React, { useState, useEffect, useCallback } from 'react';
import { LogOut, Lock, User } from 'lucide-react';
import useAuth from './hooks/useAuth';
import { uploadFile, getFiles, anonymizeData, downloadFile, checkJobStatus, deleteFile } from './services/api';
import { objectsToRows } from './utils/dataTransformers';
import Dashboard from './components/Dashboard';
import UploadData from './components/UploadData';
import ConfigureAnonymization from './components/ConfigureAnonymization';
import ProcessingView from './components/ProcessingView';
import PreviewResults from './components/PreviewResults';
import DeleteModal from './components/DeleteModal';
import Header from './components/Header';
import AuthView from './components/AuthView';

const AnonimaData = () => {
  const { user, loading, authError, firebaseLoaded, handleLogin, handleLogout } = useAuth();

  const [currentView, setCurrentView] = useState('dashboard');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('');
  const [algorithmParams, setAlgorithmParams] = useState({});
  const [dataPreview, setDataPreview] = useState(null);
  const [anonymizedPreview, setAnonymizedPreview] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('idle');
  const [datasets, setDatasets] = useState([]);
  const [columnConfig, setColumnConfig] = useState({});
  const [stats, setStats] = useState({
    totalDatasets: 0,
    dataProtected: 0
  });
  const [jobId, setJobId] = useState(null);
  const [pollingInterval, setPollingInterval] = useState(null);
  const [processingMessage, setProcessingMessage] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [currentPreviewFilename, setCurrentPreviewFilename] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [statsError, setStatsError] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  // Load dashboard statistics and datasets
  const loadStats = useCallback(async () => {
    setIsRefreshing(true);
    setStatsError(false);
    try {
      const consolidatedData = await getFiles();
      setStats({
        totalDatasets: consolidatedData.totalDatasets || 0,
        completedJobs: consolidatedData.completedJobs || 0,
        dataProtected: consolidatedData.dataProtected || 0
      });

      if (consolidatedData.files && consolidatedData.files.length > 0) {
        const transformedDatasets = consolidatedData.files.map(file => ({
          id: file.job_id,
          name: file.filename,
          algorithm: file.method || 'Unknown',
          created: file.datetime_completition
            ? new Date(file.datetime_completition).toLocaleString()
            : (file.datetime_upload ? new Date(file.datetime_upload).toLocaleString() : 'N/A'),
          status: file.status,
          rows: file.rows || 0,
          filename: file.job_id,
          anonymizedPreview: file.anonymized_preview || [],
          rawCompletionDate: file.datetime_completition ? new Date(file.datetime_completition) : null,
          rawUploadDate: new Date(file.datetime_upload),
        }));

        transformedDatasets.sort((a, b) => {
          if (a.status !== 'anonymized' && b.status === 'anonymized') return -1;
          if (a.status === 'anonymized' && b.status !== 'anonymized') return 1;

          const dateA = a.rawCompletionDate || a.rawUploadDate;
          const dateB = b.rawCompletionDate || b.rawUploadDate;

          if (!dateA && !dateB) return 0;
          if (!dateA) return 1;
          if (!dateB) return -1;

          return dateB.getTime() - dateA.getTime();
        });
        setDatasets(transformedDatasets);
      } else {
        setDatasets([]);
      }
    } catch (error) {
      console.error('Error loading statistics:', error);
      setStatsError(true);
      setStats({ totalDatasets: 0, completedJobs: 0, dataProtected: 0 });
      setDatasets([]);
    }
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    if (user) {
      setCurrentView('dashboard');
      loadStats();
    } else {
      setCurrentView('login');
    }
  }, [user, loadStats]);

  // Poll job status for processing and anonymization
  const startPolling = useCallback((jobId) => {
    setJobId(jobId);
    setProcessingStatus('processing');
    setProcessingMessage('Analyzing your dataset...');

    const interval = setInterval(async () => {
      try {
        const response = await checkJobStatus(jobId);
        setErrorMessage(null);
        setCurrentPreviewFilename(null);
        if (response.status === 'analyzed') {
          setProcessingStatus('completed');
          setProcessingMessage('Analysis completed successfully!');
          const columns = response.processed_data_info?.columns || response.columns || [];
          const rows = objectsToRows(response.processed_data_preview || response.sample || [], columns);
          setDataPreview({ columns, rows });
          clearInterval(interval);
          setPollingInterval(null);
          setCurrentView('configure');
        } else if (response.status === 'anonymized' || response.status === 'completed') {
          setProcessingStatus('completed');
          setProcessingMessage('Anonymization completed successfully!');
          const columns = response.columns || [];
          const anonymizedData = response.anonymized_preview || [];
          const rows = objectsToRows(anonymizedData, columns);
          setAnonymizedPreview({ columns, rows });
          setCurrentPreviewFilename(response.fileName);
          clearInterval(interval);
          setPollingInterval(null);
          loadStats();
          setCurrentView('preview');
        } else if (response.status === 'error') {
          setProcessingStatus('error');
          setProcessingMessage(response.details || 'An error occurred during processing');
          setErrorMessage(response.error_message || 'An error occurred');
          clearInterval(interval);
          setPollingInterval(null);
        } else {
          setProcessingMessage(response.details || 'Processing your data...');
        }
      } catch (error) {
        console.error('Polling error:', error);
        setProcessingMessage('Checking status...');
      }
    }, 1000);

    setPollingInterval(interval);
  }, [loadStats]);

  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  // Reset state when switching to upload view
  useEffect(() => {
    if (currentView === 'upload') {
      setUploadedFile(null);
      setProcessingMessage('');
      setSelectedAlgorithm('');
      setAlgorithmParams({});
      setDataPreview(null);
      setAnonymizedPreview(null);
      setJobId(null);
      setProcessingStatus('idle');
      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
      }
    }
  }, [currentView, pollingInterval]);

  // Handle file upload
const handleFileUpload = async (event) => {
  const file = event.target.files[0];
  if (file) {
    const validTypes = ['text/csv', 'application/json'];
    const validExtensions = ['.csv', '.json'];
    const fileType = file.type;
    const fileName = file.name.toLowerCase();
    const hasValidType = validTypes.includes(fileType);
    const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));

    if (hasValidType || hasValidExtension) {
      setUploadedFile(file);

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await uploadFile(formData);
        if (response.job_id) {
          startPolling(response.job_id);
          setCurrentView('processing');
        } else {
          throw new Error('No job_id returned from server');
        }
      } catch (error) {
        console.error('Error uploading file:', error);
        setProcessingStatus('error');
        setProcessingMessage('Failed to upload file. Please try again.');
        setCurrentView('upload');
      }
    }
  }
};

  // Handle algorithm parameter change
  const handleParamChange = (paramName, value) => {
    setAlgorithmParams(prev => ({ ...prev, [paramName]: value }));
  };

  // Handle column configuration change
  const handleColumnConfig = (column, type) => {
    setColumnConfig(prev => ({ ...prev, [column]: type }));
  };

  // Start anonymization process
  const handleAnonymize = async () => {
    setProcessingStatus('processing');
    setCurrentView('processing');
    setProcessingMessage('Starting anonymization process...');

    try {
      const userSelection = {};
      dataPreview.columns.forEach(column => {
        userSelection[column] = {
          quasi: columnConfig[column]?.quasi || false,
          sensitive: columnConfig[column]?.sensitive || false
        };
      });

      const params = {
        job_id: jobId,
        algorithm: selectedAlgorithm,
        params: algorithmParams,
        userSelection: userSelection
      };

      const response = await anonymizeData(params);
      if (response.job_id) {
        startPolling(response.job_id);
      } else {
        throw new Error('No job_id returned from anonymization request');
      }
    } catch (error) {
      console.error('Error during anonymization:', error);
      setProcessingStatus('error');
      setProcessingMessage('Anonymization failed. Please try again.');
    }
  };

  // Download anonymized file
  const handleDownload = async (jobId, fileName) => {
    try {
      const fileBlob = await downloadFile(jobId);
      const url = window.URL.createObjectURL(fileBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `anonymized_${fileName}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Failed to download file. Please try again.');
    }
  };

  // Show delete confirmation modal
  const handleDeleteRequest = async (jobId, filename) => {
    setCurrentPreviewFilename(filename);
    setJobId(jobId);
    setShowDeleteModal(true);
  };

  // Delete dataset
  const handleDelete = async (jobId) => {
    try {
      await deleteFile(jobId);
      await loadStats();
    } catch (error) {
      console.error('Error deleting file:', error);
      alert('Failed to delete file. Please try again.');
    }
  };

  // Save and return to dashboard
  const handleSave = () => {
    setCurrentView('dashboard');
    setAnonymizedPreview(null);
    setUploadedFile(null);
    setSelectedAlgorithm('');
    setAlgorithmParams({});
    setColumnConfig({});
    setProcessingStatus('idle');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-white border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-white text-lg">
            {firebaseLoaded ? 'Initializing...' : 'Loading authentication...'}
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <AuthView
        handleLogin={handleLogin}
        authError={authError}
        firebaseLoaded={firebaseLoaded}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header
        user={user}
        handleLogout={handleLogout}
        setCurrentView={setCurrentView}
        currentView={currentView}
        loadStats={loadStats}
      />

      {/* Show error if present */}
      {statsError && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative m-4 max-w-7xl mx-auto">
          <strong className="font-bold">Error:</strong>
          <span className="block sm:inline ml-2">failed to contact the server. Retry in a few minutes.</span>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentView === 'dashboard' && (
          <Dashboard
            datasets={datasets}
            stats={stats}
            setCurrentView={setCurrentView}
            loadStats={loadStats}
            handleDownload={handleDownload}
            handleDelete={handleDeleteRequest}
            openJob={startPolling}
            getFiles={getFiles}
            isLoading={isRefreshing}
          />
        )}

        {currentView === 'upload' && (
          <UploadData
            handleFileUpload={handleFileUpload}
            uploadedFile={uploadedFile}
          />
        )}

        {currentView === 'configure' && dataPreview && (
          <ConfigureAnonymization
            dataPreview={dataPreview}
            columnConfig={columnConfig}
            handleColumnConfig={handleColumnConfig}
            selectedAlgorithm={selectedAlgorithm}
            setSelectedAlgorithm={setSelectedAlgorithm}
            algorithmParams={algorithmParams}
            handleParamChange={handleParamChange}
            handleAnonymize={handleAnonymize}
          />
        )}

        {currentView === 'processing' && (
          <ProcessingView
            processingMessage={processingMessage}
            errorMessage={errorMessage}
            jobId={jobId}
            pollingInterval={pollingInterval}
            setPollingInterval={setPollingInterval}
            setCurrentView={setCurrentView}
            setProcessingStatus={setProcessingStatus}
          />
        )}

        {currentView === 'preview' && (
          <PreviewResults
            processingStatus={processingStatus}
            processingMessage={processingMessage}
            anonymizedPreview={anonymizedPreview}
            selectedAlgorithm={selectedAlgorithm}
            jobId={jobId}
            handleDownload={handleDownload}
            handleSave={handleSave}
            setCurrentView={setCurrentView}
            fileName={currentPreviewFilename}
          />
        )}

        <DeleteModal
          show={showDeleteModal}
          onClose={() => setShowDeleteModal(false)}
          filename={currentPreviewFilename}
          jobId={jobId}
          onDelete={handleDelete}
        />
      </main>
    </div>
  );
};

export default AnonimaData;