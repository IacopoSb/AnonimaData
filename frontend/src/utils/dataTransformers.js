// Utility to convert an array of objects into an array of objects with consistent column names
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
      return {}; // Returns an empty object for invalid rows
    }

    const newRow = {};
    columns.forEach(col => {
      const value = obj[col];
      if (value === undefined) {
        console.warn(`Column "${col}" not found in object:`, obj);
      }
      // Assigns the value or an empty string if undefined
      newRow[col] = value !== undefined ? value : '';
    });

    console.log('objectsToRows: converted row', newRow);
    return newRow; // Returns an object { "col1": "val1", "col2": "val2" }
  });

  console.log('objectsToRows output:', rows);
  return rows; // Returns an array of objects
}