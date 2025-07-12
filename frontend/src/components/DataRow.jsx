import React, { useState } from 'react';
import { Download, Eye, Clock, Trash, FormInputIcon, CheckCircle, AlertCircle } from 'lucide-react';
import LoadingSpinner from './LoadingSpinner';

// Skeleton loader for loading state
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
  const [previewLoading, setPreviewLoading] = useState(false);

  // If status is not completed, show skeleton loader
  if (dataset.status !== 'anonymized') {
    return (
      <tr className="hover:bg-gray-50 opacity-80">
        {/* Dataset name always visible */}
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="font-medium text-gray-900">{dataset.name}</div>
        </td>
        
        {/* Algorithm - skeleton or empty if not available */}
        <td className="px-6 py-4 whitespace-nowrap">
          {dataset.algorithm && dataset.algorithm !== 'Unknown' ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {dataset.algorithm}
            </span>
          ) : (
            <Skeleton width="w-16" />
          )}
        </td>
        
        {/* Rows - skeleton or value if available */}
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {dataset.rows ? dataset.rows.toLocaleString() : <Skeleton width="w-12" />}
        </td>
        
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            {dataset.created && dataset.created !== 'N/A' ? dataset.created : <Skeleton width="w-24" />}
        </td>

        {/* Status - only shown if not error */}
        {dataset.status !== 'error' ? (
          <td className="px-6 py-4 whitespace-nowrap">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              <Clock className="w-3 h-3 mr-1" />
              {dataset.status === 'analyzed' ? 'Waiting for input' : 'Processing'}
            </span>
          </td>
        ) : (
          <td className="px-6 py-4 whitespace-nowrap">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
              <AlertCircle className="w-3 h-3 mr-1" />
              Error
            </span>
          </td>
        )}

        {/* Actions - skeleton to indicate not yet available */}
        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
          <div className="flex items-center gap-4">
            {dataset.status === 'analyzed' ? (
                <button 
                    className="text-green-600 hover:text-green-900"
                    disabled={previewLoading}
                    onClick={async () => {
                    setPreviewLoading(true);
                    handlePreview(dataset.id);
                    }}
                    title="Set Parameters"
                >
                    {previewLoading ? (
                    <LoadingSpinner size={16}/>
                    ) : (
                    <FormInputIcon className="w-4 h-4" />
                    )}
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

  // If status is completed, show all data
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
            className={`text-purple-600 hover:text-purple-900 relative`}
            disabled={previewLoading}
            onClick={async () => {
              setPreviewLoading(true);
              handlePreview(dataset.id);
            }}
            title="Preview Dataset"
          >
            {previewLoading ? (
              <LoadingSpinner size={16}/>
            ) : (
              <Eye className="w-4 h-4" />
            )}
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