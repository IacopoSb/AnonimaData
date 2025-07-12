import React from 'react';
import { Settings } from 'lucide-react';
import { anonymizationAlgorithms } from '../constants/anonymizationConfig'; // Import algorithms

const ConfigureAnonymization = ({
  dataPreview,
  columnConfig,
  handleColumnConfig,
  selectedAlgorithm,
  setSelectedAlgorithm,
  algorithmParams,
  handleParamChange,
  handleAnonymize,
}) => {
  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-bold text-gray-900">Configure Anonymization</h2>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Column Configuration</h3>
        <p className="text-sm text-gray-600 mb-6">Select the type for each column in your dataset</p>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-900">Column Name</th>
                <th className="text-center py-3 px-4 font-medium text-gray-900">Quasi-Identifier</th>
                <th className="text-center py-3 px-4 font-medium text-gray-900">Sensitive</th>
              </tr>
            </thead>
            <tbody>
              {dataPreview.columns.map((column) => (
                <tr key={column} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-4 px-4">
                    <div className="font-medium text-gray-900">{column}</div>
                  </td>
                  <td className="py-4 px-4 text-center">
                    <input
                      type="checkbox"
                      id={`quasi-${column}`}
                      checked={columnConfig[column]?.quasi || false}
                      onChange={(e) => handleColumnConfig(column, {
                        ...columnConfig[column],
                        quasi: e.target.checked
                      })}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                  </td>
                  <td className="py-4 px-4 text-center">
                    <input
                      type="checkbox"
                      id={`sensitive-${column}`}
                      checked={columnConfig[column]?.sensitive || false}
                      onChange={(e) => handleColumnConfig(column, {
                        ...columnConfig[column],
                        sensitive: e.target.checked
                      })}
                      className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-600 rounded"></div>
            <span className="text-gray-600">
              <strong>Quasi-Identifier:</strong> Columns that could be used to identify individuals (e.g., age, zip code)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-purple-600 rounded"></div>
            <span className="text-gray-600">
              <strong>Sensitive:</strong> Columns containing sensitive information (e.g., medical data, salary)
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Algorithm</h3>
            <div className="space-y-3">
              {anonymizationAlgorithms.map((algorithm) => (
                <label key={algorithm.id} className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="radio"
                    name="algorithm"
                    value={algorithm.id}
                    checked={selectedAlgorithm === algorithm.id}
                    onChange={(e) => setSelectedAlgorithm(e.target.value)}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-gray-900">{algorithm.name}</div>
                    <div className="text-sm text-gray-500">{algorithm.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {selectedAlgorithm && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Parameters</h3>
              {anonymizationAlgorithms.find(a => a.id === selectedAlgorithm)?.params.map((param) => (
                <div key={param.name} className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {param.description}
                  </label>
                  {param.type === 'number' ? (
                    <input
                      type="number"
                      min={param.min}
                      max={param.max}
                      step={param.step || 1}
                      value={algorithmParams[param.name] ||  ''}
                      onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  ) : param.type === 'select' ? (
                    <select
                      value={algorithmParams[param.name] || ''}
                      onChange={(e) => handleParamChange(param.name, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select column...</option>
                      {dataPreview.columns.map(col => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                  ) : null}
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleAnonymize}
            disabled={!selectedAlgorithm}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-400 text-white px-6 py-3 rounded-xl font-semibold transition-all duration-300 flex items-center justify-center gap-2"
          >
            <Settings className="w-5 h-5" />
            Start Anonymization
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfigureAnonymization;