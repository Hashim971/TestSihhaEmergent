import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Brain, 
  Activity, 
  MessageSquare, 
  Shield, 
  Users, 
  Heart, 
  Bell, 
  Calendar, 
  LineChart, 
  Clock, 
  Share2, 
  FileText, 
  Phone,
  Mail,
  MapPin,
  Facebook,
  Twitter,
  Linkedin,
  Instagram
} from 'lucide-react';

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-blue-50">
      {/* Hero Section */}
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 pt-24 sm:pt-32 pb-16 sm:pb-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex justify-center mb-6">
            <Brain className="h-12 w-12 sm:h-16 sm:w-16 text-blue-600" />
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-gray-900 mb-4 sm:mb-6 px-4">
            Your Personal AI Health Assistant
          </h1>
          <p className="text-lg sm:text-xl text-gray-600 mb-6 sm:mb-8 px-4">
            Experience the future of healthcare monitoring with AI-powered insights and real-time health tracking
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center px-4">
            <Link
              to="/signup"
              className="w-full sm:w-auto bg-blue-600 text-white px-8 py-3 rounded-full hover:bg-blue-700 transition-colors text-center"
            >
              Get Started
            </Link>
            <Link
              to="/health-chat"
              className="w-full sm:w-auto border-2 border-blue-600 text-blue-600 px-8 py-3 rounded-full hover:bg-blue-50 transition-colors text-center"
            >
              Try Health Chat
            </Link>
          </div>
        </div>
      </div>

      {/* Key Features Section */}
      <div className="bg-white py-16 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-900 mb-4">
            Comprehensive Health Monitoring
          </h2>
          <p className="text-gray-600 text-center mb-8 sm:mb-12 max-w-2xl mx-auto px-4">
            Our platform offers a complete suite of health monitoring tools powered by advanced AI technology
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
            <FeatureCard
              icon={Heart}
              title="Vital Signs Monitoring"
              description="Track heart rate, blood pressure, temperature, and oxygen levels in real-time"
              features={[
                "24/7 continuous monitoring",
                "Instant alerts for abnormal readings",
                "Historical data analysis",
                "Trend visualization"
              ]}
            />
            <FeatureCard
              icon={MessageSquare}
              title="AI Health Assistant"
              description="Get instant health insights and personalized recommendations"
              features={[
                "Symptom analysis",
                "Health risk assessment",
                "Medication reminders",
                "Lifestyle recommendations"
              ]}
            />
            <FeatureCard
              icon={LineChart}
              title="Health Analytics"
              description="Comprehensive health data analysis and insights"
              features={[
                "Personalized health reports",
                "Progress tracking",
                "Goal setting",
                "Performance metrics"
              ]}
            />
            <FeatureCard
              icon={Bell}
              title="Smart Notifications"
              description="Stay informed about your health status"
              features={[
                "Customizable alerts",
                "Medication reminders",
                "Appointment notifications",
                "Health tips and updates"
              ]}
            />
            <FeatureCard
              icon={Users}
              title="Care Network"
              description="Connect with healthcare providers and specialists"
              features={[
                "Direct provider messaging",
                "Appointment scheduling",
                "Medical record sharing",
                "Emergency contacts"
              ]}
            />
            <FeatureCard
              icon={Shield}
              title="Data Security"
              description="Enterprise-grade security for your health data"
              features={[
                "End-to-end encryption",
                "HIPAA compliance",
                "Secure data storage",
                "Privacy controls"
              ]}
            />
          </div>
        </div>
      </div>

      {/* How It Works Section */}
      <div className="py-16 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-900 mb-4">
            How It Works
          </h2>
          <p className="text-gray-600 text-center mb-8 sm:mb-12 max-w-2xl mx-auto px-4">
            Get started with Sihha AI in just a few simple steps
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            <StepCard
              number={1}
              icon={Activity}
              title="Connect Devices"
              description="Link your health monitoring devices or input data manually"
            />
            <StepCard
              number={2}
              icon={Share2}
              title="Share Health Data"
              description="Securely sync your health data with our platform"
            />
            <StepCard
              number={3}
              icon={Clock}
              title="Real-time Monitoring"
              description="Get continuous health monitoring and instant alerts"
            />
            <StepCard
              number={4}
              icon={FileText}
              title="Receive Insights"
              description="Access personalized health insights and recommendations"
            />
          </div>
        </div>
      </div>

      {/* Testimonials Section */}
      <div className="bg-white py-16 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-900 mb-8 sm:mb-12">
            Trusted by Healthcare Professionals
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
            <TestimonialCard
              quote="Sihha AI has revolutionized how we monitor patient health. The real-time insights have significantly improved patient outcomes."
              image="https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=100&h=100"
              name="Dr. Sarah Johnson"
              title="Chief of Cardiology, Heart Care Center"
            />
            <TestimonialCard
              quote="The AI-powered health assistant provides accurate and timely recommendations. It's like having a medical professional available 24/7."
              image="https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=100&h=100"
              name="Dr. Michael Chen"
              title="Internal Medicine Specialist"
            />
            <TestimonialCard
              quote="Patient engagement has improved significantly since we started using Sihha AI. The platform makes health monitoring accessible and user-friendly."
              image="https://images.unsplash.com/photo-1594824476967-48c8b964273f?auto=format&fit=crop&q=80&w=100&h=100"
              name="Dr. Emily Rodriguez"
              title="Digital Health Director"
            />
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-blue-600 py-16 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4 sm:mb-6">
            Start Your Health Journey Today
          </h2>
          <p className="text-lg sm:text-xl text-blue-100 mb-6 sm:mb-8">
            Join thousands of users who trust Sihha AI for their health monitoring needs
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/signup"
              className="w-full sm:w-auto bg-white text-blue-600 px-8 py-3 rounded-full hover:bg-blue-50 transition-colors text-center"
            >
              Get Started Now
            </Link>
            <a
              href="#contact"
              className="w-full sm:w-auto border-2 border-white text-white px-8 py-3 rounded-full hover:bg-blue-700 transition-colors text-center"
            >
              Contact Sales
            </a>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 sm:gap-12">
            <div>
              <div className="flex items-center space-x-2 mb-6">
                <Brain className="h-8 w-8 text-blue-500" />
                <span className="text-xl sm:text-2xl font-bold text-white">Sihha AI</span>
              </div>
              <p className="text-gray-400 mb-6">
                Revolutionizing healthcare monitoring with AI-powered insights and real-time tracking.
              </p>
              <div className="flex space-x-4">
                <SocialLink icon={Facebook} href="#" />
                <SocialLink icon={Twitter} href="#" />
                <SocialLink icon={Linkedin} href="#" />
                <SocialLink icon={Instagram} href="#" />
              </div>
            </div>
            
            <div className="mt-8 sm:mt-0">
              <h3 className="text-white font-semibold text-lg mb-4">Features</h3>
              <FooterLinks
                links={[
                  { label: "Health Monitoring", href: "/monitoring" },
                  { label: "AI Assistant", href: "/health-chat" },
                  { label: "Dashboard", href: "/dashboard" },
                  { label: "Analytics", href: "#" },
                  { label: "Care Network", href: "#" }
                ]}
              />
            </div>

            <div>
              <h3 className="text-white font-semibold text-lg mb-4">Company</h3>
              <FooterLinks
                links={[
                  { label: "About Us", href: "#" },
                  { label: "Careers", href: "#" },
                  { label: "Privacy Policy", href: "#" },
                  { label: "Terms of Service", href: "#" },
                  { label: "Contact", href: "#" }
                ]}
              />
            </div>

            <div>
              <h3 className="text-white font-semibold text-lg mb-4">Contact</h3>
              <div className="space-y-4">
                <ContactInfo icon={Phone} text="+1 (555) 123-4567" />
                <ContactInfo icon={Mail} text="contact@sihha.ai" />
                <ContactInfo icon={MapPin} text="123 Health Street, Medical District, NY 10001" />
              </div>
            </div>
          </div>
          
          <div className="border-t border-gray-800 mt-8 sm:mt-12 pt-8 text-center text-gray-400">
            <p>&copy; {new Date().getFullYear()} Sihha AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

