import React from 'react';
import { Lock, User, AlertCircle } from 'lucide-react';

const AuthView = ({ handleLogin, authError, firebaseLoaded }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 w-full max-w-md border border-white/20">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-32 h-32 rounded-full mb-8">
            <img src="/logo_dark.png" alt="AnonimaData Logo" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">AnonimaData</h1>
          <p className="text-gray-300">Secure Dataset Anonymization Platform</p>
        </div>

        {authError && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <p className="text-red-300 text-sm">{authError}</p>
            </div>
          </div>
        )}

        <button
          onClick={handleLogin}
          disabled={!firebaseLoaded}
          className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-500 disabled:to-gray-600 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-xl transition-all duration-300 transform hover:scale-105 hover:shadow-lg flex items-center justify-center gap-3"
        >
          <User className="w-5 h-5" />
          {firebaseLoaded ? 'Sign in with Google' : 'Loading...'}
        </button>

        <div className="mt-6 text-center">
        </div>
      </div>
    </div>
  );
};

export default AuthView;