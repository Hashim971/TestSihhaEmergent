-- Add more comprehensive medical QA data
INSERT INTO medquad (question, answer, source) VALUES
  -- Abdominal Pain
  (
    'What are the common causes of right-sided abdominal pain?',
    'Common causes include: 1) Appendicitis (sharp pain in lower right abdomen) 2) Gallbladder issues (upper right pain, often after eating) 3) Kidney stones (severe pain that may radiate) 4) Liver conditions (upper right quadrant) 5) Muscle strain. Seek immediate care for severe or worsening pain.',
    'Emergency Medicine Guidelines'
  ),
  (
    'What symptoms suggest appendicitis?',
    'Key symptoms include: 1) Pain starting around navel, moving to lower right abdomen 2) Pain worsening with movement 3) Fever 4) Nausea/vomiting 5) Loss of appetite 6) Rebound tenderness. This is a medical emergency requiring immediate evaluation.',
    'Surgical Guidelines'
  ),
  (
    'When should abdominal pain be considered an emergency?',
    'Seek immediate medical attention if: 1) Pain is severe or sudden 2) Accompanied by fever over 102°F 3) Unable to keep food down 4) Blood in stool 5) Abdomen is tender to touch 6) Pain with breathing 7) Unable to sit still or find comfortable position.',
    'Emergency Medicine Protocol'
  ),
  -- Digestive Issues
  (
    'What are signs of gallbladder problems?',
    'Common signs include: 1) Pain in upper right abdomen 2) Pain after eating fatty foods 3) Nausea 4) Vomiting 5) Fever 6) Yellowing of skin/eyes 7) Clay-colored stools. Pain often occurs after meals and may radiate to back or shoulder.',
    'Gastroenterology Reference'
  ),
  -- Pain Assessment
  (
    'How to assess abdominal pain characteristics?',
    'Key factors to consider: 1) Location (quadrant/region) 2) Quality (sharp, dull, cramping) 3) Severity (1-10 scale) 4) Timing (sudden vs gradual) 5) Duration 6) Aggravating/relieving factors 7) Associated symptoms. Pattern of pain helps determine urgency and possible causes.',
    'Clinical Assessment Guidelines'
  ),
  -- Gastrointestinal Symptoms
  (
    'What do different types of abdominal pain indicate?',
    'Pain characteristics can suggest causes: 1) Sharp, localized pain - possible inflammation/infection 2) Cramping - possible intestinal/menstrual issues 3) Dull, persistent ache - possible chronic condition 4) Sudden, severe pain - possible medical emergency 5) Burning pain - possible acid-related issues.',
    'Medical Diagnosis Manual'
  ),
  -- Emergency Indicators
  (
    'What are red flags for abdominal pain?',
    'Warning signs include: 1) Severe pain that comes on suddenly 2) Fever with abdominal pain 3) Inability to pass stool or gas 4) Persistent vomiting 5) Swollen or tender abdomen 6) Pain lasting several days 7) Signs of dehydration. These symptoms require immediate medical attention.',
    'Emergency Care Protocol'
  ),
  -- Treatment Guidelines
  (
    'What are first steps for managing abdominal pain?',
    'Initial management includes: 1) Rest and avoid food temporarily 2) Stay hydrated with clear fluids 3) Avoid pain medications until evaluated 4) Note timing and triggers of pain 5) Monitor for worsening symptoms. Seek medical care if pain is severe or persistent.',
    'Primary Care Guidelines'
  ),
  -- Diagnostic Considerations
  (
    'How is the cause of abdominal pain diagnosed?',
    'Diagnosis typically involves: 1) Detailed medical history 2) Physical examination 3) Location and character of pain 4) Associated symptoms 5) Recent dietary changes 6) Physical activity history 7) Previous similar episodes. Additional tests may be needed based on findings.',
    'Diagnostic Protocols'
  ),
  -- Prevention
  (
    'How can abdominal pain be prevented?',
    'Prevention strategies include: 1) Regular meals and healthy diet 2) Adequate hydration 3) Regular exercise 4) Stress management 5) Avoiding trigger foods 6) Proper food handling/storage 7) Regular health check-ups. Some causes may not be preventable.',
    'Preventive Medicine Guidelines'
  );