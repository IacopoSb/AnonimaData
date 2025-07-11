// Utility per convertire array di oggetti in array di array secondo l'ordine delle colonne, con debug
function objectsToRows(objects, columns) {
  console.log('objectsToRows input:', { objects, columns });

  if (!Array.isArray(objects) || objects.length === 0) {
    console.log('objectsToRows: empty or invalid objects');
    return [];
  }
  if (!Array.isArray(columns) || columns.length === 0) {
    console.log('objectsToRows: empty or invalid columns');
    return [];
  }

  const rows = objects.map(obj => {
    if (typeof obj !== 'object' || obj === null) {
      console.log('objectsToRows: invalid object', obj);
      return [];
    }

    const row = columns.map(col => {
      const value = obj[col];
      if (value === undefined) {
        console.warn(`🚨 Column "${col}" not found in object:`, obj);
      }
      return value !== undefined ? value : '';
    });

    console.log('objectsToRows: converted row', row);
    return row;
  });

  console.log('objectsToRows output:', rows);
  return rows;
}

import React, { useState, useEffect } from 'react';
import { Upload, Download, Settings, Eye, Lock, User, LogOut, CheckCircle, AlertCircle, Clock, Database, FileText, Trash } from 'lucide-react';
import { uploadFile, getFiles, anonymizeData, downloadFile, checkJobStatus, deleteFile } from './api';

import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from 'firebase/auth';
import '../src/firebase'; // Assicura che Firebase sia inizializzato

const anonymizationAlgorithms = [
  {
    id: 'k-anonymity',
    name: 'K-Anonymity',
    description: 'Groups records so each group has at least k identical records',
    params: [{ name: 'k', type: 'number', min: 2, max: 100, default: 5, description: 'Minimum group size' }]
  },
  {
    id: 'l-diversity',
    name: 'L-Diversity',
    description: 'Ensures each group has at least l different sensitive values',
    params: [
      { name: 'l', type: 'number', min: 2, max: 50, default: 3, description: 'Minimum diversity' },
      { name: 'sensitive_column', type: 'select', description: 'Sensitive attribute column' }
    ]
  },

  {
    id: 'differential-privacy',
    name: 'Differential-Privacy',
    description: 'Adds calibrated noise to protect individual privacy',
    params: [{ name: 'epsilon', type: 'number', min: 0.1, max: 10, step: 0.1, default: 1.0, description: 'Privacy budget (lower = more private)' }]
  }
];

