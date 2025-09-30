# AI Companion System API Documentation

## Overview

The AI Companion System provides a comprehensive RESTful API for interacting with the multi-user AI companion platform. The API is organized into several key areas:

- **Chat**: Primary conversation endpoints for user-agent interactions
- **Memory**: Memory management and search capabilities  
- **Personality**: Personality state inspection and management
- **Admin**: System administration and monitoring endpoints
- **Health**: Service health and status checking

All API endpoints are prefixed with `/api` and are accessible through the gateway service.

## Base URL

```
http://localhost:8000/api
```

In production, this would be your domain (e.g., `https://api.yourdomain.com/api`)

## Authentication

Most endpoints require user identification through the `user_id` parameter. Administrative endpoints require additional authorization tokens.

## Rate Limits

The API implements rate limiting:
- 100 requests per minute per IP address
- 1000 requests per hour per user
- 50 concurrent requests per user

Exceeding limits will result in a 429 Too Many Requests response.

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": "Descriptive error message",
  "detail": "Additional details about the error",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## API Endpoints

### Chat Endpoints

#### POST `/chat/message`

Process a user message and generate an AI companion response.

**Request Body:**
```json
{
  "user_id": "string",
  "message": "string",
  "session_id": "string",
  "message_id": "string"
}
```

**Response:**
```json
{
  "user_id": "string",
  "message_id": "string", 
  "agent_response": "string",
  "processing_time_ms": 150.5,
  "emotional_impact": {
    "pleasure": 0.2,
    "arousal": 0.1, 
    "dominance": 0.05,
    "emotion_label": "content"
  },
  "memories_retrieved": 3,
  "security_threat_detected": null
}
```

#### POST `/chat/proactive/{user_id}`

Initiate a proactive conversation with a user.

**Request Body:**
```json
{
  "trigger_reason": "string",
  "context": "string",
  "confidence": 0.8
}
```

**Response:**
```json
{
  "user_id": "string",
  "message_id": "string",
  "agent_response": "string", 
  "processing_time_ms": 120.3,
  "is_proactive": true,
  "proactive_trigger": "need_urgency"
}
```

#### GET `/chat/session/{user_id}`

Get a conversation session for a user.

**Query Parameters:**
- `session_id` (optional): Specific session ID
- `limit`: Number of messages to return (default: 50)

**Response:**
```json
{
  "user_id": "string",
  "session_id": "string",
  "messages": [...],
  "session_start": "2024-01-01T12:00:00Z",
  "session_end": "2024-01-01T12:15:00Z",
  "message_count": 12
}
```

### Memory Endpoints

#### POST `/memory/search/{user_id}`

Search for memories using semantic search with MMR ranking.

**Request Body:**
```json
{
  "text": "string",
  "k": 5,
  "memory_type": "episodic",
  "min_importance": 0.3,
  "lambda_param": 0.7
}
```

**Response:**
```json
[
  {
    "id": "string",
    "content": "string", 
    "memory_type": "episodic",
    "importance_score": 0.8,
    "recency_score": 0.9,
    "relevance_score": 0.75
  }
]
```

#### GET `/memory/episodic/{user_id}`

Get episodic memories for a user.

