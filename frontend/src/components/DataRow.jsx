import React from 'react';
import { Download, Eye, Clock, Trash, FormInputIcon, CheckCircle } from 'lucide-react';

// Utility: Skeleton loader for loading state
function Skeleton({ width = "w-20", height = "h-4" }) {
  return (
    <span className={`inline-block bg-gray-200 rounded ${width} ${height} animate-pulse`} />
  );
}

const DataRow = ({ 
  dataset, 
  handleDownload, 
  handlePreview, 
  handleDelete 
}) => {
  // Status non completato - mostra skeleton loader
  if (dataset.status !== 'anonymized') {
    return (
      <tr className="hover:bg-gray-50 opacity-80">
        {/* Nome dataset sempre visibile */}
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="font-medium text-gray-900">{dataset.name}</div>
        </td>
        
        {/* Algoritmo - skeleton o vuoto se non disponibile */}
        <td className="px-6 py-4 whitespace-nowrap">
          {dataset.algorithm && dataset.algorithm !== 'Unknown' ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {dataset.algorithm}
            </span>
          ) : (
            <Skeleton width="w-16" />
          )}
        </td>
        
        {/* Righe - skeleton o valore se disponibile */}
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {dataset.rows ? dataset.rows.toLocaleString() : <Skeleton width="w-12" />}
        </td>
        
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            {dataset.created && dataset.created !== 'N/A' ? dataset.created : <Skeleton width="w-24" />}
        </td>

        {/* Status - sempre mostrato */}
        <td className="px-6 py-4 whitespace-nowrap">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                <Clock className="w-3 h-3 mr-1" />
                {dataset.status === 'analyzed' ? 'Waiting for input' : 'Processing'}
            </span>
        </td>

        {/* Azioni - skeleton per indicare che non sono ancora disponibili */}
        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
          <div className="flex items-center gap-4">
            {dataset.status === 'analyzed' ? (
                  <button 
                    className="text-green-600 hover:text-green-900"
                    onClick={() => handlePreview(dataset.id)}
                    title="Set Parameters"
                    >
                    {/* You can use any icon, here reusing CheckCircle for demo */}
                    <FormInputIcon className="w-4 h-4" />
                    </button>
              ) : null}
            <button 
              className="text-red-600 hover:text-red-900"
              onClick={() => handleDelete(dataset.id, dataset.name)}
              title="Delete Dataset"
            >
              <Trash className="w-4 h-4" />
            </button>
          </div>
        </td>
      </tr>
    );
  }

  // Status completato - mostra tutti i dati
  return (
    <tr className="hover:bg-gray-50">
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
          Anonymized
        </span>
      </td>
      
      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
        <div className="flex items-center gap-4">
          <button 
            className="text-blue-600 hover:text-blue-900"
            onClick={() => handleDownload(dataset.id, dataset.name)}
            title="Download Dataset"
          >
            <Download className="w-4 h-4" />
          </button>
          <button 
            className="text-purple-600 hover:text-purple-900"
            onClick={() => handlePreview(dataset.id)}
            title="Preview Dataset"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button 
            className="text-red-600 hover:text-red-900"
            onClick={() => handleDelete(dataset.id, dataset.name)}
            title="Delete Dataset"
          >
            <Trash className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
};

export default DataRow;