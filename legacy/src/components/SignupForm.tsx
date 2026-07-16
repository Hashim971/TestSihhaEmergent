import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertCircle } from 'lucide-react';
import { signUp } from '../lib/auth';

interface FormData {
  email: string;
  password: string;
  generalInfo: {
    height: string;
    heightUnit: 'cm' | 'ft';
    weight: string;
    weightUnit: 'kg' | 'lbs';
    dateOfBirth: string;
    calendar: 'Gregorian' | 'Hijri';
  };
  demographics: {
    ethnicity: string;
    gender: string;
  };
  healthHistory: {
    chronicConditions: boolean;
    familyHistory: boolean;
    allergies: boolean;
    surgicalHistory: boolean;
  };
  medications: {
    current: {
      taking: boolean;
      list: string[];
    };
    past: {
      taking: boolean;
      list: string[];
    };
  };
  lifestyle: {
    smoking: {
      status: boolean;
      type?: '1-10 cigarettes' | 'About 1 pack' | 'More than 1 pack' | 'Electronic cigarettes/vaping';
    };
    diet: {
      status: boolean;
      type?: 'None-specific' | 'Balanced meals' | 'Frequent Fast Food';
    };
    physicalActivity: {
      status: boolean;
      level?: 'No physical activity' | 'Low activity (1-2 days per week)' | 'Moderate activity (3-5 days per week)' | 'High activity (5-7 days per week)' | 'Very high activity (intense daily exercise)';
    };
    sleepPattern: {
      status: boolean;
      pattern?: 'Very irregular sleep pattern' | 'Irregular sleep pattern' | 'Somewhat regular sleep pattern' | 'Regular sleep pattern';
    };
    stressLevel: {
      status: boolean;
      level?: 'No stress' | 'Low stress (occasional minor stressors)' | 'Moderate stress (regular but manageable stress)' | 'High stress (frequent and significant stress)';
    };
  };
}

