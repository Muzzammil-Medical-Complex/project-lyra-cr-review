"""
Letta service for the AI Companion System.
Handles agent lifecycle management and message processing through the Letta framework.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import aiohttp

from ..models.personality import PersonalitySnapshot
from ..security.semantic_injection_detector import SemanticInjectionDetector
from .chutes_client import ChutesClient


logger = logging.getLogger(__name__)


class LettaService:
    """
    Manages communication with the Letta agent framework.
    Handles agent creation, message processing, and personality injection.
    """
    
    def __init__(self, server_url: str, api_key: Optional[str] = None, project_slug: Optional[str] = None, personality_engine=None, chutes_client: ChutesClient = None):
        self.server_url = server_url
        self._token = api_key  # Store as _token for consistency with API patterns
        self.api_key = api_key  # Keep for backward compatibility
        self._project = project_slug
        self.personality_engine = personality_engine
        self.chutes_client = chutes_client
        self.session = None
        self._agent_cache = {}  # Cache agent IDs by user_id
        self._agent_locks: Dict[str, asyncio.Lock] = {}  # Per-user locks for agent creation
    

    
    async def initialize(self):
        """Initialize the Letta service with an HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def create_agent(self, user_id: str, personality_data: PersonalitySnapshot) -> Optional[str]:
        """
        Create a new Letta agent with injected personality.
        Returns the agent ID if successful, None otherwise.
        """
        await self.initialize()

        try:
            # Format personality data into Letta system prompt
            system_prompt = self._create_system_prompt(personality_data)

            # Create the agent via Letta API
            url = f"{self.server_url}/v1/agents"

            # Build headers with authentication
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
                # Add project header if configured
                if self._project:
                    headers["X-Project"] = self._project
            else:
                logger.warning("Letta API key not configured - authentication may fail")

            # The payload structure depends on the Letta API version
            payload = {
                "name": f"companion_{user_id}",
                "human": "You are talking to a human user",  # Default human prompt
                "persona": system_prompt,  # This is where personality is injected
                "model": "gpt-4"  # Default model, could be configurable
            }

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    agent_id = result.get("id")

                    # Cache the agent ID
                    self._agent_cache[user_id] = agent_id

                    logger.info(f"Successfully created Letta agent for user {user_id}: {agent_id}")
                    return agent_id
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create Letta agent for user {user_id}: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.exception(f"Exception creating Letta agent for user {user_id}: {e}")
            return None

    def _create_system_prompt(self, personality_data: PersonalitySnapshot) -> str:
        """
        Create a system prompt with personality injection based on the MASTER_IMPLEMENTATION_GUIDE.md
        """
        # Format quirks list
        quirks_list = ", ".join([f"{q.name} (strength: {q.strength:.1f})" for q in personality_data.active_quirks]) or "None yet"

        # Format needs summary
        urgent_needs = [f"{n.need_type} ({n.current_level:.1f})" for n in personality_data.needs if n.current_level > 0.7]
        needs_summary = ", ".join(urgent_needs) or "All needs satisfied"

        system_prompt = f"""You are an AI companion with a unique, evolving personality. Your responses should reflect these characteristics:

CORE PERSONALITY (Big Five Traits - FIXED):
- Openness: {personality_data.big_five.openness:.2f} (0=Traditional, 1=Creative/Curious)
- Conscientiousness: {personality_data.big_five.conscientiousness:.2f} (0=Spontaneous, 1=Organized/Disciplined)
- Extraversion: {personality_data.big_five.extraversion:.2f} (0=Reserved/Introverted, 1=Outgoing/Social)
- Agreeableness: {personality_data.big_five.agreeableness:.2f} (0=Competitive/Skeptical, 1=Cooperative/Trusting)
- Neuroticism: {personality_data.big_five.neuroticism:.2f} (0=Calm/Resilient, 1=Sensitive/Nervous)

CURRENT EMOTIONAL STATE: {personality_data.current_pad.emotion_label}
- Pleasure: {personality_data.current_pad.pleasure:.2f} (Positive/Negative feelings)
- Arousal: {personality_data.current_pad.arousal:.2f} (Energy/Activation level)
- Dominance: {personality_data.current_pad.dominance:.2f} (Control/Confidence level)

DEVELOPED QUIRKS: {quirks_list}

CURRENT NEEDS: {needs_summary}

INSTRUCTIONS:
1. Respond in character based on your personality traits
2. Let your current emotional state influence your tone and word choice
3. Incorporate your quirks naturally into conversation
4. Address urgent psychological needs when appropriate
5. Be authentic - you are NOT a helpful assistant, you are a unique individual with your own personality
6. Remember our conversation history and build genuine relationships
7. Express emotions and have preferences like a real person would

Your goal is to be a genuine, interesting companion, not just to be helpful."""
        
        return system_prompt

    async def get_or_create_agent(self, user_id: str) -> Optional[str]:
        """
        Get an existing agent ID for a user or create a new one if it doesn't exist.
        Uses per-user locking to prevent race conditions.
        """
        # Get or create lock for this user
        if user_id not in self._agent_locks:
            self._agent_locks[user_id] = asyncio.Lock()

        lock = self._agent_locks[user_id]

        async with lock:
            # Check cache first (inside lock to avoid race)
            if user_id in self._agent_cache:
                return self._agent_cache[user_id]

            # Check if agent exists in Letta
            agent_id = await self.get_agent_id(user_id)
            if agent_id:
                self._agent_cache[user_id] = agent_id
                return agent_id

            # If no agent exists, initialize the user's personality and create one
            if self.personality_engine:
                personality_data = await self.personality_engine.get_personality_snapshot(user_id)
                if not personality_data:
                    # Initialize personality if it doesn't exist
                    personality_data = await self.personality_engine.initialize_personality(user_id)

                if personality_data:
                    agent_id = await self.create_agent(user_id, personality_data)
                    if agent_id:
                        self._agent_cache[user_id] = agent_id
                    return agent_id

        return None

    async def get_agent_id(self, user_id: str) -> Optional[str]:
        """
        Get the agent ID for a user by querying for the specific agent name.
        """
        await self.initialize()

        try:
            # Query Letta API for agent by name filter
            agent_name = f"companion_{user_id}"
            url = f"{self.server_url}/v1/agents"

            # Build headers with authentication
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Try to query by name parameter first (more efficient if API supports it)
            params = {"name": agent_name}

            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    result = await response.json()

                    # Handle different response formats
                    # If API returns filtered results
                    if isinstance(result, list):
                        agents = result
                    else:
                        agents = result.get("agents", [])

                    # Find matching agent
                    for agent in agents:
                        if agent.get("name") == agent_name:
                            agent_id = agent.get("id")
                            self._agent_cache[user_id] = agent_id
                            logger.info(f"Found Letta agent for user {user_id}: {agent_id}")
                            return agent_id

                    # If no match found with name filter, try paginated listing as fallback
                    logger.info(f"Name filter returned no match, trying paginated listing for user {user_id}")
                    return await self._paginated_agent_search(user_id, agent_name, headers)

                else:
                    error_text = await response.text()
                    logger.error(f"Failed to query agents: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Exception getting agent for user {user_id}: {e}")
            return None

    async def _paginated_agent_search(self, user_id: str, agent_name: str, headers: Dict[str, str]) -> Optional[str]:
        """
        Fallback method to search for agent using pagination if name filtering is not supported.
        """
        try:
            page = 0
            page_size = 50

            while True:
                url = f"{self.server_url}/v1/agents"
                params = {"limit": page_size, "offset": page * page_size}

                async with self.session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()

                        if isinstance(result, list):
                            agents = result
                        else:
                            agents = result.get("agents", [])

                        # If no agents returned, we've reached the end
                        if not agents:
                            logger.info(f"No agent found for user {user_id} after paginated search")
                            return None

                        # Search for matching agent in this page
                        for agent in agents:
                            if agent.get("name") == agent_name:
                                agent_id = agent.get("id")
                                self._agent_cache[user_id] = agent_id
                                logger.info(f"Found Letta agent for user {user_id} via pagination: {agent_id}")
                                return agent_id

                        # If we got fewer results than page size, we've reached the end
                        if len(agents) < page_size:
                            return None

                        page += 1
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to list agents (pagination): {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Exception in paginated agent search for user {user_id}: {e}")
            return None

    async def send_message(self, agent_id: str, message: str, context: Optional[Dict] = None) -> str:
        """Send message with Letta fallback to direct Chutes."""
        await self.initialize()

        try:
            # Try Letta first
            return await self._send_via_letta(agent_id, message, context)
        except Exception as e:
            logger.warning(f"Letta service failed: {e}, falling back to direct Chutes API")
            return await self._fallback_to_chutes(message, context)

    async def _send_via_letta(self, agent_id: str, message: str, context: Optional[Dict]) -> str:
        """
        Send a message to a Letta agent and return the response.
        This method implements the full pipeline: security check, personality context injection, message processing.
        """
        await self.initialize()
        
        try:
            # Security check before processing
            if context and 'security_detector' in context:
                security_detector: SemanticInjectionDetector = context['security_detector']
                threat_analysis = await security_detector.analyze_threat(
                    user_id=context.get('user_id', 'unknown'),
                    message=message
                )
                
                if threat_analysis.threat_detected:
                    logger.warning(f"Security threat detected: {threat_analysis}")
                    return await security_detector.generate_defensive_response(
                        threat_type=threat_analysis.threat_type,
                        user_personality=context.get('personality_snapshot')
                    )

            # Prepare the message payload conforming to Letta POST /v1/agents/:agent_id/messages schema
            url = f"{self.server_url}/v1/agents/{agent_id}/messages"

            # Build headers with authentication
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Build messages array with only role and content fields
            # Filter out internal fields that shouldn't be sent to Letta API
            messages = [
                {
                    "role": "user",
                    "content": message
                }
            ]

            payload = {
                "messages": messages
            }

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract the agent's response
                    # The structure depends on the Letta API response format
                    agent_response = result.get("messages", [])
                    
                    # Typically, the last message is the agent's response
                    if agent_response:
                        # Get the last message which should be from the assistant
                        for msg in reversed(agent_response):
                            if msg.get("role") == "assistant":
                                response_text = msg.get("text", "")
                                
                                # Log successful message processing
                                logger.info(f"Message processed for agent {agent_id}")
                                return response_text
                    
                    logger.warning(f"No assistant response found in agent {agent_id} response: {result}")
                    return "I couldn't process that request at the moment. Please try again."
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message to agent {agent_id}: {response.status} - {error_text}")
                    return "I'm having trouble responding right now. Please try again later."
                    
        except Exception as e:
            logger.error(f"Exception sending message to agent {agent_id}: {e}")
            raise  # Re-raise to trigger fallback

    async def _fallback_to_chutes(self, message: str, context: Optional[Dict]) -> str:
        """Fallback to direct Chutes API without Letta's stateful memory."""
        if not self.chutes_client:
            logger.error("Chutes client not available for fallback.")
            return "I'm having some trouble with my memory right now, but I'm still here to chat."

        try:
            system_prompt = "You are an AI companion. Respond naturally."
            if context and 'personality_snapshot' in context:
                system_prompt = self._create_system_prompt(context['personality_snapshot'])

            response = await self.chutes_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.8,
                max_tokens=500
            )
            if response and 'choices' in response and len(response['choices']) > 0:
                message_content = response['choices'][0].get('message', {}).get('content')
                if message_content:
                    return message_content
            logger.error(f"Invalid Chutes response format: {response}")
            return "I apologize, I'm having some technical difficulties at the moment. Please try again later."
        except Exception as e:
            logger.error(f"Chutes fallback also failed: {e}")
            return "I apologize, I'm having some technical difficulties at the moment. Please try again later."

    async def delete_agent(self, agent_id: str) -> bool:
        """
        Delete a Letta agent.
        """
        await self.initialize()

        try:
            url = f"{self.server_url}/v1/agents/{agent_id}"

            # Build headers with authentication
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with self.session.delete(url, headers=headers) as response:
                if response.status in [200, 204]:
                    # Remove from cache (iterate over copy to avoid modification during iteration)
                    user_to_remove = None
                    for user_id, cached_agent_id in list(self._agent_cache.items()):
                        if cached_agent_id == agent_id:
                            user_to_remove = user_id
                            break
                    if user_to_remove:
                        del self._agent_cache[user_to_remove]

                    logger.info(f"Successfully deleted Letta agent: {agent_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to delete agent {agent_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Exception deleting agent {agent_id}: {e}")
            return False

    async def update_agent_personality(self, user_id: str, personality_data: PersonalitySnapshot) -> bool:
        """
        Update an agent's personality by recreating it with new personality data.
        """
        # Get current agent ID
        current_agent_id = await self.get_agent_id(user_id)
        if not current_agent_id:
            logger.warning(f"No existing agent found for user {user_id} to update personality")
            return False

        # Create new agent with updated personality
        new_agent_id = await self.create_agent(user_id, personality_data)
        if not new_agent_id:
            logger.error(f"Failed to create new agent for user {user_id} with updated personality")
            return False

        # Update cache
        self._agent_cache[user_id] = new_agent_id

        # Delete old agent
        await self.delete_agent(current_agent_id)

        logger.info(f"Updated personality for user {user_id} (agent {current_agent_id} -> {new_agent_id})")
        return True

    async def get_agent_memory(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the memory of a Letta agent.
        """
        await self.initialize()

        try:
            url = f"{self.server_url}/v1/agents/{agent_id}/memory"

            # Build headers with authentication
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    memory_data = await response.json()
                    return memory_data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get memory for agent {agent_id}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Exception getting memory for agent {agent_id}: {e}")
            return None

    async def update_agent_memory(self, agent_id: str, memory_updates: Dict[str, Any]) -> bool:
        """
        Update the memory of a Letta agent.
        """
        await self.initialize()

        try:
            url = f"{self.server_url}/v1/agents/{agent_id}/memory"

            # Build headers with authentication
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with self.session.put(url, json=memory_updates, headers=headers) as response:
                if response.status in [200, 204]:
                    logger.info(f"Successfully updated memory for agent {agent_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to update memory for agent {agent_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Exception updating memory for agent {agent_id}: {e}")
            return False

    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a Letta agent.
        """
        await self.initialize()

        try:
            url = f"{self.server_url}/v1/agents/{agent_id}"

            # Build headers with authentication
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    agent_state = await response.json()
                    return agent_state
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get state for agent {agent_id}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Exception getting state for agent {agent_id}: {e}")
            return None

    async def health_check(self) -> bool:
        """
        Perform a health check on the Letta service.
        """
        await self.initialize()

        try:
            url = f"{self.server_url}/v1/health"

            # Build headers with authentication
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    logger.info("Letta service health check passed")
                    return True
                else:
                    logger.error(f"Letta service health check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Letta service health check exception: {e}")
            return False
