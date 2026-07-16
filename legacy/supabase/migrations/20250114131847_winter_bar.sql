-- Create or replace search function
CREATE OR REPLACE FUNCTION search_medquad(
  search_query text,
  category_filter text DEFAULT NULL,
  limit_count int DEFAULT 5
) RETURNS TABLE (
  id uuid,
  question text,
  answer text,
  source text,
  category text,
  metadata jsonb,
  relevance float4
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.question,
    m.answer,
    m.source,
    m.category,
    m.metadata,
    ts_rank_cd(m.content, websearch_to_tsquery('english', search_query)) as relevance
  FROM medquad m
  WHERE
    (category_filter IS NULL OR m.category = category_filter)
    AND m.content @@ websearch_to_tsquery('english', search_query)
  ORDER BY relevance DESC
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Insert initial medical QA data
INSERT INTO medquad (question, answer, source, category, metadata) VALUES
    (
        'What are the common symptoms of COVID-19?',
        'Common COVID-19 symptoms include: 1) Fever or chills 2) Cough 3) Shortness of breath 4) Fatigue 5) Muscle/body aches 6) Headache 7) Loss of taste/smell 8) Sore throat 9) Congestion 10) Nausea/vomiting 11) Diarrhea. Seek immediate medical attention for severe symptoms.',
        'WHO Guidelines',
        'Infectious Disease',
        '{"severity": "high", "requires_monitoring": true}'
    ),
    (
        'When should I seek emergency medical care?',
        'Seek emergency care immediately for: 1) Difficulty breathing 2) Persistent chest pain/pressure 3) New confusion 4) Inability to wake/stay awake 5) Bluish lips/face 6) Severe allergic reactions 7) Signs of stroke/heart attack 8) Severe injuries 9) Poisoning.',
        'Emergency Medicine Protocol',
        'Emergency Medicine',
        '{"emergency": true, "immediate_action_required": true}'
    ),
    (
        'What are signs of dehydration?',
        'Common signs include: 1) Dark urine 2) Decreased urination 3) Thirst 4) Dry mouth/lips 5) Fatigue 6) Dizziness 7) Headache 8) Decreased skin elasticity. Severe cases may show: 9) Rapid heartbeat 10) Confusion 11) Sunken eyes. Seek medical care for severe symptoms.',
        'Medical Reference Guide',
        'General Medicine',
        '{"severity": "variable", "preventable": true}'
    ),
    (
        'What are the warning signs of a heart attack?',
        'Key warning signs include: 1) Chest pain/pressure 2) Pain radiating to arm/jaw/back 3) Shortness of breath 4) Nausea/vomiting 5) Cold sweat 6) Lightheadedness 7) Fatigue 8) Anxiety. Women may experience different symptoms. Call emergency services immediately if suspected.',
        'Cardiology Guidelines',
        'Cardiology',
        '{"emergency": true, "time_critical": true}'
    ),
    (
        'How can I manage anxiety symptoms?',
        'Management strategies include: 1) Deep breathing exercises 2) Regular physical activity 3) Adequate sleep 4) Healthy diet 5) Stress management 6) Mindfulness/meditation 7) Limiting caffeine/alcohol 8) Social support 9) Professional counseling when needed.',
        'Mental Health Guidelines',
        'Mental Health',
        '{"chronic_condition": true, "self_manageable": true}'
    );