const SignupForm: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
    generalInfo: {
      height: '',
      heightUnit: 'cm',
      weight: '',
      weightUnit: 'kg',
      dateOfBirth: '',
      calendar: 'Gregorian'
    },
    demographics: {
      ethnicity: '',
      gender: ''
    },
    healthHistory: {
      chronicConditions: false,
      familyHistory: false,
      allergies: false,
      surgicalHistory: false
    },
    medications: {
      current: {
        taking: false,
        list: []
      },
      past: {
        taking: false,
        list: []
      }
    },
    lifestyle: {
      smoking: {
        status: false
      },
      diet: {
        status: false
      },
      physicalActivity: {
        status: false
      },
      sleepPattern: {
        status: false
      },
      stressLevel: {
        status: false
      }
    }
  });

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);

    try {
      await signUp(formData.email, formData.password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to create account');
      setCurrentStep(1); // Go back to first step on error
    } finally {
      setLoading(false);
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Create Your Account</h2>
            <p className="text-gray-600">Enter your email and create a secure password to get started</p>
            
            {error && (
              <div className="p-4 bg-red-50 rounded-lg flex items-start">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" />
                <p className="text-red-700 text-sm">{error}</p>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  placeholder="your@email.com"
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                  Password
                </label>
                <input
                  type="password"
                  id="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">General Information</h2>
            <p className="text-gray-600">
              By providing general information about you we'll make sure your experience will be completely tailored to your needs.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="height" className="block text-sm font-medium text-gray-700">
                  Height
                </label>
                <div className="mt-1 flex rounded-md">
                  <input
                    type="number"
                    id="height"
                    value={formData.generalInfo.height}
                    onChange={(e) => setFormData({
                      ...formData,
                      generalInfo: { ...formData.generalInfo, height: e.target.value }
                    })}
                    className="block w-full rounded-l-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  />
                  <select
                    value={formData.generalInfo.heightUnit}
                    onChange={(e) => setFormData({
                      ...formData,
                      generalInfo: { ...formData.generalInfo, heightUnit: e.target.value as 'cm' | 'ft' }
                    })}
                    className="rounded-r-md border border-l-0 border-gray-300 bg-gray-50 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  >
                    <option value="cm">cm</option>
                    <option value="ft">ft</option>
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="weight" className="block text-sm font-medium text-gray-700">
                  Weight
                </label>
                <div className="mt-1 flex rounded-md">
                  <input
                    type="number"
                    id="weight"
                    value={formData.generalInfo.weight}
                    onChange={(e) => setFormData({
                      ...formData,
                      generalInfo: { ...formData.generalInfo, weight: e.target.value }
                    })}
                    className="block w-full rounded-l-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  />
                  <select
                    value={formData.generalInfo.weightUnit}
                    onChange={(e) => setFormData({
                      ...formData,
                      generalInfo: { ...formData.generalInfo, weightUnit: e.target.value as 'kg' | 'lbs' }
                    })}
                    className="rounded-r-md border border-l-0 border-gray-300 bg-gray-50 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  >
                    <option value="kg">kg</option>
                    <option value="lbs">lbs</option>
                  </select>
                </div>
              </div>
            </div>
            <div>
              <label htmlFor="dateOfBirth" className="block text-sm font-medium text-gray-700">
                Date of Birth
              </label>
              <div className="mt-1 flex space-x-4">
                <div className="flex-1">
                  <input
                    type="date"
                    id="dateOfBirth"
                    value={formData.generalInfo.dateOfBirth}
                    onChange={(e) => setFormData({
                      ...formData,
                      generalInfo: { ...formData.generalInfo, dateOfBirth: e.target.value }
                    })}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  />
                </div>
                <div className="flex space-x-4">
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      checked={formData.generalInfo.calendar === 'Gregorian'}
                      onChange={() => setFormData({
                        ...formData,
                        generalInfo: { ...formData.generalInfo, calendar: 'Gregorian' }
                      })}
                      className="form-radio text-blue-600"
                    />
                    <span className="ml-2">Gregorian</span>
                  </label>
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      checked={formData.generalInfo.calendar === 'Hijri'}
                      onChange={() => setFormData({
                        ...formData,
                        generalInfo: { ...formData.generalInfo, calendar: 'Hijri' }
                      })}
                      className="form-radio text-blue-600"
                    />
                    <span className="ml-2">Hijri</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Health History</h2>
            <div className="space-y-8">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Chronic and Past Health Conditions</h3>
                <p className="text-gray-600 mb-4">Include any chronic conditions or medical issues experienced. Essential for understanding health history and personalized care.</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, chronicConditions: true }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.healthHistory.chronicConditions
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, chronicConditions: false }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.healthHistory.chronicConditions
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Family Health History</h3>
                <p className="text-gray-600 mb-4">The family's health history can indicate genetic risks. Knowing this helps us predict and prevent potential health issues.</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, familyHistory: true }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.healthHistory.familyHistory
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, familyHistory: false }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.healthHistory.familyHistory
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Allergies</h3>
                <p className="text-gray-600 mb-4">Do you suffer from allergies to foods, medications, or other things?</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, allergies: true }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.healthHistory.allergies
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, allergies: false }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.healthHistory.allergies
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Surgical History</h3>
                <p className="text-gray-600 mb-4">Include any surgical procedures done.</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, surgicalHistory: true }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.healthHistory.surgicalHistory
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      healthHistory: { ...formData.healthHistory, surgicalHistory: false }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.healthHistory.surgicalHistory
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Medications</h2>
            <div className="space-y-8">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Current Medications</h3>
                <p className="text-gray-600 mb-4">Medications that are taken on daily bases.</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      medications: {
                        ...formData.medications,
                        current: { ...formData.medications.current, taking: true }
                      }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.medications.current.taking
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      medications: {
                        ...formData.medications,
                        current: { ...formData.medications.current, taking: false }
                      }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.medications.current.taking
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
                {formData.medications.current.taking && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">Please Specify:</label>
                    <input
                      type="text"
                      placeholder="Enter medications"
                      className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                      onChange={(e) => setFormData({
                        ...formData,
                        medications: {
                          ...formData.medications,
                          current: { ...formData.medications.current, list: [e.target.value] }
                        }
                      })}
                    />
                  </div>
                )}
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Medications Taken in the Last 6 Months</h3>
                <p className="text-gray-600 mb-4">Such as antibiotics, pain relievers, antihistamines, or other medications.</p>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      medications: {
                        ...formData.medications,
                        past: { ...formData.medications.past, taking: true }
                      }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      formData.medications.past.taking
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setFormData({
                      ...formData,
                      medications: {
                        ...formData.medications,
                        past: { ...formData.medications.past, taking: false }
                      }
                    })}
                    className={`px-8 py-3 rounded-full ${
                      !formData.medications.past.taking
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    No
                  </button>
                </div>
                {formData.medications.past.taking && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">Please Specify:</label>
                    <input
                      type="text"
                      placeholder="Enter medications"
                      className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                      onChange={(e) => setFormData({
                        ...formData,
                        medications: {
                          ...formData.medications,
                          past: { ...formData.medications.past, list: [e.target.value] }
                        }
                      })}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Lifestyle Information</h2>
            <div className="space-y-8">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Do You Smoke?</h3>
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          smoking: { ...formData.lifestyle.smoking, status: true }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        formData.lifestyle.smoking.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          smoking: { status: false }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        !formData.lifestyle.smoking.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      No
                    </button>
                  </div>
                  {formData.lifestyle.smoking.status && (
                    <div className="flex flex-wrap gap-2">
                      {['1-10 cigarettes', 'About 1 pack', 'More than 1 pack', 'Electronic cigarettes/vaping'].map((option) => (
                        <button
                          key={option}
                          onClick={() => setFormData({
                            ...formData,
                            lifestyle: {
                              ...formData.lifestyle,
                              smoking: {
                                ...formData.lifestyle.smoking,
                                type: option as any
                              }
                            }
                          })}
                          className={`px-4 py-2 rounded-full border ${
                            formData.lifestyle.smoking.type === option
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'border-gray-300 text-gray-700 hover:border-blue-600'
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Dietary Habits</h3>
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          diet: { ...formData.lifestyle.diet, status: true }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        formData.lifestyle.diet.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          diet: { status: false }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        !formData.lifestyle.diet.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      No
                    </button>
                  </div>
                  {formData.lifestyle.diet.status && (
                    <div className="flex flex-wrap gap-2">
                      {['None-specific', 'Balanced meals', 'Frequent Fast Food'].map((option) => (
                        <button
                          key={option}
                          onClick={() => setFormData({
                            ...formData,
                            lifestyle: {
                              ...formData.lifestyle,
                              diet: {
                                ...formData.lifestyle.diet,
                                type: option as any
                              }
                            }
                          })}
                          className={`px-4 py-2 rounded-full border ${
                            formData.lifestyle.diet.type === option
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'border-gray-300 text-gray-700 hover:border-blue-600'
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Weekly Physical Activity Level</h3>
                <p className="text-gray-600 mb-4">Indicate the average level of physical activity performed each week.</p>
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          physicalActivity: { ...formData.lifestyle.physicalActivity, status: true }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        formData.lifestyle.physicalActivity.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          physicalActivity: { status: false }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        !formData.lifestyle.physicalActivity.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      No
                    </button>
                  </div>
                  {formData.lifestyle.physicalActivity.status && (
                    <div className="flex flex-wrap gap-2">
                      {[
                        'No physical activity',
                        'Low activity (1-2 days per week)',
                        'Moderate activity (3-5 days per week)',
                        'High activity (5-7 days per week)',
                        'Very high activity (intense daily exercise)'
                      ].map((option) => (
                        <button
                          key={option}
                          onClick={() => setFormData({
                            ...formData,
                            lifestyle: {
                              ...formData.lifestyle,
                              physicalActivity: {
                                ...formData.lifestyle.physicalActivity,
                                level: option as any
                              }
                            }
                          })}
                          className={`px-4 py-2 rounded-full border ${
                            formData.lifestyle.physicalActivity.level === option
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'border-gray-300 text-gray-700 hover:border-blue-600'
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Daily Sleep Pattern</h3>
                <p className="text-gray-600 mb-4">Indicate your typical sleep pattern each day.</p>
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          sleepPattern: { ...formData.lifestyle.sleepPattern, status: true }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        formData.lifestyle.sleepPattern.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          sleepPattern: { status: false }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        !formData.lifestyle.sleepPattern.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text- gray-700'
                      }`}
                    >
                      No
                    </button>
                  </div>
                  {formData.lifestyle.sleepPattern.status && (
                    <div className="flex flex-wrap gap-2">
                      {[
                        'Very irregular sleep pattern',
                        'Irregular sleep pattern',
                        'Somewhat regular sleep pattern',
                        'Regular sleep pattern'
                      ].map((option) => (
                        <button
                          key={option}
                          onClick={() => setFormData({
                            ...formData,
                            lifestyle: {
                              ...formData.lifestyle,
                              sleepPattern: {
                                ...formData.lifestyle.sleepPattern,
                                pattern: option as any
                              }
                            }
                          })}
                          className={`px-4 py-2 rounded-full border ${
                            formData.lifestyle.sleepPattern.pattern === option
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'border-gray-300 text-gray-700 hover:border-blue-600'
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Stress Level</h3>
                <p className="text-gray-600 mb-4">Indicate your average level of stress experienced.</p>
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          stressLevel: { ...formData.lifestyle.stressLevel, status: true }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        formData.lifestyle.stressLevel.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setFormData({
                        ...formData,
                        lifestyle: {
                          ...formData.lifestyle,
                          stressLevel: { status: false }
                        }
                      })}
                      className={`px-8 py-3 rounded-full ${
                        !formData.lifestyle.stressLevel.status
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      No
                    </button>
                  </div>
                  {formData.lifestyle.stressLevel.status && (
                    <div className="flex flex-wrap gap-2">
                      {[
                        'No stress',
                        'Low stress (occasional minor stressors)',
                        'Moderate stress (regular but manageable stress)',
                        'High stress (frequent and significant stress)'
                      ].map((option) => (
                        <button
                          key={option}
                          onClick={() => setFormData({
                            ...formData,
                            lifestyle: {
                              ...formData.lifestyle,
                              stressLevel: {
                                ...formData.lifestyle.stressLevel,
                                level: option as any
                              }
                            }
                          })}
                          className={`px-4 py-2 rounded-full border ${
                            formData.lifestyle.stressLevel.level === option
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'border-gray-300 text-gray-700 hover:border-blue-600'
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pt-20">
      <div className="container mx-auto px-4 py-8">
        <Link to="/" className="flex items-center text-gray-600 hover:text-gray-900 mb-8">
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back to Home
        </Link>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-4">
            {[1, 2, 3, 4, 5].map((step) => (
              <React.Fragment key={step}>
                {step > 1 && (
                  <div
                    className={`h-0.5 w-12 ${
                      step <= currentStep ? 'bg-blue-600' : 'bg-gray-300'
                    }`}
                  />
                )}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    step <= currentStep
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-300 text-gray-600'
                  }`}
                >
                  {step < currentStep ? '✓' : step}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Form Content */}
        <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-8">
          {renderStep()}

          {/* Navigation Buttons */}
          <div className="mt-8 flex justify-between">
            {currentStep > 1 && (
              <button
                onClick={() => setCurrentStep(currentStep - 1)}
                className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Back
              </button>
            )}
            <button
              onClick={() => {
                if (currentStep < 5) {
                  setCurrentStep(currentStep + 1);
                } else {
                  handleSubmit();
                }
              }}
              disabled={loading}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors ml-auto disabled:opacity-50"
            >
              {loading ? 'Creating Account...' : currentStep === 5 ? 'Complete' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignupForm;