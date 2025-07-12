// Header.jsx
import React from 'react';
import { LogOut, Lock } from 'lucide-react';

const Header = ({ user, handleLogout, setCurrentView, currentView, loadStats  }) => {
  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center">
              <img src="/logo_dark.png" alt="AnonimaData Logo" className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">AnonimaData</h1>
          </div>

          <nav className="hidden md:flex space-x-8">
            <button
              onClick={() => {
                setCurrentView('dashboard');
                if (loadStats) {
                  loadStats();
                }
              }}
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${currentView === 'dashboard' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'}`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setCurrentView('upload')}
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${currentView === 'upload' ? 'text-blue-600 bg-blue-50' : 'text-gray-500 hover:text-gray-900'}`}
            >
              Upload Data
            </button>
          </nav>

          <div className="flex items-center gap-4">
            <img
              src={user.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=6366f1&color=fff`}
              alt={user.name}
              className="w-8 h-8 rounded-full"
              onError={(e) => {
                e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=6366f1&color=fff`;
              }}
            />
            <div className="hidden md:block">
              <span className="text-sm font-medium text-gray-700 block">{user.name}</span>
              <span className="text-xs text-gray-500">{user.email}</span>
            </div>
            <button
              onClick={handleLogout}
              className="text-gray-400 hover:text-gray-600 transition-colors p-2 rounded-lg hover:bg-gray-100"
              title="Sign out"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;