**Query Parameters:**
- `limit`: Number of memories (default: 20)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
[
  {
    "id": "string",
    "user_id": "string",
    "content": "string",
    "memory_type": "episodic",
    "importance_score": 0.7,
    "created_at": "2024-01-01T12:00:00Z",
    "metadata": {}
  }
]
```

#### POST `/memory/store/{user_id}`

Store a new memory for a user.

**Request Body:**
```json
{
  "content": "string",
  "memory_type": "episodic",
  "importance_score": 0.6,
  "metadata": {}
}
```

**Response:**
```json
"memory_id_12345"
```

### Personality Endpoints

#### GET `/personality/current/{user_id}`

Get the current personality snapshot for a user.

**Response:**
```json
{
  "user_id": "string",
  "big_five": {
    "openness": 0.7,
    "conscientiousness": 0.6,
    "extraversion": 0.5,
    "agreeableness": 0.8,
    "neuroticism": 0.3
  },
  "current_pad": {
    "pleasure": 0.2,
    "arousal": 0.1,
    "dominance": 0.3,
    "emotion_label": "content"
  },
  "active_quirks": [
    {
      "name": "uses_emoji_frequently",
      "strength": 0.7,
      "category": "speech_pattern"
    }
  ],
  "needs": [
    {
      "need_type": "social",
      "current_level": 0.4,
      "trigger_threshold": 0.7
    }
  ],
  "stability_score": 0.85
}
```

#### GET `/personality/history/{user_id}`

Get historical personality states for a user.

**Query Parameters:**
- `days`: Number of days of history (default: 7)

**Response:**
```json
[
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "pad_state": {
      "pleasure": 0.1,
      "arousal": 0.0,
      "dominance": 0.2
    },
    "emotion_label": "neutral"
  }
]
```

#### GET `/personality/quirks/{user_id}`

Get all quirks for a user.

**Query Parameters:**
- `active_only`: Boolean (default: true)

**Response:**
```json
[
  {
    "id": "string",
    "user_id": "string",
    "name": "string",
    "category": "speech_pattern",
    "description": "string",
    "strength": 0.7,
    "is_active": true,
    "confidence": 0.8
  }
]
```

### Admin Endpoints

#### GET `/admin/users`

Get a paginated list of all users.

**Query Parameters:**
- `skip`: Offset (default: 0)
- `limit`: Page size (default: 50)

**Response:**
```json
{
  "users": [...],
  "total_users": 1250,
  "skip": 0,
  "limit": 50,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### GET `/admin/stats`

Get comprehensive system statistics.

**Response:**
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "system_stats": {
    "total_users": 1250,
    "active_users_24h": 342,
    "active_users_7d": 891,
    "total_memories": 45678,
    "total_interactions": 123456,
    "interactions_24h": 2345
  }
}
```

#### GET `/admin/security/incidents`

Get security incidents with filtering.

**Query Parameters:**
- `limit`: Number of incidents (default: 50)
- `severity`: Filter by severity (low, medium, high, critical)
- `status`: Filter by status (detected, investigating, resolved, ignored)

**Response:**
```json
[
  {
    "id": "string",
    "user_id": "string",
    "incident_type": "injection_attempt",
    "severity": "high",
    "confidence": 0.85,
    "detected_content": "string",
    "detected_at": "2024-01-01T12:00:00Z",
    "status": "investigating"
  }
]
```

### Health Endpoints

#### GET `/health`

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "message": "AI Companion Gateway is running",
  "timestamp": 1704110400.123,
  "version": "1.0.0"
}
```

#### GET `/health/detailed`

Detailed health check with service-specific status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1704110400.123,
  "services": {
    "database": {
      "status": "healthy",
      "response_time": 0.015,
      "details": "Connected"
    },
    "groq_api": {
      "status": "healthy",
      "response_time": 0.234,
      "details": "Connected"
    }
  },
  "overall_healthy": true
}
```

## WebSocket Support

Some endpoints support WebSocket connections for real-time updates:

- `/ws/chat/{user_id}`: Real-time chat streaming
- `/ws/personality/{user_id}`: Real-time personality updates

## Data Models

### PADState
```json
{
  "pleasure": 0.2,      // -1.0 to 1.0
  "arousal": 0.1,       // -1.0 to 1.0  
  "dominance": 0.3,      // -1.0 to 1.0
  "emotion_label": "content"
}
```

### BigFiveTraits
```json
{
  "openness": 0.7,           // 0.0 to 1.0
  "conscientiousness": 0.6,  // 0.0 to 1.0
  "extraversion": 0.5,       // 0.0 to 1.0
  "agreeableness": 0.8,      // 0.0 to 1.0
  "neuroticism": 0.3         // 0.0 to 1.0
}
```

### PsychologicalNeed
```json
{
  "need_type": "social",
  "current_level": 0.4,      // 0.0 to 1.0
  "baseline_level": 0.5,     // 0.0 to 1.0
  "trigger_threshold": 0.7,   // 0.0 to 1.0
  "proactive_weight": 1.0    // 0.0 to 2.0
}
```

### Quirk
```json
{
  "name": "uses_emoji_frequently",
  "category": "speech_pattern",
  "description": "Tends to use emojis in messages",
  "strength": 0.7,           // 0.0 to 1.0
  "is_active": true,
  "confidence": 0.8          // 0.0 to 1.0
}
```

## Rate Limiting Headers

All responses include rate limiting information in headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704110700
```

## CORS Support

The API supports Cross-Origin Resource Sharing (CORS) for all origins by default in development. In production, this is restricted to configured domains.

## Versioning

The API uses semantic versioning. Breaking changes increment the major version number. Non-breaking additions increment the minor version. Bug fixes increment the patch version.

Current version: `v1.0.0`

## Changelog

### v1.0.0 (Initial Release)
- Initial release of all core endpoints
- Full personality system integration
- Memory management with MMR ranking
- Proactive conversation management
- Security threat detection
- Multi-user support with isolation

## Support

For API support, contact the system administrator or check the project documentation.