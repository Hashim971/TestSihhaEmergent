import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Brain, Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import LandingPage from './components/LandingPage';
import HealthMonitoring from './components/HealthMonitoring';
import HealthChatbot from './components/HealthChatbot';
import SignupForm from './components/SignupForm';
import LoginModal from './components/LoginModal';
import UserDashboard from './components/UserDashboard';

function App() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-gradient-to-b from-white to-blue-50">
          {/* Navigation */}
          <nav className="bg-white/80 backdrop-blur-sm fixed w-full z-50 border-b border-gray-100">
            <div className="container mx-auto px-4">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center">
                  <button
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    className="p-2 rounded-md text-gray-600 hover:text-gray-900 focus:outline-none lg:hidden"
                  >
                    {isMobileMenuOpen ? (
                      <X className="h-6 w-6" />
                    ) : (
                      <Menu className="h-6 w-6" />
                    )}
                  </button>
                  <Link to="/" className="flex items-center space-x-2">
                    <Brain className="h-8 w-8 text-blue-600" />
                    <span className="text-2xl font-bold text-gray-800">Sihha AI</span>
                  </Link>
                </div>

                {/* Desktop Navigation */}
                <div className="hidden lg:flex items-center space-x-6">
                  <Link to="/monitoring" className="text-gray-600 hover:text-gray-900">
                    Monitoring
                  </Link>
                  <Link to="/health-chat" className="text-gray-600 hover:text-gray-900">
                    Health Chat
                  </Link>
                  <button
                    onClick={() => setIsLoginModalOpen(true)}
                    className="text-gray-600 hover:text-gray-900"
                  >
                    Login
                  </button>
                  <Link to="/signup" className="bg-blue-600 text-white px-6 py-2 rounded-full hover:bg-blue-700 transition-colors">
                    Get Started
                  </Link>
                </div>
              </div>

              {/* Mobile Navigation */}
              <div 
                className={`${
                  isMobileMenuOpen ? 'block' : 'hidden'
                } lg:hidden border-t border-gray-100 py-2 absolute left-0 right-0 bg-white`}
              >
                <div className="flex flex-col space-y-2 px-4 pb-3">
                  <Link 
                    to="/monitoring" 
                    className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Monitoring
                  </Link>
                  <Link 
                    to="/health-chat" 
                    className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Health Chat
                  </Link>
                  <button
                    onClick={() => {
                      setIsLoginModalOpen(true);
                      setIsMobileMenuOpen(false);
                    }}
                    className="text-left text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md"
                  >
                    Login
                  </button>
                  <Link 
                    to="/signup" 
                    className="bg-blue-600 text-white px-6 py-2 rounded-full hover:bg-blue-700 transition-colors inline-block text-center"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Get Started
                  </Link>
                </div>
              </div>
            </div>
          </nav>

          <LoginModal 
            isOpen={isLoginModalOpen}
            onClose={() => setIsLoginModalOpen(false)}
          />

          {/* Mobile Menu Overlay */}
          {isMobileMenuOpen && (
            <div
              className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
              onClick={() => setIsMobileMenuOpen(false)}
            />
          )}

          <div className="pt-16">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/monitoring" element={<HealthMonitoring />} />
              <Route path="/health-chat" element={<HealthChatbot />} />
              <Route path="/signup" element={<SignupForm />} />
              <Route path="/dashboard" element={<UserDashboard />} />
            </Routes>
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;