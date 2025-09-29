"""
OCC Appraisal Engine for AI Companion System
Calculates emotional changes based on user interactions using the OCC model.
"""
from typing import Dict, Any, List
import re
import logging
from dataclasses import dataclass

from ..models.personality import PADState

logger = logging.getLogger(__name__)

@dataclass
class AppraisalResult:
    """Result of OCC appraisal calculation"""
    pad_delta: PADState
    appraisal_factors: Dict[str, float]
    confidence: float
    explanation: str

class AppraisalEngine:
    """
    Implements the OCC (Ortony, Clore, Collins) cognitive appraisal model
    for calculating emotional responses to user interactions.
    """
    
    def __init__(self):
        # OCC appraisal categories and their PAD mappings
        self.appraisal_rules = {
            'goal_outcome': {
                'achieved': PADState(pleasure=0.3, arousal=0.1, dominance=0.2),
                'failed': PADState(pleasure=-0.2, arousal=0.2, dominance=-0.1),
                'attempted': PADState(pleasure=0.1, arousal=0.1, dominance=0.05)
            },
            'event_affect': {
                'positive': PADState(pleasure=0.2, arousal=0.1, dominance=0.1),
                'negative': PADState(pleasure=-0.2, arousal=0.1, dominance=-0.1)
            },
            'agent_action': {
                'praise': PADState(pleasure=0.4, arousal=0.05, dominance=0.3),
                'criticism': PADState(pleasure=-0.3, arousal=0.1, dominance=-0.2),
                'help': PADState(pleasure=0.25, arousal=0.05, dominance=0.15),
                'hinder': PADState(pleasure=-0.25, arousal=0.1, dominance=-0.15)
            },
            'object_appraisal': {
                'like': PADState(pleasure=0.15, arousal=0.05, dominance=0.1),
                'dislike': PADState(pleasure=-0.15, arousal=0.05, dominance=-0.1)
            }
        }
        
        # Sentiment analysis keywords
        self.positive_keywords = {
            'achieved', 'succeeded', 'completed', 'finished', 'won', 'excellent', 'amazing', 
            'wonderful', 'fantastic', 'brilliant', 'outstanding', 'perfect', 'incredible',
            'awesome', 'great', 'good', 'nice', 'happy', 'pleased', 'delighted', 'thrilled',
            'excited', 'grateful', 'thankful', 'appreciated', 'valued', 'respected', 'loved'
        }
        
        self.negative_keywords = {
            'failed', 'lost', 'missed', 'ruined', 'broken', 'terrible', 'awful', 'horrible',
            'disgusting', 'hate', 'dislike', 'angry', 'frustrated', 'annoyed', 'disappointed',
            'upset', 'sad', 'depressed', 'worried', 'anxious', 'stressed', 'exhausted', 'bored'
        }
        
        # Context-sensitive appraisal modifiers
        self.context_modifiers = {
            'intimate': 1.2,    # Close relationships amplify emotions
            'formal': 0.8,      # Formal contexts dampen emotions
            'urgent': 1.3,      # Urgent situations intensify emotions
            'casual': 1.0       # Baseline
        }

    def calculate_emotion_delta(self, user_message: str, context: Dict[str, Any] = None) -> AppraisalResult:
        """
        Calculate PAD state delta based on user message using OCC appraisal rules.
        
        SPECIFIC RULE-BASED MAPPING from MASTER_IMPLEMENTATION_GUIDE.md:
        - Goal Achievement: +pleasure, +arousal, +dominance
        - Goal Failure: -pleasure, +arousal (frustration), -dominance
        - User Compliments: +pleasure, +arousal, +dominance
        - Unexpected Events: +arousal, +/- pleasure based on sentiment
        - Social Connection: +pleasure, +arousal, +dominance
        """
        if context is None:
            context = {}
            
        pad_delta = PADState(pleasure=0.0, arousal=0.0, dominance=0.0)
        appraisal_factors = {}
        confidence = 0.0
        explanations = []
        
        # Normalize message for processing
        message_lower = user_message.lower().strip()
        
        # 1. Goal Outcome Appraisal
        goal_delta, goal_confidence, goal_explanation = self._appraise_goal_outcome(message_lower)
        if goal_confidence > 0:
            pad_delta.pleasure += goal_delta.pleasure
            pad_delta.arousal += goal_delta.arousal
            pad_delta.dominance += goal_delta.dominance
            appraisal_factors['goal_outcome'] = goal_confidence
            confidence = max(confidence, goal_confidence)
            if goal_explanation:
                explanations.append(goal_explanation)
        
        # 2. Agent Action Appraisal (user's action toward companion)
        agent_delta, agent_confidence, agent_explanation = self._appraise_agent_action(message_lower)
        if agent_confidence > 0:
            pad_delta.pleasure += agent_delta.pleasure
            pad_delta.arousal += agent_delta.arousal
            pad_delta.dominance += agent_delta.dominance
            appraisal_factors['agent_action'] = agent_confidence
            confidence = max(confidence, agent_confidence)
            if agent_explanation:
                explanations.append(agent_explanation)
        
        # 3. Event Affect Appraisal (general sentiment)
        event_delta, event_confidence, event_explanation = self._appraise_event_affect(message_lower)
        if event_confidence > 0:
            pad_delta.pleasure += event_delta.pleasure
            pad_delta.arousal += event_delta.arousal
            pad_delta.dominance += event_delta.dominance
            appraisal_factors['event_affect'] = event_confidence
            confidence = max(confidence, event_confidence)
            if event_explanation:
                explanations.append(event_explanation)
        
        # 4. Object Appraisal (attitude toward topics/objects)
        object_delta, object_confidence, object_explanation = self._appraise_object_attitude(message_lower)
        if object_confidence > 0:
            pad_delta.pleasure += object_delta.pleasure
            pad_delta.arousal += object_delta.arousal
            pad_delta.dominance += object_delta.dominance
            appraisal_factors['object_appraisal'] = object_confidence
            confidence = max(confidence, object_confidence)
            if object_explanation:
                explanations.append(object_explanation)
        
        # Apply context modifiers
        context_type = context.get('context_type', 'casual')
        modifier = self.context_modifiers.get(context_type, 1.0)
        
        pad_delta.pleasure *= modifier
        pad_delta.arousal *= modifier
        pad_delta.dominance *= modifier
        
        # Clamp values to valid PAD range
        pad_delta.pleasure = max(-1.0, min(1.0, pad_delta.pleasure))
        pad_delta.arousal = max(-1.0, min(1.0, pad_delta.arousal))
        pad_delta.dominance = max(-1.0, min(1.0, pad_delta.dominance))
        
        explanation = "; ".join(explanations) if explanations else "No significant emotional content detected"
        
        return AppraisalResult(
            pad_delta=pad_delta,
            appraisal_factors=appraisal_factors,
            confidence=confidence,
            explanation=explanation
        )

    def _appraise_goal_outcome(self, message: str) -> tuple:
        """Appraise goal-related outcomes in user message"""
        # Goal achievement keywords
        achievement_patterns = [
            r'\b(finished|completed|achieved|succeeded|won|accomplished)\b',
            r'\b(got|received|obtained) (.+?)\b',
            r'\b(made it|did it|nailed it)\b'
        ]
        
        # Goal failure keywords
        failure_patterns = [
            r'\b(failed|couldn\'t|didn\'t work|gave up|impossible|lost)\b',
            r'\b(missed|ruined|broke|destroyed)\b',
            r'\b(couldn\'t make it|didn\'t succeed)\b'
        ]
        
        # Check for achievement patterns
        for pattern in achievement_patterns:
            if re.search(pattern, message):
                confidence = 0.8 if 'amazing' in message or 'excellent' in message else 0.6
                explanation = f"Goal achievement detected: {pattern}"
                return (self.appraisal_rules['goal_outcome']['achieved'], confidence, explanation)
        
        # Check for failure patterns
        for pattern in failure_patterns:
            if re.search(pattern, message):
                confidence = 0.7 if 'frustrated' in message or 'angry' in message else 0.5
                explanation = f"Goal failure detected: {pattern}"
                return (self.appraisal_rules['goal_outcome']['failed'], confidence, explanation)
        
        return (PADState(pleasure=0.0, arousal=0.0, dominance=0.0), 0.0, "")

    def _appraise_agent_action(self, message: str) -> tuple:
        """Appraise user actions toward the companion (praise, criticism, etc.)"""
        # Praise patterns (user complimenting the companion)
        praise_patterns = [
            r'\b(you are|you\'re) (great|amazing|wonderful|fantastic|brilliant|awesome)\b',
            r'\b(thank you|thanks|thankful|appreciate) (.+?)\b',
            r'\b(you helped|you\'re helpful|so useful)\b',
            r'\b(best (ai|assistant|companion))\b'
        ]
        
        # Criticism patterns
        criticism_patterns = [
            r'\b(you are|you\'re) (stupid|useless|annoying|terrible|awful)\b',
            r'\b(you failed|you didn\'t help|not helpful)\b',
            r'\b(disappointed by|frustrated with) (you|your response)\b'
        ]
        
        # Help-seeking patterns (user asking for assistance)
        help_patterns = [
            r'\b(need help|help me|can you help|assist me)\b',
            r'\b(don\'t understand|confused|unclear)\b',
            r'\b(looking for advice|need advice|guidance)\b'
        ]
        
        # Check for praise
        for pattern in praise_patterns:
            if re.search(pattern, message):
                confidence = 0.9 if 'love' in message or 'best' in message else 0.7
                explanation = f"User praise detected: {pattern}"
                return (self.appraisal_rules['agent_action']['praise'], confidence, explanation)
        
        # Check for criticism
        for pattern in criticism_patterns:
            if re.search(pattern, message):
                confidence = 0.8
                explanation = f"User criticism detected: {pattern}"
                return (self.appraisal_rules['agent_action']['criticism'], confidence, explanation)
        
        # Check for help-seeking
        for pattern in help_patterns:
            if re.search(pattern, message):
                confidence = 0.6
                explanation = f"User seeking help: {pattern}"
                return (self.appraisal_rules['agent_action']['help'], confidence, explanation)
        
        return (PADState(pleasure=0.0, arousal=0.0, dominance=0.0), 0.0, "")

    def _appraise_event_affect(self, message: str) -> tuple:
        """Appraise general emotional content in user message"""
        positive_count = sum(1 for word in self.positive_keywords if word in message)
        negative_count = sum(1 for word in self.negative_keywords if word in message)
        
        if positive_count > 0 and negative_count == 0:
            confidence = min(0.8, positive_count * 0.2)
            explanation = f"Positive sentiment detected ({positive_count} positive keywords)"
            return (self.appraisal_rules['event_affect']['positive'], confidence, explanation)
        elif negative_count > 0 and positive_count == 0:
            confidence = min(0.8, negative_count * 0.2)
            explanation = f"Negative sentiment detected ({negative_count} negative keywords)"
            return (self.appraisal_rules['event_affect']['negative'], confidence, explanation)
        elif positive_count > 0 and negative_count > 0:
            # Mixed sentiment - net effect
            net_sentiment = positive_count - negative_count
            if net_sentiment > 0:
                confidence = min(0.6, net_sentiment * 0.15)
                explanation = f"Mixed sentiment, net positive ({positive_count} positive, {negative_count} negative)"
                return (self.appraisal_rules['event_affect']['positive'], confidence, explanation)
            elif net_sentiment < 0:
                confidence = min(0.6, abs(net_sentiment) * 0.15)
                explanation = f"Mixed sentiment, net negative ({positive_count} positive, {negative_count} negative)"
                return (self.appraisal_rules['event_affect']['negative'], confidence, explanation)
        
        return (PADState(pleasure=0.0, arousal=0.0, dominance=0.0), 0.0, "")

    def _appraise_object_attitude(self, message: str) -> tuple:
        """Appraise user's attitude toward objects/topics"""
        # Like/dislike expressions
        like_patterns = [
            r'\b(love|adore|enjoy|like) (music|movies|books|games|art|sports)\b',
            r'\b(favorite|passion for|interested in)\b',
            r'\b(excited about|looking forward to)\b'
        ]
        
        dislike_patterns = [
            r'\b(hate|dislike|can\'t stand) (music|movies|books|games|art|sports)\b',
            r'\b(bored of|tired of|over it)\b',
            r'\b(not interested in|don\'t care about)\b'
        ]
        
        # Check for like patterns
        for pattern in like_patterns:
            if re.search(pattern, message):
                confidence = 0.5
                explanation = f"Positive object attitude detected: {pattern}"
                return (self.appraisal_rules['object_appraisal']['like'], confidence, explanation)
        
        # Check for dislike patterns
        for pattern in dislike_patterns:
            if re.search(pattern, message):
                confidence = 0.5
                explanation = f"Negative object attitude detected: {pattern}"
                return (self.appraisal_rules['object_appraisal']['dislike'], confidence, explanation)
        
        return (PADState(pleasure=0.0, arousal=0.0, dominance=0.0), 0.0, "")

    def get_emotion_label(self, pad_state: PADState) -> str:
        """
        Convert PAD state to emotion label based on octant mapping.
        """
        p, a, d = pad_state.pleasure > 0, pad_state.arousal > 0, pad_state.dominance > 0
        mapping = {
            (True, True, True): "exuberant",
            (True, True, False): "bored",
            (True, False, True): "relaxed",
            (True, False, False): "sleepy",
            (False, True, True): "anxious",
            (False, True, False): "stressed",
            (False, False, True): "calm",
            (False, False, False): "depressed"
        }
        return mapping.get((p, a, d), "neutral")
