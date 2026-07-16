import React, { useState } from 'react';
import { 
  Activity, 
  MessageSquare, 
  Watch, 
  Building2, 
  Pill, 
  History, 
  FileText, 
  Settings, 
  LogOut,
  MapPin,
  PlusCircle,
  Brain,
  Menu,
  X
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { signOut } from '../lib/auth';
import HealthMonitoring from './HealthMonitoring';
import HealthChatbot from './HealthChatbot';
import ChatHistory from './ChatHistory';

type Section = 'monitoring' | 'chat' | 'devices' | 'healthcare' | 'pharmacy' | 'history' | 'reports' | 'settings';
type LocationType = 'healthcare' | 'pharmacy' | null;

const UserDashboard: React.FC = () => {
  const [activeSection, setActiveSection] = useState<Section>('monitoring');
  const [showLocationPrompt, setShowLocationPrompt] = useState(false);
  const [locationType, setLocationType] = useState<LocationType>(null);
  const [location, setLocation] = useState<GeolocationPosition | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate('/');
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const handleSectionClick = (section: Section) => {
    if (section === 'healthcare' || section === 'pharmacy') {
      setLocationType(section);
      setShowLocationPrompt(true);
    }
    setActiveSection(section);
    setIsSidebarOpen(false);
  };

  const navigationItems = [
    { id: 'monitoring', icon: Activity, label: 'Monitoring' },
    { id: 'chat', icon: MessageSquare, label: 'Health Chat' },
    { id: 'devices', icon: Watch, label: 'Connected Devices' },
    { id: 'healthcare', icon: Building2, label: 'Healthcare Centers' },
    { id: 'pharmacy', icon: Pill, label: 'Pharmacies' },
    { id: 'history', icon: History, label: 'Chat History' },
    { id: 'reports', icon: FileText, label: 'Reports' },
    { id: 'settings', icon: Settings, label: 'Settings' }
  ];

  const handleLocationPermission = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation(position);
          setShowLocationPrompt(false);
        },
        (error) => {
          console.error('Error getting location:', error);
          setShowLocationPrompt(false);
        }
      );
    }
  };

  const renderContent = () => {
    switch (activeSection) {
      case 'monitoring':
        return <HealthMonitoring />;
      case 'chat':
        return <HealthChatbot />;
      case 'history':
        return <ChatHistory />;
      case 'devices':
        return (
          <div className="p-6">
            <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <Watch className="h-12 w-12 text-gray-400 mb-4" />
              <p className="text-gray-600 mb-4 text-center">No devices connected yet</p>
              <button className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <PlusCircle className="h-5 w-5 mr-2" />
                Connect Device
              </button>
            </div>
          </div>
        );
      case 'healthcare':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Healthcare Centers</h2>
            {location ? (
              <p>Showing healthcare centers near your location...</p>
            ) : (
              <p>Please enable location access to view nearby healthcare centers.</p>
            )}
          </div>
        );
      case 'pharmacy':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Pharmacies</h2>
            {location ? (
              <p>Showing pharmacies near your location...</p>
            ) : (
              <p>Please enable location access to view nearby pharmacies.</p>
            )}
          </div>
        );
      case 'reports':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Health Reports</h2>
            <p>Your health reports will appear here.</p>
          </div>
        );
      case 'settings':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Settings</h2>
            <p>Account and application settings will appear here.</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Main Header */}
      <header className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="h-16 flex items-center justify-between px-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 -ml-2 text-gray-600 hover:text-gray-900 lg:hidden focus:outline-none"
            >
              {isSidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
            <Link to="/" className="flex items-center space-x-2">
              <Brain className="h-8 w-8 text-blue-600" />
              <span className="text-xl font-bold text-gray-800">Sihha AI</span>
            </Link>
          </div>
          {user && (
            <div className="flex items-center space-x-4">
              <span className="text-gray-600">{user.email}</span>
            </div>
          )}
        </div>
      </header>

      <div className="flex h-screen pt-16">
        {/* Mobile Sidebar Overlay */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-30 lg:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`${
            isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
          } lg:translate-x-0 fixed lg:sticky top-16 left-0 w-64 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 overflow-y-auto transition-transform duration-200 ease-in-out z-40`}
        >
          <nav className="py-4">
            {navigationItems.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                onClick={() => handleSectionClick(id as Section)}
                className={`flex items-center w-full px-6 py-3 text-left ${
                  activeSection === id 
                    ? 'bg-blue-50 text-blue-600' 
                    : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
                }`}
              >
                <Icon className="h-5 w-5 mr-3" />
                {label}
              </button>
            ))}
          </nav>

          <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 bg-white">
            <button 
              onClick={handleSignOut}
              className="flex items-center w-full px-6 py-3 text-left text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg"
            >
              <LogOut className="h-5 w-5 mr-3" />
              Logout
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 lg:ml-64">
          <div className="min-h-[calc(100vh-4rem)]">
            {renderContent()}
          </div>
        </main>
      </div>

      {/* Location Permission Modal */}
      {showLocationPrompt && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-start mb-4">
              <MapPin className="h-6 w-6 text-blue-600 mr-3 flex-shrink-0" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Location Access Required</h3>
                <p className="mt-2 text-gray-600">
                  To show you nearby {locationType === 'healthcare' ? 'healthcare centers' : 'pharmacies'}, 
                  we need access to your location. Would you like to allow location access?
                </p>
              </div>
            </div>
            <div className="flex justify-end space-x-4 mt-6">
              <button
                onClick={() => setShowLocationPrompt(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleLocationPermission}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Allow Location Access
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserDashboard;