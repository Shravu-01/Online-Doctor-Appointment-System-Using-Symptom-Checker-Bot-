# symptom_checker.py
import re
from difflib import SequenceMatcher
try:
    from .chatbot_trainer import ChatbotTrainer
except ImportError:
    # Fallback for direct execution
    from chatbot_trainer import ChatbotTrainer

# Define synonyms directly in the same file
SYMPTOM_SYNONYMS = {
    # Fever related
    'fever': ['temperature', 'hot', 'warm', 'burning', 'high temp', 'pyrexia', 'febrile'],
    'cough': ['coughing', 'hacking', 'clearing throat', 'chest cough', 'dry cough', 'wet cough'],
    'cold': ['chills', 'shivering', 'feeling cold', 'runny nose', 'nasal congestion', 'sneezing'],
    
    # Pain related
    'headache': ['head pain', 'migraine', 'head throbbing', 'head ache', 'temple pain'],
    'pain': ['ache', 'sore', 'tenderness', 'discomfort', 'hurting', 'soreness'],
    
    # Breathing related
    'breathing difficulty': ['shortness of breath', 'breathlessness', 'can\'t breathe', 'lungs tight', 'wheezing'],
    'chest pain': ['chest tightness', 'heart pain', 'chest discomfort', 'chest pressure'],
    
    # Stomach related
    'vomiting': ['throwing up', 'puking', 'nausea', 'feeling sick', 'queasy', 'upset stomach'],
    'diarrhea': ['loose motions', 'watery stool', 'frequent bathroom', 'bowel problems'],
    
    # General symptoms
    'fatigue': ['tiredness', 'exhaustion', 'weakness', 'low energy', 'lethargy'],
    'dizziness': ['lightheaded', 'vertigo', 'spinning', 'unsteady', 'woozy'],
    'swelling': ['inflammation', 'puffiness', 'bloating', 'edema', 'swollen']
}