const AnonimaData = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [firebaseLoaded, setFirebaseLoaded] = useState(false);
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
    dataProtected: 0 // Totale righe protette
  });
  // stati per il polling
  const [jobId, setJobId] = useState(null);
  const [pollingInterval, setPollingInterval] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingMessage, setProcessingMessage] = useState('');
  // --- QUESTI SONO I TRE STATI PER LA PREVIEW ---
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [currentPreviewData, setCurrentPreviewData] = useState([]);
  const [currentPreviewFilename, setCurrentPreviewFilename] = useState('');

  // Gestione autenticazione con Firebase Modular SDK
  useEffect(() => {
    const auth = getAuth();
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        setUser({
          uid: user.uid,
          name: user.displayName,
          email: user.email,
          avatar: user.photoURL
        });
        setCurrentView('dashboard');
        loadStats();
      } else {
        setUser(null);
        setCurrentView('login');
      }
      setLoading(false);
    });
    setFirebaseLoaded(true);
    return () => unsubscribe();
  }, []);


  // Firebase Google Sign In (modular)
  const handleLogin = async () => {
    const auth = getAuth();
    const provider = new GoogleAuthProvider();
    try {
      setAuthError('');
      await signInWithPopup(auth, provider);
      // User will be set automatically by the auth state listener
    } catch (error) {
      console.error('Authentication error:', error);
      setAuthError(getAuthErrorMessage(error.code));
    }
  };

  // Firebase Sign Out (modular)
  const handleLogout = async () => {
    const auth = getAuth();
    try {
      await signOut(auth);
      // User will be cleared automatically by the auth state listener
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  // Helper function to get user-friendly error messages
  const getAuthErrorMessage = (errorCode) => {
    switch (errorCode) {
      case 'auth/popup-closed-by-user':
        return 'Sign-in cancelled. Please try again.';
      case 'auth/popup-blocked':
        return 'Pop-up blocked. Please allow pop-ups for this site.';
      case 'auth/network-request-failed':
        return 'Network error. Please check your connection.';
      default:
        return 'Authentication failed. Please try again.';
    }
  };





  // *** FUNZIONE PER LA PREVIEW ***
  const handlePreview = (jobId) => {
    const datasetToPreview = datasets.find(d => d.id === jobId);
    console.log('Dataset to preview:', datasetToPreview);
    console.log('preview id:', jobId);
    if (datasetToPreview && datasetToPreview.anonymizedPreview) {
      setCurrentPreviewData(datasetToPreview.anonymizedPreview);
      setCurrentPreviewFilename(datasetToPreview.name);
      setShowPreviewModal(true);
    } else {
      console.warn(`Preview data not found for job_id: ${jobId}`);
    }
  };


  const handleDelete = async (jobId, filename) => {
    if (window.confirm(`Sei sicuro di voler eliminare il dataset "${filename}"? Questa operazione è irreversibile.`)) {
      try {
        setProcessingStatus('deleting'); // Puoi usare uno stato di caricamento per il pulsante
        setProcessingMessage(`Eliminazione di "${filename}" in corso...`);

        await deleteFile(jobId);

        setProcessingStatus('idle');
        setProcessingMessage(`Dataset "${filename}" eliminato con successo!`);
        // Dopo l'eliminazione, ricarica la lista dei dataset per aggiornare la tabella
        await loadStats();

      } catch (error) {
        console.error('Errore durante l\'eliminazione del file:', error);
        setProcessingStatus('error');
        setProcessingMessage(`Errore durante l'eliminazione di "${filename}": ${error.message}`);
        // Puoi aggiungere un setTimeout per far sparire il messaggio di errore dopo un po'
        setTimeout(() => setProcessingMessage(''), 5000);
      }
    }
  };

  //  handleFileUpload 
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];

    if (file && (file.type === 'text/csv' || file.type === 'application/json')) {
      setUploadedFile(file);
      setUploadProgress(0);

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await uploadFile(formData);
        console.log('Upload response:', response);

        // La risposta ora è sempre: { message: "...", job_id: "uuid-string", filename: "example.csv" }
        if (response.job_id) {
          startPolling(response.job_id);
          setCurrentView('processing');
        } else {
          throw new Error('No job_id returned from server');
        }
      } catch (error) {
        console.error('Errore durante l\'upload del file:', error);
        setProcessingStatus('error');
        setProcessingMessage('Failed to upload file. Please try again.');
      }
    }
  };

  // Algorithm parameter change handler
  const handleParamChange = (paramName, value) => {
    setAlgorithmParams(prev => ({
      ...prev,
      [paramName]: value
    }));
  };

  // Column configuration handler
  const handleColumnConfig = (column, type) => {
    setColumnConfig(prev => ({
      ...prev,
      [column]: type
    }));
  };


  // Funzione per avviare il polling
  const startPolling = (jobId) => {
    setJobId(jobId);
    setProcessingStatus('processing');
    setProcessingMessage('Analyzing your dataset...');

    const interval = setInterval(async () => {
      try {
        const response = await checkJobStatus(jobId);
        console.log("Polling status:", response);
        if (response.status === 'analyzed') {
          setProcessingStatus('completed');
          setProcessingMessage('Analysis completed successfully!');
          setUploadProgress(100);

          let columns = response.processed_data_info?.columns
            || response.anonymized_data_info?.columns
            || response.columns
            || [];
          let rows;

          if (Array.isArray(response.processed_data_preview)) {
            rows = objectsToRows(response.processed_data_preview, columns);
          } else if (Array.isArray(response.sample)) {
            rows = objectsToRows(response.sample, columns);
          } else {
            rows = [];
          }
          setDataPreview({ columns, rows });
          clearInterval(interval);
          setPollingInterval(null);
          setCurrentView('configure');
        } else if (response.status === 'anonymized' || response.status === 'completed') {
          setProcessingStatus('completed');
          setProcessingMessage('Anonymization completed successfully!');
          setUploadProgress(100);
          /*
          // Estrai colonne e dati dalla risposta
          let columns =
            (response.columns) ||
            (response.metadata && Array.isArray(response.metadata)
              ? response.metadata.map(m => m.column_name)
              : null) ||
            (response.columns) ||
            (response.anonymized_preview && response.anonymized_preview.length > 0
              ? Object.keys(response.anonymized_preview[0])
              : []);
          let anonymizedData =
            response.anonymized_preview ||
            response.anonymized_data_preview ||
            response.anonymized_data ||
            response.rows ||
            response.sample ||
            [];
          let rows = Array.isArray(anonymizedData)
            ? objectsToRows(anonymizedData, columns)
            : [];
          */
          console.log('Anonymization response:', response);
          let columns = response.columns;
          console.log('Columns:', columns);
          let anonymizedData = response.anonymized_preview;
          console.log('Anonymization data:', anonymizedData);
          let rows = objectsToRows(anonymizedData, columns);
          setAnonymizedPreview({ columns, rows });
          window.__lastAnonymizedRaw = anonymizedData;
          console.log('Set anonymizedPreview:', { columns, rows });
          clearInterval(interval);
          setPollingInterval(null);
        } else if (response.status === 'error') {
          // Errore
          setProcessingStatus('error');
          setProcessingMessage(response.details || 'An error occurred during processing');
          clearInterval(interval);
          setPollingInterval(null);

        } else {
          // Ancora in elaborazione
          setProcessingMessage(response.details || 'Processing your data...');
        }
      } catch (error) {
        console.error('Polling error:', error);
        setProcessingMessage('Checking status...');
      }
    }, 1000);

    setPollingInterval(interval);
  };


  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);


 useEffect(() => {
    // Questa funzione si attiva ogni volta che currentView cambia.
    // Vogliamo resettare gli stati solo quando l'utente *entra* nella vista 'upload'.
    if (currentView === 'upload') {
      setUploadedFile(null); // Resetta il file caricato
      setProcessingMessage(''); // Resetta il messaggio di processo
      setSelectedAlgorithm(''); // Resetta l'algoritmo selezionato
      setAlgorithmParams({}); // Resetta i parametri dell'algoritmo
      setDataPreview(null); // Resetta la preview dei dati originali
      // Non resettare anonymizedPreview qui, perché è legata al dataset
      // e non necessariamente all'upload corrente.
    }
  }, [currentView]); // La dipendenza è currentView



  // 3. Aggiorna handleAnonymize per usare il nuovo formato
  const handleAnonymize = async () => {
    setProcessingStatus('processing');
    setCurrentView('preview');
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
        job_id: jobId, // Assicurati che questo sia disponibile
        algorithm: selectedAlgorithm,
        params: algorithmParams,
        userSelection: userSelection
      };

      console.log('Sending anonymization request:', params);

      const response = await anonymizeData(params);
      console.log('Anonymization response:', response);

      if (response.job_id) {
        // Continua il polling per l'anonimizzazione
        startPolling(response.job_id);
      } else {
        throw new Error('No job_id returned from anonymization request');
      }
    } catch (error) {
      console.error('Errore anonimizzazione:', error);
      setProcessingStatus('error');
      setProcessingMessage('Anonymization failed. Please try again.');
    }
  };


  // 4. Aggiorna handleDownload per usare il nuovo formato
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
      console.error('Errore nel download:', error);
    }
  };

  // Save anonymized dataset
  const handleSave = () => {
    const newDataset = {
      id: Date.now(),
      name: `${uploadedFile.name.split('.')[0]}_anonymized`,
      algorithm: selectedAlgorithm,
      created: new Date().toLocaleDateString(),
      status: 'completed',
      rows: anonymizedPreview.rows.length
    };
    setDatasets(prev => [...prev, newDataset]);
    setCurrentView('dashboard');
    loadStats();
  };



  const loadStats = async () => {
    try {
      // getFiles ora restituisce un oggetto consolidato, non un array.
      const consolidatedData = await getFiles();
      console.log('Dati consolidati ricevuti da getFiles:', consolidatedData);

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

        // --- LOGICA DI ORDINAMENTO ---
        transformedDatasets.sort((a, b) => {
          // I dataset non-anonymized vanno sempre prima
          if (a.status !== 'anonymized' && b.status === 'anonymized') {
            return -1;
          }
          if (a.status === 'anonymized' && b.status !== 'anonymized') {
            return 1;
          }

          const dateA = a.rawCompletionDate || a.rawUploadDate;
          const dateB = b.rawCompletionDate || b.rawUploadDate;

          if (!dateA && !dateB) return 0;
          if (!dateA) return 1;
          if (!dateB) return -1;

          return dateB.getTime() - dateA.getTime();
        });
        // --- FINE LOGICA DI ORDINAMENTO ---

        setDatasets(transformedDatasets);
      } else {
        setDatasets([]);
      }
    } catch (error) {
      console.error('Errore nel caricamento delle statistiche:', error);
      setStats({ totalDatasets: 0, completedJobs: 0, dataProtected: 0 });
      setDatasets([]);
    }
  };
  // Login View
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
      <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center p-4">
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 w-full max-w-md border border-white/20">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full mb-4">
              <Lock className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">AnonimaData</h1>
            <p className="text-gray-300">Secure Dataset Anonymization Platform</p>
          </div>

          {authError && (
            <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <p className="text-red-300 text-sm">{authError}</p>
              </div>
            </div>
          )}

          <button
            onClick={handleLogin}
            disabled={!firebaseLoaded}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-500 disabled:to-gray-600 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-xl transition-all duration-300 transform hover:scale-105 hover:shadow-lg flex items-center justify-center gap-3"
          >
            <User className="w-5 h-5" />
            {firebaseLoaded ? 'Sign in with Google' : 'Loading...'}
          </button>

          <div className="mt-6 text-center">
            <p className="text-gray-400 text-sm">
              Secure authentication powered by Firebase
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Lock className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">AnonimaData</h1>
            </div>

            <nav className="hidden md:flex space-x-8">
              <button
                onClick={() => {
                  setCurrentView('dashboard');
                  loadStats(); // Aggiungi questa riga
                }}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${currentView === 'dashboard' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'
                  }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setCurrentView('upload')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${currentView === 'upload' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'
                  }`}
              >
                Upload Data
              </button>
            </nav>

            <div className="flex items-center gap-4">
              <img
                src={user.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=6366f1&color=fff`}
                alt={user.name}
                className="w-8 h-8 rounded-full"
                onError={(e) => {
                  e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=6366f1&color=fff`;
                }}
              />
              <div className="hidden md:block">
                <span className="text-sm font-medium text-gray-700 block">{user.name}</span>
                <span className="text-xs text-gray-500">{user.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-gray-600 transition-colors p-2 rounded-lg hover:bg-gray-100"
                title="Sign out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentView === 'dashboard' && (
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

            {/* Schede Statistiche */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6"> {/* Cambiato md:grid-cols-3 in md:grid-cols-2 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Dataset Totali</p>
                    <p className="text-3xl font-bold text-gray-900">{stats.totalDatasets}</p>
                  </div>
                  <Database className="w-8 h-8 text-blue-600" />
                </div>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Righe Totali Protette</p> {/* Etichetta aggiornata */}
                    <p className="text-3xl font-bold text-gray-900">{stats.dataProtected}</p> {/* Ora mostra correttamente dataProtected (che deriva da total_rows) */}
                  </div>
                  <Lock className="w-8 h-8 text-purple-600" />
                </div>
              </div>
            </div>

            {/* Datasets Table */}
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
                        {/* Intestazione della colonna modificata */}
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
                          {/* Visualizzazione della data di completamento/upload */}
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {dataset.created}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {/* Stile e icona condizionali per lo status */}
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
                            {/* Pulsanti visibili solo se lo status è 'anonymized' */}
                            {dataset.status === 'anonymized' && (
                              <>
                                <button className="text-blue-600 hover:text-blue-900 mr-4"
                                  onClick={() => handleDownload(dataset.id,dataset.name)}
                                >
                                  <Download className="w-4 h-4" />
                                </button>
                                <button className="text-purple-600 hover:text-purple-900 mr-4"
                                  onClick={() => handlePreview(dataset.id)}>
                                  <Eye className="w-4 h-4" />
                                </button>
                              </>
                            )}
                            {/* Pulsante di cancellazione - visibile per tutti i dataset (o con logica specifica) */}
                            {/* Potresti voler renderlo visibile solo per determinati stati, ad es. 'anonymized' o 'uploaded' */}
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
        )}
        {/* --- NUOVO JSX DEL MODAL (ESEMPIO CON TAILWIND CSS) --- */}
        {showPreviewModal && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
            <div className="relative p-5 border w-11/12 md:w-2/3 lg:w-1/2 shadow-lg rounded-md bg-white">
              <div className="flex justify-between items-center pb-3">
                <h3 className="text-lg font-bold">Preview: {currentPreviewFilename}</h3>
              </div>
              <div className="mt-2 text-sm text-gray-500 max-h-96 overflow-y-auto">
                {currentPreviewData.length > 0 ? (
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        {/* Estrai dinamicamente le intestazioni dalla prima riga di dati */}
                        {Object.keys(currentPreviewData[0]).map((key) => (
                          <th key={key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {key}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {currentPreviewData.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {Object.values(row).map((value, colIndex) => (
                            <td key={colIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {value}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p>Nessun dato di preview disponibile.</p>
                )}
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => setShowPreviewModal(false)}
                  className="px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  Chiudi
                </button>
              </div>
            </div>
          </div>
        )}
        {/* --- FINE NUOVO JSX DEL MODAL --- */}
        {currentView === 'upload' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl font-bold text-gray-900 mb-8">Upload Dataset</h2>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-400 transition-colors">
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Upload your dataset</h3>
                <p className="text-gray-500 mb-4">Support for CSV and JSON files up to 100MB</p>

                <input
                  type="file"
                  accept=".csv,.json"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
                >
                  Choose File
                </label>
              </div>

              {uploadedFile && (
                <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-green-800 font-medium">File uploaded successfully: {uploadedFile.name}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}


        {currentView === 'configure' && dataPreview && (
          <div className="space-y-8">
            <h2 className="text-3xl font-bold text-gray-900">Configure Anonymization</h2>

            {/* Column Configuration Table */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Column Configuration</h3>
              <p className="text-sm text-gray-600 mb-6">Select the type for each column in your dataset</p>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 font-medium text-gray-900">Column Name</th>

                      <th className="text-center py-3 px-4 font-medium text-gray-900">Quasi-Identifier</th>
                      <th className="text-center py-3 px-4 font-medium text-gray-900">Sensitive</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataPreview.columns.map((column, index) => (
                      <tr key={column} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-4 px-4">
                          <div className="font-medium text-gray-900">{column}</div>
                        </td>

                        <td className="py-4 px-4 text-center">
                          <input
                            type="checkbox"
                            id={`quasi-${column}`}
                            checked={columnConfig[column]?.quasi || false}
                            onChange={(e) => handleColumnConfig(column, {
                              ...columnConfig[column],
                              quasi: e.target.checked
                            })}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                        </td>
                        <td className="py-4 px-4 text-center">
                          <input
                            type="checkbox"
                            id={`sensitive-${column}`}
                            checked={columnConfig[column]?.sensitive || false}
                            onChange={(e) => handleColumnConfig(column, {
                              ...columnConfig[column],
                              sensitive: e.target.checked
                            })}
                            className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-blue-600 rounded"></div>
                  <span className="text-gray-600">
                    <strong>Quasi-Identifier:</strong> Columns that could be used to identify individuals (e.g., age, zip code)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-purple-600 rounded"></div>
                  <span className="text-gray-600">
                    <strong>Sensitive:</strong> Columns containing sensitive information (e.g., medical data, salary)
                  </span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-8">
              {/* Configuration Panel */}
              <div className="space-y-6">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Algorithm</h3>

                  <div className="space-y-3">
                    {anonymizationAlgorithms.map((algorithm) => (
                      <label key={algorithm.id} className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                        <input
                          type="radio"
                          name="algorithm"
                          value={algorithm.id}
                          checked={selectedAlgorithm === algorithm.id}
                          onChange={(e) => setSelectedAlgorithm(e.target.value)}
                          className="mt-1"
                        />
                        <div>
                          <div className="font-medium text-gray-900">{algorithm.name}</div>
                          <div className="text-sm text-gray-500">{algorithm.description}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {selectedAlgorithm && (
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Parameters</h3>
                    {anonymizationAlgorithms.find(a => a.id === selectedAlgorithm)?.params.map((param) => (
                      <div key={param.name} className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          {param.description}
                        </label>
                        {param.type === 'number' ? (
                          <input
                            type="number"
                            min={param.min}
                            max={param.max}
                            step={param.step || 1}
                            onChange={(e) => handleParamChange(param.name, parseInt(e.target.value))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        ) : param.type === 'select' ? (
                          <select
                            onChange={(e) => handleParamChange(param.name, e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="">Select column...</option>
                            {dataPreview.columns.map(col => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={handleAnonymize}
                  disabled={!selectedAlgorithm}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-400 text-white px-6 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center justify-center gap-2"
                >
                  <Settings className="w-5 h-5" />
                  Start Anonymization
                </button>
              </div>

            </div>
          </div>
        )}


        {/*prova del polling dio campo*/}

        {currentView === 'processing' && (
          <div className="space-y-8">
            <h2 className="text-3xl font-bold text-gray-900">Processing Dataset</h2>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
              <div className="text-center">
                <div className="animate-spin w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-6"></div>

                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  {processingMessage}
                </h3>

                {uploadProgress > 0 && (
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                )}

                <p className="text-gray-500 mb-6">
                  Please wait while we process your dataset. This may take a few minutes.
                </p>

                <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
                  <Clock className="w-4 h-4" />
                  <span>Job ID: {jobId}</span>
                </div>

                <p className="text-xs text-gray-400 mt-2">
                  We're checking every second for updates...
                </p>
              </div>
            </div>

            {/* Pulsante per annullare o tornare indietro */}
            <div className="flex justify-center">
              <button
                onClick={() => {
                  if (pollingInterval) {
                    clearInterval(pollingInterval);
                    setPollingInterval(null);
                  }
                  setCurrentView('dashboard');
                  setProcessingStatus('idle');
                }}
                className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
              >
                Cancel & Return to Dashboard
              </button>
            </div>
          </div>
        )}






        {currentView === 'preview' && (
          <div className="space-y-8">
            <h2 className="text-3xl font-bold text-gray-900">Anonymization Results</h2>

            {processingStatus === 'processing' && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{processingMessage}</h3>

                {uploadProgress > 0 && (
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-4 max-w-md mx-auto">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                )}

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
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-8 h-8 text-green-600" />
                    <div>
                      <h3 className="text-lg font-semibold text-green-900">Anonymization Completed</h3>
                      <p className="text-green-700">Your dataset has been successfully anonymized using {selectedAlgorithm}.</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1  gap-8">
                  

                  {/* Anonymized Data */}
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Anonymized Data</h3>
                    
                    {/* Messaggio di errore se la preview è vuota */}
                    {(!Array.isArray(anonymizedPreview.rows) || anonymizedPreview.rows.length === 0) && (
                      <div className="mb-4 p-4 bg-red-100 border border-red-200 rounded text-red-700 flex items-center gap-2">
                        <AlertCircle className="w-5 h-5 text-red-500" />
                        <span>No anonymized data found in the backend response. Please check the backend or contact support.</span>
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
                            anonymizedPreview.rows.slice(0, 3).map((row, idx) => {
                              // Se row è undefined/null, mostra una riga vuota
                              if (!row) {
                                return (
                                  <tr key={idx} className="border-b">
                                    <td colSpan={anonymizedPreview.columns.length} className="p-2 text-gray-400 text-center">Empty row</td>
                                  </tr>
                                );
                              }
                              // Se row è un array, mostra i valori
                              if (Array.isArray(row)) {
                                return (
                                  <tr key={idx} className="border-b">
                                    {row.map((cell, cellIdx) => (
                                      <td key={cellIdx} className="p-2 text-blue-600 font-medium">{cell}</td>
                                    ))}
                                  </tr>
                                );
                              }
                              // Se row è un oggetto, mostra i valori nell'ordine delle colonne
                              if (typeof row === 'object' && row !== null) {
                                return (
                                  <tr key={idx} className="border-b">
                                    {anonymizedPreview.columns.map((col, cellIdx) => (
                                      <td key={cellIdx} className="p-2 text-blue-600 font-medium">{row[col] !== undefined ? row[col] : ''}</td>
                                    ))}
                                  </tr>
                                );
                              }
                              // Altrimenti, mostra il valore come stringa
                              return (
                                <tr key={idx} className="border-b">
                                  <td colSpan={anonymizedPreview.columns.length} className="p-2 text-blue-600 font-medium">{String(row)}</td>
                                </tr>
                              );
                            })
                          ) : (
                            <tr>
                              <td colSpan={anonymizedPreview?.columns?.length || 1} className="p-2 text-gray-400 text-center">
                                No data available
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
                    onClick={handleSave}
                    className="bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 text-white px-8 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center gap-2"
                  >
                    Chiudi
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default AnonimaData;