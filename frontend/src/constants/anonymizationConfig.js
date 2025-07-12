// src/constants/anonymizationConfig.js
export const anonymizationAlgorithms = [
  {
    id: 'k-anonymity',
    name: 'K-Anonymity',
    description: 'Groups records so each group has at least k identical records',
    params: [{ name: 'k', type: 'number', min: 2, max: 100, default: 5, description: 'Minimum group size' }]
  },
  {
    id: 'l-diversity',
    name: 'L-Diversity',
    description: 'Ensures each group has at least l different sensitive values',
    params: [
      { name: 'l', type: 'number', min: 2, max: 50, default: 3, description: 'Minimum diversity' },
      { name: 'sensitive_column', type: 'select', description: 'Sensitive attribute column' }
    ]
  },
  {
    id: 'differential-privacy',
    name: 'Differential-Privacy',
    description: 'Adds calibrated noise to protect individual privacy',
    params: [{ name: 'epsilon', type: 'number', min: 0.1, max: 10, step: 0.1, default: 1.0, description: 'Privacy budget (lower = more private)' }]
  }
];