const FeatureCard: React.FC<{
  icon: React.ElementType;
  title: string;
  description: string;
  features: string[];
}> = ({ icon: Icon, title, description, features }) => {
  return (
    <div className="p-6 bg-blue-50 rounded-xl hover:shadow-lg transition-shadow">
      <Icon className="h-8 w-8 text-blue-600 mb-4" />
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600 mb-4">{description}</p>
      <ul className="space-y-2">
        {features.map((feature, index) => (
          <li key={index} className="flex items-center text-gray-700">
            <div className="w-1.5 h-1.5 bg-blue-600 rounded-full mr-2"></div>
            {feature}
          </li>
        ))}
      </ul>
    </div>
  );
};

const StepCard: React.FC<{
  number: number;
  icon: React.ElementType;
  title: string;
  description: string;
}> = ({ number, icon: Icon, title, description }) => {
  return (
    <div className="text-center">
      <div className="relative inline-block">
        <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mb-4 mx-auto">
          <Icon className="h-8 w-8 text-white" />
        </div>
        <div className="absolute -top-2 -right-2 w-8 h-8 bg-blue-800 rounded-full flex items-center justify-center text-white font-bold">
          {number}
        </div>
      </div>
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
};

const TestimonialCard: React.FC<{
  quote: string;
  image: string;
  name: string;
  title: string;
}> = ({ quote, image, name, title }) => {
  return (
    <div className="bg-blue-50 p-6 rounded-xl h-full">
      <blockquote className="text-gray-600 italic mb-6">{quote}</blockquote>
      <div className="flex items-center">
        <img
          src={image}
          alt={name}
          className="w-12 h-12 rounded-full object-cover mr-4"
        />
        <div>
          <div className="font-semibold text-gray-900">{name}</div>
          <div className="text-gray-600 text-sm">{title}</div>
        </div>
      </div>
    </div>
  );
};

const SocialLink: React.FC<{
  icon: React.ElementType;
  href: string;
}> = ({ icon: Icon, href }) => {
  return (
    <a
      href={href}
      className="w-10 h-10 bg-gray-800 rounded-full flex items-center justify-center hover:bg-blue-600 transition-colors"
    >
      <Icon className="h-5 w-5" />
    </a>
  );
};

const FooterLinks: React.FC<{
  links: Array<{ label: string; href: string }>;
}> = ({ links }) => {
  return (
    <ul className="space-y-3">
      {links.map((link, index) => (
        <li key={index}>
          <Link
            to={link.href}
            className="hover:text-blue-400 transition-colors"
          >
            {link.label}
          </Link>
        </li>
      ))}
    </ul>
  );
};

const ContactInfo: React.FC<{
  icon: React.ElementType;
  text: string;
}> = ({ icon: Icon, text }) => {
  return (
    <div className="flex items-center">
      <Icon className="h-5 w-5 mr-3 text-blue-500 flex-shrink-0" />
      <span className="break-words">{text}</span>
    </div>
  );
};

export default LandingPage;