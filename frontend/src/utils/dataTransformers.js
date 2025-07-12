// src/utils/dataTransformers.js
// Utility per convertire array di oggetti in array di array secondo l'ordine delle colonne, con debug
/*
export function objectsToRows(objects, columns) {
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
}*/
// src/utils/dataTransformers.js
// Utility per convertire array di oggetti in array di oggetti, per mantenere la consistenza con i nomi delle colonne
export function objectsToRows(objects, columns) {
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
      return {}; // Restituisce un oggetto vuoto per riga non valida
    }

    const newRow = {};
    columns.forEach(col => {
      const value = obj[col];
      if (value === undefined) {
        console.warn(`🚨 Column "${col}" not found in object:`, obj);
      }
      // Assegna il valore o una stringa vuota se undefined
      newRow[col] = value !== undefined ? value : '';
    });

    console.log('objectsToRows: converted row', newRow);
    return newRow; // Restituisce un oggetto { "col1": "val1", "col2": "val2" }
  });

  console.log('objectsToRows output:', rows);
  return rows; // Restituisce un array di oggetti
}