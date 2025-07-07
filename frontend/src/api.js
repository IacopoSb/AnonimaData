//import { getAuth } from 'firebase/auth';

//const API_BASE_URL = 'http://localhost:5000';


const API_BASE_URL = window?.env?.BACKEND_URL;

const getAuthHeader = async () => {
  /*const auth = getAuth();
  const user = auth.currentUser;
  if (!user) throw new Error('Utente non autenticato');

  const token = await user.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
  };*/
  return {} //vuoto solo per i test
};



// Check dello status - ora controlla sia analisi che anonimizzazione
export const checkJobStatus = async (jobId) => {
  try {
    // Prima prova a controllare lo status dell'analisi
    const analysisResponse = await fetch(`${API_BASE_URL}/get_analysis_status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(await getAuthHeader()),
      }
    });

    if (analysisResponse.ok) {
      const analysisData = await analysisResponse.json();
      
      // Se l'analisi è completata, restituisci i dati dell'analisi
      if (analysisData.status === 'analyzed') {
        return {
          status: 'analized', // Mantieni il nome che il frontend si aspetta
          job_id: jobId,
          columns: analysisData.processed_data_info?.columns || [],
          sample: analysisData.processed_data_preview || [],
          colonna: analysisData.processed_data_info?.columns || [], // Fallback per compatibilità
          rows: analysisData.processed_data_preview || []
        };
      }
      
      // Se l'analisi è ancora in corso
      return {
        status: analysisData.status,
        job_id: jobId,
        progress: analysisData.progress,
        details: analysisData.details
      };
    }

    // Se l'analisi non è trovata, prova a controllare l'anonimizzazione
    const anonymizationResponse = await fetch(`${API_BASE_URL}/get_anonymization_status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(await getAuthHeader()),
      }
    });

    if (anonymizationResponse.ok) {
      const anonymizationData = await anonymizationResponse.json();
      
      if (anonymizationData.status === 'completed') {
        return {
          status: 'anonymized', // Nuovo status per indicare che l'anonimizzazione è completata
          job_id: jobId,
          columns: anonymizationData.data_info?.columns || [],
          dati_anonimizzati: anonymizationData.data || [],
          anonymized_data: anonymizationData.data || [],
          method_used: anonymizationData.method_used,
          params_used: anonymizationData.params_used
        };
      }
      
      return {
        status: anonymizationData.status,
        job_id: jobId
      };
    }

    throw new Error('Job not found');
  } catch (error) {
    console.error('Status check error:', error);
    throw new Error(`Status check failed: ${error.message}`);
  }
};


// Funzione per l'upload del file (modificata)
export const uploadFile = async (formData) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }

  return response.json();
};



// 3. Anonimizzazione - ora usa l'endpoint corretto con payload corretto
export const anonymizeData = async (params) => {
  const headers = {
    ...(await getAuthHeader()),
    'Content-Type': 'application/json',
  };

  // Trasforma i parametri nel formato che l'API si aspetta
  const payload = {
    job_id: params.job_id,
    method: params.algorithm, // 'algorithm' diventa 'method'
    params: params.params,
    user_selections: {
      quasi_identifiers: [],
      sensitive_attributes: [],
      identifiers_to_remove: []
    }
  };

  // Trasforma userSelection nel formato corretto
  if (params.userSelection) {
    Object.entries(params.userSelection).forEach(([column, config]) => {
      if (config.quasi) {
        payload.user_selections.quasi_identifiers.push(column);
      }
      if (config.sensitive) {
        payload.user_selections.sensitive_attributes.push(column);
      }
      // Potresti aggiungere logica per identifiers_to_remove se necessario
    });
  }

  const response = await fetch(`${API_BASE_URL}/request_anonymization`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Anonymization failed: ${response.status}`);
  }

  return response.json();
  // Risposta attesa: { message: "Anonymization request published", job_id: "uuid-string" }
};









// 4. Download del file - ora supporta sia full che sample
export const downloadFile = async (jobId, type = 'full') => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/download/${jobId}/${type}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error('Errore nel download del file');
  }
  
  return response.blob();
};


// 5. Get files - ora usa l'endpoint corretto e gestisce la risposta
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
  
  // La risposta è un array con due elementi: [statistics, files]
  if (Array.isArray(data) && data.length >= 2) {
    const [statistics, files] = data;
    
    return {
      totalDatasets: statistics[0]?.datasets || 0,
      completedJobs: files.filter(f => f.status === 'completed').length,
      dataProtected: statistics[0]?.total_rows || 0,
      files: files || []
    };
  }
  
  // Fallback per compatibilità
  return {
    totalDatasets: 0,
    completedJobs: 0,
    dataProtected: 0,
    files: []
  };
};


// 6. Nuova funzione per esportare JSON
export const exportAnonymizationJSON = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/export_anonymization_json/${jobId}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error('Errore nell\'esportazione JSON');
  }
  
  return response.blob();
};