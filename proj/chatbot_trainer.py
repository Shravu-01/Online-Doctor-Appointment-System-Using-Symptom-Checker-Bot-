# chatbot_trainer.py
import re
import json
from datetime import datetime

class ChatbotTrainer:
    def __init__(self):
        self.conversation_patterns = self.load_conversation_patterns()
        self.symptom_intensity_indicators = self.load_intensity_indicators()
        self.context_memory = {}
        
    def load_conversation_patterns(self):
        """Load comprehensive conversation patterns"""
        return {
            # Greetings and casual conversation
            'greeting': {
                'patterns': [
                    r'\b(hi|hello|hey|hola|namaste|howdy|hii|hie|hiee|heyy|heyaa)\b',
                    r'\bgood\s+(morning|afternoon|evening|night)\b',
                    r'\bhey\s+there\b',
                    r'\bhello\s+there\b'
                ],
                'responses': [
                    "👋 Hello! Hope you're doing well today. I'm here to help with your health concerns.",
                    "😊 Hi there! Welcome to our symptom checker. How can I assist you today?",
                    "🌟 Hello! Good to see you. I hope you're feeling okay. What symptoms would you like to discuss?"
                ]
            },
            
            'casual_inquiry': {
                'patterns': [
                    r'\bhow\s+are\s+you\b',
                    r'\bwhat\'?s\s+up\b',
                    r'\bhow\s+is\s+it\s+going\b',
                    r'\bhow\s+do\s+you\s+do\b'
                ],
                'responses': [
                    "😊 I'm doing well, thank you for asking! Ready to help with any health concerns.",
                    "🌟 I'm functioning perfectly and here to assist you! How can I help with your symptoms today?",
                    "💙 I'm great! Hope you're doing well too. What health issues are you experiencing?"
                ]
            },
            
            'gratitude': {
                'patterns': [
                    r'\b(thank you|thanks|thankyou|thx)\b',
                    r'\bappreciate\sit\b',
                    r'\bthat\s+helps\b'
                ],
                'responses': [
                    "🌟 You're welcome! I'm glad I could help.",
                    "😊 Happy to assist! Feel free to ask about any other symptoms.",
                    "💙 You're most welcome! Take care of your health."
                ]
            },
            
            # Symptom context patterns
            'symptom_description': {
                'patterns': [
                    r'\b(i\s+have|i\'?m\s+having|i\s+feel|i\'?m\s+feeling|experiencing|suffering\s+from)\b',
                    r'\b(pain|ache|hurt|sore|discomfort)\b',
                    r'\b(fever|cough|headache|nausea|vomiting|diarrhea)\b',
                    r'\b(breathing|chest|stomach|head|throat|muscle|joint)\b'
                ]
            },
            
            'symptom_intensity': {
                'patterns': [
                    r'\b(mild|slight|minor|moderate|severe|extreme|unbearable)\b',
                    r'\b(little\s+bit|a\s+bit|very|really|extremely)\b',
                    r'\b(can\'?t\s+stand|can\'?t\s+bear|worst\s+ever)\b'
                ]
            },
            
            'symptom_duration': {
                'patterns': [
                    r'\b(for|since|about|approximately|around)\s+(\d+\s+(hours?|days?|weeks?|months?))',
                    r'\b(\d+\s+(hours?|days?|weeks?|months?))\s+ago',
                    r'\b(started|began)\s+(\w+\s+ago|yesterday|today)'
                ]
            },
            
            'emergency_keywords': {
                'patterns': [
                    r'\b(emergency|urgent|immediate|911|ambulance)\b',
                    r'\b(severe\s+pain|can\'?t\s+breathe|chest\s+pain|unconscious)\b',
                    r'\b(bleeding\s+heavily|broken\s+bone|heart\s+attack|stroke)\b'
                ],
                'responses': [
                    "🚨 This sounds serious! Please seek immediate medical attention. Call emergency services or go to the nearest hospital.",
                    "⚠️ This appears to be an emergency situation. Please contact emergency services immediately.",
                    "💥 For your safety, please seek urgent medical care right away."
                ]
            },
            
            'clarification_needed': {
                'patterns': [
                    r'\b(not\s+sure|don\'?t\s+know|unclear|maybe|perhaps)\b',
                    r'\b(something|anything|everything|nothing)\b',
                    r'^\s*\w{1,3}\s*$'  # Very short vague responses
                ],
                'responses': [
                    "🤔 I want to make sure I understand correctly. Could you provide more details about your symptoms?",
                    "🔍 Let me help you better. Can you describe what you're feeling in more detail?",
                    "💭 I need a bit more information to assist you properly. What specific symptoms are you experiencing?"
                ]
            }
        }
    
    def load_intensity_indicators(self):
        """Load symptom intensity indicators"""
        return {
            'mild': ['slight', 'mild', 'minor', 'little bit', 'a bit', 'somewhat'],
            'moderate': ['moderate', 'medium', 'noticeable', 'bothering'],
            'severe': ['severe', 'strong', 'intense', 'very', 'really', 'extremely'],
            'critical': ['unbearable', 'excruciating', 'worst ever', 'can\'t stand', 'emergency']
        }
    
    def analyze_message_intent(self, message, user_id=None):
        """Comprehensive message intent analysis"""
        message_lower = message.lower().strip()
        analysis = {
            'intent': 'unknown',
            'confidence': 0.0,
            'message_type': 'unknown',
            'symptom_context': False,
            'urgency_level': 'low',
            'needs_clarification': False,
            'detected_patterns': [],
            'response_template': None
        }
        
        # Check for emergency situations first
        if self._check_emergency(message_lower):
            analysis.update({
                'intent': 'emergency',
                'confidence': 0.95,
                'message_type': 'emergency',
                'urgency_level': 'critical',
                'response_template': 'emergency'
            })
            return analysis
        
        # Check conversation patterns
        for intent_type, intent_data in self.conversation_patterns.items():
            for pattern in intent_data.get('patterns', []):
                if re.search(pattern, message_lower, re.IGNORECASE):
                    analysis['detected_patterns'].append(intent_type)
                    
                    if intent_type in ['greeting', 'casual_inquiry', 'gratitude']:
                        analysis.update({
                            'intent': intent_type,
                            'confidence': 0.85,
                            'message_type': 'conversation',
                            'response_template': intent_type
                        })
                        return analysis
        
        # Analyze symptom context
        symptom_score = self._calculate_symptom_score(message_lower)
        clarity_score = self._calculate_clarity_score(message_lower)
        
        if symptom_score >= 0.7:
            analysis.update({
                'intent': 'symptom_description',
                'confidence': symptom_score,
                'message_type': 'symptoms',
                'symptom_context': True,
                'urgency_level': self._assess_urgency(message_lower)
            })
        elif symptom_score >= 0.3:
            analysis.update({
                'intent': 'possible_symptoms',
                'confidence': symptom_score,
                'message_type': 'symptoms',
                'symptom_context': True,
                'needs_clarification': clarity_score < 0.5,
                'urgency_level': self._assess_urgency(message_lower)
            })
        elif clarity_score < 0.4:
            analysis.update({
                'intent': 'clarification_needed',
                'confidence': 0.8,
                'message_type': 'clarification',
                'needs_clarification': True,
                'response_template': 'clarification_needed'
            })
        else:
            analysis.update({
                'intent': 'general_inquiry',
                'confidence': 0.6,
                'message_type': 'general',
                'response_template': 'general_help'
            })
        
        return analysis
    
    def _check_emergency(self, message):
        """Check for emergency keywords"""
        emergency_patterns = self.conversation_patterns['emergency_keywords']['patterns']
        return any(re.search(pattern, message, re.IGNORECASE) for pattern in emergency_patterns)
    
    def _calculate_symptom_score(self, message):
        """Calculate how likely the message contains symptoms"""
        symptom_indicators = self.conversation_patterns['symptom_description']['patterns']
        symptom_words = [
            'fever', 'cough', 'pain', 'headache', 'nausea', 'vomiting', 'diarrhea',
            'rash', 'swelling', 'dizziness', 'fatigue', 'bleeding', 'infection',
            'breathing', 'chest', 'stomach', 'abdominal', 'muscle', 'joint'
        ]
        
        score = 0
        # Check patterns
        for pattern in symptom_indicators:
            if re.search(pattern, message, re.IGNORECASE):
                score += 0.3
        
        # Check specific symptom words
        for word in symptom_words:
            if word in message:
                score += 0.2
        
        return min(1.0, score)
    
    def _calculate_clarity_score(self, message):
        """Calculate how clear and specific the message is"""
        words = message.split()
        if len(words) < 3:
            return 0.2  # Very short messages are unclear
        
        # Check for vague terms
        vague_terms = ['something', 'anything', 'everything', 'nothing', 'maybe', 'perhaps']
        vague_count = sum(1 for word in words if word in vague_terms)
        
        # Check for specific descriptors
        specific_indicators = ['pain', 'fever', 'cough', 'headache', 'when', 'where', 'how long']
        specific_count = sum(1 for indicator in specific_indicators if indicator in message)
        
        clarity_score = (specific_count * 0.3) - (vague_count * 0.2)
        return max(0.1, min(1.0, 0.5 + clarity_score))
    
    def _assess_urgency(self, message):
        """Assess the urgency level of the message"""
        message_lower = message.lower()
        
        # Critical urgency indicators
        critical_terms = ['unbearable', 'excruciating', 'can\'t breathe', 'chest pain', 'emergency']
        if any(term in message_lower for term in critical_terms):
            return 'critical'
        
        # High urgency indicators
        high_terms = ['severe', 'intense', 'very bad', 'getting worse', 'worsening']
        if any(term in message_lower for term in high_terms):
            return 'high'
        
        # Moderate urgency indicators
        moderate_terms = ['moderate', 'bothering', 'persistent', 'continuous']
        if any(term in message_lower for term in moderate_terms):
            return 'moderate'
        
        return 'low'
    
    def generate_response(self, intent_analysis, original_message, user_id=None):
        """Generate appropriate response based on intent analysis"""
        intent_type = intent_analysis['intent']
        confidence = intent_analysis['confidence']
        
        if intent_type == 'emergency':
            responses = self.conversation_patterns['emergency_keywords']['responses']
            return {
                'response': responses[0],
                'action_required': True,
                'urgency_level': 'critical'
            }
        
        elif intent_type in ['greeting', 'casual_inquiry', 'gratitude']:
            responses = self.conversation_patterns[intent_type]['responses']
            return {
                'response': responses[0],
                'action_required': False,
                'suggest_followup': True
            }
        
        elif intent_type == 'clarification_needed':
            responses = self.conversation_patterns['clarification_needed']['responses']
            return {
                'response': responses[0],
                'action_required': False,
                'needs_clarification': True
            }
        
        elif intent_type in ['symptom_description', 'possible_symptoms']:
            # For symptoms, we'll let the main symptom checker handle it
            # but we can add contextual advice
            urgency_advice = {
                'critical': "This sounds serious. Please consider seeking immediate medical attention.",
                'high': "Your symptoms sound concerning. It's important to consult a doctor soon.",
                'moderate': "I'll help you find the right specialist for your symptoms.",
                'low': "Let me help you find appropriate medical guidance for your symptoms."
            }
            
            return {
                'response': f"🔍 {urgency_advice[intent_analysis['urgency_level']]} I'm analyzing your symptoms now...",
                'action_required': False,
                'proceed_to_symptom_analysis': True,
                'urgency_level': intent_analysis['urgency_level']
            }
        
        else:
            # Default response for unclear messages
            return {
                'response': "🤖 I'm here to help with health concerns. Could you tell me what symptoms you're experiencing?",
                'action_required': False,
                'needs_clarification': True
            }
    
    def update_context(self, user_id, message, intent_analysis):
        """Update conversation context for a user"""
        if user_id not in self.context_memory:
            self.context_memory[user_id] = {
                'conversation_history': [],
                'last_intent': None,
                'symptoms_mentioned': [],
                'last_interaction': datetime.now()
            }
        
        self.context_memory[user_id]['conversation_history'].append({
            'timestamp': datetime.now(),
            'message': message,
            'intent': intent_analysis['intent'],
            'confidence': intent_analysis['confidence']
        })
        
        # Keep only last 10 messages
        if len(self.context_memory[user_id]['conversation_history']) > 10:
            self.context_memory[user_id]['conversation_history'] = \
                self.context_memory[user_id]['conversation_history'][-10:]
        
        self.context_memory[user_id]['last_intent'] = intent_analysis['intent']
        self.context_memory[user_id]['last_interaction'] = datetime.now()