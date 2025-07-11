
import '../src/firebase';
import { getAuth } from 'firebase/auth';




export const API_BASE_URL =
  window.RUNTIME_ENV && window.RUNTIME_ENV.API_BASE_URL
    ? window.RUNTIME_ENV.API_BASE_URL.replace(/\/$/, '')
    : "https://orchestratore-614401261394.europe-west1.run.app"; // fallback opzionale, senza slash finale

const getAuthHeader = async () => {
  const auth = getAuth();
  console.log(auth)
  const user = auth.currentUser;
  if (!user) throw new Error('Utente non autenticato');

  const token = await user.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
  };

}



// Check dello status - ora controlla sia analisi che anonimizzazione
export const checkJobStatus = async (jobId) => {
  try {
    // Prima prova a controllare lo status dell'analisi
    const analysisResponse = await fetch(`${API_BASE_URL}/get_status/${jobId}`, {
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
        // Estrai le colonne sia da metadata (array di oggetti) che da metadata.columns (array di stringhe)
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
        /*return {
          status: 'anonymized',
          job_id: jobId,
          columns: analysisData.anonymized_data_info?.columns || analysisData.data_info?.columns || [],
          anonymized_data: analysisData.anonymized_data_preview,
          rows: analysisData.anonymized_data_preview,
          preview: data
        }*/
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
      // Se l'analisi è ancora in corso
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


// Funzione per l'upload del file (modificata)
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



// 3. Anonimizzazione - ora usa l'endpoint corretto con payload corretto
export const anonymizeData = async (params) => {
  const headers = {
    ...(await getAuthHeader()),
    'Content-Type': 'application/json',
  };

  // Trasforma userSelection nel formato che l'API si aspetta
  let user_selections = [];
  if (params.userSelection) {
    Object.entries(params.userSelection).forEach(([column, config]) => {
      user_selections.push({
        column_name: column,
        is_quasi_identifier: !!config.quasi,
        should_anonymize: !!config.sensitive // esempio: true se sensitive o quasi
      });
    });
  }

  const payload = {
    job_id: params.job_id,
    method: params.algorithm, // 'algorithm' diventa 'method'
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
  // Risposta attesa: { message: "Anonymization request published", job_id: "uuid-string" }
};









// 4. Download del file - ora supporta sia full che sample
export const downloadFile = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/download/${jobId}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error('Errore nel download del file');
  }

  return response.blob();
};

/*
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
  
  // Supporta sia risposta come [statistics, files] sia come oggetto { stats: [...], files: [...] }
  if (Array.isArray(data) && data.length >= 2) {
    const [statistics, files] = data;
    return {
      totalDatasets: statistics[0]?.datasets || 0,
      completedJobs: files.filter(f => f.status === 'completed').length,
      dataProtected: statistics[0]?.total_rows || 0,
      files: files || []
    };
  } else if (typeof data === 'object' && data.stats && data.files) {
    const statistics = data.stats;
    const files = data.files;
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
*/



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

  // Nuova struttura: array con due oggetti, uno con stats, uno con files
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
    // In caso venga usata ancora la struttura ad oggetto
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



export const deleteFile = async (jobId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/delete/${jobId}`, {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    // Gestisci gli errori in base alla risposta del tuo backend
    const errorData = await response.json().catch(() => ({ message: 'Errore sconosciuto' }));
    throw new Error(`Cancellazione file fallita: ${response.status} - ${errorData.message || response.statusText}`);
  }

  // Se la cancellazione ha successo, il backend potrebbe rispondere con uno stato 200 OK senza corpo,
  // oppure con un messaggio di conferma. Non è strettamente necessario leggere il JSON qui
  // a meno che non ti aspetti dati specifici di ritorno.
  // const data = await response.json(); // Se il tuo backend restituisce un JSON alla cancellazione
  return true; // Indica che l'operazione ha avuto successo
};