class SymptomChecker:
    def __init__(self, db, Doctor):
        self.db = db
        self.Doctor = Doctor
        self.trainer = ChatbotTrainer()  # Add the trainer
        
        # Build comprehensive symptom dictionary from synonyms
        self.symptom_dictionary = set()
        for main_symptom, synonyms in SYMPTOM_SYNONYMS.items():
            self.symptom_dictionary.add(main_symptom)
            self.symptom_dictionary.update(synonyms)
        
        # Common words that should NOT be corrected
        self.common_words = {
            'hi', 'hello', 'hey', 'good','hie','hii', 'morning', 'afternoon', 'evening', 'night',
            'how', 'are', 'you', 'doing', 'fine', 'well', 'okay', 'ok', 'thanks', 'thank',
            'please', 'help', 'me', 'my', 'i', 'am', 'have', 'has', 'had', 'feeling', 'feel',
            'not', 'able', 'to', 'can', 'cannot', "can't", 'breath', 'breathe', 'breathing',
            'the', 'and', 'or', 'but', 'with', 'for', 'from', 'that', 'this', 'these', 'those',
            'what', 'when', 'where', 'why', 'how', 'which', 'who', 'whose'
        }
        
        # Medical context words that indicate actual symptoms
        self.medical_context_words = {
            'fever', 'headache', 'cough', 'pain', 'vomiting', 'diarrhea', 'rash', 'breathing',
            'chest', 'stomach', 'nausea', 'dizziness', 'fatigue', 'cold', 'flu', 'infection',
            'injury', 'swelling', 'bleeding', 'pressure', 'heart', 'lung', 'liver', 'kidney',
            'muscle', 'bone', 'joint', 'skin', 'eye', 'ear', 'nose', 'throat', 'abdominal'
        }

    def smart_analyze_message(self, user_input, user_id=None):
        """
        Main entry point for analyzing any user message
        Uses the trained chatbot to understand intent first
        """
        print(f"Smart Analysis - User Input: '{user_input}'")
        
        # Step 1: Analyze message intent using trained model
        intent_analysis = self.trainer.analyze_message_intent(user_input, user_id)
        print(f"Intent Analysis: {intent_analysis}")
        
        # Step 2: Generate appropriate response
        bot_response = self.trainer.generate_response(intent_analysis, user_input, user_id)
        
        # Step 3: Update context
        if user_id:
            self.trainer.update_context(user_id, user_input, intent_analysis)
        
        # Step 4: If it's a symptom message, proceed with medical analysis
        if bot_response.get('proceed_to_symptom_analysis'):
            medical_result = self.analyze_symptoms(user_input, intent_analysis)
            return self._combine_responses(bot_response, medical_result)
        
        # Return the conversational response
        return {
            'match_found': False,
            'message_type': intent_analysis['message_type'],
            'intent': intent_analysis['intent'],
            'confidence': intent_analysis['confidence'],
            'advice': bot_response['response'],
            'action_required': bot_response.get('action_required', False),
            'urgency_level': bot_response.get('urgency_level', 'low'),
            'available_doctors': [],
            'corrected_input': user_input
        }

    def _combine_responses(self, conversational_response, medical_result):
        """Combine conversational response with medical analysis"""
        if medical_result.get('match_found'):
            # Medical analysis found matches
            combined_result = {
                **medical_result,
                'conversational_context': conversational_response,
                'urgency_level': conversational_response.get('urgency_level', 'low')
            }
            # Add intent information if available
            if hasattr(medical_result, 'get'):
                combined_result['intent'] = medical_result.get('intent', 'symptom_description')
            return combined_result
        else:
            # No medical matches found
            combined_advice = f"{conversational_response['response']}"
            if medical_result.get('advice'):
                combined_advice += f" {medical_result['advice']}"
            
            return {
                **medical_result,
                'advice': combined_advice,
                'urgency_level': conversational_response.get('urgency_level', 'low'),
                'intent': 'symptom_description'
            }

    def analyze_symptoms(self, user_input, intent_analysis=None):
        """
        Enhanced symptom analysis with better context understanding
        """
        if intent_analysis is None:
            intent_analysis = self.trainer.analyze_message_intent(user_input)
        
        # Only proceed if it's likely a symptom message
        if intent_analysis['intent'] not in ['symptom_description', 'possible_symptoms']:
            return self.get_clarification_response(user_input)
        
        corrected_input = self.preprocess_input(user_input)
        
        # Get all doctors with their disease and symptom data
        doctors_data = self.Doctor.query.filter(self.Doctor.disease.isnot(None)).all()
        
        if not doctors_data:
            return self.fallback_analysis(corrected_input, user_input)
        
        matched_doctors = []
        matched_conditions = []
        
        for doctor in doctors_data:
            if doctor.symptoms:
                original_symptoms = [symptom.strip().lower() for symptom in doctor.symptoms.split(',')]
                
                # Expand symptoms with synonyms for matching
                expanded_symptoms = []
                for symptom in original_symptoms:
                    expanded_symptoms.append(symptom)
                    if symptom in SYMPTOM_SYNONYMS:
                        expanded_symptoms.extend(SYMPTOM_SYNONYMS[symptom])
                
                score = self.calculate_enhanced_match_score(corrected_input, original_symptoms, expanded_symptoms)
                
                if score > 0:
                    # Track which symptoms were matched
                    matched_syms = self.get_matched_symptoms(corrected_input, original_symptoms, expanded_symptoms)
                    
                    matched_conditions.append({
                        'doctor_id': doctor.id,
                        'doctor_name': doctor.name,
                        'specialization': doctor.specialization,
                        'disease': doctor.disease,
                        'score': score,
                        'matched_symptoms': matched_syms,
                        'email': doctor.email
                    })
                    
                    matched_doctors.append(doctor)
        
        if matched_doctors:
            return self.prepare_success_response_all_doctors(matched_doctors, matched_conditions, corrected_input, user_input)
        else:
            return self.fallback_analysis(corrected_input, user_input)

    def conservative_spelling_correction(self, word):
        """Only correct spelling for clear medical terms, leave common words alone"""
        word = word.lower().strip()
        
        # Don't correct common words
        if word in self.common_words:
            return word
        
        # Don't correct words that are already correct
        if word in self.symptom_dictionary:
            return word
        
        # Only correct if it's very likely a medical term misspelling
        best_match = None
        best_ratio = 0
        
        for correct_word in self.symptom_dictionary:
            ratio = SequenceMatcher(None, word, correct_word).ratio()
            if ratio > best_ratio and ratio > 0.8:  # Higher threshold for medical terms
                best_ratio = ratio
                best_match = correct_word
        
        return best_match if best_match else word

    def preprocess_input(self, user_input):
        """Enhanced preprocessing that's more conservative with corrections"""
        # For symptom analysis, do conservative correction
        words = re.findall(r'\b\w+\b', user_input.lower())
        
        # Only correct words that are likely medical terms
        corrected_words = []
        for word in words:
            if len(word) > 2 and word not in self.common_words:
                corrected_word = self.conservative_spelling_correction(word)
                corrected_words.append(corrected_word)
            else:
                corrected_words.append(word)
        
        # Reconstruct the corrected sentence
        corrected_input = ' '.join(corrected_words)
        
        print(f"Original: {user_input}")
        print(f"Corrected: {corrected_input}")
        
        return corrected_input
    
    def calculate_enhanced_match_score(self, user_input, original_symptoms, expanded_symptoms):
        """Calculate match score with synonym support"""
        score = 0
        user_words = user_input.split()
        
        for symptom in expanded_symptoms:
            symptom_lower = symptom.lower()
            
            # Exact match
            if symptom_lower in user_input.lower():
                score += 3
            
            # Word-based match
            symptom_words = symptom_lower.split()
            for symptom_word in symptom_words:
                if symptom_word in user_words:
                    score += 2
        
        return score
    
    def get_matched_symptoms(self, user_input, original_symptoms, expanded_symptoms):
        """Get which symptoms were matched (including via synonyms)"""
        matched = []
        
        for symptom in original_symptoms:
            symptom_lower = symptom.lower()
            
            # Check direct match
            if symptom_lower in user_input.lower():
                matched.append(symptom)
                continue
            
            # Check synonym match
            if symptom_lower in SYMPTOM_SYNONYMS:
                synonyms = SYMPTOM_SYNONYMS[symptom_lower]
                for synonym in synonyms:
                    if synonym in user_input.lower():
                        matched.append(f"{symptom}")
                        break
        
        return matched
    
    def prepare_success_response_all_doctors(self, matched_doctors, matched_conditions, corrected_input, original_input):
        """Prepare success response with ALL matching doctors"""
        
        # Get all unique specializations from matched doctors
        unique_specializations = list(set([doctor.specialization for doctor in matched_doctors]))
        
        # Get all available doctors for these specializations
        all_relevant_doctors = []
        for specialization in unique_specializations:
            doctors_in_specialization = self.Doctor.query.filter_by(specialization=specialization).all()
            all_relevant_doctors.extend(doctors_in_specialization)
        
        # Remove duplicates by doctor id
        unique_doctors_dict = {}
        for doctor in all_relevant_doctors:
            unique_doctors_dict[doctor.id] = doctor
        
        doctors_list = []
        for doctor in unique_doctors_dict.values():
            doctors_list.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'email': doctor.email,
                'disease': doctor.disease,
                'symptoms': doctor.symptoms
            })
        
        # Get spelling corrections (only show meaningful ones)
        original_words = re.findall(r'\b\w+\b', original_input.lower())
        corrected_words = corrected_input.split()
        corrections = []
        
        for orig, corr in zip(original_words, corrected_words):
            if (orig != corr and len(orig) > 2 and 
                orig not in self.common_words and 
                corr in self.symptom_dictionary):
                corrections.append(f"'{orig}'→'{corr}'")
        
        # Count synonyms used
        synonyms_used = 0
        all_matched_symptoms = []
        all_possible_diseases = set()
        
        for condition in matched_conditions:
            all_matched_symptoms.extend(condition['matched_symptoms'])
            all_possible_diseases.add(condition['disease'])
        
        synonyms_used = len([s for s in all_matched_symptoms if 'understood from' in s])
        
        # Calculate confidence based on number of matches
        confidence_score = min(100, len(matched_doctors) * 20)
        
        return {
            'match_found': True,
            'message_type': 'symptoms',
            'intent': 'symptom_description',
            'confidence_score': confidence_score,
            'possible_diseases': list(all_possible_diseases),
            'recommended_specializations': unique_specializations,
            'matching_doctors_count': len(matched_doctors),
            'available_doctors': doctors_list,
            'matched_symptoms': list(set(all_matched_symptoms)),  # Remove duplicates
            'corrected_input': corrected_input,
            'spelling_corrections': corrections,
            'synonyms_used': synonyms_used,
            'advice': f"Found {len(matched_doctors)} doctor(s) matching your symptoms. Here are the available specialists."
        }
    
    def fallback_analysis(self, corrected_input, original_input):
        """Enhanced fallback that returns multiple doctors"""
        # Get all available doctors for fallback
        all_doctors = self.Doctor.query.limit(10).all()
        
        doctors_list = []
        for doctor in all_doctors:
            doctors_list.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'email': doctor.email,
                'disease': getattr(doctor, 'disease', 'General Consultation'),
                'symptoms': getattr(doctor, 'symptoms', 'Various symptoms')
            })
        
        return {
            'match_found': False,
            'message_type': 'symptoms',
            'intent': 'symptom_description',
            'available_doctors': doctors_list,
            'corrected_input': corrected_input,
            'spelling_corrections': [],
            'advice': f"I couldn't identify specific symptoms matching our database. Here are {len(doctors_list)} available doctors for general consultation."
        }

    def get_clarification_response(self, user_input):
        """Enhanced clarification response"""
        return {
            'match_found': False,
            'message_type': 'clarification',
            'intent': 'clarification_needed',
            'advice': "I want to make sure I understand your health concerns correctly. Could you please describe your symptoms more specifically? For example: 'I have chest pain when breathing' or 'Headache and fever for 2 days'.",
            'available_doctors': [],
            'corrected_input': user_input
        }

    # Backward compatibility methods
    def analyze_message_type(self, user_input):
        """Backward compatibility - delegate to trainer"""
        return self.trainer.analyze_message_intent(user_input)
    
    def get_greeting_response(self, user_input):
        """Backward compatibility"""
        intent_analysis = self.trainer.analyze_message_intent(user_input)
        bot_response = self.trainer.generate_response(intent_analysis, user_input)
        return {
            'match_found': False,
            'message_type': 'greeting',
            'advice': bot_response['response'],
            'available_doctors': [],
            'corrected_input': user_input
        }
    
    def get_casual_response(self, user_input):
        """Backward compatibility"""
        intent_analysis = self.trainer.analyze_message_intent(user_input)
        bot_response = self.trainer.generate_response(intent_analysis, user_input)
        return {
            'match_found': False,
            'message_type': 'casual',
            'advice': bot_response['response'],
            'available_doctors': [],
            'corrected_input': user_input
        }

# Don't create instance here - we'll create it in routes.py