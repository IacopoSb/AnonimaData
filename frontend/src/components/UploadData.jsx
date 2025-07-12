// UploadData.jsx
import React from 'react';
import { Upload, CheckCircle } from 'lucide-react';

const UploadData = ({ handleFileUpload, uploadedFile }) => {
  return (
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
  );
};

export default UploadData;