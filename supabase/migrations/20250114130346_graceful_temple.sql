-- Import MedQuAD dataset
INSERT INTO medquad (question, answer, source, category, metadata) VALUES
  -- Headache-related entries
  (
    'What are the common causes of persistent headaches?',
    'Common causes include: 1) Tension headaches (stress, poor posture) 2) Migraines 3) Dehydration 4) Eye strain 5) Sinus problems 6) Sleep disorders 7) Medication overuse. Persistent headaches lasting several days should be evaluated by a healthcare provider.',
    'Neurology Guidelines',
    'Neurology',
    '{"severity": "moderate", "requires_evaluation": true}'
  ),
  (
    'What are the warning signs for severe headaches?',
    'Seek immediate medical attention if headache: 1) Is sudden and severe ("thunderclap") 2) Accompanied by fever, stiff neck 3) Causes confusion or personality changes 4) Follows head injury 5) Causes vision problems 6) Worsens with movement/position changes 7) Is accompanied by weakness/numbness.',
    'Emergency Medicine Protocol',
    'Emergency Medicine',
    '{"severity": "severe", "requires_immediate_care": true}'
  ),
  (
    'How can tension headaches be managed?',
    'Management strategies include: 1) Stress reduction techniques 2) Regular exercise 3) Proper posture 4) Adequate sleep 5) Staying hydrated 6) Over-the-counter pain relievers when needed 7) Regular breaks from screens 8) Identifying and avoiding triggers.',
    'Primary Care Guidelines',
    'General Medicine',
    '{"severity": "mild", "self_manageable": true}'
  ),
  (
    'What distinguishes migraines from other headaches?',
    'Migraine characteristics include: 1) Throbbing/pulsating pain 2) Often one-sided 3) Sensitivity to light/sound 4) Nausea/vomiting 5) Visual auras in some cases 6) Duration of 4-72 hours 7) May be triggered by specific factors 8) Family history common.',
    'Neurology Reference',
    'Neurology',
    '{"condition_type": "chronic", "requires_management": true}'
  ),
  (
    'When should headaches be evaluated by a doctor?',
    'Seek medical evaluation if: 1) Headaches are new or different 2) Frequency/severity increases 3) Interfere with daily activities 4) Wake you from sleep 5) Started after age 50 6) Not relieved by over-the-counter medication 7) Occur with other neurological symptoms.',
    'Clinical Assessment Guidelines',
    'General Medicine',
    '{"evaluation_priority": "moderate", "red_flags": true}'
  ),
  (
    'What lifestyle factors can trigger headaches?',
    'Common triggers include: 1) Stress and anxiety 2) Irregular sleep patterns 3) Skipped meals 4) Dehydration 5) Certain foods/drinks 6) Environmental factors (bright lights, loud noises) 7) Hormonal changes 8) Poor posture 9) Screen time.',
    'Preventive Medicine Guidelines',
    'General Medicine',
    '{"preventable": true, "lifestyle_related": true}'
  ),
  (
    'How can chronic headaches be prevented?',
    'Prevention strategies include: 1) Regular sleep schedule 2) Balanced diet 3) Stress management 4) Regular exercise 5) Proper hydration 6) Ergonomic workspace setup 7) Limiting caffeine/alcohol 8) Keeping a headache diary to identify triggers.',
    'Preventive Medicine Guidelines',
    'General Medicine',
    '{"prevention_focused": true, "lifestyle_modification": true}'
  ),
  (
    'What are signs of medication overuse headaches?',
    'Signs include: 1) Daily or near-daily headaches 2) Headaches worsen with pain medication 3) Headaches improve briefly with medication then return 4) Using pain medication more than 2-3 days per week 5) Headaches become more frequent over time.',
    'Neurology Guidelines',
    'Neurology',
    '{"medication_related": true, "requires_medical_attention": true}'
  ),
  (
    'How are severe headaches diagnosed?',
    'Diagnosis typically involves: 1) Detailed medical history 2) Physical examination 3) Neurological examination 4) Headache diary review 5) Imaging studies if needed 6) Blood tests when indicated 7) Assessment of associated symptoms.',
    'Diagnostic Protocols',
    'Neurology',
    '{"diagnostic_process": true, "medical_evaluation": true}'
  ),
  (
    'What are emergency signs with headaches?',
    'Seek emergency care for headache with: 1) Sudden, severe onset 2) Loss of consciousness 3) Seizures 4) High fever 5) Severe neck stiffness 6) Confusion/mental changes 7) Weakness/numbness 8) Recent head trauma.',
    'Emergency Medicine Protocol',
    'Emergency Medicine',
    '{"emergency": true, "immediate_care_required": true}'
  );