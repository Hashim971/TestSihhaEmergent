import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, FileText, AlertCircle } from 'lucide-react';
import { healthAI } from '../lib/healthAI';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/auth';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const HealthChatbot: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isFirstMessage, setIsFirstMessage] = useState(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load existing chat session if available
  useEffect(() => {
    if (user) {
      loadLatestSession();
    }
  }, [user]);

  const loadLatestSession = async () => {
    try {
      // Get the latest active session
      const { data: sessionData, error: sessionError } = await supabase
        .from('chat_sessions')
        .select('*')
        .eq('user_id', user?.id)
        .eq('status', 'active')
        .order('started_at', { ascending: false })
        .limit(1)
        .single();

      if (sessionError && sessionError.code !== 'PGRST116') {
        throw sessionError;
      }

      if (sessionData) {
        setSessionId(sessionData.id);
        setIsFirstMessage(false);

        // Load messages for this session
        const { data: messagesData, error: messagesError } = await supabase
          .from('messages')
          .select('*')
          .eq('session_id', sessionData.id)
          .order('created_at', { ascending: true });

        if (messagesError) throw messagesError;

        if (messagesData) {
          setMessages(messagesData.map(msg => ({
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            timestamp: new Date(msg.created_at)
          })));
        }
      }
    } catch (error) {
      console.error('Error loading chat session:', error);
    }
  };

  const createChatSession = async () => {
    if (!user) return null;

    try {
      const { data: sessionData, error: sessionError } = await supabase
        .from('chat_sessions')
        .insert([{
          user_id: user.id,
          status: 'active'
        }])
        .select()
        .single();

      if (sessionError) throw sessionError;
      return sessionData.id;
    } catch (error) {
      console.error('Error creating chat session:', error);
      return null;
    }
  };

  const saveMessage = async (message: Message, currentSessionId: string) => {
    if (!user) return;

    try {
      const { error: messageError } = await supabase
        .from('messages')
        .insert([{
          session_id: currentSessionId,
          role: message.role,
          content: message.content
        }]);

      if (messageError) throw messageError;
    } catch (error) {
      console.error('Error saving message:', error);
      throw error;
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const newMessage: Message = { 
      role: 'user', 
      content: input,
      timestamp: new Date()
    };
    
    try {
      setMessages(prev => [...prev, newMessage]);
      setInput('');
      setIsLoading(true);
      setError(null);

      // Create a new session if this is the first message
      let currentSessionId = sessionId;
      if (isFirstMessage) {
        currentSessionId = await createChatSession();
        setSessionId(currentSessionId);
        setIsFirstMessage(false);
      }

      // Save user message if we have a session
      if (currentSessionId) {
        await saveMessage(newMessage, currentSessionId);
      }

      const response = await healthAI.continueConversation(input);
      const assistantMessage: Message = { 
        role: 'assistant', 
        content: response,
        timestamp: new Date()
      };
      
      // Save assistant message if we have a session
      if (currentSessionId) {
        await saveMessage(assistantMessage, currentSessionId);
      }
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
      }
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!user || !sessionId) {
      setError('Please sign in to generate reports');
      return;
    }

    try {
      setIsGeneratingReport(true);
      setError(null);
      
      const generatingMessage: Message = {
        role: 'assistant',
        content: 'Generating your health screening report...',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, generatingMessage]);
      await saveMessage(generatingMessage, sessionId);

      const doc = await healthAI.generateReport();
      
      // Save report to database
      const { error: reportError } = await supabase
        .from('health_reports')
        .insert([{
          session_id: sessionId,
          user_id: user.id,
          content: {
            messages: messages,
            generated_at: new Date().toISOString()
          }
        }]);

      if (reportError) throw reportError;
      
      // Update session status
      await supabase
        .from('chat_sessions')
        .update({ status: 'completed', ended_at: new Date().toISOString() })
        .eq('id', sessionId);
      
      doc.save('health-screening-report.pdf');
      
      const confirmationMessage: Message = {
        role: 'assistant',
        content: 'Your health screening report has been generated and downloaded. Please share this report with your healthcare provider.',
        timestamp: new Date()
      };
      
      await saveMessage(confirmationMessage, sessionId);
      setMessages(prev => [...prev, confirmationMessage]);
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
        const errorMessage: Message = {
          role: 'assistant',
          content: 'Sorry, I encountered an error while generating your report. Please try again.',
          timestamp: new Date()
        };
        if (sessionId) {
          await saveMessage(errorMessage, sessionId);
        }
        setMessages(prev => [...prev, errorMessage]);
      }
      console.error('Error generating report:', error);
    } finally {
      setIsGeneratingReport(false);
    }
  };

  return (
    <div className="p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-xl p-4 text-center">
            <AlertCircle className="h-6 w-6 text-red-500 mx-auto mb-2" />
            <p className="text-red-600">{error}</p>
          </div>
        )}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <div className="flex flex-col h-[600px]">
            <div className="flex-1 overflow-y-auto p-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`mb-4 ${
                    message.role === 'user' ? 'text-right' : 'text-left'
                  }`}
                >
                  <div
                    className={`inline-block p-3 rounded-lg ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-800'
                    } max-w-[80%]`}
                  >
                    {message.content}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              ))}
              {(isLoading || isGeneratingReport) && (
                <div className="text-left">
                  <div className="inline-block p-3 rounded-lg bg-gray-100">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="border-t p-4">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="Describe your symptoms..."
                  className="flex-1 p-2 border rounded-lg focus:outline-none focus:border-blue-600"
                  disabled={isLoading || isGeneratingReport}
                />
                <button
                  onClick={handleSend}
                  disabled={isLoading || isGeneratingReport || !input.trim()}
                  className="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  <Send className="h-5 w-5" />
                </button>
                {messages.length > 1 && (
                  <button
                    onClick={handleGenerateReport}
                    disabled={isLoading || isGeneratingReport || !user}
                    className={`${
                      isGeneratingReport ? 'bg-blue-100' : 'bg-gray-100'
                    } text-gray-700 p-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50`}
                    title={user ? 'Generate Report' : 'Sign in to generate reports'}
                  >
                    <FileText className="h-5 w-5" />
                  </button>
                )}
              </div>
              {!user && (
                <p className="text-sm text-gray-500 mt-2">
                  Sign in to save your chat history and generate reports
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HealthChatbot;