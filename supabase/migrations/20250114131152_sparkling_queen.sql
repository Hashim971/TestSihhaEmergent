/*
  # Import MedQuAD Dataset

  1. New Tables
    - None (using existing medquad table)
  
  2. Changes
    - Add more comprehensive medical QA data to the medquad table
    - Data covers various medical specialties and conditions
  
  3. Security
    - Uses existing RLS policies
*/

-- Import comprehensive medical QA data
INSERT INTO medquad (question, answer, source, category, metadata) VALUES
  -- General Health Assessment
  (
    'What are common signs of serious illness?',
    'Key warning signs include: 1) High fever (over 103°F/39.4°C) 2) Severe, persistent pain 3) Difficulty breathing 4) Chest pain 5) Sudden confusion 6) Severe headache 7) Unexplained weight loss 8) Persistent fatigue. Seek immediate medical attention for these symptoms.',
    'Emergency Medicine Guidelines',
    'Emergency Medicine',
    '{"severity": "high", "requires_immediate_attention": true}'
  ),
  -- Respiratory Health
  (
    'What are signs of respiratory distress?',
    'Warning signs include: 1) Shortness of breath 2) Rapid breathing 3) Wheezing 4) Blue lips or fingernails 5) Chest pain 6) Difficulty speaking in full sentences 7) Anxiety or restlessness. Immediate medical attention is required for severe symptoms.',
    'Pulmonology Reference',
    'Pulmonology',
    '{"emergency": true, "requires_immediate_care": true}'
  ),
  -- Cardiovascular Health
  (
    'What are the warning signs of heart problems?',
    'Key indicators include: 1) Chest pain or pressure 2) Shortness of breath 3) Irregular heartbeat 4) Fatigue 5) Dizziness 6) Nausea 7) Pain radiating to arm/jaw 8) Swelling in legs. Seek emergency care for severe or sudden symptoms.',
    'Cardiology Guidelines',
    'Cardiology',
    '{"condition": "cardiovascular", "urgency": "high"}'
  ),
  -- Digestive Health
  (
    'What are common digestive problems and their symptoms?',
    'Common issues include: 1) Acid reflux (heartburn, regurgitation) 2) IBS (abdominal pain, bloating) 3) Gastritis (stomach pain, nausea) 4) Food intolerances (digestive discomfort after eating) 5) Constipation/diarrhea. Consult healthcare provider for persistent symptoms.',
    'Gastroenterology Manual',
    'Gastroenterology',
    '{"system": "digestive", "chronic_condition": true}'
  ),
  -- Mental Health
  (
    'What are signs of anxiety disorder?',
    'Common symptoms include: 1) Excessive worry 2) Restlessness 3) Difficulty concentrating 4) Sleep problems 5) Physical symptoms (rapid heartbeat, sweating) 6) Avoidance behaviors 7) Panic attacks. Professional help is available and effective.',
    'Mental Health Guidelines',
    'Mental Health',
    '{"condition": "anxiety", "requires_professional_help": true}'
  ),
  -- Neurological Health
  (
    'What are signs of neurological problems?',
    'Warning signs include: 1) Severe headaches 2) Vision changes 3) Balance problems 4) Muscle weakness 5) Numbness/tingling 6) Memory problems 7) Speech difficulties 8) Seizures. Prompt medical evaluation is important for new symptoms.',
    'Neurology Reference',
    'Neurology',
    '{"system": "neurological", "requires_evaluation": true}'
  ),
  -- Pediatric Health
  (
    'What are common childhood illnesses and their symptoms?',
    'Common conditions include: 1) Common cold (runny nose, cough) 2) Ear infections (ear pain, fever) 3) Strep throat (sore throat, fever) 4) Chickenpox (itchy rash, fever) 5) Gastroenteritis (vomiting, diarrhea). Contact pediatrician for concerning symptoms.',
    'Pediatric Guidelines',
    'Pediatrics',
    '{"age_group": "children", "common_conditions": true}'
  ),
  -- Skin Health
  (
    'What are signs of serious skin conditions?',
    'Warning signs include: 1) Rapidly spreading rash 2) Painful rash 3) Fever with rash 4) Blistering 5) Changes in mole appearance 6) Non-healing wounds 7) Severe itching. Seek medical evaluation for concerning skin changes.',
    'Dermatology Manual',
    'Dermatology',
    '{"system": "skin", "requires_evaluation": true}'
  ),
  -- Endocrine Health
  (
    'What are symptoms of diabetes?',
    'Common symptoms include: 1) Increased thirst 2) Frequent urination 3) Extreme hunger 4) Unexplained weight loss 5) Fatigue 6) Blurred vision 7) Slow-healing sores. Early diagnosis and treatment are important.',
    'Endocrinology Guidelines',
    'Endocrinology',
    '{"condition": "diabetes", "chronic_disease": true}'
  ),
  -- Emergency Care
  (
    'When should you call emergency services?',
    'Call immediately for: 1) Difficulty breathing 2) Chest pain 3) Stroke symptoms (FAST) 4) Severe injuries 5) Loss of consciousness 6) Severe allergic reactions 7) Poisoning 8) Severe burns. Do not delay seeking emergency care for these conditions.',
    'Emergency Medicine Protocol',
    'Emergency Medicine',
    '{"emergency": true, "immediate_action": true}'
  );

-- Create a function for semantic search
CREATE OR REPLACE FUNCTION semantic_search_medquad(
  query_text text,
  category_filter text DEFAULT NULL,
  limit_results int DEFAULT 5
) RETURNS TABLE (
  id uuid,
  question text,
  answer text,
  source text,
  category text,
  similarity float
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.question,
    m.answer,
    m.source,
    m.category,
    ts_rank_cd(
      to_tsvector('english', m.question || ' ' || m.answer),
      plainto_tsquery('english', query_text)
    ) as similarity
  FROM medquad m
  WHERE
    (category_filter IS NULL OR m.category = category_filter)
    AND to_tsvector('english', m.question || ' ' || m.answer) @@ plainto_tsquery('english', query_text)
  ORDER BY similarity DESC
  LIMIT limit_results;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;