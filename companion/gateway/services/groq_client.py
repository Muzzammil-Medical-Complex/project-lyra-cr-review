"""
Groq API client for the AI Companion System.

This module provides a wrapper around the Groq API for fast LLM operations
like scoring and security analysis.
"""

import httpx
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from ..utils.exceptions import ServiceUnavailableError


class GroqClient:
    """
    A client for interacting with the Groq API for fast LLM operations.
    """
    
    def __init__(self, api_key: str, model: str = "llama-4-maverick"):
        """
        Initialize the Groq client.
        
        Args:
            api_key: Groq API key
            model: Model to use for completions
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
        self.logger = logging.getLogger(__name__)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate a chat completion using the Groq API.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to instance model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            API response dictionary
            
        Raises:
            ServiceUnavailableError: If API call fails
        """
        model = model or self.model
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise ServiceUnavailableError(
                    service_name="Groq",
                    message=f"API request failed with status {response.status_code}: {response.text}"
                )
                
        except httpx.RequestError as e:
            self.logger.exception("Groq API request error")
            raise ServiceUnavailableError(
                service_name="Groq",
                message=f"Request error: {e}"
            ) from e
        except Exception as e:
            self.logger.exception("Unexpected error in Groq API call")
            raise ServiceUnavailableError(
                service_name="Groq",
                message=f"Unexpected error: {e}"
            ) from e
    
    async def _request_with_backoff(
        self,
        endpoint: str,
        data: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make a request with exponential backoff for rate limiting.
        
        Args:
            endpoint: API endpoint
            data: Request data
            max_retries: Maximum number of retry attempts
            
        Returns:
            API response dictionary
        """
        import random
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/{endpoint}",
                    json=data
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    if attempt == max_retries - 1:
                        raise ServiceUnavailableError(
                            service_name="Groq",
                            message="Rate limit exceeded after max retries"
                        )
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                else:
                    raise ServiceUnavailableError(
                        service_name="Groq",
                        message=f"API request failed with status {response.status_code}: {response.text}"
                    )
                    
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise ServiceUnavailableError(
                        service_name="Groq",
                        message=f"Request error after max retries: {str(e)}"
                    )
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)
    
    async def score_importance(self, content: str, context: Dict[str, Any]) -> float:
        """
        Score memory importance using Groq API.

        Args:
            content: Content to score
            context: Context for scoring

        Returns:
            Importance score between 0.0 and 1.0
        """
        raise NotImplementedError("score_importance not implemented - use ImportanceScorer instead")
    
    async def detect_threat(self, message: str, threat_types: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect security threats in user messages.

        Args:
            message: User message to analyze
            threat_types: Types of threats to check for
            context: Additional context for analysis

        Returns:
            Threat analysis result
        """
        raise NotImplementedError("detect_threat not implemented - use SemanticInjectionDetector instead")

    async def health_check(self) -> bool:
        """
        Check if the Groq API is accessible and responding.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Make a minimal API call to test connectivity
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                    "temperature": 0.0
                }
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Groq health check failed: {e}")
            return False

    async def analyze_json_response(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.2) -> Dict[str, Any]:
        """
        Executes a prompt that is expected to return a JSON object and parses it.
        Includes retry logic for parsing errors.
        """
        for attempt in range(2): # Try up to 2 times
            try:
                response_dict = await self.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                # Extract content from the response dictionary
                response_text = response_dict['choices'][0]['message']['content']

                # Ensure response_text is a string before cleaning
                if not isinstance(response_text, str):
                    response_text = json.dumps(response_text)

                # Clean the response to ensure it's valid JSON
                clean_response = response_text.strip().replace("```json", "").replace("```", "").strip()
                return json.loads(clean_response)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                # Safely reference response_text for logging
                try:
                    text_preview = response_text[:200] if 'response_text' in locals() else str(response_dict)[:200]
                except:
                    text_preview = "Unable to extract response preview"
                self.logger.warning(f"Failed to parse JSON response on attempt {attempt + 1}: {e}. Response: {text_preview}")
                if attempt == 1:
                    raise ServiceUnavailableError("GroqClient", "Failed to get valid JSON response after multiple attempts.")
                await asyncio.sleep(1) # Wait before retrying
        return {} # Should not be reached

    async def analyze_behavioral_changes(self, interactions: List[Dict[str, Any]], analysis_focus: List[str]) -> Dict[str, Any]:
        """
        Analyze behavioral changes in user interactions.

        Args:
            interactions: List of interaction data
            analysis_focus: List of analysis focus areas

        Returns:
            Dictionary containing detected changes and confidence
        """
        prompt = f"""
        Analyze the following user interactions for behavioral changes and patterns.

        Interactions:
        {json.dumps(interactions, indent=2)}

        Analysis Focus:
        {', '.join(analysis_focus)}

        Return a JSON object with the following structure:
        {{
            "detected_changes": [
                {{
                    "type": "change_type",
                    "description": "description of change",
                    "confidence": 0.0-1.0,
                    "evidence": ["supporting evidence"]
                }}
            ],
            "confidence": 0.0-1.0,
            "communication_evolution": {{
                "style_changes": "description",
                "frequency_changes": "description",
                "emotional_tone_changes": "description"
            }}
        }}
        """

        try:
            response = await self.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )

            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback response
                return {
                    "detected_changes": [],
                    "confidence": 0.5,
                    "communication_evolution": {
                        "style_changes": "No significant changes detected",
                        "frequency_changes": "No significant changes detected",
                        "emotional_tone_changes": "No significant changes detected"
                    }
                }

        except Exception as e:
            self.logger.exception("Failed to analyze behavioral changes")
            # Return safe fallback
            return {
                "detected_changes": [],
                "confidence": 0.5,
                "communication_evolution": {
                    "style_changes": "Analysis failed",
                    "frequency_changes": "Analysis failed",
                    "emotional_tone_changes": "Analysis failed"
                }
            }

    async def detect_conversation_patterns(self, interactions: List[Dict[str, Any]], pattern_types: List[str]) -> Dict[str, Any]:
        """
        Detect recurring patterns in conversation data.

        Args:
            interactions: List of interaction data
            pattern_types: Types of patterns to detect

        Returns:
            Dictionary containing detected patterns
        """
        prompt = f"""
        Analyze the following conversation interactions for recurring patterns.

        Interactions:
        {json.dumps(interactions, indent=2)}

        Pattern Types to Detect:
        {', '.join(pattern_types)}

        Return a JSON object with the following structure:
        {{
            "patterns": [
                {{
                    "pattern_type": "pattern_type",
                    "description": "description of pattern",
                    "confidence": 0.0-1.0,
                    "frequency": "how often this pattern occurs",
                    "strength": 0.0-1.0,
                    "metadata": {{
                        "time_preference": "preferred time if temporal",
                        "duration_preference": "preferred length if duration",
                        "additional_details": "other relevant details"
                    }}
                }}
            ]
        }}
        """

        try:
            response = await self.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )

            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback response
                return {"patterns": []}

        except Exception as e:
            self.logger.exception("Failed to detect conversation patterns")
            # Return safe fallback
            return {"patterns": []}

    async def analyze_emotional_patterns(self, emotion_data: List[Dict[str, Any]], trend_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze emotional patterns and trends.

        Args:
            emotion_data: List of emotional state data
            trend_analysis: Pre-calculated trend metrics

        Returns:
            Dictionary containing emotional insights
        """
        prompt = f"""
        Analyze the following emotional data for patterns and insights.

        Emotion Data:
        {json.dumps(emotion_data, indent=2)}

        Trend Analysis:
        {json.dumps(trend_analysis, indent=2)}

        Return a JSON object with the following structure:
        {{
            "insights": [
                "insight about emotional patterns",
                "another insight"
            ],
            "stability_score": 0.0-1.0,
            "confidence": 0.0-1.0,
            "key_findings": {{
                "overall_emotional_state": "description",
                "notable_patterns": ["pattern1", "pattern2"],
                "recommendations": ["recommendation1", "recommendation2"]
            }}
        }}
        """

        try:
            response = await self.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )

            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback response
                return {
                    "insights": ["Unable to analyze emotional patterns"],
                    "stability_score": 0.5,
                    "confidence": 0.5,
                    "key_findings": {
                        "overall_emotional_state": "Analysis failed",
                        "notable_patterns": [],
                        "recommendations": []
                    }
                }

        except Exception as e:
            self.logger.exception("Failed to analyze emotional patterns")
            # Return safe fallback
            return {
                "insights": ["Emotional pattern analysis failed"],
                "stability_score": 0.5,
                "confidence": 0.5,
                "key_findings": {
                    "overall_emotional_state": "Analysis failed",
                    "notable_patterns": [],
                    "recommendations": []
                }
            }

    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
