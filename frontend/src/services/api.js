import { getAuth } from 'firebase/auth';

// API base URL, fallback used during development
export const API_BASE_URL =
  window.RUNTIME_ENV && window.RUNTIME_ENV.API_BASE_URL
    ? window.RUNTIME_ENV.API_BASE_URL.replace(/\/$/, '')
    : "https://orchestratore-614401261394.europe-west1.run.app";

const getAuthHeader = async () => {
  const auth = getAuth();
  console.log(auth)
  const user = auth.currentUser;
  if (!user) throw new Error('User not authenticated');

  const token = await user.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
  };
}

// Check job status (analysis and anonymization)
export const checkJobStatus = async (jobId) => {
  try {
    const analysisResponse = await fetch(`${API_BASE_URL}/get_status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(await getAuthHeader()),
      }
    });

    if (analysisResponse.ok) {
      const analysisData = await analysisResponse.json();

      // If analysis is completed, return analysis data
      if (analysisData.status === 'analyzed') {
        let columns = [];
        if (Array.isArray(analysisData.metadata)) {
          columns = analysisData.metadata.map(col => col.column_name);
        } else if (Array.isArray(analysisData.metadata?.columns)) {
          columns = analysisData.metadata.columns;
        } else if (Array.isArray(analysisData.columns)) {
          columns = analysisData.columns;
        }
        return {
          status: 'analyzed',
          job_id: jobId,
          columns,
          sample: analysisData.processed_data_preview || [],
          rows: analysisData.processed_data_preview || [],
          metadata: analysisData.metadata
        };
      }
      else if (analysisData.status === 'anonymized') {
        let column = [];
        column = analysisData.metadata.map(col => col.column_name);

        return {
          status: 'anonymized',
          job_id: jobId,
          columns: column,
          anonymized_preview: analysisData.anonymized_preview,
          metadata: analysisData.metadata
        };
      }
      // If analysis is still in progress
      return {
        status: analysisData.status,
        job_id: jobId,
        progress: analysisData.progress,
        details: analysisData.details
      };
    }
  } catch (error) {
    console.error('Status check error:', error);
    throw new Error(`Status check failed: ${error.message}`);
  }
};

// File upload function
export const uploadFile = async (formData) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/upload_and_analyze`, {
    method: 'POST',
    body: formData,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }

  return response.json();
};

// Data anonymization function
export const anonymizeData = async (params) => {
  const headers = {
    ...(await getAuthHeader()),
    'Content-Type': 'application/json',
  };

  // Transform userSelection to API expected format
  let user_selections = [];
  if (params.userSelection) {
    Object.entries(params.userSelection).forEach(([column, config]) => {
      user_selections.push({
        column_name: column,
        is_quasi_identifier: !!config.quasi,
        should_anonymize: !!config.sensitive
      });
    });
  }

  const payload = {
    job_id: params.job_id,
    method: params.algorithm,
    params: params.params,
    user_selections: user_selections
  };

  const response = await fetch(`${API_BASE_URL}/request_anonymization`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Anonymization failed: ${response.status}`);
  }

  return response.json();
};

// Download file function (supports full and sample)
export const downloadFile = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/download/${jobId}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error('Error downloading file');
  }

  return response.blob();
};

// Get files function
export const getFiles = async () => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/get_files`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error(`Get files failed: ${response.status}`);
  }

  const data = await response.json();
  console.log('Get files response:', data);

  // New structure: array with two objects, one with stats, one with files
  if (Array.isArray(data) && data.length >= 2) {
    const statsObj = data.find(item => item.stats);
    const filesObj = data.find(item => item.files);

    const statistics = statsObj?.stats || [];
    const files = filesObj?.files || [];

    return {
      totalDatasets: statistics[0]?.datasets || 0,
      completedJobs: files.filter(f => f.status === 'completed').length,
      dataProtected: statistics[0]?.total_rows || 0,
      files
    };
  } else if (typeof data === 'object' && data.stats && data.files) {
    // In case object structure is still used
    const statistics = data.stats;
    const files = data.files;

    return {
      totalDatasets: statistics[0]?.datasets || 0,
      completedJobs: files.filter(f => f.status === 'completed').length,
      dataProtected: statistics[0]?.total_rows || 0,
      files
    };
  }

  // Fallback
  return {
    totalDatasets: 0,
    completedJobs: 0,
    dataProtected: 0,
    files: []
  };
};

// Export anonymization JSON function
export const exportAnonymizationJSON = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/export_anonymization_json/${jobId}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error('Error exporting JSON');
  }

  return response.blob();
};

// Delete file function
export const deleteFile = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/delete/${jobId}`, {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(`File deletion failed: ${response.status} - ${errorData.message || response.statusText}`);
  }
  return true;
};
