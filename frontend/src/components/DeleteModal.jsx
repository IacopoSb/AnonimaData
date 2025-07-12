import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';

const DeleteModal = ({ show, onClose, filename, jobId, onDelete }) => {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl p-8 w-full max-w-md text-black transform transition-all duration-300 scale-100 animate-in fade-in zoom-in">
        {/* Animated Warning Icon */}
        <div className="flex justify-center mb-6">
          <div className="relative">
            <AlertTriangle className="w-16 h-16 text-red-500" />
            
          </div>
        </div>

        <h2 className="text-2xl font-bold mb-4 text-center text-gray-800">
          Delete Dataset
        </h2>
        
        <p className="mb-6 text-center text-gray-600 leading-relaxed">
          Are you sure you want to delete <br />
          <span className="font-bold text-gray-800 bg-gray-100 px-2 py-1 rounded text-sm">
            {filename}
          </span>
          <br />
          from the system?
          <br />
          <span className="text-red-600 font-semibold">This action cannot be undone.</span>
        </p>

        <div className="flex items-center justify-center gap-2 text-sm text-gray-400 mb-8 bg-gray-50 p-3 rounded-lg">
          <Info className="w-4 h-4" />
          <span>Job ID: {jobId}</span>
        </div>

        <div className="flex justify-center gap-4">
          <button
            className="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors duration-200 font-medium min-w-[100px]"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg hover:from-red-700 hover:to-red-800 transition-all duration-200 font-medium shadow-lg hover:shadow-xl transform hover:scale-105 min-w-[100px]"
            onClick={() => {
              if (onDelete) {
                onDelete(jobId, filename);
              }
              onClose();
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteModal;