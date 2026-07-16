import OpenAI from 'openai';
import { createClient } from '@supabase/supabase-js';
import { jsPDF } from 'jspdf';

interface Assessment {
  mainSymptom?: string;
  location?: string;
  characteristics?: string;
  duration?: string;
  intensity?: number;
  associatedSymptoms?: string[];
  triggers?: string[];
  history?: string;
  medications?: string[];
  impact?: string;
}

export class HealthAI {
  private openai: OpenAI | null = null;
  private supabase;
  private conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }> = [];
  private currentAssessment: Assessment = {};
  private screeningStage: 'initial' | 'assessment' | 'followup' = 'initial';

  constructor() {
    const apiKey = import.meta.env.VITE_OPENAI_API_KEY;
    if (!apiKey) {
      console.error('OpenAI API key not configured');
    } else {
      this.openai = new OpenAI({
        apiKey,
        dangerouslyAllowBrowser: true
      });
    }

    this.supabase = createClient(
      import.meta.env.VITE_SUPABASE_URL,
      import.meta.env.VITE_SUPABASE_ANON_KEY
    );
  }

  private async searchMedQuAD(query: string) {
    try {
      const { data, error } = await this.supabase
        .from('medquad')
        .select('question, answer, source, focus_area')
        .textSearch('content', query, {
          type: 'plain',
          config: 'english'
        })
        .limit(3);

      if (error) throw error;
      return data || [];
    } catch (error) {
      console.error('Error searching MedQuAD:', error);
      return [];
    }
  }

  async startScreening() {
    if (!this.openai) {
      throw new Error('OpenAI API key not configured');
    }

    this.conversationHistory = [];
    this.currentAssessment = {};
    this.screeningStage = 'initial';
    
    return "Hello! I'm here to help assess your health concerns. Could you please tell me what brings you in today?";
  }

  async continueConversation(userInput: string) {
    if (!this.openai) {
      throw new Error('OpenAI API key not configured');
    }

    // Add user input to history
    this.conversationHistory.push({ role: "user", content: userInput });

    try {
      // Search MedQuAD for relevant information
      const medquadResults = await this.searchMedQuAD(userInput);
      const medicalContext = medquadResults.length > 0 
        ? "Medical context from database: " + medquadResults.map(r => `Question: ${r.question} Answer: ${r.answer} (Source: ${r.source}, Focus Area: ${r.focus_area})`).join(" ") 
        : "";

      let systemPrompt = "";
      
      if (this.screeningStage === 'initial') {
        systemPrompt = `This GPT is designed to provide accurate and detailed information regarding various medical conditions It should ask the patient to further explain what are they feeling exactly to give proper answers before jumping into conclusions basically it should do basic health screening or symptom checking as well as give proper diagnostics like a professional doctor would and assess the user's symptoms to give a proper health screening report to be used by the healthcare professional as they will be relying on it (all questions must be asked one by one give room for the patient to answer the questions one by one). The questions should be one by one giving the patient room to answer all questions properly (all questions must be asked one by one). with a focus on questions and answers sourced from the model knowledge database: use this: (${medicalContext}). It should always reference reputable sources and maintain a formal, professional tone. In situations where there is insufficient information to provide a detailed response, it should ask for clarification and suggest consulting a healthcare professional as well as suggesting what the user should do depending on their situation and also ask the user if they need the health screening medical report after the health screening is over. It should also utilize the dataset provided. Generate a report in pdf format after the symptom check is done but ask the user if they need it first.`;
        
        if (this.conversationHistory.length === 1) {
          this.screeningStage = 'assessment';
        }
      } else if (this.screeningStage === 'assessment') {
        systemPrompt = `This GPT is designed to provide accurate and detailed information regarding various medical conditions It should ask the patient to further explain what are they feeling exactly to give proper answers before jumping into conclusions basically it should do basic health screening or symptom checking as well as give proper diagnostics like a professional doctor would and assess the user's symptoms to give a proper health screening report to be used by the healthcare professional as they will be relying on it (all questions must be asked one by one give room for the patient to answer the questions one by one). The questions should be one by one giving the patient room to answer all questions properly (all questions must be asked one by one). with a focus on questions and answers sourced from the model knowledge database: use this: (${medicalContext}). It should always reference reputable sources and maintain a formal, professional tone. In situations where there is insufficient information to provide a detailed response, it should ask for clarification and suggest consulting a healthcare professional as well as suggesting what the user should do depending on their situation and also ask the user if they need the health screening medical report after the health screening is over. It should also utilize the dataset provided. Generate a report in pdf format after the symptom check is done but ask the user if they need it first.`;
      }

      const response = await this.openai.chat.completions.create({
        model: "gpt-4.1",
        messages: [
          {
            role: "system",
            content: `${systemPrompt}\n\n${medicalContext}`
          },
          ...this.conversationHistory
        ],
        temperature: 0.3,
        max_tokens: 150
      });

      const assistantMessage = response.choices[0].message.content || "";
      this.conversationHistory.push({ role: "assistant", content: assistantMessage });

      // Update assessment based on the conversation
      this.updateAssessment(userInput, assistantMessage);

      return assistantMessage;
    } catch (error) {
      console.error('Error continuing conversation:', error);
      throw error;
    }
  }

  private updateAssessment(userInput: string, assistantResponse: string) {
    // Extract information from the conversation to update the assessment
    if (this.screeningStage === 'initial') {
      if (!this.currentAssessment.mainSymptom) {
        this.currentAssessment.mainSymptom = userInput;
      }
    }

    // Look for severity indicators (1-10 scale)
    const severityMatch = userInput.match(/\b([0-9]|10)\b/);
    if (severityMatch) {
      this.currentAssessment.intensity = parseInt(severityMatch[0]);
    }

    // Look for duration information
    const durationKeywords = ['day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years'];
    for (const keyword of durationKeywords) {
      if (userInput.toLowerCase().includes(keyword)) {
        this.currentAssessment.duration = userInput;
        break;
      }
    }

    // Look for location information
    const bodyParts = ['head', 'chest', 'back', 'arm', 'leg', 'stomach', 'neck', 'shoulder', 'knee', 'foot'];
    for (const part of bodyParts) {
      if (userInput.toLowerCase().includes(part)) {
        this.currentAssessment.location = userInput;
        break;
      }
    }
  }

  async generateReport() {
    if (!this.openai) {
      throw new Error('OpenAI API key not configured');
    }

    try {
      const reportPrompt = `Generate a comprehensive medical screening report based on this conversation. Include:

      1. CHIEF COMPLAINT
         - Main symptoms
         - Onset and duration
         - Severity and characteristics

      2. HISTORY OF PRESENT ILLNESS
         - Progression of symptoms
         - Associated symptoms
         - Aggravating/relieving factors
         - Impact on daily activities

      3. ASSESSMENT SUMMARY
         - Key findings from the conversation
         - Areas requiring attention

      4. RECOMMENDATIONS
         - Suggested next steps
         - Lifestyle modifications if applicable
         - Warning signs to watch for

      5. IMPORTANT NOTES
         - This is not a diagnosis
         - Advise consulting a healthcare provider
         - Note any concerning symptoms that require immediate attention

      Base this report on the following conversation and assessment:
      Conversation: ${JSON.stringify(this.conversationHistory)}
      Assessment: ${JSON.stringify(this.currentAssessment)}`;

      const report = await this.openai.chat.completions.create({
        model: "gpt-4",
        messages: [
          { role: "system", content: reportPrompt }
        ],
        temperature: 0.7,
        max_tokens: 1000
      });

      const reportContent = report.choices[0].message.content || "";
      
      // Create PDF
      const doc = new jsPDF();
      
      // Add header
      doc.setFontSize(24);
      doc.setTextColor(41, 98, 255);
      doc.text("HEALTH SCREENING REPORT", 105, 20, { align: "center" });
      
      // Add timestamp
      doc.setFontSize(10);
      doc.setTextColor(100);
      doc.text(`Generated on: ${new Date().toLocaleString()}`, 20, 30);
      
      // Add disclaimer
      doc.setDrawColor(220, 53, 69);
      doc.setFillColor(248, 215, 218);
      doc.rect(20, 35, 170, 25, 'FD');
      doc.setTextColor(220, 53, 69);
      doc.setFontSize(12);
      doc.text("IMPORTANT MEDICAL DISCLAIMER", 105, 42, { align: "center" });
      doc.setFontSize(9);
      const disclaimer = [
        "This report is for informational purposes only and is NOT a medical diagnosis.",
        "It should be reviewed with a qualified healthcare provider.",
        "Seek immediate medical attention if symptoms worsen or concern you."
      ];
      doc.text(disclaimer, 105, 48, { align: "center", maxWidth: 160 });
      
      // Add report content
      doc.setTextColor(0);
      doc.setFontSize(11);
      
      // Split content into sections and add to PDF
      const sections = reportContent.split('\n\n');
      let yPosition = 70;
      
      sections.forEach(section => {
        if (section.includes(':')) {
          const [title, ...content] = section.split('\n');
          doc.setFontSize(12);
          doc.setTextColor(41, 98, 255);
          doc.text(title.trim(), 20, yPosition);
          yPosition += 7;
          
          doc.setFontSize(10);
          doc.setTextColor(0);
          const contentText = content.join('\n').trim();
          const splitText = doc.splitTextToSize(contentText, 170);
          doc.text(splitText, 20, yPosition);
          yPosition += splitText.length * 5 + 10;
        } else {
          doc.setFontSize(10);
          doc.setTextColor(0);
          const splitText = doc.splitTextToSize(section.trim(), 170);
          doc.text(splitText, 20, yPosition);
          yPosition += splitText.length * 5 + 5;
        }
        
        if (yPosition > 270) {
          doc.addPage();
          yPosition = 20;
        }
      });
      
      // Add footer
      doc.setFontSize(8);
      doc.setTextColor(100);
      const pageCount = doc.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.text(
          `Page ${i} of ${pageCount} | Sihha AI Health Assistant | For medical review purposes only`,
          105,
          doc.internal.pageSize.height - 10,
          { align: "center" }
        );
      }
      
      return doc;
    } catch (error) {
      console.error('Error generating report:', error);
      throw error;
    }
  }
}

// Create and export a singleton instance
export const healthAI = new HealthAI();