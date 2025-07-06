//import { getAuth } from 'firebase/auth';

const API_BASE_URL = 'http://localhost:5000';

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

export const uploadFile = async (formData) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });
  return response.json();
};

export const anonymizeData = async (params) => {
  const headers = {
    ...(await getAuthHeader()),
    'Content-Type': 'application/json',
  };

  const response = await fetch(`${API_BASE_URL}/anonimyze`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  });
  return response.json();
};

export const downloadFile = async (fileId) => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/download/${fileId}`, {
    method: 'GET',
    headers,
  });
  if (!response.ok) throw new Error('Errore nel download del file');
  return response.blob();
};

export const getFiles = async () => {
  const headers = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}/get-files`, {
    method: 'GET',
    headers,
  });
  return response.json();
};
