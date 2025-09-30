"""
OCC Appraisal Engine for the AI Companion System.
Implements the Ortony, Clore, and Collins cognitive appraisal model for calculating
emotional changes in response to user messages.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import logging

from ..models.personality import PADState, PersonalitySnapshot
from ..models.interaction import InteractionRecord
from ..services.groq_client import GroqClient


class AppraisalEngine:
    """Implements the OCC (Ortony, Clore, Collins) cognitive appraisal model."""
    
    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client
        # Sentiment analysis keywords for determining emotional responses
        self.positive_keywords = {
            'achievement': ['succeeded', 'finished', 'completed', 'accomplished', 'achieved', 'won', 'gained'],
            'compliments': ['you\'re great', 'thank you', 'you helped', 'amazing', 'wonderful', 'fantastic', 'awesome'],
            'positive_events': ['celebrating', 'happy', 'excited', 'joy', 'love', 'enjoy', 'pleased'],
            'success': ['success', 'victory', 'triumph', 'accomplishment', 'progress', 'improvement']
        }
        
        self.negative_keywords = {
            'failure': ['failed', 'couldn\'t', 'didn\'t work', 'gave up', 'impossible', 'lost', 'missed'],
            'negative_events': ['sad', 'angry', 'frustrated', 'disappointed', 'annoyed', 'upset'],
            'challenges': ['difficulty', 'struggle', 'hard', 'tough', 'problem', 'issue', 'struggling']
        }
        
        self.surprise_keywords = ['surprise', 'unexpected', 'suddenly', 'out of nowhere', 'shocked', 'amazed', 'stunned']
        self.anticipation_keywords = ['looking forward', 'excited for', 'waiting for', 'anticipating', 'planning']
        self.social_keywords = ['friend', 'family', 'together', 'met someone', 'date', 'party', 'gathering', 'relationship']
        
        # Sentiment analysis using simple keyword matching
        self.sentiment_model = self._initialize_sentiment_model()

    def _initialize_sentiment_model(self):
        """Initialize simple keyword-based sentiment analysis"""
        # This is a simplified model; in production, this would be a more sophisticated ML model
        return {
            'positive': list(self.positive_keywords.values()),
            'negative': list(self.negative_keywords.values()),
            'neutral': ['ok', 'fine', 'normal', 'usual', 'same']
        }

    def calculate_emotion_delta(self, user_message: str, context: dict) -> PADState:
        """
        Calculate emotional change based on user message content and context
        using the OCC cognitive appraisal model
        """
        message_lower = user_message.lower()
        delta = PADState(pleasure=0.0, arousal=0.0, dominance=0.0)

        # Rule 1: Achievement-related emotions (success/failure)
        achievement_words = self.positive_keywords['achievement'] + self.negative_keywords['failure']
        if any(word in message_lower for word in achievement_words):
            if self._has_positive_sentiment(user_message):
                # Success -> pride/joy
                delta.pleasure += 0.2
                delta.arousal += 0.1
                delta.dominance += 0.05
            elif self._has_negative_sentiment(user_message):
                # Failure -> shame/disappointment
                delta.pleasure -= 0.15
                delta.arousal += 0.05  # Frustration increases arousal
                delta.dominance -= 0.1

        # Rule 2: User Compliments (positive words directed at assistant)
        elif any(phrase in message_lower for phrase in self.positive_keywords['compliments']):
            delta.pleasure += 0.3
            delta.arousal += 0.05
            delta.dominance += 0.1

        # Rule 3: Unexpected Events (surprise keywords)
        elif any(word in message_lower for word in self.surprise_keywords):
            delta.arousal += 0.2  # Surprise increases arousal
            # Pleasure depends on sentiment
            if self._has_positive_sentiment(user_message):
                delta.pleasure += 0.1
            else:
                delta.pleasure -= 0.1

        # Rule 4: Social Connection (relationship/people keywords)
        elif any(word in message_lower for word in self.social_keywords):
            delta.pleasure += 0.1
            delta.arousal += 0.05
            delta.dominance += 0.02

        # Rule 5: Anticipation of Events
        elif any(word in message_lower for word in self.anticipation_keywords):
            delta.pleasure += 0.05
            delta.arousal += 0.1  # Anticipation increases arousal
            delta.dominance += 0.05

        # Rule 6: Challenges/Difficulties
        elif any(word in message_lower for word in self.negative_keywords['challenges']):
            # Response depends on context - does user need help?
            if 'help' in message_lower or 'support' in message_lower:
                # User seeking help - companion feels helpful
                delta.pleasure += 0.05
                delta.dominance += 0.1
            else:
                # User experiencing difficulties - companion empathy
                delta.pleasure -= 0.05
                delta.arousal += 0.05
                delta.dominance -= 0.05

        # Apply sentiment analysis for more nuanced emotion
        sentiment_score = self._get_sentiment_score(user_message)
        delta.pleasure += sentiment_score * 0.1  # Adjust pleasure based on overall sentiment

        return delta

    def _has_positive_sentiment(self, message: str) -> bool:
        """Check if message has positive sentiment"""
        message_lower = message.lower()
        positive_count = sum(1 for word in sum(self.positive_keywords.values(), []) 
                            if word in message_lower)
        negative_count = sum(1 for word in sum(self.negative_keywords.values(), []) 
                            if word in message_lower)
        return positive_count > negative_count

    def _has_negative_sentiment(self, message: str) -> bool:
        """Check if message has negative sentiment"""
        message_lower = message.lower()
        positive_count = sum(1 for word in sum(self.positive_keywords.values(), []) 
                            if word in message_lower)
        negative_count = sum(1 for word in sum(self.negative_keywords.values(), []) 
                            if word in message_lower)
        return negative_count > positive_count

    def _get_sentiment_score(self, message: str) -> float:
        """Get a sentiment score between -1 (negative) and 1 (positive)"""
        message_lower = message.lower()
        
        positive_count = 0
        negative_count = 0
        
        # Count positive words
        for category in self.positive_keywords.values():
            for word in category:
                if word in message_lower:
                    positive_count += 1
        
        # Count negative words
        for category in self.negative_keywords.values():
            for word in category:
                if word in message_lower:
                    negative_count += 1
        
        # Calculate normalized score
        total_sentiment_words = positive_count + negative_count
        if total_sentiment_words == 0:
            return 0.0
        
        return (positive_count - negative_count) / total_sentiment_words

    async def assess_goal_relevance(self, user_message: str, personality: PersonalitySnapshot) -> Dict[str, Any]:
        """
        Assess how the user message relates to the companion's goals and values
        based on personality traits and needs
        """
        assessment = {
            'relevance_score': 0.0,
            'goal_type': 'other',
            'affect_type': 'neutral',
            'intensity': 0.0,
            'coping_potential': 0.0,
            'expectedness': 0.0
        }
        
        message_lower = user_message.lower()
        
        # Check for goal-relevant content based on personality traits
        if personality.big_five.extraversion > 0.6:
            # User is more extroverted - social content is more relevant
            if any(word in message_lower for word in self.social_keywords):
                assessment['relevance_score'] += 0.3
                assessment['goal_type'] = 'social'
        
        if personality.big_five.openness > 0.6:
            # User is more open - novel/exploratory content is more relevant
            if any(word in message_lower for word in self.anticipation_keywords + self.surprise_keywords):
                assessment['relevance_score'] += 0.2
                assessment['goal_type'] = 'exploration'
        
        if personality.big_five.agreeableness > 0.6:
            # User is more agreeable - harmony/helpful content is more relevant
            if 'help' in message_lower or 'support' in message_lower:
                assessment['relevance_score'] += 0.2
                assessment['goal_type'] = 'harmony'
        
        if personality.big_five.conscientiousness > 0.6:
            # User is more conscientious - achievement/progress content is more relevant
            if any(word in message_lower for word in self.positive_keywords['achievement'] + 
                  self.positive_keywords['success']):
                assessment['relevance_score'] += 0.2
                assessment['goal_type'] = 'achievement'
        
        # Assess affect type based on OCC model
        if assessment['relevance_score'] > 0.5:
            if self._has_positive_sentiment(user_message):
                if assessment['goal_type'] == 'achievement':
                    assessment['affect_type'] = 'joy/pride'
                    assessment['intensity'] = 0.8
                elif assessment['goal_type'] == 'social':
                    assessment['affect_type'] = 'love/affection'
                    assessment['intensity'] = 0.7
            elif self._has_negative_sentiment(user_message):
                if assessment['goal_type'] == 'achievement':
                    assessment['affect_type'] = 'shame/disappointment'
                    assessment['intensity'] = 0.6
                elif assessment['goal_type'] == 'social':
                    assessment['affect_type'] = 'sadness/loneliness'
                    assessment['intensity'] = 0.5
        
        return assessment

    async def calculate_emotional_response(self, user_message: str, personality: PersonalitySnapshot) -> PADState:
        """
        Calculates the emotional response delta using an AI-driven OCC appraisal.
        """
        prompt = f"""
        Analyze the user's message using the OCC cognitive appraisal model to determine an emotional response delta.
        Consider the AI's personality:
        - Neuroticism: {personality.big_five.neuroticism:.2f} (higher means stronger reactions)
        - Agreeableness: {personality.big_five.agreeableness:.2f} (higher means more positive reactions to prosocial messages)

        User Message: "{user_message}"

        Based on the message and personality, evaluate these OCC components:
        1. Desirability: Is the event in the message good or bad for the user/AI? (Score -1.0 to 1.0)
        2. Praiseworthiness: Is the user's action praiseworthy or blameworthy? (Score -1.0 to 1.0)
        3. Expectedness: How surprising is this event? (Score 0.0 for expected, 1.0 for very surprising)

        From these, determine the change (delta) in the AI's PAD state (Pleasure, Arousal, Dominance).
        - Pleasure delta is mainly influenced by Desirability.
        - Arousal delta is mainly influenced by Expectedness.
        - Dominance delta is mainly influenced by Praiseworthiness (praise increases dominance/confidence).

        Respond in JSON format:
        {{
          "pleasure_delta": float,
          "arousal_delta": float,
          "dominance_delta": float
        }}
        """
        
        try:
            response_json = await self.groq.analyze_json_response(prompt, max_tokens=150)
            delta = PADState(
                pleasure=response_json.get("pleasure_delta", 0.0),
                arousal=response_json.get("arousal_delta", 0.0),
                dominance=response_json.get("dominance_delta", 0.0)
            )
            
            # Amplify based on neuroticism
            neuroticism_factor = 1.0 + (personality.big_five.neuroticism * 0.5)
            delta.pleasure *= neuroticism_factor
            delta.arousal *= neuroticism_factor
            
            return delta
        except Exception as e:
            self.logger.error(f"AI-enhanced appraisal failed: {e}. Falling back to basic appraisal.")
            return self.calculate_emotion_delta(user_message, {}) # Fallback to old method

    def _calculate_appraisal_components(self, event: str, personality: PersonalitySnapshot) -> Dict[str, float]:
        """
        Calculate the core components of OCC appraisal:
        - Desirability: How desirable is this outcome?
        - Praiseworthiness: How praiseworthy was the action?
        - Like/Dislike: How do I feel about this agent?
        """
        components = {
            'desirability': 0.0,
            'praiseworthiness': 0.0,
            'like_dislike': 0.0,
            'personal_relevance': 0.0
        }
        
        event_lower = event.lower()
        
        # Desirability - based on if the event benefits the companion or user
        if any(word in event_lower for word in self.positive_keywords['achievement']):
            components['desirability'] = 0.7  # Positive for achievements
        elif any(word in event_lower for word in self.negative_keywords['failure']):
            components['desirability'] = -0.5  # Negative for failures
        
        # Praiseworthiness - how praiseworthy is the user's action
        praiseworthy_actions = ['helped', 'supported', 'thanked', 'appreciated']
        if any(word in event_lower for word in praiseworthy_actions):
            components['praiseworthiness'] = 0.8
        
        # Like-dislike - feelings towards user based on their behavior
        if self._has_positive_sentiment(event):
            components['like_dislike'] = 0.5  # Positive sentiment increases liking
        elif self._has_negative_sentiment(event):
            components['like_dislike'] = -0.3  # Negative sentiment decreases liking
        
        # Personal relevance based on personality
        if personality.big_five.extraversion > 0.6 and any(word in event_lower for word in self.social_keywords):
            components['personal_relevance'] = 0.6
        elif personality.big_five.conscientiousness > 0.6 and any(word in event_lower for word in self.positive_keywords['achievement']):
            components['personal_relevance'] = 0.5
        
        return components

    async def generate_emotional_state(self, user_message: str, current_state: PADState, 
                                      personality: PersonalitySnapshot) -> PADState:
        """
        Generate new emotional state based on user message and current state
        """
        # Calculate emotional response to new event
        response_delta = await self.calculate_emotional_response(user_message, personality)
        
        # Calculate appraisal components
        appraisal = self._calculate_appraisal_components(user_message, personality)
        
        # Weight the response by relevance and importance
        weighted_delta = PADState(
            pleasure=response_delta.pleasure * (0.5 + 0.5 * appraisal['personal_relevance']),
            arousal=response_delta.arousal * (0.5 + 0.5 * (appraisal['desirability'] + 1.0) / 2),
            dominance=response_delta.dominance * (0.5 + 0.5 * (appraisal['praiseworthiness'] + 1.0) / 2)
        )
        
        # Apply to current state
        new_pleasure = current_state.pleasure + weighted_delta.pleasure
        new_arousal = current_state.arousal + weighted_delta.arousal
        new_dominance = current_state.dominance + weighted_delta.dominance
        
        # Clamp to valid ranges
        new_pleasure = max(-1.0, min(1.0, new_pleasure))
        new_arousal = max(-1.0, min(1.0, new_arousal))
        new_dominance = max(-1.0, min(1.0, new_dominance))
        
        return PADState(
            pleasure=new_pleasure,
            arousal=new_arousal,
            dominance=new_dominance,
            emotion_label=self._determine_emotion_label(new_pleasure, new_arousal, new_dominance)
        )

    def _determine_emotion_label(self, pleasure: float, arousal: float, dominance: float) -> str:
        """
        Map PAD coordinates to emotional labels
        """
        if pleasure > 0.5 and arousal > 0.5:
            return "excited" if dominance > 0 else "delighted"
        elif pleasure > 0.5 and arousal <= 0.5:
            return "content" if dominance > 0 else "serene"
        elif pleasure <= 0.5 and arousal > 0.5:
            return "angry" if dominance > 0 else "tense"
        elif pleasure <= 0.5 and arousal <= 0.5:
            return "depressed" if dominance <= 0 else "bored"
        else:
            return "neutral"

    async def appraise_interaction(self, interaction: InteractionRecord, personality: PersonalitySnapshot) -> Dict[str, Any]:
        """
        Perform a complete appraisal of an interaction using the OCC model
        """
        appraisal_result = {
            'timestamp': datetime.utcnow(),
            'event': interaction.user_message,
            'basic_appraisal': self.calculate_emotion_delta(interaction.user_message, {}),
            'goal_relevance': await self.assess_goal_relevance(interaction.user_message, personality),
            'appraisal_components': self._calculate_appraisal_components(interaction.user_message, personality),
            'predicted_emotional_response': await self.calculate_emotional_response(interaction.user_message, personality),
            'contextual_modifiers': {}
        }
        
        # Add contextual modifiers based on previous state
        if interaction.pad_before:
            prev_pleasure = interaction.pad_before.pleasure if hasattr(interaction.pad_before, 'pleasure') else interaction.pad_before.get('pleasure', 0)
            
            # If previous state was very positive, same positive event might have less impact
            if prev_pleasure > 0.7:
                appraisal_result['contextual_modifiers']['habituation_factor'] = 0.7
            elif prev_pleasure < -0.5:
                # If previous state was negative, positive events might have more impact
                appraisal_result['contextual_modifiers']['contrast_factor'] = 1.3
        
        return appraisal_result

    def _calculate_anticipation_impact(self, message: str) -> float:
        """
        Calculate the emotional impact of anticipated events
        """
        anticipation_words = self.anticipation_keywords
        if any(word in message.lower() for word in anticipation_words):
            # Anticipation typically increases arousal
            return 0.15
        return 0.0

    def _adjust_for_stimulus_quality(self, message: str, base_delta: PADState) -> PADState:
        """
        Adjust the basic emotional delta based on stimulus quality factors
        """
        # Length of message might indicate engagement level
        if len(message) > 100:
            # Longer messages may indicate deeper engagement
            base_delta.arousal += 0.05
        
        # Number of exclamation points might indicate excitement
        exclamation_count = message.count('!')
        if exclamation_count > 0:
            base_delta.arousal += min(0.15, exclamation_count * 0.05)
            if exclamation_count > 2:
                base_delta.pleasure += 0.05  # Very excited!
        
        # Number of question marks might indicate curiosity or concern
        question_count = message.count('?')
        if question_count > 1:
            base_delta.arousal += 0.1  # Uncertainty increases arousal
            base_delta.dominance -= 0.05  # Questions might decrease dominance
        
        return base_delta
