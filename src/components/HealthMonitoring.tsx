import React from 'react';
import { Heart, Activity, Thermometer, Droplets, Scale, Clock } from 'lucide-react';

// Sample data
const vitalSigns = {
  heartRate: {
    current: 72,
    min: 65,
    max: 85,
    unit: 'bpm',
    trend: [65, 68, 72, 70, 72, 75, 72]
  },
  bloodPressure: {
    systolic: 120,
    diastolic: 80,
    unit: 'mmHg',
    trend: [[115, 75], [118, 77], [120, 80], [117, 79], [120, 80]]
  },
  temperature: {
    current: 36.6,
    unit: '°C',
    trend: [36.5, 36.6, 36.7, 36.6, 36.6]
  },
  oxygenLevel: {
    current: 98,
    unit: '%',
    trend: [97, 98, 98, 99, 98]
  },
  weight: {
    current: 70.5,
    unit: 'kg',
    trend: [70.2, 70.3, 70.5, 70.4, 70.5]
  }
};

const HealthMonitoring: React.FC = () => {
  return (
    <div className="p-4 md:p-6">
      <div className="mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Health Monitoring Dashboard</h1>
        <p className="text-sm md:text-base text-gray-600 mt-2">Real-time health metrics and vital signs monitoring</p>
      </div>

      {/* Last Updated Status */}
      <div className="flex items-center mb-6 text-xs md:text-sm text-gray-600">
        <Clock className="h-4 w-4 mr-2" />
        Last updated: {new Date().toLocaleTimeString()}
      </div>

      {/* Vital Signs Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6 mb-6">
        {/* Heart Rate Card */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Heart className="h-5 w-5 md:h-6 md:w-6 text-red-500 mr-2" />
              <h3 className="font-semibold text-gray-900 text-sm md:text-base">Heart Rate</h3>
            </div>
            <span className="text-xl md:text-2xl font-bold text-gray-900">
              {vitalSigns.heartRate.current}
              <span className="text-xs md:text-sm text-gray-500 ml-1">{vitalSigns.heartRate.unit}</span>
            </span>
          </div>
          <div className="h-16 md:h-20 flex items-end space-x-1 md:space-x-2">
            {vitalSigns.heartRate.trend.map((value, index) => (
              <div
                key={index}
                className="bg-red-100 rounded-t w-full"
                style={{
                  height: `${(value / vitalSigns.heartRate.max) * 100}%`,
                }}
              ></div>
            ))}
          </div>
          <div className="mt-3 md:mt-4 flex justify-between text-xs md:text-sm text-gray-600">
            <span>Min: {vitalSigns.heartRate.min}</span>
            <span>Max: {vitalSigns.heartRate.max}</span>
          </div>
        </div>

        {/* Blood Pressure Card */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Activity className="h-5 w-5 md:h-6 md:w-6 text-blue-500 mr-2" />
              <h3 className="font-semibold text-gray-900 text-sm md:text-base">Blood Pressure</h3>
            </div>
            <span className="text-xl md:text-2xl font-bold text-gray-900">
              {vitalSigns.bloodPressure.systolic}/{vitalSigns.bloodPressure.diastolic}
              <span className="text-xs md:text-sm text-gray-500 ml-1">{vitalSigns.bloodPressure.unit}</span>
            </span>
          </div>
          <div className="h-16 md:h-20 flex items-end space-x-1 md:space-x-2">
            {vitalSigns.bloodPressure.trend.map((value, index) => (
              <div key={index} className="w-full">
                <div
                  className="bg-blue-100 rounded-t"
                  style={{
                    height: `${(value[0] / 140) * 100}%`,
                  }}
                ></div>
              </div>
            ))}
          </div>
        </div>

        {/* Temperature Card */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Thermometer className="h-5 w-5 md:h-6 md:w-6 text-orange-500 mr-2" />
              <h3 className="font-semibold text-gray-900 text-sm md:text-base">Temperature</h3>
            </div>
            <span className="text-xl md:text-2xl font-bold text-gray-900">
              {vitalSigns.temperature.current}
              <span className="text-xs md:text-sm text-gray-500 ml-1">{vitalSigns.temperature.unit}</span>
            </span>
          </div>
          <div className="h-16 md:h-20 flex items-end space-x-1 md:space-x-2">
            {vitalSigns.temperature.trend.map((value, index) => (
              <div
                key={index}
                className="bg-orange-100 rounded-t w-full"
                style={{
                  height: `${((value - 35) / 3) * 100}%`,
                }}
              ></div>
            ))}
          </div>
        </div>

        {/* Oxygen Level Card */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Droplets className="h-5 w-5 md:h-6 md:w-6 text-indigo-500 mr-2" />
              <h3 className="font-semibold text-gray-900 text-sm md:text-base">Oxygen Level</h3>
            </div>
            <span className="text-xl md:text-2xl font-bold text-gray-900">
              {vitalSigns.oxygenLevel.current}
              <span className="text-xs md:text-sm text-gray-500 ml-1">{vitalSigns.oxygenLevel.unit}</span>
            </span>
          </div>
          <div className="h-16 md:h-20 flex items-end space-x-1 md:space-x-2">
            {vitalSigns.oxygenLevel.trend.map((value, index) => (
              <div
                key={index}
                className="bg-indigo-100 rounded-t w-full"
                style={{
                  height: `${value}%`,
                }}
              ></div>
            ))}
          </div>
        </div>

        {/* Weight Card */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Scale className="h-5 w-5 md:h-6 md:w-6 text-green-500 mr-2" />
              <h3 className="font-semibold text-gray-900 text-sm md:text-base">Weight</h3>
            </div>
            <span className="text-xl md:text-2xl font-bold text-gray-900">
              {vitalSigns.weight.current}
              <span className="text-xs md:text-sm text-gray-500 ml-1">{vitalSigns.weight.unit}</span>
            </span>
          </div>
          <div className="h-16 md:h-20 flex items-end space-x-1 md:space-x-2">
            {vitalSigns.weight.trend.map((value, index) => (
              <div
                key={index}
                className="bg-green-100 rounded-t w-full"
                style={{
                  height: `${(value / 100) * 100}%`,
                }}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* Health Status Summary */}
      <div className="bg-white rounded-xl shadow-sm p-4 md:p-6">
        <h3 className="text-lg md:text-xl font-semibold text-gray-900 mb-4">Health Status Summary</h3>
        <div className="space-y-3 md:space-y-4">
          <div className="flex items-center">
            <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
            <span className="text-sm md:text-base text-gray-700">All vital signs are within normal range</span>
          </div>
          <div className="flex items-center">
            <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
            <span className="text-sm md:text-base text-gray-700">Blood pressure has been stable for the last 24 hours</span>
          </div>
          <div className="flex items-center">
            <div className="w-2 h-2 bg-yellow-500 rounded-full mr-2"></div>
            <span className="text-sm md:text-base text-gray-700">Recommended to maintain current physical activity level</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HealthMonitoring;