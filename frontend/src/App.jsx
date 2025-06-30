import React, { useState, useEffect } from 'react';
import { Upload, Download, Settings, Eye, Lock, User, LogOut, CheckCircle, AlertCircle, Clock, Database, FileText } from 'lucide-react';

// Firebase configuration - Replace with your actual config
const firebaseConfig = {
  apiKey: "your-api-key",
  authDomain: "your-project-firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "your-app-id"
};

// Firebase will be loaded from CDN - we'll initialize it in useEffect
let auth = null;
let provider = null;

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
    id: 't-closeness', 
    name: 'T-Closeness', 
    description: 'Distribution of sensitive attribute in each group close to overall distribution',
    params: [
      { name: 't', type: 'number', min: 0.1, max: 1, step: 0.1, default: 0.3, description: 'Closeness threshold' },
      { name: 'sensitive_column', type: 'select', description: 'Sensitive attribute column' }
    ]
  },
  { 
    id: 'differential-privacy', 
    name: 'Differential Privacy', 
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

  // Load Firebase SDK and initialize
  useEffect(() => {
    const loadFirebase = async () => {
      try {
        // Load Firebase scripts
        const firebaseAppScript = document.createElement('script');
        firebaseAppScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/firebase/9.22.0/firebase-app-compat.min.js';
        firebaseAppScript.onload = () => {
          const firebaseAuthScript = document.createElement('script');
          firebaseAuthScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/firebase/9.22.0/firebase-auth-compat.min.js';
          firebaseAuthScript.onload = () => {
            // Initialize Firebase after scripts are loaded
            if (window.firebase) {
              const app = window.firebase.initializeApp(firebaseConfig);
              auth = window.firebase.auth();
              provider = new window.firebase.auth.GoogleAuthProvider();
              
              // Set up auth state listener
              const unsubscribe = auth.onAuthStateChanged((user) => {
                if (user) {
                  setUser({
                    uid: user.uid,
                    name: user.displayName,
                    email: user.email,
                    avatar: user.photoURL
                  });
                  setCurrentView('dashboard');
                } else {
                  setUser(null);
                  setCurrentView('login');
                }
                setLoading(false);
              });

              setFirebaseLoaded(true);
              
              // Cleanup function
              window.firebaseUnsubscribe = unsubscribe;
            }
          };
          document.head.appendChild(firebaseAuthScript);
        };
        document.head.appendChild(firebaseAppScript);
      } catch (error) {
        console.error('Firebase loading error:', error);
        setLoading(false);
        setAuthError('Failed to load authentication system');
      }
    };

    loadFirebase();

    // Cleanup
    return () => {
      if (window.firebaseUnsubscribe) {
        window.firebaseUnsubscribe();
      }
    };
  }, []);

  // Firebase Google Sign In
  const handleLogin = async () => {
    if (!auth || !provider) {
      setAuthError('Authentication system not ready');
      return;
    }

    try {
      setAuthError('');
      const result = await auth.signInWithPopup(provider);
      // User will be set automatically by the auth state listener
    } catch (error) {
      console.error('Authentication error:', error);
      setAuthError(getAuthErrorMessage(error.code));
    }
  };

  // Firebase Sign Out
  const handleLogout = async () => {
    if (!auth) return;
    
    try {
      await auth.signOut();
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

  // File upload handler
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && (file.type === 'text/csv' || file.type === 'application/json')) {
      setUploadedFile(file);
      // Mock data preview
      setDataPreview({
        columns: ['id', 'name', 'age', 'city', 'salary'],
        rows: [
          ['1', 'Mario Rossi', '35', 'Roma', '45000'],
          ['2', 'Anna Verdi', '28', 'Milano', '52000'],
          ['3', 'Luigi Bianchi', '42', 'Napoli', '38000']
        ]
      });
      setCurrentView('configure');
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

  // Process anonymization
  const handleAnonymize = async () => {
    setProcessingStatus('processing');
    setCurrentView('preview');
    
    // Simulate processing time
    setTimeout(() => {
      setAnonymizedPreview({
        columns: dataPreview.columns,
        rows: [
          ['*', 'Person A', '30-40', 'Centro Italia', '40000-50000'],
          ['*', 'Person B', '25-35', 'Nord Italia', '50000-60000'],
          ['*', 'Person C', '40-50', 'Sud Italia', '35000-45000']
        ]
      });
      setProcessingStatus('completed');
    }, 3000);
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
                onClick={() => setCurrentView('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentView === 'dashboard' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                Dashboard
              </button>
              <button 
                onClick={() => setCurrentView('upload')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentView === 'upload' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'
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

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Datasets</p>
                    <p className="text-3xl font-bold text-gray-900">{datasets.length}</p>
                  </div>
                  <Database className="w-8 h-8 text-blue-600" />
                </div>
              </div>
              
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Completed Jobs</p>
                    <p className="text-3xl font-bold text-gray-900">{datasets.filter(d => d.status === 'completed').length}</p>
                  </div>
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
              </div>
              
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Data Protected</p>
                    <p className="text-3xl font-bold text-gray-900">{datasets.reduce((sum, d) => sum + d.rows, 0)}</p>
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
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
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
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              {dataset.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <button className="text-blue-600 hover:text-blue-900 mr-4">
                              <Download className="w-4 h-4" />
                            </button>
                            <button className="text-purple-600 hover:text-purple-900">
                              <Eye className="w-4 h-4" />
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
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
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
                            defaultValue={param.default}
                            onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value))}
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

              {/* Data Preview */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Preview</h3>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        {dataPreview.columns.map((col) => (
                          <th key={col} className="text-left p-2 font-medium text-gray-900">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {dataPreview.rows.slice(0, 5).map((row, idx) => (
                        <tr key={idx} className="border-b">
                          {row.map((cell, cellIdx) => (
                            <td key={cellIdx} className="p-2 text-gray-600">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                
                <p className="text-sm text-gray-500 mt-2">
                  Showing 5 of {dataPreview.rows.length} rows
                </p>
              </div>
            </div>
          </div>
        )}

        {currentView === 'preview' && (
          <div className="space-y-8">
            <h2 className="text-3xl font-bold text-gray-900">Anonymization Results</h2>
            
            {processingStatus === 'processing' && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Processing your dataset...</h3>
                <p className="text-gray-500">This may take a few minutes depending on the dataset size.</p>
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

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Original Data */}
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Original Data</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            {dataPreview.columns.map((col) => (
                              <th key={col} className="text-left p-2 font-medium text-gray-900">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {dataPreview.rows.slice(0, 3).map((row, idx) => (
                            <tr key={idx} className="border-b">
                              {row.map((cell, cellIdx) => (
                                <td key={cellIdx} className="p-2 text-gray-600">{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Anonymized Data */}
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Anonymized Data</h3>
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
                          {anonymizedPreview.rows.map((row, idx) => (
                            <tr key={idx} className="border-b">
                              {row.map((cell, cellIdx) => (
                                <td key={cellIdx} className="p-2 text-blue-600 font-medium">{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div className="flex gap-4 justify-center">
                  <button 
                    onClick={() => setCurrentView('configure')}
                    className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
                  >
                    Reconfigure
                  </button>
                  <button 
                    onClick={handleSave}
                    className="bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 text-white px-8 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center gap-2"
                  >
                    <Download className="w-5 h-5" />
                    Save & Download
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